"""Parity proof: registry-loop output EQUALS MediaChecker output (DISPATCH).

This is THE acceptance criterion for sub-phase 2.1. For both movie and tvshow
items in the Phase-0 corpus, the list of CheckResults produced by iterating
``registry.checks_for(DISPATCH, mt)`` must be byte-for-byte equal to the
output of the (still-unchanged) ``MediaChecker.check_movie`` /
``check_tvshow``. ``CheckResult`` is a dataclass (auto ``__eq__``), so
list-equality is exact — including order, severity, message, and fixable flag.

If a single corpus item mismatches, the plugin extraction is wrong. Keeping
this green guarantees that sub-phase 2.2 (which replaces MediaChecker's body
with this exact loop) preserves the characterization golden.
"""

from __future__ import annotations

from pathlib import Path

import personalscraper.verify.checks  # noqa: F401 — triggers plugin registration
from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.checker import MediaChecker
from personalscraper.verify.checks.base import CheckContext, CheckStage
from personalscraper.verify.checks.registry import registry
from tests.verify.golden import _corpus


def _loop(media_type: str, media_dir: Path, cfg: object) -> list:
    """Run the DISPATCH registry loop for a single media item.

    Args:
        media_type: ``"movie"`` or ``"tvshow"``.
        media_dir: Path to the media directory.
        cfg: Config instance (the ``test_config`` fixture).

    Returns:
        List of CheckResult in registry (_ORDER) sequence.
    """
    ctx = CheckContext(
        media_dir=media_dir,
        media_type=media_type,
        stage=CheckStage.DISPATCH,
        config=cfg,  # type: ignore[arg-type]
        patterns=PATTERNS,
    )
    return [r for check in registry.checks_for(CheckStage.DISPATCH, media_type) for r in check.run(ctx)]


def test_movie_parity(test_config, tmp_path):
    """Registry loop == MediaChecker.check_movie over every movie corpus item."""
    items = _corpus.build_item_corpus(tmp_path / "p_mov")
    chk = MediaChecker(PATTERNS, test_config)
    checked = 0
    for name, path in items.items():
        if name.startswith("movie_"):
            assert _loop("movie", path, test_config) == chk.check_movie(path), f"parity mismatch: {name}"
            checked += 1
    assert checked > 0, "no movie corpus items found — fail-on-empty guard"


def test_tvshow_parity(test_config, tmp_path):
    """Registry loop == MediaChecker.check_tvshow over every tvshow corpus item."""
    items = _corpus.build_item_corpus(tmp_path / "p_tv")
    chk = MediaChecker(PATTERNS, test_config)
    checked = 0
    for name, path in items.items():
        if name.startswith("tvshow_"):
            assert _loop("tvshow", path, test_config) == chk.check_tvshow(path), f"parity mismatch: {name}"
            checked += 1
    assert checked > 0, "no tvshow corpus items found — fail-on-empty guard"
