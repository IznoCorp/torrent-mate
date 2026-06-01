"""Unit tests for CheckRegistry, @register_check, checks_for, apply_fixes."""

from personalscraper.verify.checks.base import (
    CheckContext,
    CheckStage,
    Severity,
)
from personalscraper.verify.checks.registry import CheckRegistry


def _make_ctx(media_type: str = "movie", stage: CheckStage = CheckStage.DISPATCH) -> CheckContext:
    from pathlib import Path
    from unittest.mock import MagicMock

    return CheckContext(
        media_dir=Path("/tmp/fake"),
        media_type=media_type,
        stage=stage,
        config=MagicMock(),
        patterns=MagicMock(),
    )


def test_register_and_get():
    """register() stores a check instance retrievable by (stage, name)."""
    reg = CheckRegistry()

    @reg.register
    class DummyCheck:
        name = "dummy_test"
        group = "test"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.ERROR
        description = "test check"

        def run(self, ctx):
            return []

    check = reg.get(CheckStage.DISPATCH, "dummy_test")
    assert check is not None
    assert check.name == "dummy_test"


def test_get_unknown_returns_none():
    """get() returns None for an unregistered check name."""
    reg = CheckRegistry()
    assert reg.get(CheckStage.DISPATCH, "nonexistent") is None


def test_list_specs_returns_check_spec():
    """list_specs() returns CheckSpec instances for all registered checks."""
    reg = CheckRegistry()

    @reg.register
    class ACheck:
        name = "a_check"
        group = "grp"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.WARNING
        description = "a"

        def run(self, ctx):
            return []

    specs = reg.list_specs()
    names = [s.name for s in specs]
    assert "a_check" in names


def test_checks_for_filters_by_stage_and_media_type():
    """checks_for() returns only checks matching the given media_type."""
    reg = CheckRegistry()

    @reg.register
    class MovieCheck:
        name = "movie_only"
        group = "g"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.ERROR
        description = "movie only"

        def run(self, ctx):
            return []

    @reg.register
    class TvCheck:
        name = "tv_only"
        group = "g"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"tvshow"})
        default_severity = Severity.ERROR
        description = "tv only"

        def run(self, ctx):
            return []

    movie_checks = reg.checks_for(CheckStage.DISPATCH, "movie")
    tv_checks = reg.checks_for(CheckStage.DISPATCH, "tvshow")
    assert all(c.name != "tv_only" for c in movie_checks)
    assert all(c.name != "movie_only" for c in tv_checks)


def test_stage_name_collision():
    """(stage, name) keys are independent — nfo_ids on DISPATCH != STAGING."""
    reg = CheckRegistry()

    @reg.register
    class DispatchNfoIds:
        name = "nfo_ids"
        group = "nfo"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie", "tvshow"})
        default_severity = Severity.ERROR
        description = "dispatch nfo_ids"

        def run(self, ctx):
            return []

    @reg.register
    class StagingNfoIds:
        name = "nfo_ids"
        group = "coherence"
        stages = frozenset({CheckStage.STAGING})
        media_types = frozenset({"movie", "tvshow"})
        default_severity = Severity.WARNING
        description = "staging nfo_ids"

        def run(self, ctx):
            return []

    d = reg.get(CheckStage.DISPATCH, "nfo_ids")
    s = reg.get(CheckStage.STAGING, "nfo_ids")
    assert d is not s
    assert d is not None and s is not None
