"""Tests for the SSE board change-signal stream (keel STEP 4).

Two levels:

* **Unit** — the pure-ish ``monitor_event_stream`` generator + the cheap local readers
  (``read_board_version`` / ``read_daemon_tick``), driven with plain callables + a fake async sleep
  so the bounded loop is exercised deterministically and we can prove: it emits on a version bump,
  it never busy-spins (it sleeps every iteration), and it makes NO GitHub call (the readers are local
  file reads only).
* **HTTP** — the ``/api/monitor/stream`` route requires auth (401 without a session when login is
  enabled) and emits a ``change`` SSE frame carrying the board ``version`` from the LOCAL store.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402

from kanbanmate.http.auth import AuthConfig, make_token  # noqa: E402
from kanbanmate.http.auth import COOKIE_NAME  # noqa: E402
from kanbanmate.http.monitor_stream import (  # noqa: E402
    monitor_event_stream,
    read_board_version,
    read_daemon_tick,
)


# --- unit: the cheap local readers ------------------------------------------------------


def test_read_board_version_parses_version(tmp_path: Path) -> None:
    p = tmp_path / "board.json"
    p.write_text(json.dumps({"version": 7, "columns": [], "order": {}}), encoding="utf-8")
    assert read_board_version(p) == 7


def test_read_board_version_none_when_absent_or_malformed(tmp_path: Path) -> None:
    assert read_board_version(tmp_path / "nope.json") is None  # absent
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert read_board_version(bad) is None  # malformed → None, never raises
    # ``true`` must NOT be read as version 1 (bool is an int subclass).
    boolish = tmp_path / "boolish.json"
    boolish.write_text(json.dumps({"version": True}), encoding="utf-8")
    assert read_board_version(boolish) is None


def test_read_daemon_tick_json_and_legacy(tmp_path: Path) -> None:
    j = tmp_path / "daemon.heartbeat"
    j.write_text(json.dumps({"ts": 1234.5, "last_tick_ok": True}), encoding="utf-8")
    assert read_daemon_tick(j) == 1234.5
    # legacy bare-epoch marker
    legacy = tmp_path / "legacy.heartbeat"
    legacy.write_text("1700000000.0", encoding="utf-8")
    assert read_daemon_tick(legacy) == 1700000000.0
    # absent / garbage → None (degrade, never raise)
    assert read_daemon_tick(tmp_path / "missing") is None
    garbage = tmp_path / "g.heartbeat"
    garbage.write_text("not-a-number", encoding="utf-8")
    assert read_daemon_tick(garbage) is None


# --- unit: the bounded SSE generator ----------------------------------------------------


async def _collect(stream: Any) -> list[str]:
    return [frame async for frame in stream]


def _parse_change(frame: str) -> dict[str, Any]:
    """Extract the JSON ``data:`` payload from a ``change`` SSE frame."""
    line = next(ln for ln in frame.splitlines() if ln.startswith("data:"))
    payload: dict[str, Any] = json.loads(line[len("data:") :].strip())
    return payload


def test_stream_emits_initial_then_on_version_bump() -> None:
    """First frame is always a ``change`` (baseline); a later version bump emits another ``change``."""
    versions = iter([5, 5, 6])  # unchanged across the first two reads, then a bump
    sleeps: list[float] = []

    async def fake_sleep(d: float) -> None:
        sleeps.append(d)

    stream = monitor_event_stream(
        lambda: next(versions),
        lambda: None,  # tick never changes
        poll_interval=0.01,
        keepalive_interval=1000.0,  # high → no keep-alive interferes
        max_iterations=3,
        sleep=fake_sleep,
    )
    frames = asyncio.run(_collect(stream))
    changes = [f for f in frames if f.startswith("event: change")]
    # Iteration 1 (baseline v=5) → change; iteration 2 (v=5, unchanged) → no change; iteration 3
    # (v=6) → change. So exactly TWO change frames.
    assert len(changes) == 2
    assert _parse_change(changes[0])["version"] == 5
    assert _parse_change(changes[1])["version"] == 6
    # BOUNDED CPU: it slept once per iteration (never a busy-loop).
    assert sleeps == [0.01, 0.01, 0.01]


def test_stream_emits_keepalive_when_idle() -> None:
    """An unchanging board yields keep-alive COMMENT frames, not change events, after the baseline."""
    sleeps: list[float] = []

    async def fake_sleep(d: float) -> None:
        sleeps.append(d)

    stream = monitor_event_stream(
        lambda: 9,  # constant version
        lambda: None,
        poll_interval=1.0,
        keepalive_interval=2.0,  # 2 idle poll_intervals → a keep-alive
        max_iterations=4,
        sleep=fake_sleep,
    )
    frames = asyncio.run(_collect(stream))
    # frame0: baseline change; then silence accrues — a keep-alive comment fires once 2 s elapsed.
    assert frames[0].startswith("event: change")
    assert any(f.startswith(": ") for f in frames[1:]), "expected a keep-alive comment frame"
    assert all(d == 1.0 for d in sleeps)  # bounded sleep every iteration


def test_stream_makes_no_github_call() -> None:
    """The stream path reads ONLY the injected local callables — no network / GitHub import is hit.

    Proven by construction: the generator calls its two readers and nothing else. We assert the
    readers are the ONLY callables invoked by recording every call.
    """
    calls: list[str] = []

    def version_reader() -> int | None:
        calls.append("version")
        return 1

    def tick_reader() -> float | None:
        calls.append("tick")
        return None

    async def fake_sleep(_: float) -> None:
        return None

    stream = monitor_event_stream(
        version_reader, tick_reader, poll_interval=0.0, max_iterations=2, sleep=fake_sleep
    )
    asyncio.run(_collect(stream))
    # Only the local readers were called (version + tick per iteration); nothing else.
    assert set(calls) == {"version", "tick"}
    assert calls.count("version") == 2 and calls.count("tick") == 2


# --- HTTP: auth + emits the local version -----------------------------------------------


def _native_root_with_clone(tmp_path: Path) -> Path:
    """A registry with a native-backed project + a clone holding columns.yml/transitions.yml."""
    import importlib.resources as r

    from kanbanmate.core.transitions_defaults import render_transitions_yaml

    root = tmp_path / "root"
    root.mkdir()
    ck = tmp_path / "clone" / ".claude" / "kanban"
    ck.mkdir(parents=True)
    ck.joinpath("transitions.yml").write_text(render_transitions_yaml("Org/repo"), encoding="utf-8")
    cols = (r.files("kanbanmate") / "assets" / "columns.yml.tmpl").read_text()
    ck.joinpath("columns.yml").write_text(cols, encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_x": {
                    "repo": "Org/repo",
                    "clone": str(tmp_path / "clone"),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                    "board_backend": "native",
                }
            }
        ),
        encoding="utf-8",
    )
    return root


def test_stream_requires_auth(tmp_path: Path) -> None:
    """With login enabled, the stream is 401 without a session — it does NOT bypass the auth guard."""
    import kanbanmate.http.config_api as api_mod

    api_mod.app.state.kanban_root = _native_root_with_clone(tmp_path)
    api_mod.app.state.auth = AuthConfig(login="admin", password="hunter2", secret="testsecret")
    try:
        with TestClient(api_mod.app) as client:
            resp = client.get("/api/monitor/stream")
        assert resp.status_code == 401  # the middleware blocks the unauthenticated stream
    finally:
        api_mod.app.state.auth = None


def test_stream_emits_local_version_frame(tmp_path: Path) -> None:
    """An authenticated stream emits a ``change`` SSE frame carrying the LOCAL board.json version."""
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board

    # A real local board store at version 3 (NO GitHub anywhere in this path).
    store = FsBoardStateStore(tmp_path / "store")
    seed_board(store, ["Backlog"], {"i1": "Backlog"}, {"Backlog": ["i1"]}, version=3)

    api_mod.app.state.kanban_root = _native_root_with_clone(tmp_path)
    api_mod.app.state.auth = AuthConfig(login="admin", password="hunter2", secret="testsecret")
    api_mod.app.state.board_store = store
    # BOUND the loop to a single iteration so the streamed body TERMINATES (the production stream
    # runs until the client disconnects); a tiny poll keeps it instant.
    api_mod.app.state.monitor_stream_poll_interval = 0.0
    api_mod.app.state.monitor_stream_max_iterations = 1
    token = make_token("admin", "testsecret", ttl=100)
    try:
        with TestClient(api_mod.app) as client:
            resp = client.get("/api/monitor/stream", cookies={COOKIE_NAME: token})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        # The single (baseline) frame carries the LOCAL store version — no GitHub call.
        data_line = next(ln for ln in resp.text.splitlines() if ln.startswith("data:"))
        payload = json.loads(data_line[len("data:") :].strip())
        assert payload["version"] == 3
    finally:
        api_mod.app.state.auth = None
        for k in ("board_store", "monitor_stream_poll_interval", "monitor_stream_max_iterations"):
            if hasattr(api_mod.app.state, k):
                delattr(api_mod.app.state, k)
