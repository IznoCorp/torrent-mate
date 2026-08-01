"""Tests for the config_home verify check.

Warns when the resolved config directory lives inside a git working tree
(DESIGN §3.4).
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.verify.config_home import (
    _is_inside_worktree,
    check_config_home,
)


def test_is_inside_worktree_true_when_ancestor_git_dir_present(tmp_path: Path) -> None:
    """A path whose ANCESTOR has a .git subdirectory is inside a worktree."""
    (tmp_path / ".git").mkdir()
    child = tmp_path / "sub"
    child.mkdir()
    assert _is_inside_worktree(child) is True


def test_is_inside_worktree_true_when_git_file_present(tmp_path: Path) -> None:
    """A path whose parent has .git (git worktree) is inside a worktree."""
    (tmp_path / ".git").write_text("gitdir: /some/path")
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    assert _is_inside_worktree(sub) is True


def test_is_inside_worktree_false_outside_any_worktree(tmp_path: Path) -> None:
    """A path with no .git anywhere up to root is NOT inside a worktree."""
    assert _is_inside_worktree(tmp_path) is False


def test_is_inside_worktree_stops_at_root(tmp_path: Path) -> None:
    """The walk stops at filesystem root and returns False."""
    result = _is_inside_worktree(Path("/tmp"))
    # /tmp may or may not have .git — but the walk won't crash
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# D3 exemption — the canonical config dir is itself a git repo (mini-repo)
# ---------------------------------------------------------------------------


def test_is_inside_worktree_false_when_own_git_is_sanctioned_mini_repo(tmp_path: Path) -> None:
    """Own .git is the sanctioned mini-repo (D3), not a worktree violation.

    A config dir that IS itself a git repo (own .git) with no ancestor
    worktree is NOT inside a worktree — D3 sanctions the mini-repo.
    """
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / ".git").mkdir()  # sanctioned mini-repo
    # No .git at tmp_path or above
    assert _is_inside_worktree(cfg) is False


def test_is_inside_worktree_true_when_ancestor_worktree_even_with_own_git(tmp_path: Path) -> None:
    """Own .git is irrelevant when an ancestor worktree exists.

    A config dir that IS a git repo BUT also lives under an ancestor
    worktree IS inside a worktree — the ancestor .git is the hazard.
    """
    (tmp_path / ".git").mkdir()  # ancestor worktree
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / ".git").mkdir()  # sanctioned mini-repo (irrelevant — ancestor wins)
    assert _is_inside_worktree(cfg) is True


def test_check_config_home_warns_inside_worktree(tmp_path: Path) -> None:
    """check_config_home returns a warning when config is inside a worktree."""
    (tmp_path / ".git").mkdir()
    cfg = tmp_path / "config"
    cfg.mkdir()
    warnings = check_config_home(cfg)
    assert len(warnings) >= 1
    assert any("inside a git working tree" in w for w in warnings)


def test_check_config_home_silent_outside_worktree(tmp_path: Path) -> None:
    """check_config_home returns empty list when config is NOT inside a worktree."""
    cfg = tmp_path / "isolated" / "config"
    cfg.mkdir(parents=True)
    warnings = check_config_home(cfg)
    assert warnings == []


def test_check_config_home_handles_nonexistent_dir() -> None:
    """check_config_home handles a nonexistent directory gracefully."""
    warnings = check_config_home(Path("/nonexistent/path/to/config"))
    assert len(warnings) >= 1  # should warn about missing dir, not crash


# ── Integration: composition-root wiring ────────────────────────────────────


def test_build_app_context_warns_when_config_in_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``_build_app_context`` logs a warning when config dir is inside a worktree.

    End-to-end integration test for the DESIGN §3.4 boot guard: the TRUE
    composition root (:func:`personalscraper.cli_helpers._build_app_context`)
    calls :func:`check_config_home` at context-build time and logs every
    warning via the module logger.  Config dir inside an ancestor git worktree
    → warning emitted; clean dir → silent.
    """
    caplog.set_level(logging.WARNING)

    # Create an ancestor .git (worktree) with a config dir inside it.
    (tmp_path / ".git").mkdir()
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "config.json5").write_text('{"config_version":"0.0.0","overlays":[]}')
    monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(cfg_dir))

    from personalscraper.cli_helpers import _build_app_context
    from personalscraper.core.ownership import NullOwnershipChecker

    cfg = MagicMock()
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300.0
    cfg.torrent.active = ""

    with (
        patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        patch("personalscraper.acquire._factory.build_acquire_context"),
        patch(
            "personalscraper.cli_helpers._build_ownership_checker",
            return_value=NullOwnershipChecker(),
        ),
    ):
        _build_app_context(cfg, MagicMock())

    # The warning must mention "config_home" and "inside a git working tree".
    warnings = [r for r in caplog.records if "config_home" in r.getMessage()]
    assert len(warnings) >= 1, (
        f"No config_home warning logged; caplog records: {[r.getMessage() for r in caplog.records]}"
    )
    assert any("inside a git working tree" in r.getMessage() for r in warnings), (
        f"Warning does not mention worktree hazard; messages: {[r.getMessage() for r in warnings]}"
    )


def test_build_app_context_silent_when_config_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``_build_app_context`` does NOT log a warning for a clean config dir.

    When the config directory is NOT inside any ancestor git working tree,
    the composition root must not emit any ``config_home`` warning.
    """
    caplog.set_level(logging.WARNING)

    # Clean temp dir — no .git anywhere.
    cfg_dir = tmp_path / "isolated" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json5").write_text('{"config_version":"0.0.0","overlays":[]}')
    monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(cfg_dir))

    from personalscraper.cli_helpers import _build_app_context
    from personalscraper.core.ownership import NullOwnershipChecker

    cfg = MagicMock()
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300.0
    cfg.torrent.active = ""

    with (
        patch("personalscraper.api.metadata.registry.ProviderRegistry"),
        patch("personalscraper.acquire._factory.build_acquire_context"),
        patch(
            "personalscraper.cli_helpers._build_ownership_checker",
            return_value=NullOwnershipChecker(),
        ),
    ):
        _build_app_context(cfg, MagicMock())

    # No config_home warning.
    warnings = [r for r in caplog.records if "config_home" in r.getMessage()]
    assert warnings == [], f"Unexpected config_home warning: {[r.getMessage() for r in warnings]}"
