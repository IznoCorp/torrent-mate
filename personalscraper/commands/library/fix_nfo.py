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
  Backup write failure → skip mutation (no overwrite without safety net).
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

Examples:
    personalscraper library-fix-nfo
    personalscraper library-fix-nfo --apply
    personalscraper library-fix-nfo --db /custom/path/library.db --apply
"""

from __future__ import annotations

import re as _re
import typing
import xml.etree.ElementTree as _ET
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Literal

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.logger import get_logger

log = get_logger("cli")

_ROOT_CLOSE_RE = _re.compile(rb"</(tvshow|movie)>", _re.IGNORECASE)
_SAFE_TRAILING_DOMAINS = frozenset({"thetvdb.com", "themoviedb.org", "imdb.com", "omdbapi.com", "trakt.tv"})
_URL_RE = _re.compile(rb"https?://[^\s]+")

_Outcome = Literal[
    "nfo_missing",
    "nfo_resolved",
    "already_ok",
    "no_root_close",
    "unsafe_trailing",
    "still_malformed",
    "fixed",
    "skipped_apple_double",
    "backup_failed",
    "truncate_failed",
    "nfo_unreadable",
    "ambiguous_nfo",
]


@dataclass
class FixNfoStats:
    """Per-outcome counts for ``library_fix_nfo``.

    Mutable during the scan loop (counters updated via :meth:`inc`) and
    converted to an immutable snapshot via :meth:`frozen` once the loop
    terminates. ``items_scanned`` is set once at init time; every other
    field tracks a member of :data:`_Outcome` and is incremented via
    ``stats.inc(outcome)``.
    """

    items_scanned: int = 0
    nfo_resolved: int = 0
    nfo_missing: int = 0
    already_ok: int = 0
    no_root_close: int = 0
    unsafe_trailing: int = 0
    still_malformed: int = 0
    fixed: int = 0
    skipped_apple_double: int = 0
    backup_failed: int = 0
    truncate_failed: int = 0
    nfo_unreadable: int = 0
    ambiguous_nfo: int = 0

    def inc(self, outcome: _Outcome) -> None:
        """Increment the counter for *outcome* by 1."""
        setattr(self, outcome, getattr(self, outcome) + 1)

    def frozen(self) -> "FixNfoStats":
        """Return an independent copy (defensive for downstream emitters)."""
        return replace(self)

    def to_cli_json(self, *, apply: bool) -> dict[str, int | bool | list[str]]:
        """Project to the CLI JSON output shape.

        Iterates :data:`_Outcome` so a new outcome added to the Literal
        automatically appears in the output without a parallel edit
        here. The ``fixed`` counter is renamed to ``would_fix`` in
        dry-run mode (without ``--apply``) for operator clarity.

        Args:
            apply: Whether ``--apply`` was passed. Controls the key used
                for the ``fixed`` count (``"would_fix"`` vs ``"fixed"``).

        Returns:
            Dict ready for :func:`emit`.
        """
        result: dict[str, int | bool | list[str]] = {"items_scanned": self.items_scanned}
        for outcome in typing.get_args(_Outcome):
            value: int = getattr(self, outcome)
            if outcome == "fixed":
                result["would_fix" if not apply else "fixed"] = value
            else:
                result[outcome] = value
        result["apply"] = apply
        result["errors"] = []
        return result

    def to_log_dict(self) -> dict[str, int]:
        """Project to a ``dict[str, int]`` suitable for structlog ``stats=``."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


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


def _resolve_nfo_path(dispatch_path: str, kind: str) -> tuple[Path | None, Literal["ok", "missing", "ambiguous"]]:
    """Derive the expected NFO file path from a media item's dispatch directory.

    For TV shows the NFO is always ``tvshow.nfo`` at the root.  For movies the
    NFO name matches the title stem — we glob for ``*.nfo`` files, skipping
    macOS AppleDouble (``._`` prefix).  When multiple NFO candidates exist
    (e.g. a trailer NFO alongside the main one), the result is ambiguous and
    the file is skipped.

    .. note::
       Sibling at ``personalscraper/indexer/scanner/_modes/backfill_ids.py``
       has a ``_resolve_nfo_path`` with the same shape but a different concern:
       this one detects ambiguous NFOs for repair; the other is read-only path
       resolution for backfill.

    Args:
        dispatch_path: Filesystem path of the media item root directory.
        kind: ``'movie'`` or ``'show'``.

    Returns:
        Tuple of ``(resolved_path, reason)`` where *reason* is ``"ok"`` (path
        ready to use), ``"missing"`` (no NFO found), or ``"ambiguous"``
        (multiple NFO candidates — cannot safely pick one).
    """
    base = Path(dispatch_path)
    if kind == "show":
        nfo = base / "tvshow.nfo"
        if nfo.exists():
            return nfo, "ok"
        return base / "tvshow.nfo", "missing"
    nfo_files = sorted(f for f in base.glob("*.nfo") if not f.name.startswith("._"))
    if not nfo_files:
        return None, "missing"
    if len(nfo_files) > 1:
        log.warning(
            "nfo_fix_ambiguous_nfo",
            dispatch_path=dispatch_path,
            candidates=[str(f.name) for f in nfo_files],
        )
        return None, "ambiguous"
    return nfo_files[0], "ok"


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

    from personalscraper.indexer.db import _apply_pragmas as _db_apply_pragmas  # noqa: PLC0415

    conn = _sqlite3.connect(str(db_path))
    _db_apply_pragmas(conn)
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

    stats = FixNfoStats(items_scanned=len(rows))

    log.info("nfo_fix_scan_started", items_count=len(rows))

    for row in rows:
        item_id: int = row["id"]
        kind: str = row["kind"]
        title: str = row["title"]
        dispatch_path: str = row["dispatch_path"]

        nfo_path, reason = _resolve_nfo_path(dispatch_path, kind)
        if nfo_path is None:
            if reason == "ambiguous":
                stats.inc("ambiguous_nfo")
            else:
                stats.inc("nfo_missing")
            continue

        if nfo_path.name.startswith("._"):
            stats.inc("skipped_apple_double")
            continue

        if not nfo_path.exists():
            stats.inc("nfo_missing")
            continue

        stats.inc("nfo_resolved")

        # Fast path: already well-formed.  NFO files are local and trusted —
        # the XXE risk from xml.etree.ElementTree does not apply.
        try:
            _ET.parse(str(nfo_path))  # noqa: S314
            stats.inc("already_ok")
            continue
        except _ET.ParseError:
            pass
        except OSError:
            stats.inc("nfo_unreadable")
            log.warning(
                "nfo_fix_read_failed",
                item_id=item_id,
                title=title,
                nfo=str(nfo_path),
            )
            continue

        # Read raw bytes for regex-based root-close-tag detection.
        try:
            data = nfo_path.read_bytes()
        except OSError:
            stats.inc("nfo_unreadable")
            log.warning(
                "nfo_fix_read_bytes_failed",
                item_id=item_id,
                title=title,
                nfo=str(nfo_path),
            )
            continue

        matches = list(_ROOT_CLOSE_RE.finditer(data))
        if not matches:
            stats.inc("no_root_close")
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
            stats.inc("already_ok")
            continue

        if not _is_trailing_safe(trailing):
            stats.inc("unsafe_trailing")
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
        # Post-truncation re-parse — local trusted NFO, XXE not applicable.
        try:
            _ET.fromstring(truncated)  # noqa: S314
        except _ET.ParseError as exc:
            stats.inc("still_malformed")
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
                stats.inc("backup_failed")
                log.warning(
                    "nfo_fix_backup_failed",
                    item_id=item_id,
                    title=title,
                    nfo=str(nfo_path),
                    bak=str(bak_path),
                )
                continue

            try:
                nfo_path.write_bytes(truncated)
            except OSError as exc:
                # Truncation write failed AFTER backup succeeded — without
                # the wrapper an OSError here would abort the entire loop
                # mid-pass, losing every accumulated stat and leaving the
                # .bak as an orphan. Count it, clean the orphan, continue.
                stats.inc("truncate_failed")
                log.warning(
                    "nfo_fix_truncate_failed",
                    item_id=item_id,
                    title=title,
                    nfo=str(nfo_path),
                    bak=str(bak_path),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                try:
                    bak_path.unlink()
                except OSError as unlink_exc:
                    log.warning(
                        "nfo_fix_truncate_bak_orphan",
                        bak=str(bak_path),
                        error=str(unlink_exc),
                        error_type=type(unlink_exc).__name__,
                    )
                continue
            log.info(
                "nfo_fix_truncate",
                item_id=item_id,
                title=title,
                nfo=str(nfo_path),
                bytes_trimmed=bytes_trimmed,
            )

        stats.inc("fixed")

    log.info("nfo_fix_done", stats=stats.to_log_dict())

    emit(stats.frozen().to_cli_json(apply=apply))
