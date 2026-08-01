"""Config-home safety check.

Warns when the resolved config directory lives inside an **ancestor** git
working tree (defense-in-depth against the pre-relocation vector that made
a dev branch checkout crash prod at boot — DESIGN §1, §3.4).  The config
dir's own ``.git`` (the sanctioned mini-repo, D3) is explicitly excluded.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("verify.config_home")


def _is_inside_worktree(path: Path) -> bool:
    """Walk up from *path*'s **parent** to the filesystem root looking for ``.git``.

    A ``.git`` entry (file or directory) at any **ancestor** means *path* is
    inside a git working tree — the REAL invariant (DESIGN §3.4).  The path's
    OWN ``.git`` is explicitly **excluded**: the canonical config dir at
    ``~/.torrentmate/config`` is itself a git repo (the sanctioned mini-repo,
    D3), so its own ``.git`` is NOT a violation.  Only an ancestor ``.git``
    makes the config ``inside a worktree``.

    Args:
        path: Absolute path to check.

    Returns:
        ``True`` if a ``.git`` file or directory is found at any ancestor of
        *path* (excluding *path* itself) up to the filesystem root.
    """
    current = path.resolve().parent
    root = Path(current.anchor)  # "/" on Unix
    while current != root:
        if (current / ".git").exists():
            return True
        current = current.parent
    # Check root itself (unlikely but complete).
    return (root / ".git").exists()


def check_config_home(config_dir: Path) -> list[str]:
    """Verify that *config_dir* is NOT inside any **ancestor** git working tree.

    This is a lightweight startup guard.  After relocation (§3.1), the
    canonical config lives at ``~/.torrentmate/config`` which is NOT inside
    any working tree by construction.  The config dir's OWN ``.git`` is the
    sanctioned mini-repo (D3) — it does NOT trigger a warning; only an
    ancestor ``.git`` makes the config ``inside a worktree``.

    If this check fires, someone (or a stale env var) is still pointing at
    the old in-repo location.

    Args:
        config_dir: Resolved path to the active config directory.

    Returns:
        List of warning strings.  Empty if the config is safely outside all
        ancestor working trees.
    """
    warnings: list[str] = []

    if not config_dir.is_dir():
        warnings.append(
            f"config_home: directory not found: {config_dir} — run 'personalscraper init-config' to create one."
        )
        return warnings

    if _is_inside_worktree(config_dir):
        warnings.append(
            f"config_home: config directory {config_dir} is inside a git "
            f"working tree. This is a boot-break hazard (DESIGN §1). "
            f"After migration, the canonical config lives at "
            f"~/.torrentmate/config — update PERSONALSCRAPER_CONFIG."
        )

    return warnings
