"""In-process MCP client roundtrip over the stdio ``Server`` (conduit Phase 3, DESIGN §12).

This wires :func:`kanbanmate.mcp.server.build_server` with the SAME in-memory fakes Phase 2 uses
(``tests/mcp/test_tools.py`` / ``test_resources.py``) and drives it through the SDK's documented
in-memory transport (:func:`mcp.shared.memory.create_connected_server_and_client_session`, which
runs ``server.run`` over a paired memory stream and yields a real :class:`mcp.ClientSession`). So the
list/read/call paths are exercised end-to-end through the real protocol — never by calling the
handlers directly. We assert: the six ``kanban://`` URIs are listed; the read + write tool names are
present AND there is NO ``merge`` tool; ``kanban://board`` carries the documented top-level keys; a
read tool returns the same shape; and a pinned WRITE tool called with a FOREIGN issue refuses
end-to-end with ZERO writes on the fakes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from mcp.server import Server

from kanbanmate.adapters.github.types import IssueContext
from kanbanmate.core.domain import BoardSnapshot, Column, ColumnClass, Ticket
from kanbanmate.core.transitions import Transition, TransitionConfig
from kanbanmate.mcp import server as mcp_server
from kanbanmate.ports.store import TicketState, TicketStatus

PINNED = 42


@pytest.fixture
def anyio_backend() -> str:
    """Pin the anyio pytest plugin to the asyncio backend (the SDK ships only an asyncio runtime)."""
    return "asyncio"


@dataclass
class _FakeBoardReader:
    """A board reader whose ``snapshot`` / ``issue_context`` return fixed values."""

    snapshot_obj: BoardSnapshot
    contexts: dict[int, IssueContext] = field(default_factory=dict)

    def snapshot(self) -> BoardSnapshot:
        return self.snapshot_obj

    def issue_context(self, number: int) -> IssueContext:
        return self.contexts[number]


@dataclass
class _FakeWriter:
    """A BoardWriter recording every comment (so 'zero writes' is provable end-to-end)."""

    comments: list[tuple[int, str]] = field(default_factory=list)

    def comment(self, issue_number: int, body: str) -> None:
        self.comments.append((issue_number, body))

    def list_issue_comments(self, issue_number: int) -> list[object]:
        return []

    def update_comment(self, comment_id: int, body: str) -> None:  # pragma: no cover - unused
        raise AssertionError("update_comment must not be called in this roundtrip")


@dataclass
class _FakeSeeder:
    """A Seeder recording body patches (unused in this roundtrip but required by build_server)."""

    body_updates: list[tuple[str, str]] = field(default_factory=list)

    def fetch_issue(self, issue_number: int) -> object:  # pragma: no cover - unused here
        raise AssertionError("fetch_issue must not be called in this roundtrip")

    def update_issue_body(self, issue_node_id: str, body: str) -> None:  # pragma: no cover
        self.body_updates.append((issue_node_id, body))


@dataclass
class _FakeStore:
    """An in-memory store implementing the read methods + the write breadcrumbs the tools touch."""

    running: list[TicketState] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    last_status: str | None = "WAITING"
    queued_ids: tuple[int, ...] = ()
    queued_payloads: dict[int, dict[str, object]] = field(default_factory=dict)
    paused: bool = False
    intents: dict[str, dict[str, object]] = field(default_factory=dict)
    nudges: int = 0
    dones: list[tuple[int, float]] = field(default_factory=list)

    def list_running(self) -> list[TicketState]:
        return list(self.running)

    def read_status_events(self) -> tuple[dict[str, object], ...]:
        return tuple(self.events)

    def get_status_last_enum(self) -> str | None:
        return self.last_status

    def dequeue_pending(self) -> tuple[int, ...]:
        return self.queued_ids

    def load_queued(self, issue_number: int) -> dict[str, object] | None:
        return self.queued_payloads.get(issue_number)

    def kill_switch_active(self) -> bool:
        return self.paused

    def enqueue_intent(self, intent_id: str, payload: dict[str, object]) -> None:
        self.intents[intent_id] = dict(payload)

    def nudge_daemon(self) -> None:
        self.nudges += 1

    def record_agent_done(self, issue_number: int, *, now: float) -> None:
        self.dones.append((issue_number, now))


def _ticket(n: int, col: str) -> Ticket:
    return Ticket(item_id=f"PVTI_{n}", issue_number=n, title=f"t{n}", column_key=col)


def _running(n: int) -> TicketState:
    return TicketState(
        issue_number=n,
        item_id=f"PVTI_{n}",
        session_id="sess",
        status=TicketStatus.RUNNING,
        heartbeat=990.0,
        stage="InProgress",
        profile="dev",
        mode="auto",
        started=900.0,
        worktree="/tmp/wt",
        retries=0,
    )


def _columns() -> dict[str, Column]:
    return {
        "Backlog": Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT),
        "InProgress": Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT),
        "Review": Column(key="Review", name="Review", column_class=ColumnClass.INERT),
    }


def _transitions() -> TransitionConfig:
    launch = Transition(from_col="Backlog", to_col="InProgress", profile="dev", prompt="go")
    return TransitionConfig(
        project="owner/repo",
        concurrency_cap=3,
        _explicit={("Backlog", "InProgress"): launch},
        _wild_to={},
        _wild_from={},
    )


def _build_server(
    writer: _FakeWriter, store: _FakeStore, tmp_path: Path
) -> "Server[object, object]":
    """Build the server under test with the Phase-2 fakes, pinned to ``PINNED``."""
    reader = _FakeBoardReader(
        BoardSnapshot(tickets=(_ticket(PINNED, "InProgress"),), fetched_at=0.0),
        contexts={
            PINNED: IssueContext(
                body="the spec body",
                comments=("first", "second"),
                linked_issue_body="the design",
            )
        },
    )
    return mcp_server.build_server(
        reader,  # type: ignore[arg-type]
        writer,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        _FakeSeeder(),  # type: ignore[arg-type]
        pinned_issue=PINNED,
        columns=_columns(),
        transitions=_transitions(),
        root=tmp_path,
    )


@pytest.mark.anyio
async def test_list_resources_exposes_six_kanban_uris(tmp_path: Path) -> None:
    """list_resources → the 6 ``kanban://`` URIs present (ticket pinned to the agent's issue)."""
    from mcp.shared.memory import create_connected_server_and_client_session

    server = _build_server(_FakeWriter(), _FakeStore(running=[_running(PINNED)]), tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_resources()
        uris = {str(r.uri) for r in result.resources}
    assert uris == {
        "kanban://board",
        f"kanban://ticket/{PINNED}",
        "kanban://agents",
        "kanban://queue",
        "kanban://health",
        "kanban://events",
    }


@pytest.mark.anyio
async def test_list_tools_has_read_and_write_no_merge(tmp_path: Path) -> None:
    """list_tools → read+write tool names present, and NO ``merge`` tool (DESIGN §6)."""
    from mcp.shared.memory import create_connected_server_and_client_session

    server = _build_server(_FakeWriter(), _FakeStore(), tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
    assert {"get_board", "get_state", "get_ticket"} <= names  # read tools
    assert {"comment", "progress", "move", "done", "update_body", "update_main"} <= names  # writes
    assert "merge" not in names


@pytest.mark.anyio
async def test_read_board_resource_has_documented_keys(tmp_path: Path) -> None:
    """read_resource ``kanban://board`` → the documented top-level keys (health/board/agents/...)."""
    from mcp.shared.memory import create_connected_server_and_client_session
    from pydantic import AnyUrl

    store = _FakeStore(running=[_running(PINNED)], last_status="WAITING")
    server = _build_server(_FakeWriter(), store, tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.read_resource(AnyUrl("kanban://board"))
        assert result.contents and result.contents[0].mimeType == "application/json"
        payload = json.loads(result.contents[0].text)  # type: ignore[union-attr]
    for key in ("health", "paused", "board", "agents", "queue", "events", "daemon"):
        assert key in payload
    assert payload["health"] == "WAITING"


@pytest.mark.anyio
async def test_call_read_tool_returns_board_shape(tmp_path: Path) -> None:
    """call_tool ``get_state`` → the same unified board shape as the resource."""
    from mcp.shared.memory import create_connected_server_and_client_session

    store = _FakeStore(running=[_running(PINNED)], last_status="WAITING")
    server = _build_server(_FakeWriter(), store, tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_state", {})
        assert not result.isError
        payload = json.loads(result.content[0].text)  # type: ignore[union-attr]
    for key in ("health", "paused", "board", "agents", "queue", "events", "daemon"):
        assert key in payload


@pytest.mark.anyio
async def test_pinned_write_with_foreign_issue_refuses_zero_writes(tmp_path: Path) -> None:
    """A pinned WRITE tool called with a foreign issue refuses end-to-end with ZERO writes."""
    from mcp.shared.memory import create_connected_server_and_client_session

    writer = _FakeWriter()
    store = _FakeStore()
    server = _build_server(writer, store, tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("comment", {"issue": 99, "body": "hi"})
        assert not result.isError  # a refusal is a normal (non-error) tool result string
        text = result.content[0].text  # type: ignore[union-attr]
    assert f"pinned to #{PINNED}" in text
    assert writer.comments == []  # ZERO writes reached the board through the whole SDK roundtrip
    assert store.intents == {}


@pytest.mark.anyio
async def test_get_ticket_with_foreign_issue_refuses(tmp_path: Path) -> None:
    """FIX 3: the ``get_ticket`` READ tool is pinned too — a foreign issue refuses (DESIGN §7)."""
    from mcp.shared.memory import create_connected_server_and_client_session

    server = _build_server(_FakeWriter(), _FakeStore(), tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_ticket", {"issue": 99})
        assert not result.isError  # a refusal is a normal (non-error) string result
        text = result.content[0].text  # type: ignore[union-attr]
    assert "refusing to read #99" in text
    assert f"pinned to #{PINNED}" in text


@pytest.mark.anyio
async def test_read_ticket_resource_with_foreign_issue_refuses(tmp_path: Path) -> None:
    """FIX 3: reading ``kanban://ticket/<n>`` for a foreign issue is refused (reads are pinned too)."""
    from mcp.shared.memory import create_connected_server_and_client_session
    from pydantic import AnyUrl

    server = _build_server(_FakeWriter(), _FakeStore(), tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        with pytest.raises(Exception, match="refusing to read #99"):
            await client.read_resource(AnyUrl("kanban://ticket/99"))


@pytest.mark.anyio
async def test_update_main_listed_with_no_client_args(tmp_path: Path) -> None:
    """list_tools → ``update_main`` advertises NO client inputs (empty schema, no required, §6/§7).

    An agent must never supply git-repo paths to a write tool: the clone pair is server-resolved, so
    the advertised inputSchema carries no ``base_clone``/``dev_repo`` properties and no ``required``.
    """
    from mcp.shared.memory import create_connected_server_and_client_session

    server = _build_server(_FakeWriter(), _FakeStore(), tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()
        update_main = next(t for t in result.tools if t.name == "update_main")
    schema = update_main.inputSchema
    assert schema.get("properties", {}) == {}  # no client-supplied paths
    assert not schema.get("required")  # nothing required
    assert "base_clone" not in schema.get("properties", {})
    assert "dev_repo" not in schema.get("properties", {})


def test_dispatch_update_main_resolves_clones_server_side(tmp_path: Path) -> None:
    """``_dispatch_tool`` runs ``update_main`` from the SERVER-RESOLVED clone pair, ignoring args.

    Proves Finding 1's fix at the dispatch seam: the build passes a registry-resolved
    ``clone_paths``; the dispatcher feeds THAT pair (never any client ``arguments``) into the git
    sync. We monkeypatch the workspace adapter so no real git runs and assert the exact resolved
    paths reach ``fetch_base`` / ``ff_dev_clone`` in order.
    """
    import pytest as _pytest  # local alias; this is a sync test (no anyio needed)

    calls: list[tuple[str, str]] = []
    mp = _pytest.MonkeyPatch()
    mp.setattr(
        "kanbanmate.adapters.workspace.base_sync.fetch_base",
        lambda clone: calls.append(("fetch", str(clone))),
    )
    mp.setattr(
        "kanbanmate.adapters.workspace.base_sync.ff_dev_clone",
        lambda repo: calls.append(("ff", str(repo))),
    )
    try:
        store = _FakeStore()
        # The client passes a HOSTILE path; the dispatcher MUST ignore it and use clone_paths.
        out = mcp_server._dispatch_tool(
            "update_main",
            {"base_clone": "/evil", "dev_repo": "/evil"},
            board_reader=_FakeBoardReader(BoardSnapshot(tickets=(), fetched_at=0.0)),  # type: ignore[arg-type]
            board_writer=_FakeWriter(),  # type: ignore[arg-type]
            store=store,  # type: ignore[arg-type]
            seeder=_FakeSeeder(),  # type: ignore[arg-type]
            pinned_issue=PINNED,
            columns=_columns(),
            transitions=_transitions(),
            root=tmp_path,
            clone_paths=("/registry/base", "/registry/dev"),
        )
    finally:
        mp.undo()
    assert "refreshed main" in str(out)
    # The SERVER-RESOLVED pair (never the hostile client args) reached the git sync, in order.
    assert calls == [("fetch", "/registry/base"), ("ff", "/registry/dev")]


def test_dispatch_update_main_refuses_when_no_clone_paths(tmp_path: Path) -> None:
    """With no server-resolved clone pair, ``update_main`` refuses (no git I/O) — fail-soft default."""
    out = mcp_server._dispatch_tool(
        "update_main",
        {},
        board_reader=_FakeBoardReader(BoardSnapshot(tickets=(), fetched_at=0.0)),  # type: ignore[arg-type]
        board_writer=_FakeWriter(),  # type: ignore[arg-type]
        store=_FakeStore(),  # type: ignore[arg-type]
        seeder=_FakeSeeder(),  # type: ignore[arg-type]
        pinned_issue=PINNED,
        columns=_columns(),
        transitions=_transitions(),
        root=tmp_path,
        clone_paths=None,
    )
    assert "no clone paths" in str(out)


@pytest.mark.anyio
async def test_pinned_move_write_routes_intent_through_sdk(tmp_path: Path) -> None:
    """A pinned ``move`` HAPPY path travels end-to-end through the SDK: ``_dispatch_tool`` marshals the
    client args into an enqueued intent carrying the column KEY + nudges the daemon. The refusal test
    above never reaches this marshaling, so this closes the happy-path arg-threading gap."""
    from mcp.shared.memory import create_connected_server_and_client_session

    writer = _FakeWriter()
    store = _FakeStore()
    server = _build_server(writer, store, tmp_path)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("move", {"issue": PINNED, "to_col": "Review"})
        assert not result.isError
        text = result.content[0].text  # type: ignore[union-attr]
    assert "enqueued move" in text
    assert len(store.intents) == 1
    payload = next(iter(store.intents.values()))
    assert payload["kind"] == "move"
    assert payload["issue"] == PINNED
    assert payload["args"] == {"to_col": "Review"}  # the column KEY, marshaled through the SDK
    assert store.nudges == 1
