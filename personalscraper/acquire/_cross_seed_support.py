"""Private helpers for :mod:`cross_seed` — dataclasses + pure functions.

Extracted from ``cross_seed.py`` to keep the orchestrator module under the
800-line soft ceiling while remaining importable for tests via the parent
module's re-exports.

Layering: ``acquire/`` imports ``api/`` downward — never ``sorter`` /
``cleaner`` / ``scraper``.  This module imports ``api._contracts``
(:class:`~personalscraper.api._contracts.MediaType`) and the third-party
``guessit`` library.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from guessit import guessit as guess

from personalscraper.api._contracts import MediaType
from personalscraper.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CrossSeedResult:
    """Result of one :meth:`CrossSeedService.check` call.

    Attributes:
        injected: Info-hashes of successfully injected cross-seeds.
        rejected: ``(candidate_hash_or_id, tracker, reason)`` triples for
            each candidate that was considered but rejected.
        skipped: ``True`` when the entire check was skipped (kill-switch,
            not-found, seed-pure, etc.).
        skip_reason: Machine-readable reason for the skip, or ``None``.
    """

    injected: list[str] = field(default_factory=list)
    rejected: list[tuple[str, str, str]] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class SweepResult:
    """Result of one :meth:`CrossSeedService.sweep` call (X2 — back-catalog).

    Attributes:
        checked: Number of torrents where :meth:`CrossSeedService.check` was
            actually invoked.
        injected: Total number of successfully injected cross-seeds across
            all checked torrents.
        quota_exhausted: ``True`` when the sweep stopped early because the
            daily quota was reached.
        lister_failed: ``True`` when :meth:`TorrentLister.get_completed`
            raised an exception — the sweep could not even enumerate the
            torrent list.  The caller (CLI) should surface this as a hard
            error (exit 1).
    """

    checked: int = 0
    injected: int = 0
    quota_exhausted: bool = False
    lister_failed: bool = False


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _media_type_for(name: str) -> MediaType:
    """Derive the :class:`MediaType` from a release name using guessit.

    D6 (back-catalog sweep) requires ALL completed torrents regardless of
    media type.  D7 (strongest signal) mandates searching by release name.
    Hardcoding ``MediaType.MOVIE`` violates D6: TV/anime completions would
    search the movies category and miss candidates.  This helper uses guessit
    to detect episode-style releases and route to the correct tracker endpoint
    (c411 picks its ``t=movie`` / ``t=tvsearch`` endpoint by media_type).

    Args:
        name: Release name (e.g. ``"Show.S01E01.1080p.x264-GROUP"``).

    Returns:
        ``MediaType.TV`` when guessit detects ``type == "episode"``,
        ``MediaType.MOVIE`` otherwise (including on guessit failure).
    """
    try:
        parsed = guess(name)
        if parsed.get("type") == "episode":
            return MediaType.TV
    except Exception:
        logger.debug("acquire.cross_seed.guessit_failed", name=name)
    return MediaType.MOVIE


def _normalize_qbit_files(
    files: list[tuple[str, int]],
    item_name: str,
) -> tuple[list[tuple[str, int]], str]:
    """Normalize qBittorrent ``list_files`` output to the candidate frame.

    qBittorrent ``torrents/files`` returns names that INCLUDE the torrent
    root folder for multi-file torrents (``"Root/inner.mkv"``), while
    :func:`~personalscraper.api.torrent._base.parse_torrent_layout` yields
    paths relative to ``info.name`` WITHOUT the root (``"inner.mkv"``).
    This function strips the shared root prefix so the two frames are
    comparable via :func:`~personalscraper.api.torrent._layout.structural_match`.

    Args:
        files: The ``(path, size)`` list from qBittorrent's ``list_files``.
        item_name: The torrent's display name from qBittorrent
            (``item.name``), used as a fallback when no shared root is found.

    Returns:
        A ``(normalized_files, layout_name)`` pair.  *layout_name* is either
        the shared root component stripped from the paths or *item_name* when
        no shared root exists.
    """
    if not files:
        return files, item_name

    # Single-file torrent: the entry name IS the filename, same as info.name
    # from the .torrent.  qBit does not prefix single-file paths with a root
    # component, so the frames already agree — leave as-is.
    if len(files) == 1 and "/" not in files[0][0]:
        return files, item_name

    # Multi-file or path-containing entries: compute the first path component
    # of every entry.  If ALL entries share the same first component, it is
    # the torrent root injected by qBit — strip it and use it as the layout
    # name (more truthful than the renameable qBit display name).
    first_components: list[str | None] = []
    for path, _size in files:
        if "/" in path:
            first_components.append(path.split("/", 1)[0])
        else:
            first_components.append(None)

    unique_roots = {c for c in first_components if c is not None}

    if len(unique_roots) == 1 and None not in first_components:
        # All entries share the same root prefix — strip it.
        root = unique_roots.pop()
        stripped: list[tuple[str, int]] = [(path[len(root) + 1 :], size) for path, size in files]
        return stripped, root

    # Mixed roots (e.g. "DirA/file1" + "DirB/file2") or entries without "/"
    # (e.g. flat multi-file at top level): leave paths as-is, use item.name.
    return files, item_name


def _candidate_id(candidate: object) -> str:
    """Return a stable identifier string for a tracker search result.

    Prefers ``info_hash`` (hex or base32) when available; falls back to
    a truncated download URL for results that carry no hash.

    Args:
        candidate: A :class:`~personalscraper.api.tracker._base.TrackerResult`
            or compatible object with ``info_hash`` and ``download_url``
            attributes.

    Returns:
        A human-readable identifier string (≤ 80 chars).
    """
    info_hash = getattr(candidate, "info_hash", None)
    if info_hash:
        return str(info_hash)[:80]
    download_url = getattr(candidate, "download_url", None)
    if download_url:
        return str(download_url)[:80]
    return "unknown"
