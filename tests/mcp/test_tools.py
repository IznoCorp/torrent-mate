"""Tests for the MCP write/read tool bodies (:mod:`kanbanmate.mcp.tools`, conduit Phase 2).

For each write tool we assert the three guards/routes: (1) pinning — ``issue != pinned`` returns the
refusal and performs ZERO writes on the recording fakes; (2) PAUSE — ``kill_switch_active() is True``
refuses; (3) routing — the happy path calls exactly the one identical ``core``/``app``/port function
the bin uses, with the expected arguments. The fakes record every write so "zero writes" is provable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from kanbanmate.adapters.github.types import CommentRef, IssueRef
from kanbanmate.core.domain import Column, ColumnClass
from kanbanmate.core.transitions import Transition, TransitionConfig
from kanbanmate.mcp import tools

PINNED = 42


@dataclass
class _FakeWriter:
    """A BoardWriter recording every comment + serving an empty comment listing (fail-soft sticky)."""

    comments: list[tuple[int, str]] = field(default_factory=list)
    updated_comments: list[tuple[int, str]] = field(default_factory=list)

    def comment(self, issue_number: int, body: str) -> None:
        self.comments.append((issue_number, body))

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        return []

    def update_comment(self, comment_id: int, body: str) -> None:
        self.updated_comments.append((comment_id, body))


@dataclass
class _FakeSeeder:
    """A Seeder recording body patches and serving a fixed IssueRef per number."""

    refs: dict[int, IssueRef] = field(default_factory=dict)
    body_updates: list[tuple[str, str]] = field(default_factory=list)

    def fetch_issue(self, issue_number: int) -> IssueRef:
        return self.refs[issue_number]

    def update_issue_body(self, issue_node_id: str, body: str) -> None:
        self.body_updates.append((issue_node_id, body))


@dataclass
class _FakeStore:
    """A store recording enqueues + done breadcrumbs, with a toggleable kill switch."""

    paused: bool = False
    intents: dict[str, dict[str, object]] = field(default_factory=dict)
    nudges: int = 0
    dones: list[tuple[int, float]] = field(default_factory=list)

    def kill_switch_active(self) -> bool:
        return self.paused

    def enqueue_intent(self, intent_id: str, payload: dict[str, object]) -> None:
        self.intents[intent_id] = dict(payload)

    def nudge_daemon(self) -> None:
        self.nudges += 1

    def record_agent_done(self, issue_number: int, *, now: float) -> None:
        self.dones.append((issue_number, now))


def _columns() -> dict[str, Column]:
    return {
        "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),
        "InProgress": Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),
        "Review": Column(key="Review", name="Review", column_class=ColumnClass.INERT),
    }


def _transitions() -> TransitionConfig:
    # An explicit prompt-bearing launch transition Backlog -> InProgress (the anti-loop case);
    # all other lookups resolve to None.
    launch = Transition(from_col="Backlog", to_col="InProgress", profile="dev", prompt="go")
    return TransitionConfig(
        project="owner/repo",
        concurrency_cap=3,
        _explicit={("Backlog", "InProgress"): launch},
        _wild_to={},
        _wild_from={},
    )


# --------------------------------------------------------------------------- comment


def test_comment_pin_mismatch_writes_nothing() -> None:
    store, writer = _FakeStore(), _FakeWriter()
    out = tools.comment(writer, store, issue=99, pinned=PINNED, body="hi")  # type: ignore[arg-type]
    assert "pinned to #42" in out
    assert writer.comments == []


def test_comment_paused_writes_nothing() -> None:
    store, writer = _FakeStore(paused=True), _FakeWriter()
    out = tools.comment(writer, store, issue=PINNED, pinned=PINNED, body="hi")  # type: ignore[arg-type]
    assert "PAUSE" in out
    assert writer.comments == []


def test_comment_routes_through_board_writer_once() -> None:
    store, writer = _FakeStore(), _FakeWriter()
    tools.comment(writer, store, issue=PINNED, pinned=PINNED, body="hello")  # type: ignore[arg-type]
    assert writer.comments == [(PINNED, "hello")]


# --------------------------------------------------------------------------- progress


def test_progress_freeform_stamps_a_comment() -> None:
    store, writer = _FakeStore(), _FakeWriter()
    tools.progress(writer, store, issue=PINNED, pinned=PINNED, line="ping", now=0.0)  # type: ignore[arg-type]
    assert len(writer.comments) == 1
    assert writer.comments[0][0] == PINNED
    assert "ping" in writer.comments[0][1]


def test_progress_pin_mismatch_writes_nothing() -> None:
    store, writer = _FakeStore(), _FakeWriter()
    out = tools.progress(writer, store, issue=99, pinned=PINNED, line="x")  # type: ignore[arg-type]
    assert "pinned to #42" in out
    assert writer.comments == []


def test_progress_stage_route_upserts_a_sticky() -> None:
    store, writer = _FakeStore(), _FakeWriter()
    out = tools.progress(
        writer,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
        line="step 2",
        stage="InProgress",
        now=5.0,
    )
    # The "[InProgress]" shape is distinctive of the stage route (the free-form fallback says "(note)").
    assert out == "progress on #42 [InProgress]: step 2"
    # Empty listing → upsert_stage_comment CREATES exactly one sticky carrying the appended line.
    assert len(writer.comments) == 1
    assert writer.comments[0][0] == PINNED
    assert "step 2" in writer.comments[0][1]


def test_progress_paused_writes_nothing() -> None:
    store, writer = _FakeStore(paused=True), _FakeWriter()
    out = tools.progress(
        writer,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
        line="x",
        stage="InProgress",
    )
    assert "PAUSE" in out
    assert writer.comments == []


# --------------------------------------------------------------------------- move


def test_move_routes_one_intent_with_key_payload_and_nudge() -> None:
    store = _FakeStore()
    out = tools.move(
        store,  # type: ignore[arg-type]
        _columns(),
        _transitions(),
        issue=PINNED,
        pinned=PINNED,
        to_col="Review",  # by KEY here; "In Progress" name also resolves but Review avoids the anti-loop
        from_col="InProgress",
        now=123.0,
    )
    assert "enqueued move" in out
    assert len(store.intents) == 1
    payload = next(iter(store.intents.values()))
    assert payload == {
        "kind": "move",
        "issue": PINNED,
        "args": {"to_col": "Review"},  # the real column KEY
        "requested_at": 123.0,
        "caller": "agent",
    }
    assert store.nudges == 1


def test_move_resolves_display_name_to_key() -> None:
    store = _FakeStore()
    tools.move(
        store,  # type: ignore[arg-type]
        _columns(),
        _transitions(),
        issue=PINNED,
        pinned=PINNED,
        to_col="Review",
        now=1.0,
    )
    payload = next(iter(store.intents.values()))
    assert payload["args"] == {"to_col": "Review"}


def test_move_anti_loop_refuses_prompt_bearing_pair() -> None:
    store = _FakeStore()
    out = tools.move(
        store,  # type: ignore[arg-type]
        _columns(),
        _transitions(),
        issue=PINNED,
        pinned=PINNED,
        to_col="In Progress",  # by display name → key InProgress; (Backlog, InProgress) is a launch
        from_col="Backlog",
    )
    assert "anti-loop" in out
    assert store.intents == {}
    assert store.nudges == 0


def test_move_pin_mismatch_writes_nothing() -> None:
    store = _FakeStore()
    out = tools.move(
        store,  # type: ignore[arg-type]
        _columns(),
        _transitions(),
        issue=99,
        pinned=PINNED,
        to_col="Review",
    )
    assert "pinned to #42" in out
    assert store.intents == {}
    assert store.nudges == 0


def test_move_paused_writes_nothing() -> None:
    store = _FakeStore(paused=True)
    out = tools.move(
        store,  # type: ignore[arg-type]
        _columns(),
        _transitions(),
        issue=PINNED,
        pinned=PINNED,
        to_col="Review",
    )
    assert "PAUSE" in out
    assert store.intents == {}


def test_move_unknown_column_refuses_with_known_columns_hint() -> None:
    store = _FakeStore()
    out = tools.move(
        store,  # type: ignore[arg-type]
        _columns(),
        _transitions(),
        issue=PINNED,
        pinned=PINNED,
        to_col="Doing",  # neither a key nor a name in _columns() → resolve_target_column raises KeyError
    )
    # The KeyError's actionable "known columns: …" message is surfaced as a friendly refusal, not a repr.
    assert "refusing to move #42" in out
    assert "known columns" in out
    assert store.intents == {}
    assert store.nudges == 0


# --------------------------------------------------------------------------- done


def test_done_records_once_with_now() -> None:
    store = _FakeStore()
    tools.done(store, issue=PINNED, pinned=PINNED, now=55.0)  # type: ignore[arg-type]
    assert store.dones == [(PINNED, 55.0)]


def test_done_pin_mismatch_writes_nothing() -> None:
    store = _FakeStore()
    out = tools.done(store, issue=99, pinned=PINNED, now=55.0)  # type: ignore[arg-type]
    assert "pinned to #42" in out
    assert store.dones == []


def test_done_paused_writes_nothing() -> None:
    store = _FakeStore(paused=True)
    out = tools.done(store, issue=PINNED, pinned=PINNED, now=55.0)  # type: ignore[arg-type]
    assert "PAUSE" in out
    assert store.dones == []


# --------------------------------------------------------------------------- update_body


def _seeder(body: str, title: str) -> _FakeSeeder:
    return _FakeSeeder(
        refs={PINNED: IssueRef(node_id="NODE_42", number=PINNED, title=title, body=body)}
    )


def test_update_body_set_field_coherent_writes_once() -> None:
    store = _FakeStore()
    seeder = _seeder(body="**roadmap**: mcp\n\ndesc", title="[mcp] A board ticket")
    out = tools.update_body(
        seeder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
        set_field_kv=("design", "docs/x.md"),
    )
    assert "updated body" in out
    assert len(seeder.body_updates) == 1
    node_id, new_body = seeder.body_updates[0]
    assert node_id == "NODE_42"
    assert "**design**: docs/x.md" in new_body


def test_update_body_roadmap_title_mismatch_refuses() -> None:
    store = _FakeStore()
    # body roadmap code "other" vs title bracket "mcp" → validate_roadmap_matches_title refuses.
    seeder = _seeder(body="**roadmap**: other", title="[mcp] A ticket")
    out = tools.update_body(
        seeder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
        set_field_kv=("design", "docs/x.md"),
    )
    assert "refusing to edit" in out
    assert seeder.body_updates == []


def test_update_body_append_section_coherent_writes_once() -> None:
    store = _FakeStore()
    seeder = _seeder(body="**roadmap**: mcp", title="[mcp] A ticket")
    out = tools.update_body(
        seeder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
        append_section_ht=("## Brainstorm", "notes"),
    )
    assert "updated body" in out
    assert len(seeder.body_updates) == 1
    assert "## Brainstorm" in seeder.body_updates[0][1]


def test_update_body_pin_mismatch_writes_nothing() -> None:
    store = _FakeStore()
    seeder = _seeder(body="**roadmap**: mcp", title="[mcp] A ticket")
    out = tools.update_body(
        seeder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=99,
        pinned=PINNED,
        set_field_kv=("design", "x"),
    )
    assert "pinned to #42" in out
    assert seeder.body_updates == []


def test_update_body_paused_writes_nothing() -> None:
    store = _FakeStore(paused=True)
    seeder = _seeder(body="**roadmap**: mcp", title="[mcp] A ticket")
    out = tools.update_body(
        seeder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
        set_field_kv=("design", "x"),
    )
    assert "PAUSE" in out
    assert seeder.body_updates == []


def test_update_body_no_mode_refuses() -> None:
    store = _FakeStore()
    seeder = _seeder(body="**roadmap**: mcp", title="[mcp] A ticket")
    out = tools.update_body(
        seeder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
    )
    assert "exactly one" in out
    assert seeder.body_updates == []


def test_update_body_both_modes_refuses() -> None:
    store = _FakeStore()
    seeder = _seeder(body="**roadmap**: mcp", title="[mcp] A ticket")
    out = tools.update_body(
        seeder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        issue=PINNED,
        pinned=PINNED,
        set_field_kv=("design", "x"),
        append_section_ht=("## H", "t"),
    )
    assert "exactly one" in out
    assert seeder.body_updates == []


# --------------------------------------------------------------------------- update_main


def test_update_main_routes_fetch_then_ff_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "kanbanmate.adapters.workspace.base_sync.fetch_base",
        lambda clone: calls.append(("fetch", str(clone))),
    )
    monkeypatch.setattr(
        "kanbanmate.adapters.workspace.base_sync.ff_dev_clone",
        lambda repo: calls.append(("ff", str(repo))),
    )
    store = _FakeStore()
    out = tools.update_main(store, base_clone="/base", dev_repo="/dev")  # type: ignore[arg-type]
    assert "refreshed main" in out
    # fetch_base BEFORE ff_dev_clone, each with the caller-supplied clone path.
    assert calls == [("fetch", "/base"), ("ff", "/dev")]


def test_update_main_paused_runs_no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "kanbanmate.adapters.workspace.base_sync.fetch_base",
        lambda clone: calls.append("fetch"),
    )
    monkeypatch.setattr(
        "kanbanmate.adapters.workspace.base_sync.ff_dev_clone",
        lambda repo: calls.append("ff"),
    )
    store = _FakeStore(paused=True)
    out = tools.update_main(store, base_clone="/base", dev_repo="/dev")  # type: ignore[arg-type]
    assert "PAUSE" in out
    assert calls == []  # PAUSE refuses BEFORE any git I/O
