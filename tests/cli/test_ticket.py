"""Tests for the operator ticket-CRUD CLI (:mod:`kanbanmate.cli.ticket`, cockpit PR3).

Drives ``create`` against an in-memory store fake: enqueue-without-wait records a ticket_create
intent + returns a hint; ``--wait`` blocks on the daemon's result (created/rejected). ``sleep``/
``clock`` are injected so no real time passes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kanbanmate.cli.ticket import close, create, edit


@dataclass
class _FakeStore:
    intents: dict[str, dict[str, object]] = field(default_factory=dict)
    results: dict[str, dict[str, object]] = field(default_factory=dict)

    def enqueue_intent(self, intent_id: str, payload: dict[str, object]) -> None:
        self.intents[intent_id] = dict(payload)

    def load_intent_result(self, intent_id: str) -> dict[str, object] | None:
        return self.results.get(intent_id)


def test_enqueue_without_wait_records_ticket_create() -> None:
    store = _FakeStore()
    msg = create(store, title="New feature", body="b", labels=["x"], column="Backlog", now=100.0)  # type: ignore[arg-type]
    assert "enqueued 'New feature'" in msg
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "ticket_create"
    assert payload["issue"] is None
    assert payload["args"] == {
        "title": "New feature",
        "body": "b",
        "labels": ["x"],
        "column": "Backlog",
    }
    assert payload["caller"] == "operator"


def test_create_omits_column_when_absent() -> None:
    store = _FakeStore()
    create(store, title="N", now=100.0)  # type: ignore[arg-type]
    payload = next(iter(store.intents.values()))
    assert "column" not in payload["args"]  # type: ignore[operator]


def test_wait_returns_created_result() -> None:
    store = _FakeStore()

    def _sleep(_seconds: float) -> None:
        intent_id = next(iter(store.intents))
        store.results[intent_id] = {"state": "done", "detail": "created #201"}

    msg = create(
        store,  # type: ignore[arg-type]
        title="N",
        wait=True,
        now=100.0,
        sleep=_sleep,
        clock=iter([100.0, 100.0, 100.5]).__next__,
    )
    assert "created" in msg
    assert "#201" in msg


def test_wait_returns_rejected_result() -> None:
    store = _FakeStore()

    def _sleep(_seconds: float) -> None:
        intent_id = next(iter(store.intents))
        store.results[intent_id] = {"state": "rejected", "detail": "requires a non-empty title"}

    msg = create(
        store,  # type: ignore[arg-type]
        title="",
        wait=True,
        now=100.0,
        timeout=5.0,
        sleep=_sleep,
        clock=iter([100.0, 100.0, 101.0]).__next__,
    )
    assert "REJECTED" in msg


# ── edit / close (cockpit PR3.2) ───────────────────────────────────────────


def test_edit_enqueues_ticket_edit() -> None:
    store = _FakeStore()
    msg = edit(store, issue=8, body="new body", now=100.0)  # type: ignore[arg-type]
    assert "enqueued #8" in msg
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "ticket_edit"
    assert payload["issue"] == 8
    assert payload["args"] == {"body": "new body"}


def test_close_enqueues_ticket_close() -> None:
    store = _FakeStore()
    msg = close(store, issue=8, now=100.0)  # type: ignore[arg-type]
    assert "enqueued #8" in msg
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "ticket_close"
    assert payload["issue"] == 8


def test_edit_wait_returns_edited() -> None:
    store = _FakeStore()

    def _sleep(_s: float) -> None:
        intent_id = next(iter(store.intents))
        store.results[intent_id] = {"state": "done", "detail": "edited #8 body"}

    msg = edit(
        store,  # type: ignore[arg-type]
        issue=8,
        body="x",
        wait=True,
        now=100.0,
        sleep=_sleep,
        clock=iter([100.0, 100.0, 100.5]).__next__,
    )
    assert "edited" in msg
