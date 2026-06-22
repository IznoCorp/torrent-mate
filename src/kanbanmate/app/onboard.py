"""Onboarding imperative shell (bosun §9): path resolution + dir listing.

Holds the app-layer constant ONBOARD_BASE_DIRS (expands ``~`` → environment I/O, so NOT in core),
resolves candidate paths (follows symlinks via Path.resolve) and calls the pure
``core.onboard_paths.is_within_base_dirs`` for the decision, and lists directories for the UI
browser.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from kanbanmate.core.onboard_paths import is_within_base_dirs

ONBOARD_BASE_DIRS: tuple[str, ...] = ("~/dev", "~/deploy", "~/staging")


def _resolved_bases() -> list[PurePosixPath]:
    """Return the resolved (expanduser+resolve) ONBOARD_BASE_DIRS entries."""
    return [PurePosixPath(str(Path(b).expanduser().resolve())) for b in ONBOARD_BASE_DIRS]


def path_is_confined(candidate: str) -> bool:
    """True iff ``candidate`` (after expanduser+resolve) is under an ONBOARD_BASE_DIRS root.

    Args:
        candidate: A filesystem path string (may contain ``~``).

    Returns:
        ``True`` if the resolved path equals or is under a base dir, else ``False``.
    """
    resolved = PurePosixPath(str(Path(candidate).expanduser().resolve()))
    return is_within_base_dirs(resolved, _resolved_bases())


def list_dir(candidate: str | None = None) -> dict[str, str | list[dict[str, str | bool]]]:
    """Return ``{"path", "entries":[{"name","is_dir"}]}`` for a confined directory (DESIGN §7.1).

    Args:
        candidate: A directory path string. EMPTY/``None`` → the picker's initial view: the FIRST
            ``ONBOARD_BASE_DIRS`` root (the web DirBrowser opens with no path and expects this; read
            in-module so it honours a monkeypatched ``ONBOARD_BASE_DIRS``).

    Returns:
        A dict with ``path`` (str) and ``entries`` (list of ``{"name": str, "is_dir": bool}``).

    Raises:
        PermissionError: When the path is outside ONBOARD_BASE_DIRS (HTTP → 422).
    """
    if not candidate:
        candidate = ONBOARD_BASE_DIRS[0]
    if not path_is_confined(candidate):
        raise PermissionError("path outside allowed roots")
    base = Path(candidate).expanduser().resolve()
    _entries: list[dict[str, str | bool]] = [
        {"name": p.name, "is_dir": p.is_dir()} for p in sorted(base.iterdir())
    ]
    return {"path": str(base), "entries": _entries}
