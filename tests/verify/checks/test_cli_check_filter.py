"""Unit tests for the ``checks_for_filtered`` allow-set on CheckRegistry.

Covers sub-phase 6.1: the additive ``only: frozenset[str] | None`` filter that
Phase 6.2 wires to the ``--check`` CLI flag. The contract is:

- ``only=None`` → identity (byte-identical to ``checks_for``);
- ``only={"<known>"}`` → only the named checks, in registry order;
- an unknown name → ``KeyError`` listing the offending name(s);
- a name valid for the stage but wrong media_type → no raise, empty result.

These exercise the real singleton registry (loaded plugins) so the known/unknown
boundary matches production, plus a fresh ``CheckRegistry`` for hermetic cases.
"""

from __future__ import annotations

import pytest

import personalscraper.verify.checks  # noqa: F401 — trigger plugin registration
from personalscraper.verify.checks.base import CheckStage, Severity
from personalscraper.verify.checks.registry import CheckRegistry, registry


def test_only_none_is_identity() -> None:
    """``only=None`` returns the exact ``checks_for`` list (no filtering)."""
    full = registry.checks_for(CheckStage.DISPATCH, "movie")
    filtered = registry.checks_for_filtered(CheckStage.DISPATCH, "movie", None)
    assert filtered == full


def test_only_restricts_to_named_check() -> None:
    """A movie run with ``only={"nfo_present"}`` yields ONLY nfo_present."""
    filtered = registry.checks_for_filtered(CheckStage.DISPATCH, "movie", frozenset({"nfo_present"}))
    assert [c.name for c in filtered] == ["nfo_present"]


def test_only_preserves_registry_order() -> None:
    """The filtered subset keeps the canonical _ORDER sequence."""
    only = frozenset({"nfo_present", "video_present"})
    filtered = registry.checks_for_filtered(CheckStage.DISPATCH, "movie", only)
    # video_present precedes nfo_present in the _ORDER movie table.
    assert [c.name for c in filtered] == ["video_present", "nfo_present"]


def test_unknown_name_raises_keyerror() -> None:
    """An unknown check name raises KeyError mentioning the bad name."""
    with pytest.raises(KeyError) as excinfo:
        registry.checks_for_filtered(CheckStage.DISPATCH, "movie", frozenset({"does_not_exist"}))
    assert "does_not_exist" in str(excinfo.value)


def test_wrong_media_type_name_does_not_raise_and_filters_to_empty() -> None:
    """A stage-valid but media_type-wrong name returns [] without raising.

    ``season_structure`` is a DISPATCH-stage check registered for tvshow only.
    Naming it while filtering a MOVIE run is NOT an error (the name is known for
    the stage) — it simply contributes nothing.
    """
    filtered = registry.checks_for_filtered(CheckStage.DISPATCH, "movie", frozenset({"season_structure"}))
    assert filtered == []


def test_filtered_on_fresh_registry() -> None:
    """End-to-end on a hermetic registry: filter, identity, and unknown raise."""
    reg = CheckRegistry()

    @reg.register
    class AlphaCheck:
        name = "alpha"
        group = "g"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.ERROR
        description = "alpha"

        def run(self, ctx):  # noqa: ANN001, ANN202
            return []

    @reg.register
    class BetaCheck:
        name = "beta"
        group = "g"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie"})
        default_severity = Severity.ERROR
        description = "beta"

        def run(self, ctx):  # noqa: ANN001, ANN202
            return []

    # identity
    assert reg.checks_for_filtered(CheckStage.DISPATCH, "movie", None) == reg.checks_for(CheckStage.DISPATCH, "movie")
    # restrict
    only = reg.checks_for_filtered(CheckStage.DISPATCH, "movie", frozenset({"alpha"}))
    assert [c.name for c in only] == ["alpha"]
    # unknown raises
    with pytest.raises(KeyError):
        reg.checks_for_filtered(CheckStage.DISPATCH, "movie", frozenset({"ghost"}))


def test_all_for_stage_dedups_across_media_types() -> None:
    """_all_for_stage returns each stage check once regardless of media_type."""
    reg = CheckRegistry()

    @reg.register
    class BothCheck:
        name = "both"
        group = "g"
        stages = frozenset({CheckStage.DISPATCH})
        media_types = frozenset({"movie", "tvshow"})
        default_severity = Severity.ERROR
        description = "both"

        def run(self, ctx):  # noqa: ANN001, ANN202
            return []

    names = [c.name for c in reg._all_for_stage(CheckStage.DISPATCH)]
    assert names.count("both") == 1
