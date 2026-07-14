"""Unit tests for the single-position axiom (web/staging/stages.py — P0-A.1).

``compute_position`` is the ONE derivation every surface (board stocks,
per-stage lists, per-item timeline) consumes; these tests pin its decision
table and the timeline unrolling so the axiom cannot silently regress.
"""

from __future__ import annotations

import pytest

from personalscraper.web.staging.stages import (
    STAGE_DEFS,
    STAGE_KEYS,
    compute_position,
    compute_stages,
    position_blocked_reason,
)


def _position(**overrides):
    """Call ``compute_position`` with movie defaults, overridden per case."""
    kwargs = {
        "media_kind": "movie",
        "in_ingest": False,
        "scrapable": True,
        "is_ambiguous": False,
        "is_matched": False,
        "verify_ok": False,
        "live_stage_key": None,
    }
    kwargs.update(overrides)
    return compute_position(**kwargs)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        # Still in the ingest dir → integrated, awaiting sort.
        ({"media_kind": "unsorted", "scrapable": False, "in_ingest": True}, ("arrival", "pending")),
        # AUTRES/unknown kind → the operator qualifies it at Identification.
        ({"media_kind": "other", "scrapable": False}, ("matching", "blocked")),
        # Non-scrapable kinds go straight to dispatch.
        ({"media_kind": "ebook", "scrapable": False}, ("dispatch", "pending")),
        # A pending decision blocks Identification (resolution deck).
        ({"is_ambiguous": True}, ("matching", "blocked")),
        # No confident match → blocked at Identification (needs enqueue).
        ({}, ("matching", "blocked")),
        # Scraped but the real verify gate refuses it → blocked at Vérification.
        ({"is_matched": True}, ("verify", "blocked")),
        # Scraped + verified → awaiting Dispatch.
        ({"is_matched": True, "verify_ok": True}, ("dispatch", "pending")),
    ],
)
def test_position_decision_table(overrides: dict, expected: tuple[str, str]) -> None:
    """Each signal combination yields exactly the position of the table."""
    assert _position(**overrides) == expected


def test_position_is_always_a_known_stage() -> None:
    """Whatever the signals, the position is one of the eight stage keys."""
    for in_ingest in (True, False):
        for scrapable in (True, False):
            for ambiguous in (True, False):
                for matched in (True, False):
                    for verify_ok in (True, False):
                        stage, state = _position(
                            in_ingest=in_ingest,
                            scrapable=scrapable,
                            is_ambiguous=ambiguous,
                            is_matched=matched,
                            verify_ok=verify_ok,
                        )
                        assert stage in STAGE_KEYS
                        assert state in ("pending", "active", "blocked")


def test_live_step_lights_pending_position_active() -> None:
    """The live run's current stage flips a pending position to active — never a blocked one."""
    assert _position(is_matched=True, verify_ok=True, live_stage_key="dispatch") == ("dispatch", "active")
    # A blocked position needs the operator: the run does not light it.
    assert _position(is_ambiguous=True, live_stage_key="matching") == ("matching", "blocked")


def test_timeline_unrolls_position() -> None:
    """The timeline is the position unrolled: done before, state at, pending after."""
    steps = compute_stages(media_kind="tvshow", scrapable=True, position_stage="verify", position_state="blocked")
    by_key = {s.key: s.state for s in steps}
    assert [s.key for s in steps] == list(STAGE_KEYS)
    assert by_key["arrival"] == by_key["sorting"] == by_key["cleaning"] == "done"
    assert by_key["matching"] == by_key["scraping"] == by_key["trailers"] == "done"
    assert by_key["verify"] == "blocked"
    assert by_key["dispatch"] == "pending"


def test_timeline_skips_stages_outside_the_kind() -> None:
    """Non-scrapable kinds skip the scrape flow; AUTRES keeps Identification actionable."""
    ebook = {
        s.key: s.state
        for s in compute_stages(
            media_kind="ebook", scrapable=False, position_stage="dispatch", position_state="pending"
        )
    }
    assert ebook["matching"] == ebook["scraping"] == ebook["trailers"] == ebook["verify"] == "skipped"
    other = {
        s.key: s.state
        for s in compute_stages(
            media_kind="other", scrapable=False, position_stage="matching", position_state="blocked"
        )
    }
    assert other["matching"] == "blocked"
    assert other["scraping"] == other["trailers"] == other["verify"] == "skipped"


def test_blocked_reasons_are_actionable_french() -> None:
    """Every blocked position carries a French operator reason (A.5)."""
    assert (
        position_blocked_reason(
            media_kind="movie", stage="matching", state="blocked", is_ambiguous=True, verify_reason=None
        )
        == "À identifier : décision en attente dans la file de résolution"
    )
    assert (
        position_blocked_reason(
            media_kind="movie", stage="matching", state="blocked", is_ambiguous=False, verify_reason=None
        )
        == "Non identifié : à envoyer en résolution"
    )
    assert (
        position_blocked_reason(
            media_kind="other", stage="matching", state="blocked", is_ambiguous=False, verify_reason=None
        )
        == "À qualifier : type de média à préciser (film ou série)"
    )
    # Verify blocks pass through the real verify-gate reason.
    assert (
        position_blocked_reason(
            media_kind="tvshow",
            stage="verify",
            state="blocked",
            is_ambiguous=False,
            verify_reason="Bloqué : épisodes non renommés",
        )
        == "Bloqué : épisodes non renommés"
    )
    # A non-blocked position never carries a reason.
    assert (
        position_blocked_reason(
            media_kind="movie", stage="dispatch", state="pending", is_ambiguous=False, verify_reason=None
        )
        is None
    )


def test_stage_defs_has_no_staging_station() -> None:
    """P0-A.2: « Staging » is a place, not a step — the taxonomy has no such station."""
    labels = [label for _, label in STAGE_DEFS]
    assert "Staging" not in labels
    assert len(STAGE_DEFS) == 8
    assert [label for _, label in STAGE_DEFS] == [
        "Arrivée",
        "Tri",
        "Nettoyage",
        "Identification",
        "Scraping",
        "Trailers",
        "Vérification",
        "Dispatch",
    ]
