"""Tests for the operator pill-override CLI (:mod:`kanbanmate.cli.pill`, cockpit PR3.3).

Drives set_health/note/clear against an in-memory store fake: each enqueues the right ``pill_*``
intent; ``--wait`` blocks on the daemon's result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kanbanmate.cli.pill import clear, note, set_health


@dataclass
class _FakeStore:
    intents: dict[str, dict[str, object]] = field(default_factory=dict)
    results: dict[str, dict[str, object]] = field(default_factory=dict)

    def enqueue_intent(self, intent_id: str, payload: dict[str, object]) -> None:
        self.intents[intent_id] = dict(payload)

    def load_intent_result(self, intent_id: str) -> dict[str, object] | None:
        return self.results.get(intent_id)


def test_set_health_enqueues_pill_set_health() -> None:
    store = _FakeStore()
    msg = set_health(store, enum="WAITING", note="x", now=100.0)  # type: ignore[arg-type]
    assert "enqueued WAITING" in msg
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "pill_set_health"
    assert payload["args"] == {"enum": "WAITING", "note": "x"}
    assert payload["issue"] is None


def test_note_enqueues_pill_note() -> None:
    store = _FakeStore()
    note(store, text="hello", now=100.0)  # type: ignore[arg-type]
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "pill_note"
    assert payload["args"] == {"text": "hello"}


def test_clear_enqueues_pill_clear() -> None:
    store = _FakeStore()
    clear(store, now=100.0)  # type: ignore[arg-type]
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "pill_clear"


def test_set_health_wait_applied() -> None:
    store = _FakeStore()

    def _sleep(_s: float) -> None:
        intent_id = next(iter(store.intents))
        store.results[intent_id] = {"state": "done", "detail": "pill forced to WAITING"}

    msg = set_health(
        store,  # type: ignore[arg-type]
        enum="WAITING",
        wait=True,
        now=100.0,
        sleep=_sleep,
        clock=iter([100.0, 100.0, 100.5]).__next__,
    )
    assert "applied" in msg
