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


# ---------------------------------------------------------------------------
# End-to-end filter proof: the ``only`` allow-set must actually restrict the
# PRODUCED results past ``checks_for_filtered`` (the CLI tests mock the run
# functions, so this is the only place the restriction is exercised on real
# output from MediaChecker / check_coherence over a corpus).
# ---------------------------------------------------------------------------


def test_check_movie_only_restricts_results(test_config, tmp_path) -> None:
    """DISPATCH end-to-end: ``check_movie(only={nfo_present})`` yields ONLY nfo_present."""
    from pathlib import Path

    from personalscraper.naming_patterns import PATTERNS
    from personalscraper.verify.checker import MediaChecker
    from tests.verify.golden import _corpus

    items = _corpus.build_item_corpus(Path(tmp_path) / "flt_mov")
    movie_dir = items["movie_valid"]
    chk = MediaChecker(PATTERNS, test_config)
    results = chk.check_movie(movie_dir, only=frozenset({"nfo_present"}))
    assert {r.name for r in results} == {"nfo_present"}


def test_check_coherence_only_restricts_results(test_config, tmp_path) -> None:
    """STAGING end-to-end: ``check_coherence(only={sort_process_coherence})``.

    Every produced CoherenceResult.checks must be a subset of the allow-set.
    """
    from pathlib import Path

    from personalscraper.enforce.coherence_checker import check_coherence
    from tests.fixtures.settings_stub import make_typed_settings_stub
    from tests.verify.golden import _corpus

    cfg = _corpus.build_staging_corpus(Path(tmp_path) / "flt_stg", test_config)
    only = frozenset({"sort_process_coherence"})
    results = check_coherence(make_typed_settings_stub(), cfg, only=only)
    assert results, "corpus produced no coherence results — fail-on-empty guard"
    for r in results:
        assert set(r.checks) <= only, f"{r.path.name} ran extra checks: {r.checks}"


def test_staging_unknown_name_raises_keyerror() -> None:
    """STAGING unknown ``--check`` name raises KeyError mentioning stage 'staging'."""
    with pytest.raises(KeyError) as excinfo:
        registry.checks_for_filtered(CheckStage.STAGING, "movie", frozenset({"bogus"}))
    msg = str(excinfo.value)
    assert "bogus" in msg
    assert "staging" in msg
