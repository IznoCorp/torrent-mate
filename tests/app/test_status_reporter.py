"""Tests for the rolling project status-update reporter (:mod:`kanbanmate.app.status_reporter`).

The reporter is the tick's fail-soft last step (phase-24 §24.3): it gathers an
:class:`~kanbanmate.core.status_update.OrchestrationState` from the running tickets + the
snapshot + the queue + the kill-switch flag, renders the dashboard, and posts it to GitHub ONLY
when the body hash changed — falling back from ``update`` to ``create`` on a stale id, and
swallowing every error (observability, never a launch blocker).

These tests drive ``report_status`` directly against in-memory fakes for the store + reporter +
comment-reader (mirroring the app-test fakes), asserting: a one-agent state creates with the
rendered body; an unchanged body across two calls posts NOTHING the second time (hash match); a
stored id takes the update path, and a raising update falls back to create; a posting/parse error
is swallowed; and this tick's actions land in the events ring (newest-first when rendered, capped
at 10).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from kanbanmate.adapters.github.types import CommentRef
from kanbanmate.app.actions import Deps
from kanbanmate.app.status_reporter import event_kind_for_action, report_status
from kanbanmate.app.tick import TickConfig
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import ActionKind, BoardSnapshot, Ticket
from kanbanmate.core.stage_comment import compose, marker
from kanbanmate.core.transitions_defaults import default_transition_config
from kanbanmate.ports.store import TicketState, TicketStatus


@pytest.fixture(autouse=True)
def _clear_progress_cache() -> None:
    """Clear the module-level progress TTL cache (#10) before each test (test isolation).

    The cache is keyed by ``(issue, stage)`` with a ``now``-relative expiry; since many tests reuse
    the same ``now`` + issue, a stale cross-test HIT would otherwise leak. Clearing it per test keeps
    each test reading the sticky it set up.
    """
    import kanbanmate.app.status_reporter as _sr

    _sr._progress_cache.clear()


# A minimal one-column board model; the reporter only reads ``config.concurrency_cap``.
_COLUMNS_YAML = """
columns:
  - key: InProgress
    name: In Progress
"""


def _config(cap: int = 3) -> TickConfig:
    """Build a :class:`TickConfig` whose only relevant knob is ``concurrency_cap``."""
    return TickConfig(
        columns=load_columns(_COLUMNS_YAML),
        transitions=default_transition_config(),
        concurrency_cap=cap,
    )


# ---------------------------------------------------------------------------
# Fakes (mirror the app-test fake style: small, in-memory, assertion-friendly).
# ---------------------------------------------------------------------------


@dataclass
class _FakeReporter:
    """A recording :class:`~kanbanmate.ports.board.ProjectStatusReporter`.

    Records every ``create``/``update`` call so a test can assert which path ran with which body;
    ``update_raises`` flips the update path to raise so the create fallback is exercised.
    """

    created: list[tuple[str, str, str]] = field(default_factory=list)
    updated: list[tuple[str, str, str]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    update_raises: bool = False
    create_raises: bool = False
    delete_raises: bool = False
    _next_id: int = 0

    def create_status_update(self, project_id: str, body: str, status: str) -> str:
        """Record the create call and return a fresh synthetic node id."""
        self.created.append((project_id, body, status))
        if self.create_raises:
            raise RuntimeError("simulated create failure")
        self._next_id += 1
        return f"PVTSU_{self._next_id}"

    def update_status_update(self, status_update_id: str, body: str, status: str) -> None:
        """Record the update call; raise when ``update_raises`` is set (stale id)."""
        self.updated.append((status_update_id, body, status))
        if self.update_raises:
            raise RuntimeError("simulated stale-id update failure")

    def delete_status_update(self, status_update_id: str) -> None:
        """Record the orphan-delete call; raise when ``delete_raises`` is set (phase-36)."""
        self.deleted.append(status_update_id)
        if self.delete_raises:
            raise RuntimeError("simulated orphan-delete failure")


@dataclass
class _FakeCommentReader:
    """A minimal comment-reader satisfying the slice of ``BoardWriter`` the reporter uses.

    Only ``list_issue_comments`` is exercised by the reporter (to read each agent's sticky
    progress). ``comments`` maps issue number → the comment refs to return; ``raises`` makes the
    read raise so the per-agent fail-soft path degrades progress to ``None``.
    """

    comments: dict[int, list[CommentRef]] = field(default_factory=dict)
    raises: bool = False

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """Return the scripted comments for ``issue_number`` (or raise)."""
        if self.raises:
            raise RuntimeError("simulated list_issue_comments failure")
        return self.comments.get(issue_number, [])


@dataclass
class _FakeStatusStore:
    """An in-memory store implementing exactly the status-state methods the reporter touches.

    Backs the ring (≤10 newest), the rolling update id, and the last-posted body hash with plain
    in-memory state; ``running`` is the running-ticket view ``report_status`` is handed directly
    (so the store's own ``list_running`` is not needed here). ``append_raises`` makes the ring
    append raise so the per-append fail-soft path is covered.
    """

    update_id: str | None = None
    body_hash: str | None = None
    # The GitHub status ENUM last posted (re-create-on-enum-change guard). ``None``
    # means "never posted" → the first render is treated as an enum change.
    last_status: str | None = None
    # The project the persisted id/hash belong to (phase-33 rebind guard). ``None``
    # means "never bound" → the reporter treats the first post as a project change.
    status_project_id: str | None = None
    events: list[dict[str, object]] = field(default_factory=list)
    append_raises: bool = False

    def get_status_update_id(self) -> str | None:
        return self.update_id

    def set_status_update_id(self, status_update_id: str | None) -> None:
        self.update_id = status_update_id

    def get_status_project_id(self) -> str | None:
        return self.status_project_id

    def set_status_project_id(self, project_id: str | None) -> None:
        self.status_project_id = project_id

    def get_status_body_hash(self) -> str | None:
        return self.body_hash

    def set_status_body_hash(self, body_hash: str | None) -> None:
        self.body_hash = body_hash

    def get_status_last_enum(self) -> str | None:
        return self.last_status

    def set_status_last_enum(self, status: str | None) -> None:
        self.last_status = status

    override_enum: str | None = None
    override_note: str | None = None

    def get_status_override_enum(self) -> str | None:
        return self.override_enum

    def set_status_override_enum(self, status: str | None) -> None:
        self.override_enum = status

    def get_status_override_note(self) -> str | None:
        return self.override_note

    def set_status_override_note(self, note: str | None) -> None:
        self.override_note = note

    def append_status_event(self, event: dict[str, object]) -> None:
        if self.append_raises:
            raise RuntimeError("simulated ring append failure")
        self.events.append(dict(event))
        if len(self.events) > 10:
            self.events = self.events[-10:]

    def read_status_events(self) -> tuple[dict[str, object], ...]:
        return tuple(self.events)


def _deps(
    *,
    reporter: _FakeReporter,
    store: _FakeStatusStore,
    reader: _FakeCommentReader | None = None,
) -> Deps:
    """Assemble a :class:`Deps` wiring the status fakes (other ports are unused here).

    The reporter only touches ``status_reporter`` / ``board_writer`` (the comment-reader) /
    ``store`` / ``project_id``; the remaining ports are typed-but-unused, so a bare object stands
    in (the reporter never calls them). The constructed ``Deps`` is frozen, matching production.
    """
    placeholder = object()
    return Deps(
        board_writer=reader or _FakeCommentReader(),  # type: ignore[arg-type]
        board_reader=placeholder,  # type: ignore[arg-type]
        workspace=placeholder,  # type: ignore[arg-type]
        sessions=placeholder,  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        clock=placeholder,  # type: ignore[arg-type]
        pull_requests=placeholder,  # type: ignore[arg-type]
        status_reporter=reporter,
        project_id="PVT_proj",
    )


def _running(issue: int = 7, *, stage: str = "InProgress", heartbeat: float = 990.0) -> TicketState:
    """Build a RUNNING :class:`TicketState` for one in-flight ticket."""
    return TicketState(
        issue_number=issue,
        item_id=f"PVTI_{issue}",
        session_id="sess",
        status=TicketStatus.RUNNING,
        heartbeat=heartbeat,
        stage=stage,
        profile="dev",
        started=900.0,
    )


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets into a :class:`BoardSnapshot`."""
    return BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)


# ---------------------------------------------------------------------------
# (a) one running agent → render + create called with the body
# ---------------------------------------------------------------------------


def test_one_running_agent_creates_with_rendered_body() -> None:
    """A first post for one running agent CREATEs the rolling update with the rendered body."""
    reporter = _FakeReporter()
    store = _FakeStatusStore()  # no stored id/hash → first contact
    snapshot = _snapshot(
        Ticket(item_id="PVTI_7", issue_number=7, title="Wire it", column_key="InProgress")
    )
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=snapshot,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    # CREATE path (no stored id), not update.
    assert len(reporter.created) == 1
    assert reporter.updated == []
    project_id, body, status = reporter.created[0]
    assert project_id == "PVT_proj"
    assert status == "ACTIVE"  # one healthy running agent
    # The body is the real rendered dashboard — it carries the agent line + the title off the snapshot.
    assert "#7" in body
    assert "Wire it" in body
    # The new id + the body hash are persisted so the next tick can detect no-change / update.
    assert store.update_id == "PVTSU_1"
    assert store.body_hash is not None


def test_agent_title_resolved_from_snapshot_not_doubled_placeholder() -> None:
    """A running agent's REAL issue title renders from the snapshot — not a doubled ``[#n]`` (§25.4).

    Bug E: the dashboard rendered ``**#140** [#140]`` because the ``code`` tag was set to
    ``#{issue}`` (duplicating the leading ``**#140**``) and the title fell back to empty. The fix
    resolves the title off the snapshot board item and makes ``code`` the profile (the real type
    tag), so the agent line carries ``**#140** [docs] Pipeline Assistant``.
    """
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    snapshot = _snapshot(
        Ticket(item_id="PVTI_140", issue_number=140, title="Pipeline Assistant", column_key="Spec")
    )
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(_running(140, stage="Spec"),),
        snapshot=snapshot,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    body = reporter.created[0][1]
    # The REAL title is shown.
    assert "Pipeline Assistant" in body
    # The doubled placeholder is GONE: the code tag is now the profile ("dev"), not "#140".
    assert "[#140]" not in body
    assert "**#140** [dev] Pipeline Assistant" in body


def test_agent_title_falls_back_to_bare_reference_when_absent() -> None:
    """With no snapshot (unchanged probe) the title falls back to a bare ``#n`` — not ``[#n]`` (§25.4).

    On an unchanged-probe tick ``snapshot`` is ``None``, so the live title is unavailable. The
    graceful fallback is the BARE ``#<n>`` reference as the title (it reads cleanly), and the
    bracketed tag is the profile — so the line is ``**#140** [dev] #140``, never ``**#140** [#140]``.
    """
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(_running(140, stage="Spec"),),
        snapshot=None,  # unchanged probe → no snapshot → no live title
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    body = reporter.created[0][1]
    # No doubled placeholder; the bracket carries the profile, the title is the bare reference.
    assert "[#140]" not in body
    assert "**#140** [dev] #140" in body


# ---------------------------------------------------------------------------
# (b) unchanged body across two calls → the SECOND call posts NOTHING
# ---------------------------------------------------------------------------


def test_unchanged_body_second_call_posts_nothing() -> None:
    """An identical render on the next tick matches the stored hash → no second API call."""
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    snapshot = _snapshot(
        Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    )
    deps = _deps(reporter=reporter, store=store)

    def _report() -> None:
        report_status(
            deps,
            _config(),
            running=(_running(7),),
            snapshot=snapshot,
            queue_depth=0,
            paused=False,
            events=[],
            now=1000.0,
        )

    _report()  # first: creates
    _report()  # second: identical body → no-op

    # Exactly ONE create across both calls; the second matched the hash and posted nothing.
    assert len(reporter.created) == 1
    assert reporter.updated == []


# ---------------------------------------------------------------------------
# Project-rebind guard (phase-33): a registry re-point ignores stale id+hash.
# ---------------------------------------------------------------------------


def test_project_rebind_forces_fresh_create_ignoring_stale_id_and_hash() -> None:
    """Stored id/hash from a DIFFERENT project are ignored → a fresh create on the new board (§33).

    The board-wide ``update_id`` / ``body_hash`` markers survive a registry
    re-point: the stale id points at the OLD project and the stale hash would
    suppress the post. The rebind guard detects the project mismatch, drops both,
    creates fresh on the NEW project, and re-binds the marker.
    """
    reporter = _FakeReporter()
    # Persisted state belongs to the OLD project; deps.project_id is the NEW one.
    store = _FakeStatusStore(
        update_id="PVTSU_old", body_hash="any-stale-hash", status_project_id="PVT_old_project"
    )
    snapshot = _snapshot(
        Ticket(item_id="PVTI_7", issue_number=7, title="Wire it", column_key="InProgress")
    )
    deps = _deps(reporter=reporter, store=store)  # deps.project_id == "PVT_proj"

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=snapshot,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    # CREATE on the new board (the stale id was NOT used for an update).
    assert reporter.updated == []
    assert len(reporter.created) == 1
    assert reporter.created[0][0] == "PVT_proj"
    # The marker is re-bound to the new project, and the id/hash are the new ones.
    assert store.status_project_id == "PVT_proj"
    assert store.update_id == "PVTSU_1"
    assert store.body_hash not in (None, "any-stale-hash")


def test_same_project_keeps_on_change_no_rebind() -> None:
    """When the stored project id matches, the on-change discipline is preserved (§33).

    No rebind fires: a same-board refresh with a changed body takes the UPDATE
    path (the stored id is reused, not dropped) and an unchanged body posts
    nothing — exactly the pre-phase-33 behaviour for an unchanged registry.
    """
    reporter = _FakeReporter()
    store = _FakeStatusStore(status_project_id="PVT_proj")  # bound to the current project
    snapshot = _snapshot(
        Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    )
    deps = _deps(reporter=reporter, store=store)

    def _report() -> None:
        report_status(
            deps,
            _config(),
            running=(_running(7),),
            snapshot=snapshot,
            queue_depth=0,
            paused=False,
            events=[],
            now=1000.0,
        )

    _report()  # first: creates (no stored id yet, but project already matches → no rebind)
    first_id = store.update_id
    _report()  # second: identical body, same project → on-change suppresses the post

    assert len(reporter.created) == 1
    assert reporter.updated == []
    # The project binding was untouched and the id was preserved across ticks.
    assert store.status_project_id == "PVT_proj"
    assert store.update_id == first_id


def test_heartbeat_age_bucketed_keeps_body_stable_across_ticks() -> None:
    """#10: the heartbeat age renders bucketed, so two ticks 10s apart produce an IDENTICAL body.

    Before #10 the raw ``Ns`` heartbeat changed every tick → a fresh hash → a PATCH every poll. With
    minute-bucketing, two ticks within the same minute render the same body and post nothing the
    second time.
    """
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    snapshot = _snapshot(
        Ticket(item_id="PVTI_7", issue_number=7, title="t", column_key="InProgress")
    )
    deps = _deps(reporter=reporter, store=store)

    # Tick 1 at now=1000 (heartbeat 990 → age 10s → "<1m"); tick 2 at now=1010 (age 20s → "<1m").
    report_status(
        deps,
        _config(),
        running=(_running(7, heartbeat=990.0),),
        snapshot=snapshot,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )
    report_status(
        deps,
        _config(),
        running=(_running(7, heartbeat=990.0),),
        snapshot=snapshot,
        queue_depth=0,
        paused=False,
        events=[],
        now=1010.0,
    )

    # The bucketed age stayed "<1m" → identical body → only ONE create, no PATCH.
    assert len(reporter.created) == 1
    assert reporter.updated == []


def test_progress_read_is_ttl_cached() -> None:
    """#10: ``_latest_progress`` is TTL-cached — a second tick within the TTL does NOT re-read."""

    class _CountingReader(_FakeCommentReader):
        reads: int = 0

        def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
            type(self).reads += 1
            return super().list_issue_comments(issue_number)

    _CountingReader.reads = 0
    header = f"{marker('InProgress')}\n### running"
    body = compose(header, ["- 21:10 — milestone"])
    reader = _CountingReader(comments={7: [CommentRef(comment_id=1, body=body)]})
    store = _FakeStatusStore()
    deps = _deps(reporter=_FakeReporter(), store=store, reader=reader)

    # Two ticks 10s apart (within the 60s TTL): the second must serve the cached progress value.
    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )
    reads_after_first = _CountingReader.reads
    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[],
        now=1010.0,
    )

    # No additional progress read on the second tick (cache HIT).
    assert _CountingReader.reads == reads_after_first


# ---------------------------------------------------------------------------
# (b2) health-enum change → RE-CREATE so GitHub moves the project status pill
# (the live bug: a board stuck BLOCKED for days while the record read ACTIVE,
# because the daemon only ever updated the single rolling record IN PLACE, and
# GitHub refreshes the denormalised project pill only on a *create*).
# ---------------------------------------------------------------------------


def test_enum_change_recreates_and_deletes_old_to_move_pill() -> None:
    """When the health enum changes, the reporter re-creates (not updates) and deletes the old.

    The stored rolling update was last posted ``BLOCKED``; the new render is
    ``ACTIVE`` (a healthy running agent). An in-place ``update`` would leave the
    GitHub project pill frozen at ``BLOCKED`` (the live bug), so the reporter
    must CREATE a fresh update (which moves the pill) and best-effort delete the
    superseded one — keeping a single rolling pill.
    """
    reporter = _FakeReporter()
    store = _FakeStatusStore(
        update_id="PVTSU_old",
        body_hash="stale-hash",
        status_project_id="PVT_proj",
        last_status="BLOCKED",  # last posted enum differs from the ACTIVE render
    )
    snapshot = _snapshot(
        Ticket(item_id="PVTI_7", issue_number=7, title="Wire it", column_key="InProgress")
    )
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=snapshot,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    # RE-CREATE path: a fresh create (NOT an in-place update) moved the pill.
    assert len(reporter.created) == 1
    assert reporter.created[0][2] == "ACTIVE"
    assert reporter.updated == []
    # The superseded record was deleted so the board keeps a single rolling pill.
    assert reporter.deleted == ["PVTSU_old"]
    # The fresh id + the new enum are persisted for the next tick's change detection.
    assert store.update_id == "PVTSU_1"
    assert store.last_status == "ACTIVE"


def test_same_enum_body_change_updates_in_place_and_persists_enum() -> None:
    """An unchanged enum with a changed body updates IN PLACE — and re-persists the enum.

    No pill move is needed (the pill is already correct for this enum), so the
    cheap in-place update is used (no create / no delete), and the last-posted
    enum marker is (re)written so the next tick still detects a future change.
    """
    reporter = _FakeReporter()
    store = _FakeStatusStore(
        update_id="PVTSU_existing",
        body_hash="stale-hash",
        status_project_id="PVT_proj",
        last_status="ACTIVE",  # matches the ACTIVE render → no enum change
    )
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    assert reporter.created == []
    assert reporter.deleted == []
    assert len(reporter.updated) == 1
    assert reporter.updated[0][0] == "PVTSU_existing"
    assert store.last_status == "ACTIVE"


# ---------------------------------------------------------------------------
# (c) a stored update_id → update path; update raising → create fallback
# ---------------------------------------------------------------------------


def test_stored_id_takes_update_path() -> None:
    """A stored update id + a changed body → the UPDATE path (no new create)."""
    reporter = _FakeReporter()
    # The stored id/hash belong to the CURRENT project (no rebind) AND the last
    # posted enum matches the render (ACTIVE) — the normal same-board refresh
    # with an unchanged enum, which must take the in-place update path.
    store = _FakeStatusStore(
        update_id="PVTSU_existing",
        body_hash="stale-hash",
        status_project_id="PVT_proj",
        last_status="ACTIVE",
    )
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    assert reporter.created == []
    assert len(reporter.updated) == 1
    assert reporter.updated[0][0] == "PVTSU_existing"
    # The id is unchanged (update succeeded); the body hash was refreshed.
    assert store.update_id == "PVTSU_existing"
    assert store.body_hash != "stale-hash"


def test_update_raises_falls_back_to_create() -> None:
    """When ``update`` raises (stale/deleted id) the reporter falls back to ``create`` + re-stores."""
    reporter = _FakeReporter(update_raises=True)
    # Stored state already belongs to the current project (no rebind) and the enum
    # is unchanged (ACTIVE) → the in-place update path is taken; the stale id is
    # GitHub-stale, not project-stale, so the update raises and falls back.
    store = _FakeStatusStore(
        update_id="PVTSU_stale",
        body_hash="stale-hash",
        status_project_id="PVT_proj",
        last_status="ACTIVE",
    )
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    # Update attempted, then a create fallback re-stored a fresh id.
    assert len(reporter.updated) == 1
    assert len(reporter.created) == 1
    assert store.update_id == "PVTSU_1"  # the fresh id from the fallback create
    assert store.body_hash != "stale-hash"  # hash refreshed after the successful post
    # Phase-36: the orphaned OLD update is best-effort deleted so the project keeps a single pill.
    assert reporter.deleted == ["PVTSU_stale"]


def test_recreate_path_swallows_orphan_delete_failure(caplog) -> None:  # type: ignore[no-untyped-def]
    """A failing orphan-delete on the re-create path is swallowed (phase-36, fail-soft).

    The delete is best-effort cleanup: when it raises, the re-create still stands (the fresh id is
    stored, the hash refreshed) and ``report_status`` returns normally with a logged warning.
    """
    reporter = _FakeReporter(update_raises=True, delete_raises=True)
    store = _FakeStatusStore(
        update_id="PVTSU_stale",
        body_hash="stale-hash",
        status_project_id="PVT_proj",
        last_status="ACTIVE",
    )
    deps = _deps(reporter=reporter, store=store)

    import logging

    with caplog.at_level(logging.WARNING):
        report_status(
            deps,
            _config(),
            running=(_running(7),),
            snapshot=None,
            queue_depth=0,
            paused=False,
            events=[],
            now=1000.0,
        )

    # The delete was attempted (and failed) but the re-create stands.
    assert reporter.deleted == ["PVTSU_stale"]
    assert len(reporter.created) == 1
    assert store.update_id == "PVTSU_1"
    assert store.body_hash != "stale-hash"
    assert any(record.levelno == logging.WARNING for record in caplog.records)


# ---------------------------------------------------------------------------
# (d) a posting/parse error is swallowed (returns normally, logs a warning)
# ---------------------------------------------------------------------------


def test_posting_error_is_swallowed(caplog) -> None:  # type: ignore[no-untyped-def]
    """A create that raises is swallowed — ``report_status`` returns normally and logs a warning."""
    # Both update and create raise: a stored id forces update (raises) → create fallback (also raises).
    reporter = _FakeReporter(update_raises=True, create_raises=True)
    # Same-project stored state (no rebind) + unchanged enum so the update path is
    # forced first (it raises → create fallback also raises → both swallowed).
    store = _FakeStatusStore(
        update_id="PVTSU_x",
        body_hash="stale",
        status_project_id="PVT_proj",
        last_status="ACTIVE",
    )
    deps = _deps(reporter=reporter, store=store)

    import logging

    with caplog.at_level(logging.WARNING):
        # Must NOT raise (fail-soft) even though every post path raises.
        report_status(
            deps,
            _config(),
            running=(_running(7),),
            snapshot=None,
            queue_depth=0,
            paused=False,
            events=[],
            now=1000.0,
        )

    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_progress_read_error_is_swallowed_per_agent() -> None:
    """A failing sticky read degrades that agent's progress to None — the update still posts."""
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    reader = _FakeCommentReader(raises=True)  # every sticky read raises
    deps = _deps(reporter=reporter, store=store, reader=reader)

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    # The bad read did not drop the whole update — a create still happened.
    assert len(reporter.created) == 1


def test_progress_is_read_from_sticky() -> None:
    """The latest progress milestone is parsed off the agent's stage sticky into the body."""
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    # A sticky for stage "InProgress" carrying two progress milestones (newest last).
    header = f"{marker('InProgress')}\n### running"
    body = compose(header, ["- 20:49 — first milestone", "- 21:10 — latest milestone"])
    reader = _FakeCommentReader(comments={7: [CommentRef(comment_id=1, body=body)]})
    deps = _deps(reporter=reporter, store=store, reader=reader)

    report_status(
        deps,
        _config(),
        running=(_running(7),),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[],
        now=1000.0,
    )

    posted_body = reporter.created[0][1]
    assert "latest milestone" in posted_body
    assert "first milestone" not in posted_body  # only the LATEST milestone is shown


# ---------------------------------------------------------------------------
# (e) events ring gets this tick's actions, newest-first, capped 10
# ---------------------------------------------------------------------------


def test_events_ring_gets_this_tick_actions() -> None:
    """This tick's executed actions land in the ring; the rendered list is newest-first by ts.

    Within one tick every event shares ``now`` (stable order = append order); the newest-first
    ordering shows across ticks, so a later tick's event (higher ``ts``) renders ABOVE an earlier
    one. Two reports with distinct ``now`` exercise that.
    """
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    deps = _deps(reporter=reporter, store=store)

    # Tick 1 (earlier): a launch for #7.
    report_status(
        deps,
        _config(),
        running=(),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[("launch", 7, "→ InProgress")],
        now=1000.0,
    )
    # Tick 2 (later): a teardown for #8.
    report_status(
        deps,
        _config(),
        running=(),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[("teardown", 8, "cancelled")],
        now=2000.0,
    )

    # Both events accumulated in the ring (oldest-first in storage).
    kinds = [e["kind"] for e in store.events]
    assert kinds == ["launch", "teardown"]
    # Tick 1 CREATEd; tick 2 (stored id) took the UPDATE path. The latest post renders events
    # newest-first → the later teardown (#8) appears above the earlier launch (#7).
    body = reporter.updated[-1][1]
    assert body.index("#8") < body.index("#7")


def test_events_ring_caps_at_ten_newest() -> None:
    """Appending past the cap keeps only the 10 newest events (the store ring contract)."""
    reporter = _FakeReporter()
    store = _FakeStatusStore()
    deps = _deps(reporter=reporter, store=store)

    # 12 events this tick → the ring keeps the 10 newest.
    events: list[tuple[str, int | None, str]] = [("launch", i, f"e{i}") for i in range(12)]
    report_status(
        deps,
        _config(),
        running=(),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=events,
        now=1000.0,
    )

    assert len(store.events) == 10
    # The two OLDEST (issues 0 and 1) were dropped; the newest 10 (issues 2..11) remain.
    assert [e["issue"] for e in store.events] == list(range(2, 12))


def test_bad_ring_append_does_not_drop_the_update() -> None:
    """A ring-append failure is swallowed per-event; the dashboard still posts."""
    reporter = _FakeReporter()
    store = _FakeStatusStore(append_raises=True)
    deps = _deps(reporter=reporter, store=store)

    report_status(
        deps,
        _config(),
        running=(),
        snapshot=None,
        queue_depth=0,
        paused=False,
        events=[("launch", 7, "x")],
        now=1000.0,
    )

    # The append raised (and was swallowed), but the render + create still ran.
    assert store.events == []
    assert len(reporter.created) == 1


# ---------------------------------------------------------------------------
# event_kind_for_action mapping
# ---------------------------------------------------------------------------


def test_event_kind_for_action_maps_known_and_unknown() -> None:
    """Known action kinds map to their ring kind; unmapped kinds degrade to ``auto``."""
    assert event_kind_for_action(ActionKind.LAUNCH) == "launch"
    assert event_kind_for_action(ActionKind.TEARDOWN) == "teardown"
    assert event_kind_for_action(ActionKind.RESET) == "teardown"
    assert event_kind_for_action(ActionKind.BLOCK) == "block"
    assert event_kind_for_action(ActionKind.ROLLBACK) == "rollback"
    # NOOP / RUN_SCRIPT are not in the table → the safe fallback.
    assert event_kind_for_action(ActionKind.NOOP) == "auto"
    assert event_kind_for_action(ActionKind.RUN_SCRIPT) == "auto"
