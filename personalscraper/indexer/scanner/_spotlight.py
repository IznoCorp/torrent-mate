"""Spotlight availability probe and change-detector for APFS staging paths.

This module implements the macOS Spotlight integration layer for the media
indexer scanner (DESIGN §11.9 / sub-phase 4.8).  It:

* Detects the filesystem type of any mount point by re-parsing ``mount`` output.
* Runs ``mdutil -s <path>`` to probe whether Spotlight indexing is active.
* Provides :class:`SpotlightChangeDetector` which may be *attached* only on
  APFS mounts and silently refuses to attach on macFUSE mounts (logging a
  deduplicated warning per session).
* Respects the per-disk ``spotlight_enabled`` flag from :class:`DiskConfig`
  (or the global :class:`IndexerSpotlightConfig`).

Event names emitted (structlog):

* ``indexer.spotlight.available``        — ``mdutil -s`` reports "Indexing enabled".
* ``indexer.spotlight.unavailable``      — anything else (disabled, rebuilding, error).
* ``indexer.spotlight.skipped_macfuse``  — attach refused because the path is macFUSE.
* ``indexer.spotlight.flag_ignored_macfuse`` — ``spotlight_enabled=True`` on a macFUSE path.
"""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable

from personalscraper.indexer._fs_probe import probe_mount as _probe_mount
from personalscraper.logger import get_logger

log = get_logger("indexer.spotlight")

# ---------------------------------------------------------------------------
# Filesystem-type detection helpers
# ---------------------------------------------------------------------------


def detect_fs_type(path: str) -> str | None:
    """Return the filesystem type for *path*'s mount point, or ``None`` if unknown.

    Delegates to :func:`personalscraper.indexer._fs_probe.probe_mount`.
    Only meaningful on macOS (Darwin); returns ``None`` on other platforms.

    Args:
        path: Absolute path whose mount-point filesystem type is needed.

    Returns:
        Canonical fs-type string (e.g. ``"apfs"``, ``"ntfs_macfuse"``,
        ``"hfsplus"``), or ``None`` when the mount point cannot be determined.
    """
    if platform.system() != "Darwin":
        return None
    info = _probe_mount(path)
    return info.fs_type if info is not None else None


# ---------------------------------------------------------------------------
# mdutil probe
# ---------------------------------------------------------------------------


def probe_spotlight(path: str) -> bool:
    """Run ``mdutil -s <path>`` and return ``True`` when Spotlight is indexing.

    Emits structlog events:

    * ``indexer.spotlight.available``   — when output contains "Indexing enabled".
    * ``indexer.spotlight.unavailable`` — for all other outcomes (disabled, rebuilding,
      timeout, subprocess error).

    Args:
        path: Filesystem path to probe (typically a disk mount point or the
            staging directory).

    Returns:
        ``True`` if ``mdutil -s`` reports "Indexing enabled"; ``False`` otherwise.
    """
    if platform.system() != "Darwin":
        # Non-macOS: Spotlight never available.
        log.debug("indexer.spotlight.unavailable", path=path, reason="non_darwin_platform")
        return False

    try:
        proc = subprocess.run(
            ["mdutil", "-s", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (proc.stdout + proc.stderr).lower()
    except subprocess.TimeoutExpired:
        log.info("indexer.spotlight.unavailable", path=path, reason="mdutil_timeout")
        return False
    except Exception as exc:
        log.info("indexer.spotlight.unavailable", path=path, reason="mdutil_error", error=str(exc))
        return False

    # "Indexing enabled" means Spotlight is fully operational.
    # "Indexing enabled but rebuilding" means the index exists but is not yet
    # usable — treat it as unavailable so the scanner falls back to dir-mtime walk.
    # We require the exact phrase "indexing enabled" with no trailing qualifier.
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    _is_fully_enabled = any(
        line == "indexing enabled" or (line.startswith("indexing enabled") and "but" not in line) for line in lines
    )
    if _is_fully_enabled:
        log.info("indexer.spotlight.available", path=path)
        return True

    # Covers "Indexing disabled", "Indexing enabled but rebuilding", error
    # messages, and any other unexpected output.
    log.info("indexer.spotlight.unavailable", path=path, reason="mdutil_not_enabled", raw=output.strip())
    return False


# ---------------------------------------------------------------------------
# SpotlightChangeDetector
# ---------------------------------------------------------------------------


class SpotlightChangeDetector:
    """Change-detector that optionally delegates to Spotlight on APFS paths.

    This class is the attach-point for Spotlight-based change detection.  In
    this sub-phase it implements the *probe + guard* layer: deciding whether
    Spotlight may be used for a given path, and providing a
    :meth:`is_attached` predicate for downstream scan logic.

    The actual ``mdfind``-based query is left as a future extension
    (it will be wired in a later sub-phase once the probe layer is validated).

    Attributes:
        _attached_path: The path that Spotlight is attached to, or ``None``.
        _skipped_macfuse_paths: Deduplicated set of macFUSE paths already warned
            about in this session.

    Usage::

        detector = SpotlightChangeDetector()
        if detector.try_attach("/Volumes/Staging", spotlight_enabled=True):
            # Spotlight available — use it for change detection.
            pass
        else:
            # Fall back to dir-mtime walk.
            pass
    """

    def __init__(self) -> None:
        """Initialise a new :class:`SpotlightChangeDetector` with no attachment."""
        self._attached_path: str | None = None
        self._skipped_macfuse_paths: set[str] = set()

    def try_attach(
        self,
        path: str,
        spotlight_enabled: bool,
        *,
        fs_type_fn: Callable[[str], str | None] | None = None,
        probe_fn: Callable[[str], bool] | None = None,
    ) -> bool:
        """Attempt to attach the change detector to *path*.

        The attach succeeds only when all of the following conditions hold:

        1. ``spotlight_enabled`` is ``True`` in the caller's configuration.
        2. The path's filesystem type is ``"apfs"`` (not macFUSE, not NTFS, …).
        3. ``mdutil -s <path>`` reports "Indexing enabled".

        On macFUSE paths:

        * The ``spotlight_enabled`` flag is **ignored** — macFUSE volumes are
          not Spotlight-indexable regardless.
        * ``indexer.spotlight.flag_ignored_macfuse`` is emitted (once per session)
          when ``spotlight_enabled=True`` to warn the operator that their config
          will have no effect.
        * ``indexer.spotlight.skipped_macfuse`` is emitted (once per path per
          session) with ``reason="macfuse_not_indexable"``.

        Args:
            path: Filesystem path to attach to.
            spotlight_enabled: Whether Spotlight is enabled for this path in the
                disk/indexer configuration.
            fs_type_fn: Injectable filesystem-type detector (default:
                :func:`detect_fs_type`).  Provided for test isolation.
            probe_fn: Injectable mdutil probe (default: :func:`probe_spotlight`).
                Provided for test isolation.

        Returns:
            ``True`` when the detector successfully attached (Spotlight usable);
            ``False`` otherwise (caller should fall back to dir-mtime walk).
        """
        # Resolve injectable helpers lazily so that module-level patches applied
        # after class definition (e.g. in unit tests) take effect correctly.
        # Default parameters would capture the function object at definition
        # time, bypassing patches; ``None`` sentinel + late resolution fixes this.
        _fs_type_fn = fs_type_fn if fs_type_fn is not None else detect_fs_type
        _probe_fn = probe_fn if probe_fn is not None else probe_spotlight
        fs_type = _fs_type_fn(path)

        if fs_type == "ntfs_macfuse":
            # Emit flag_ignored_macfuse warning only if the operator opted in
            # (spotlight_enabled=True) — and only once per path per session.
            if spotlight_enabled and path not in self._skipped_macfuse_paths:
                log.warning(
                    "indexer.spotlight.flag_ignored_macfuse",
                    path=path,
                    reason="macfuse_not_indexable",
                )
            # Emit skipped_macfuse once per path per session regardless of flag.
            if path not in self._skipped_macfuse_paths:
                log.info(
                    "indexer.spotlight.skipped_macfuse",
                    path=path,
                    reason="macfuse_not_indexable",
                )
                self._skipped_macfuse_paths.add(path)
            return False

        if not spotlight_enabled:
            # Config flag disabled — do not probe or attach.
            return False

        if fs_type != "apfs":
            # Unknown or non-APFS filesystem — cannot use Spotlight.
            log.debug(
                "indexer.spotlight.unavailable",
                path=path,
                reason="not_apfs",
                fs_type=fs_type,
            )
            return False

        # APFS path with spotlight_enabled=True — run the mdutil probe.
        available = _probe_fn(path)
        if available:
            self._attached_path = path
        return available

    def is_attached(self) -> bool:
        """Return ``True`` if the detector is currently attached to a path.

        Returns:
            Whether :meth:`try_attach` succeeded on a previous call.
        """
        return self._attached_path is not None

    def detach(self) -> None:
        """Release the current attachment, if any.

        Safe to call even if not attached.
        """
        self._attached_path = None
