"""Scrape-resolve CLI — targeted metadata fetch by provider ID for the scrape-arbiter.

Resolves a pending ``scrape_decision`` row by fetching metadata directly from the
chosen provider (TMDB or TVDB) by its known ID, generating NFO + downloading artwork
into the staging folder, then marking the decision ``resolved``.  Self-acquires
``pipeline.lock`` for its lifetime (same convention as ``library-rescrape``) so it is
both human-runnable and safe as a web-runner subprocess.

Registered as ``personalscraper scrape-resolve`` on the shared Typer app.
"""

from __future__ import annotations

import sqlite3 as _sqlite3
import unicodedata
from pathlib import Path
from typing import Any, cast

import typer

from personalscraper import cli as cli_compat
from personalscraper._fs_utils import is_apple_double
from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.cli_state import state
from personalscraper.core.media_types import VIDEO_EXTENSIONS
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns

log = get_logger(__name__)

_VALID_PROVIDERS = frozenset({"tmdb", "tvdb"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_largest_video(media_dir: Path) -> Path | None:
    """Find the largest video file in a directory for stream-info extraction.

    Args:
        media_dir: Path to search recursively.

    Returns:
        Path to the largest video file by size, or ``None`` when no video
        files are found.
    """
    largest: Path | None = None
    largest_size = 0
    for f in media_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
            continue
        if is_apple_double(f.name):
            continue
        try:
            size = f.stat().st_size
            if size > largest_size:
                largest = f
                largest_size = size
        except OSError:
            continue
    return largest


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@app.command()
@handle_cli_errors
def scrape_resolve(
    ctx: typer.Context,
    staging_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Path to the staging directory for the media item.",
    ),
    provider: str = typer.Option(
        ...,
        "--provider",
        help="Metadata provider: 'tmdb' or 'tvdb'.",
    ),
    provider_id: int = typer.Option(
        ...,
        "--id",
        help="Numeric identifier assigned by the provider.",
    ),
) -> None:
    """Resolve a pending scrape decision by fetching metadata by provider ID.

    Fetches movie or TV-show metadata directly from TMDB (movies) or
    TMDB/TVDB (TV shows) by a known provider ID, writes NFO + artwork into
    the staging folder, and marks the matching ``scrape_decision`` row as
    ``resolved``.

    Self-acquires ``pipeline.lock`` for its lifetime so it is safe as
    both a direct human invocation and a web-runner subprocess (added to
    ``_CLI_SELF_LOCKING`` — the runner must NOT double-acquire).

    Exit codes:
        0 — success (NFO written, artwork downloaded, decision resolved).
        1 — scrape error (API failure, NFO write failure) or lock held.
        2 — misconfiguration (missing DB, unknown provider, no matching
            pending decision row, invalid provider for media kind).
    """
    config = ctx.obj.config
    console = state["console"]
    settings = cli_compat.get_settings()

    # ── 1. Validate provider ─────────────────────────────────────────────
    if provider not in _VALID_PROVIDERS:
        console.print(
            f"[red]Invalid provider '{provider}'. Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}.[/red]"
        )
        raise typer.Exit(2)

    # ── 2. Validate DB path ──────────────────────────────────────────────
    db_path = config.indexer.db_path
    if not db_path.exists():
        console.print(f"[red]Indexer DB not found at {db_path}; run `library-index` first.[/red]")
        raise typer.Exit(2)

    # ── 3. Look up decision row by NFC-normalized staging path ───────────
    normalized_path = unicodedata.normalize("NFC", str(staging_path.resolve()))

    conn = _sqlite3.connect(str(db_path), isolation_level=None)
    try:
        apply_pragmas(conn)
        row = conn.execute(
            "SELECT id, media_kind, status FROM scrape_decision WHERE staging_path = ?",
            (normalized_path,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        console.print(f"[red]No decision row found for staging path: {staging_path}[/red]")
        raise typer.Exit(2)

    decision_id: int = row[0]
    media_kind: str = row[1]
    status: str = row[2]

    if status != "pending":
        console.print(f"[red]Decision {decision_id} is already '{status}', not 'pending'.[/red]")
        raise typer.Exit(2)

    # ── 4. Validate provider ↔ media_kind ────────────────────────────────
    if media_kind == "movie" and provider != "tmdb":
        console.print(f"[red]Movies require provider 'tmdb', got '{provider}'.[/red]")
        raise typer.Exit(2)

    # ── 5. Acquire pipeline lock (exit 1 if held) ────────────────────────
    # Self-acquire EXACTLY like library-rescrape (analyze.py:305) — the
    # atomic authority (O_CREAT|O_EXCL) in acquire_lock() handles stale-PID
    # detection and the TOCTOU race window.
    if not cli_compat.acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)

    try:
        console.print(f"[bold]Scrape-resolving '{staging_path.name}' via {provider}:{provider_id}...[/bold]")

        scraper_config = config.scraper
        patterns = NamingPatterns()

        from personalscraper.scraper.artwork import ArtworkDownloader  # noqa: PLC0415
        from personalscraper.scraper.nfo_generator import NFOGenerator  # noqa: PLC0415

        nfo_gen = NFOGenerator(db_path=db_path)
        artwork_dl = ArtworkDownloader(
            dry_run=False,
            artwork_language=scraper_config.artwork_language,
            db_path=db_path,
        )

        with per_step_boundary(config, settings) as app_context:
            if media_kind == "movie":
                _scrape_movie(
                    app_context,
                    provider_id,
                    staging_path,
                    nfo_gen,
                    artwork_dl,
                    patterns,
                )
            else:
                _scrape_tvshow(
                    app_context,
                    provider,
                    provider_id,
                    staging_path,
                    nfo_gen,
                    artwork_dl,
                    patterns,
                )

            # ── 6. Mark decision resolved ─────────────────────────────────
            from personalscraper.scraper.decision_writer import DecisionWriter  # noqa: PLC0415

            writer = DecisionWriter(db_path)
            writer.resolve(decision_id, provider, provider_id, via="pick")

        console.print(f"[green]Successfully resolved decision {decision_id} via {provider}:{provider_id}.[/green]")

    finally:
        cli_compat.release_lock()


# ---------------------------------------------------------------------------
# Per-media-kind scrape helpers
# ---------------------------------------------------------------------------


def _scrape_movie(
    app_context: Any,
    api_id: int,
    staging_path: Path,
    nfo_gen: Any,
    artwork_dl: Any,
    patterns: NamingPatterns,
) -> None:
    """Fetch movie metadata by TMDB ID, write NFO + artwork into *staging_path*.

    Args:
        app_context: The per-step :class:`AppContext` carrying the provider
            registry.
        api_id: TMDB movie identifier.
        staging_path: The staging directory to write NFO and artwork into.
        nfo_gen: Configured :class:`NFOGenerator` instance.
        artwork_dl: Configured :class:`ArtworkDownloader` instance.
        patterns: Naming-patterns helper for filename generation.

    Raises:
        typer.Exit: 1 on any API or write failure.
    """
    from personalscraper.api.metadata.tmdb import TMDBClient  # noqa: PLC0415

    tmdb = cast("TMDBClient", app_context.provider_registry.get("tmdb"))

    try:
        movie_data = tmdb.get_movie(api_id)
    except Exception as exc:
        log.error("scrape_resolve_movie_api_failed", api_id=api_id, error=str(exc))
        raise typer.Exit(1) from exc

    from personalscraper.scraper.movie_service import _coerce_to_movie_data  # noqa: PLC0415

    coerced = _coerce_to_movie_data(movie_data)

    # Stream info from the largest video file (best-effort).
    video_file = _find_largest_video(staging_path)
    stream_info: dict[str, Any] | None = None
    if video_file is not None:
        from personalscraper.scraper.mediainfo import extract_stream_info  # noqa: PLC0415

        try:
            stream_info = extract_stream_info(video_file)
        except Exception:
            log.warning(
                "scrape_resolve_stream_info_failed",
                video_file=str(video_file),
                exc_info=True,
            )

    # NFO.  Use the format-pattern key for the filename; the actual name
    # written is validated by the NFO generator itself.
    nfo_name = patterns.format("movie_nfo", Title=staging_path.name)
    nfo_path = staging_path / nfo_name
    try:
        xml = nfo_gen.generate_movie_nfo(coerced, stream_info)
        nfo_gen.write_nfo(xml, nfo_path)
    except Exception as exc:
        log.error("scrape_resolve_nfo_write_failed", path=str(nfo_path), error=str(exc))
        raise typer.Exit(1) from exc

    # Artwork.
    try:
        artwork_dl.download_movie_artwork(coerced, staging_path, patterns)
    except Exception as exc:
        log.error(
            "scrape_resolve_artwork_failed",
            path=str(staging_path),
            error=str(exc),
        )
        raise typer.Exit(1) from exc

    log.info(
        "scrape_resolve_movie_done",
        api_id=api_id,
        staging_path=str(staging_path),
    )


def _scrape_tvshow(
    app_context: Any,
    source: str,
    api_id: int,
    staging_path: Path,
    nfo_gen: Any,
    artwork_dl: Any,
    patterns: NamingPatterns,
) -> None:
    """Fetch TV-show metadata from *source* by ID, write NFO + artwork.

    Honours the multi-provider separation boundary: a TVDB-matched show is
    fetched from TVDB (never ``tmdb.get_tv`` with a TVDB id), a TMDB-matched
    show from TMDB.  The shared :func:`~personalscraper.scraper._tvdb_convert.fetch_show_data`
    helper enforces this discipline in one place.

    Args:
        app_context: The per-step :class:`AppContext` carrying the provider
            registry.
        source: Resolved provider — ``"tvdb"`` or ``"tmdb"``.
        api_id: TVDB series id when *source* is ``"tvdb"``, otherwise TMDB id.
        staging_path: The staging directory to write NFO and artwork into.
        nfo_gen: Configured :class:`NFOGenerator` instance.
        artwork_dl: Configured :class:`ArtworkDownloader` instance.
        patterns: Naming-patterns helper for filename generation.

    Raises:
        typer.Exit: 1 on any API or write failure.
    """
    from personalscraper.scraper._tvdb_convert import fetch_show_data  # noqa: PLC0415

    provider_client = app_context.provider_registry.get(source)

    try:
        show_data, _xref_tmdb = fetch_show_data(
            source,
            api_id,
            provider_client,
            preferred_language="fr-FR",
            fallback_language="en-US",
        )
    except Exception as exc:
        log.error(
            "scrape_resolve_tvshow_api_failed",
            source=source,
            api_id=api_id,
            error=str(exc),
        )
        raise typer.Exit(1) from exc

    # NFO.
    nfo_path = staging_path / "tvshow.nfo"
    try:
        xml = nfo_gen.generate_tvshow_nfo(show_data)
        nfo_gen.write_nfo(xml, nfo_path)
    except Exception as exc:
        log.error("scrape_resolve_nfo_write_failed", path=str(nfo_path), error=str(exc))
        raise typer.Exit(1) from exc

    # Artwork.
    try:
        artwork_dl.download_tvshow_artwork(show_data, staging_path, patterns)
    except Exception as exc:
        log.error(
            "scrape_resolve_artwork_failed",
            path=str(staging_path),
            error=str(exc),
        )
        raise typer.Exit(1) from exc

    log.info(
        "scrape_resolve_tvshow_done",
        source=source,
        api_id=api_id,
        staging_path=str(staging_path),
    )
