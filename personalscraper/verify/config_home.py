"""Config-home safety check.

Warns when the resolved config directory lives inside an **ancestor** git
working tree (defense-in-depth against the pre-relocation vector that made
a dev branch checkout crash prod at boot — DESIGN §1, §3.4).  The config
dir's own ``.git`` (the sanctioned mini-repo, D3) is explicitly excluded.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.conf.config_git import _is_inside_ancestor_worktree as _is_inside_worktree
from personalscraper.logger import get_logger

log = get_logger("verify.config_home")


def check_config_home(config_dir: Path, *, report_missing: bool = True) -> list[str]:
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
        report_missing: When ``True`` (default), a nonexistent *config_dir*
            yields a warning. The composition root passes ``False``: by the
            time an AppContext is built the config has already LOADED, so a
            missing-dir warning there is either impossible or mock-induced
            noise — only the worktree hazard is meaningful at that site.

    Returns:
        List of warning strings.  Empty if the config is safely outside all
        ancestor working trees.
    """
    warnings: list[str] = []

    if not config_dir.is_dir():
        if report_missing:
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
