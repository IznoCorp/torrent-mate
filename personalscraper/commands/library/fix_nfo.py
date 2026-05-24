"""Fix malformed NFO files with trailing content after the root XML close tag.

When legacy scrapers (MediaElch, older Emby/Jellyfin versions, or manually-
authored NFOs) appended metadata URLs after the root close tag, the resulting
NFO becomes XML-ill-formed.  ``library-fix-nfo`` detects these cases, validates
that the trailing content is safe to truncate (whitelisted media-domain URLs
only — typically redundant TVDB series-page links), and truncates the file
after the last root close tag.

Safety guarantees:

- **Dry-run by default**: no mutation without ``--apply``.
- **Backup**: writes ``.nfo.bak`` alongside the NFO before mutation.
- **Whitelist gate**: only trims trailing content that consists exclusively of
  HTTP(S) URLs pointing to ``thetvdb.com``, ``themoviedb.org``, ``imdb.com``,
  ``omdbapi.com``, or ``trakt.tv``.  Any other trailing content (XML fragments,
  comments, arbitrary text) is skipped with an ``unsafe_trailing`` count.
- **Post-truncation verify**: the truncated content is re-parsed with
  ``xml.etree.ElementTree``; if it still fails, the file is skipped
  (``still_malformed``) — a different bug is at play.

Prerequisites:
    ``library.db`` must exist and have ``media_item`` rows with
    ``item_attribute(key='dispatch_path')`` populated.

Examples::

    personalscraper library-fix-nfo
    personalscraper library-fix-nfo --apply
    personalscraper library-fix-nfo --db /custom/path/library.db --apply
"""

from __future__ import annotations

import json as _json
import re as _re
import xml.etree.ElementTree as _ET
from pathlib import Path
from typing import NamedTuple

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.logger import get_logger

log = get_logger("cli")

_ROOT_CLOSE_RE = _re.compile(rb"</(tvshow|movie)>", _re.IGNORECASE)
_SAFE_TRAILING_DOMAINS = frozenset({"thetvdb.com", "themoviedb.org", "imdb.com", "omdbapi.com", "trakt.tv"})
_URL_RE = _re.compile(rb"https?://[^\s]+")


class FixNfoStats(NamedTuple):
    """Per-outcome counts for ``library_fix_nfo``."""

    items_scanned: int
    nfo_resolved: int
    nfo_missing: int
    already_ok: int
    no_root_close: int
    unsafe_trailing: int
    still_malformed: int
    fixed: int
    skipped_apple_double: int


def _is_trailing_safe(trailing: bytes) -> bool:
    """Check whether trailing content is safe to truncate.

    Safe trailing content consists exclusively of HTTP(S) URLs whose domains
    belong to the whitelist (direct match or subdomain).  Any non-URL token
    (XML tags, comments, arbitrary text) makes the trailing content unsafe.

    Args:
        trailing: Raw bytes after the last root close tag.

    Returns:
        True if the content is empty/whitespace or contains only whitelisted URLs.
    """
    stripped = trailing.strip()
    if not stripped:
        return True
    for token in _re.split(rb"\s+", stripped):
        token = token.strip()
        if not token:
            continue
        if not token.startswith((b"http://", b"https://")):
            return False
        m = _re.match(rb"https?://([^/\s:?#]+)", token)
        if not m:
            return False
        domain = m.group(1).decode("ascii", errors="replace").lower()
        if domain not in _SAFE_TRAILING_DOMAINS and not any(domain.endswith("." + d) for d in _SAFE_TRAILING_DOMAINS):
            return False
    return True


def _resolve_nfo_path(dispatch_path: str, kind: str) -> Path | None:
    """Derive the expected NFO file path from a media item's dispatch directory.

    For TV shows the NFO is always ``tvshow.nfo`` at the root.  For movies the
    NFO name matches the title stem — we glob for the first ``*.nfo`` file,
    skipping macOS AppleDouble (``._`` prefix).

    Args:
        dispatch_path: Filesystem path of the media item root directory.
        kind: ``'movie'`` or ``'show'``.

    Returns:
        Resolved Path, or None if no NFO candidate exists.
    """
    base = Path(dispatch_path)
    if kind == "show":
        return base / "tvshow.nfo"
    nfo_files = sorted(f for f in base.glob("*.nfo") if not f.name.startswith("._"))
    return nfo_files[0] if nfo_files else None


@app.command("library-fix-nfo")
@handle_cli_errors
def library_fix_nfo(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (default: dry-run preview)."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Repair NFO files broken by trailing content after root XML close tag.

    Scans every ``media_item`` row with a ``dispatch_path`` attribute, locates
    the corresponding NFO file, and checks for XML well-formedness.  When the
    NFO fails to parse because of trailing content AFTER the last ``</tvshow>``
    or ``</movie>`` tag, and that trailing content consists only of whitelisted
    media-domain URLs (typically redundant TVDB series-page links from legacy
    scrapers), the command truncates the file after the root close tag.

    Dry-run by default — use ``--apply`` to mutate files.
    """
    import sqlite3 as _sqlite3  # noqa: PLC0415

    from personalscraper.conf.loader import load_config  # noqa: PLC0415

    cfg = ctx.obj.config if ctx.obj is not None else load_config(config)

    if db is not None:
        db_path = db
    elif cfg.indexer.db_path is not None:
        db_path = Path(cfg.indexer.db_path)
    else:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)

    conn = _sqlite3.connect(str(db_path))
    conn.row_factory = _sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT m.id, m.kind, m.title, ia.value AS dispatch_path "
            "FROM media_item m "
            "JOIN item_attribute ia ON ia.item_id = m.id AND ia.key = 'dispatch_path' "
            "ORDER BY m.id"
        ).fetchall()
    finally:
        conn.close()

    stats: dict[str, int] = {
        "items_scanned": len(rows),
        "nfo_resolved": 0,
        "nfo_missing": 0,
        "already_ok": 0,
        "no_root_close": 0,
        "unsafe_trailing": 0,
        "still_malformed": 0,
        "fixed": 0,
        "skipped_apple_double": 0,
    }

    log.info("nfo_fix_scan_started", items_count=len(rows))

    for row in rows:
        item_id: int = row["id"]
        kind: str = row["kind"]
        title: str = row["title"]
        dispatch_path: str = row["dispatch_path"]

        nfo_path = _resolve_nfo_path(dispatch_path, kind)
        if nfo_path is None:
            stats["nfo_missing"] += 1
            continue

        if nfo_path.name.startswith("._"):
            stats["skipped_apple_double"] += 1
            continue

        if not nfo_path.exists():
            stats["nfo_missing"] += 1
            continue

        stats["nfo_resolved"] += 1

        # Fast path: already well-formed.
        try:
            _ET.parse(str(nfo_path))
            stats["already_ok"] += 1
            continue
        except _ET.ParseError:
            pass
        except OSError:
            stats["nfo_missing"] += 1
            continue

        # Read raw bytes for regex-based root-close-tag detection.
        try:
            data = nfo_path.read_bytes()
        except OSError:
            stats["nfo_missing"] += 1
            continue

        matches = list(_ROOT_CLOSE_RE.finditer(data))
        if not matches:
            stats["no_root_close"] += 1
            log.warning(
                "nfo_fix_no_root_close",
                item_id=item_id,
                title=title,
                nfo=str(nfo_path),
            )
            continue

        last = matches[-1]
        cutoff = last.end()
        trailing = data[cutoff:]

        if not trailing.strip():
            # Trailing whitespace only but XML still failed to parse — the
            # problem is inside the body, not trailing.  Nothing to truncate.
            stats["already_ok"] += 1
            continue

        if not _is_trailing_safe(trailing):
            stats["unsafe_trailing"] += 1
            log.warning(
                "nfo_fix_unsafe_trailing",
                item_id=item_id,
                title=title,
                nfo=str(nfo_path),
                trailing_preview=trailing[:200].decode("utf-8", errors="replace"),
            )
            continue

        truncated = data[:cutoff]
        if not truncated.endswith(b"\n"):
            truncated += b"\n"
        try:
            _ET.fromstring(truncated)
        except _ET.ParseError as exc:
            stats["still_malformed"] += 1
            log.warning(
                "nfo_fix_still_malformed",
                item_id=item_id,
                title=title,
                nfo=str(nfo_path),
                parse_error=str(exc),
            )
            continue

        bytes_trimmed = len(data) - cutoff

        if apply:
            bak_path = nfo_path.with_suffix(nfo_path.suffix + ".bak")
            try:
                bak_path.write_bytes(data)
            except OSError:
                pass

            nfo_path.write_bytes(truncated)
            log.info(
                "nfo_fix_truncate",
                item_id=item_id,
                title=title,
                nfo=str(nfo_path),
                bytes_trimmed=bytes_trimmed,
            )

        stats["fixed"] += 1

    log.info("nfo_fix_done", stats=stats)

    key = "would_fix" if not apply else "fixed"
    typer.echo(
        _json.dumps(
            {
                "apply": apply,
                "items_scanned": stats["items_scanned"],
                "nfo_resolved": stats["nfo_resolved"],
                "nfo_missing": stats["nfo_missing"],
                "already_ok": stats["already_ok"],
                "no_root_close": stats["no_root_close"],
                "unsafe_trailing": stats["unsafe_trailing"],
                "still_malformed": stats["still_malformed"],
                key: stats["fixed"],
                "skipped_apple_double": stats["skipped_apple_double"],
            }
        )
    )
