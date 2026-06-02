"""CMP-3 regression: ``Verifier._classify`` reuses ``ctx.resolved_category``.

The ``category`` check plugin classifies the media from its NFO once during the
check loop and stashes the result on ``ctx.resolved_category``. ``_classify``
must read that value instead of re-deriving it — so ``classify_from_nfo`` runs
exactly ONCE per verify (the single call inside the ``category`` plugin),
never a second time inside ``_classify``.

This pins the optimisation against regression: if ``_classify`` ever falls back
to ``classify_from_nfo`` for an item whose ``category`` plugin already resolved
a category, the call count jumps to 2 and this test fails.

The corpus ``movie_valid`` / ``tvshow_valid`` items are reused because the
characterization golden proves they resolve a non-None category under
``test_config`` — the precondition for ``_classify`` to set ``result.category``.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.verifier import Verifier
from tests.fixtures.settings_stub import make_typed_settings_stub
from tests.verify.golden import _corpus


def _patch_classify_counter(monkeypatch) -> list[str]:
    """Patch every bound name of ``classify_from_nfo`` with a call counter.

    Patches the source module plus the two import-time bindings (the ``category``
    plugin and the verifier fallback) so a second classification on either path
    would be observed.

    Returns:
        A list appended to on each ``classify_from_nfo`` invocation.
    """
    calls: list[str] = []
    import personalscraper.conf.classifier as classifier_mod

    real = classifier_mod.classify_from_nfo

    def _counting(*args, **kwargs):
        calls.append("called")
        return real(*args, **kwargs)

    monkeypatch.setattr(classifier_mod, "classify_from_nfo", _counting)
    monkeypatch.setattr("personalscraper.verify.checks.category.classify_from_nfo", _counting)
    monkeypatch.setattr("personalscraper.verify.verifier.classify_from_nfo", _counting)
    return calls


def test_verify_movie_classify_calls_classify_from_nfo_once(test_config: Config, tmp_path: Path, monkeypatch) -> None:
    """CMP-3: a normal movie resolves its category via a single classify call.

    The ``category`` plugin calls ``classify_from_nfo`` once; ``_classify``
    reuses ``ctx.resolved_category`` and does NOT call it again.
    """
    calls = _patch_classify_counter(monkeypatch)
    movie = _corpus.build_item_corpus(tmp_path / "v_mov")["movie_valid"]

    v = Verifier(make_typed_settings_stub(), PATTERNS, test_config, dry_run=False, fix=True)
    result = v.verify_movie(movie)

    assert result.category is not None  # precondition: category resolved
    # Exactly one classification: the ``category`` plugin's. _classify reuses
    # ctx.resolved_category, so the verifier fallback path is never taken.
    assert calls == ["called"], f"expected 1 classify_from_nfo call, got {len(calls)}"


def test_verify_tvshow_classify_calls_classify_from_nfo_once(test_config: Config, tmp_path: Path, monkeypatch) -> None:
    """CMP-3: a normal TV show resolves its category via a single classify call."""
    calls = _patch_classify_counter(monkeypatch)
    show = _corpus.build_item_corpus(tmp_path / "v_tv")["tvshow_valid"]

    v = Verifier(make_typed_settings_stub(), PATTERNS, test_config, dry_run=False, fix=True)
    result = v.verify_tvshow(show)

    assert result.category is not None
    assert calls == ["called"], f"expected 1 classify_from_nfo call, got {len(calls)}"
