"""Tests for the Web-UI enumeration API: catalog.list_checks() and run_check().

Asserts against the REAL singleton registry (importing
``personalscraper.verify.checks`` triggers plugin registration). These tests
lock the public CheckSpec flags (fixable / indexable) and the run_check
dispatch contract (happy path returns ``list[CheckResult]``; unknown name
raises ``KeyError``).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import personalscraper.verify.checks  # noqa: F401 — trigger plugin registration
from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.checks.base import (
    CheckContext,
    CheckResult,
    CheckStage,
)
from personalscraper.verify.checks.catalog import list_checks, run_check
from tests.verify.golden import _corpus

# DISPATCH-stage checks that MUST be in the registry roster (a representative
# subset of the verify pipeline — not the exhaustive list).
_EXPECTED_DISPATCH = {"nfo_present", "dir_naming", "category", "streamdetails"}

# STAGING-stage checks that MUST be in the registry roster.
_EXPECTED_STAGING = {"sort_process_coherence", "genre_coherence", "nfo_ids"}


def _spec_by(stage: CheckStage, name: str):
    """Return the CheckSpec for a given (stage, name) from the real registry.

    Args:
        stage: CheckStage to look up.
        name: Check name to look up.

    Returns:
        The matching CheckSpec.

    Raises:
        AssertionError: If no spec is registered for (stage, name).
    """
    for spec in list_checks():
        if spec.stage == stage and spec.name == name:
            return spec
    raise AssertionError(f"no spec registered for ({stage!r}, {name!r})")


# ── list_checks() roster ──


def test_list_checks_superset_of_dispatch_and_staging_rosters() -> None:
    """list_checks() names cover the DISPATCH roster and the STAGING names."""
    names = {s.name for s in list_checks()}
    assert _EXPECTED_DISPATCH <= names
    assert _EXPECTED_STAGING <= names


# ── CheckSpec flags ──


def test_dir_naming_spec_flags() -> None:
    """dir_naming (DISPATCH) is fixable but not indexable."""
    spec = _spec_by(CheckStage.DISPATCH, "dir_naming")
    assert spec.fixable is True
    assert spec.indexable is False


def test_nfo_present_spec_is_indexable() -> None:
    """nfo_present (DISPATCH) is indexable."""
    spec = _spec_by(CheckStage.DISPATCH, "nfo_present")
    assert spec.indexable is True


def test_streamdetails_and_category_specs_not_fixable() -> None:
    """Streamdetails and category (DISPATCH) are not fixable."""
    assert _spec_by(CheckStage.DISPATCH, "streamdetails").fixable is False
    assert _spec_by(CheckStage.DISPATCH, "category").fixable is False


# ── run_check() dispatch contract ──


def _movie_ctx(media_dir: Path) -> CheckContext:
    """Build a DISPATCH CheckContext for a movie dir (Config is a stub).

    Args:
        media_dir: Path to the movie directory.

    Returns:
        A CheckContext wired with the real NamingPatterns singleton.
    """
    return CheckContext(
        media_dir=media_dir,
        media_type="movie",
        stage=CheckStage.DISPATCH,
        config=MagicMock(),
        patterns=PATTERNS,
    )


def test_run_check_happy_path_returns_check_results(tmp_path: Path) -> None:
    """run_check(DISPATCH, nfo_present, ctx) returns a list[CheckResult]."""
    items = _corpus.build_item_corpus(tmp_path / "corpus")
    ctx = _movie_ctx(items["movie_valid"])

    results = run_check(CheckStage.DISPATCH, "nfo_present", ctx)

    assert isinstance(results, list)
    assert results  # nfo_present always emits one result for a movie
    assert all(isinstance(r, CheckResult) for r in results)


def test_run_check_unknown_name_raises_keyerror(tmp_path: Path) -> None:
    """run_check with an unregistered name raises KeyError."""
    items = _corpus.build_item_corpus(tmp_path / "corpus")
    ctx = _movie_ctx(items["movie_valid"])

    with pytest.raises(KeyError):
        run_check(CheckStage.DISPATCH, "does_not_exist", ctx)
