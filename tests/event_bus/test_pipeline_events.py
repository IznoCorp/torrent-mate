"""Tests for the pipeline event catalog — Sub-phase 3.1.

Six events flow through the bus around every pipeline run. This test module
locks:

- Each event inherits from :class:`Event` and stays a frozen dataclass.
- Each event is auto-registered in ``_EVENT_CLASS_REGISTRY``.
- Each event has a registered factory in :data:`EVENT_SAMPLE_FACTORIES`.
- Each event survives ``event_to_envelope`` → ``json.dumps`` →
  ``json.loads`` → ``event_from_envelope`` with equality preserved (the
  gate test that exercises the Report round-trip path validated in the
  pre-3.1 investigation commits).
- The generic ``test_every_event_has_factory`` assertion (vacuous in
  Phase 1) is now non-vacuous — it covers all 6 pipeline events.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from personalscraper.core.event_bus import (
    _EVENT_CLASS_REGISTRY,
    Event,
    event_from_envelope,
    event_to_envelope,
)
from personalscraper.pipeline_events import (
    ItemProgressed,
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

PIPELINE_EVENT_CLASSES: tuple[type[Event], ...] = (
    PipelineStarted,
    PipelineEnded,
    StepStarted,
    StepCompleted,
    StepErrored,
    ItemProgressed,
)


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_inherit_event_base(cls: type[Event]) -> None:
    """Every pipeline event inherits from :class:`Event`."""
    assert issubclass(cls, Event)


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_are_frozen(cls: type[Event]) -> None:
    """Every pipeline event is a frozen dataclass."""
    assert dataclasses.is_dataclass(cls)
    instance = EVENT_SAMPLE_FACTORIES[cls]()
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.source = "mutated"  # type: ignore[misc]


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_auto_registered(cls: type[Event]) -> None:
    """Each event class name appears in ``_EVENT_CLASS_REGISTRY``."""
    assert _EVENT_CLASS_REGISTRY.get(cls.__name__) is cls


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_have_factories(cls: type[Event]) -> None:
    """Each event has a registered factory in ``EVENT_SAMPLE_FACTORIES``."""
    assert cls in EVENT_SAMPLE_FACTORIES


@pytest.mark.parametrize("cls", PIPELINE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_pipeline_events_envelope_roundtrip(cls: type[Event]) -> None:
    """Envelope round-trip preserves equality for every pipeline event.

    The gate test — exercises Report serialization across the
    JSON-coerced fields fixed in the pre-3.1 investigation commits
    (``failed_items`` → ``list[FailedItem]``; ``details_payload`` →
    ``dict[str, Any]``).
    """
    e1 = EVENT_SAMPLE_FACTORIES[cls]()
    envelope = event_to_envelope(e1)
    e2 = event_from_envelope(json.loads(json.dumps(envelope)))
    assert e2 == e1


def test_every_event_has_factory() -> None:
    """Every production-registered event has a factory (Sub-phase 1.8 gate).

    Vacuous in Phase 1 (no production events). Phase 3.1 makes it
    non-vacuous — the 6 pipeline events live in the registry and every
    one MUST have a factory. Phase 4 will add more events; each must
    register its factory before the phase gate.
    """
    registered = set(_EVENT_CLASS_REGISTRY.values())
    factored = set(EVENT_SAMPLE_FACTORIES.keys())
    assert registered, "Phase 3.1: registry is non-empty (6 pipeline events)"
    missing = registered - factored
    assert not missing, (
        f"Production events missing factories in EVENT_SAMPLE_FACTORIES: {sorted(c.__name__ for c in missing)}"
    )


def test_event_registry_has_all_v1_events() -> None:
    """The catalog is pinned at 50 events.

    Phase 5 acceptance landed at 13 ; the ``provider-ids`` feature
    (sub-phase 8.4) added 4 ``Backfill*`` events for the IDs/ratings
    backfill lifecycle (→ 17). The ``tech-debt`` 0.16.0 sub-phase 3.1
    (DEV #6/#40) added ``VerifyItemDone`` for per-item verify
    telemetry (→ 18). The ``arch-cleanup-2`` Phase 1 sub-phase 1.2
    rebased the 5 provider-registry events onto the ``Event`` contract
    and eager-imported them via ``personalscraper.events``, so they now
    auto-register in the catalog (→ 23). The ``acquire-events`` RP4
    Phase 1 adds 10 acquisition events: ``SeriesFollowed``,
    ``SeriesUnfollowed``, ``WantedEnqueued``, ``WantedAbandoned``,
    ``GrabSucceeded``, ``GrabFailed``, ``SeedObligationRecorded``,
    ``SeedObligationBreached``, ``SeedObligationSatisfied``,
    ``RatioMeasured`` (→ 33). The ``tracker-auth`` Phase 1 adds
    ``TrackerAuthFailed`` (→ 34). The ``watch-seed`` Phase 5 adds
    ``CrossSeedInjected`` and ``CrossSeedRejected`` (→ 36). The
    ``watch-seed`` Phase 7 adds ``WatcherRunTriggered`` (→ 37). The
    ``pipe-control`` S2 Phase 1 adds ``PipelinePaused`` and
    ``PipelineResumed`` for the cooperative step-boundary pause (→ 39).
    The ``reg-health`` S6 Phase 2 adds ``ProviderCallCompleted`` — a
    throttled per-provider latency event that bridges into the web
    process's health projection (→ 40).
    The product-intent §5 acquisitions restoration adds ``FilmAcquired`` — a
    followed film reached the library and was auto-removed from the follows
    (→ 41).
    The ``reswitch`` #342 auto-reswitch adds ``GrabReswitched`` — a dead-stalled
    grab was switched to another release (→ 42).
    The ``season-grab`` feature adds ``SeasonAbsorbedEpisodes`` and
    ``SeasonFellBackToEpisodes`` — season wanted lifecycle events for R5
    absorption and R6 fallback (→ 44).
    The ``seed-caps`` feature (O4) adds ``DownloadStarted``,
    ``DownloadProgressed`` and ``DownloadCompleted`` — download lifecycle
    observations emitted by the reconcile sweep (→ 47).
    The ``k0-obligation-sweep`` feature adds ``SeedObligationReleased`` — the
    sweep found a seeding torrent gone from the client (→ 49). The ``k2-library-events``
    feature adds ``LibraryScanSkipped`` — a disk touched by dispatch was not re-indexed (→ 50).
    The ``k1-comptes`` feature adds ``AccountRightsChanged`` (E8) — an account's role or
    rights moved (→ 51).
    The ``preprod-purge`` feature adds ``PreprodPurgeCompleted`` — the preprod's
    nightly purge ran (→ 52).
    The ``k4a-queue-model`` feature adds ``RunQueued``, ``RunAdmitted`` and ``RunSettled`` —
    the supervisor's queue of asked runs (→ 55). The ``plex-session-notice`` feature adds
    ``PlexSessionOpened`` — a Plex sign-in opened a new session (→ 56).
    The literal count guards against silent
    additions that bypass the documented event catalog in
    ``docs/production/event-bus.md``.
    """
    import personalscraper.app.accounts.events  # noqa: F401 — registers E8 (the catalog does not import app)
    import personalscraper.app.supervisor.events  # noqa: F401 — registers RunQueued, RunAdmitted, RunSettled
    import personalscraper.events  # noqa: F401 — eager-import side effect

    assert len(_EVENT_CLASS_REGISTRY) == 56, (
        f"Expected 56 events (52 existing + the three run-queue events + PlexSessionOpened), "
        f"found {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}"
    )


def test_item_progressed_details_defaults_to_empty_dict() -> None:
    """``ItemProgressed.details`` defaults to ``{}`` for steps that emit no extras."""
    event = ItemProgressed(step="ingest", item="file.mkv", status="moved")
    assert event.details == {}


def test_step_completed_elapsed_s_is_float() -> None:
    """``StepCompleted.elapsed_s`` is the wall-clock duration in seconds."""
    event = EVENT_SAMPLE_FACTORIES[StepCompleted]()
    assert isinstance(event, StepCompleted)
    assert isinstance(event.elapsed_s, float)
    assert event.elapsed_s > 0


def test_the_catalogue_doc_states_the_registry_count_and_documents_the_run_events() -> None:
    """The catalogue doc states the registry's size, the verify exception's "other N", and rows the run events."""
    import re
    from pathlib import Path

    import personalscraper.app.accounts.events  # noqa: F401 — registers E8
    import personalscraper.app.supervisor.events  # noqa: F401 — registers the run events
    import personalscraper.events  # noqa: F401 — eager-import side effect

    doc = (Path(__file__).resolve().parents[2] / "docs" / "production" / "event-bus.md").read_text(encoding="utf-8")
    total = len(_EVENT_CLASS_REGISTRY)
    assert f"defines exactly {total} production event classes" in doc
    assert f"`len(_EVENT_CLASS_REGISTRY) == {total}`" in doc
    assert f"Unlike the other {total - 1} classes" in doc
    for name in ("RunQueued", "RunAdmitted", "RunSettled"):
        assert re.search(rf"^\| `{name}`\s+\| `personalscraper\.app\.supervisor\.events`", doc, re.M), name
