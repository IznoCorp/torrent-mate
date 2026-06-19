"""The stdio MCP board server — the ONLY module importing the ``mcp`` SDK (conduit DESIGN §4/§4.1).

This is the top entrypoint for ``kanban mcp``: it wires the real board deps, registers four
low-level :class:`mcp.server.Server` handlers — each a THIN dispatcher into the Phase-2 pure
serializers (:mod:`kanbanmate.mcp.resources`) and tool bodies (:mod:`kanbanmate.mcp.tools`) — and
runs them over stdio. Every write tool is pinned to ``--issue`` (the agent's own ticket) and
PAUSE-guarded inside :mod:`kanbanmate.mcp.tools`; there is NO ``merge`` tool (merge stays human /
merge-agent only, DESIGN §6).

Design choices grounded against the installed ``mcp`` 1.28.0 SDK:

* the LOW-LEVEL ``Server`` (not FastMCP) so the serializers/tool bodies stay SDK-free
  (``mcp/server/lowlevel/server.py``);
* ``read_resource`` returns ``Iterable[ReadResourceContents]`` (a bare ``str``/``bytes`` return is
  deprecated, ``mcp/server/lowlevel/server.py`` ``read_resource``); each resource is one JSON
  ``ReadResourceContents`` with ``application/json`` mime;
* ``call_tool`` returns ``list[TextContent]`` (the ``UnstructuredContent`` branch) — a JSON text
  block on success, a plain refusal string on a guard trip;
* ``main`` is side-effect-free at import time — all wiring + the blocking stdio run happen inside it
  (mirrors :func:`kanbanmate.http.serve.main`).

Layering: ``mcp`` is a top entrypoint — it may import ``app`` / ``adapters`` / ``core`` / ``ports`` /
``cli`` (the ``http`` permitted set) but NOT ``daemon`` / ``bin`` (``tests/test_layering.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl

from kanbanmate.core.domain import Column
from kanbanmate.core.transitions import TransitionConfig
from kanbanmate.mcp import resources, tools
from kanbanmate.ports.board import BoardReader, BoardWriter, Seeder
from kanbanmate.ports.store import StateStore

# The six ``kanban://`` resource URIs (DESIGN §5). ``ticket`` is exposed concretely pinned to the
# agent's own issue (a static URI per server instance) rather than a parametrised template — the
# server is single-ticket-scoped by construction, so listing the one ticket it may read is clearer
# than advertising a template the pin would then reject for any other number.
_RESOURCE_BOARD = "kanban://board"
_RESOURCE_AGENTS = "kanban://agents"
_RESOURCE_QUEUE = "kanban://queue"
_RESOURCE_HEALTH = "kanban://health"
_RESOURCE_EVENTS = "kanban://events"
_RESOURCE_TICKET_PREFIX = "kanban://ticket/"


def _json_block(payload: object) -> ReadResourceContents:
    """Wrap a JSON-serialisable payload as one ``application/json`` resource-content block.

    Args:
        payload: The serialised resource value (``dict`` / ``list`` / ``str`` / ``None``).

    Returns:
        A single :class:`ReadResourceContents` carrying the compact JSON text.
    """
    return ReadResourceContents(content=json.dumps(payload), mime_type="application/json")


def _text(payload: object) -> list[types.TextContent]:
    """Wrap a tool result as the SDK's unstructured ``list[TextContent]`` content.

    A ``str`` (a tool confirmation or refusal) is surfaced verbatim; any other (JSON-serialisable)
    value is rendered as compact JSON so the read tools and the resources share one shape.

    Args:
        payload: The tool return value (a refusal/confirmation ``str`` or a JSON-serialisable value).

    Returns:
        A one-element list with the text content block the SDK returns to the client.
    """
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return [types.TextContent(type="text", text=text)]


def _tool_definitions() -> list[types.Tool]:
    """Return the MCP tool catalogue: the read tools + the pinned write tools (NO ``merge``).

    The input schemas mirror the Phase-2 ``tools.*`` signatures (the pinned ``issue`` and the
    server-threaded ``pinned``/``columns``/``transitions``/``root`` are NOT client inputs — the
    server supplies them). There is deliberately no ``merge`` tool (DESIGN §6, locked decision 6).

    Returns:
        The list of :class:`mcp.types.Tool` definitions advertised by ``list_tools``.
    """
    no_args: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}

    def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": False,
        }

    return [
        # --- read tools (mirror the resources; some clients invoke tools more reliably) ---
        types.Tool(
            name="get_board", description="The unified board read model.", inputSchema=no_args
        ),
        types.Tool(name="get_state", description="Alias of get_board.", inputSchema=no_args),
        types.Tool(
            name="get_ticket",
            description="One ticket's rich context (must be the pinned issue).",
            inputSchema=_obj({"issue": {"type": "integer"}}, ["issue"]),
        ),
        # --- write tools (pinned to --issue + PAUSE-guarded inside tools.*) ---
        types.Tool(
            name="comment",
            description="Post a comment on the agent's ticket.",
            inputSchema=_obj(
                {"issue": {"type": "integer"}, "body": {"type": "string"}}, ["issue", "body"]
            ),
        ),
        types.Tool(
            name="progress",
            description="Append a stage-sticky progress line (or a free-form note).",
            inputSchema=_obj(
                {
                    "issue": {"type": "integer"},
                    "line": {"type": "string"},
                    "stage": {"type": ["string", "null"]},
                },
                ["issue", "line"],
            ),
        ),
        types.Tool(
            name="move",
            description="Enqueue a column-move intent for the daemon to drain.",
            inputSchema=_obj(
                {
                    "issue": {"type": "integer"},
                    "to_col": {"type": "string"},
                    "from_col": {"type": ["string", "null"]},
                },
                ["issue", "to_col"],
            ),
        ),
        types.Tool(
            name="done",
            description="Drop the agent's done breadcrumb (the daemon ends the session).",
            inputSchema=_obj({"issue": {"type": "integer"}}, ["issue"]),
        ),
        types.Tool(
            name="update_body",
            description="Coherence-gated issue-body edit (set_field XOR append_section).",
            inputSchema=_obj(
                {
                    "issue": {"type": "integer"},
                    # Exactly a [key, value] / [heading, text] pair: bound the length so the SDK
                    # rejects a malformed (1- or 3-element) array up front, instead of an IndexError
                    # leaking out of the tuple-unpack in _dispatch_tool / tools.update_body.
                    "set_field": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "append_section": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                ["issue"],
            ),
        ),
        types.Tool(
            name="update_main",
            # Takes NO client args (DESIGN §6 / §7): the base+dev clone paths are RESOLVED
            # SERVER-SIDE from the registry in ``_dispatch_tool`` — an agent must never supply
            # arbitrary git-repo paths to a write tool (the zero-agent-input pinning philosophy).
            description="Post-merge refresh of the base/dev clones (no args; clones server-resolved).",
            inputSchema=no_args,
        ),
    ]


def build_server(
    board_reader: BoardReader,
    board_writer: BoardWriter,
    store: StateStore,
    seeder: Seeder,
    *,
    pinned_issue: int,
    columns: dict[str, Column],
    transitions: TransitionConfig,
    root: Path,
    clone_paths: tuple[str, str] | None = None,
) -> Server[object, object]:
    """Build the low-level :class:`Server` with the four handlers wired (testable, NO live deps).

    Each handler is a THIN dispatcher into :mod:`kanbanmate.mcp.resources` / :mod:`kanbanmate.mcp.tools`,
    threading the server-fixed ``pinned_issue`` / ``columns`` / ``transitions`` / ``root`` so the
    client never supplies them. ``main`` calls this after wiring REAL deps; tests call it with fakes
    (no ``GithubClient``), so the SDK roundtrip is exercised without network I/O.

    Args:
        board_reader: The board read side (snapshots + issue context).
        board_writer: The board write side (comments + stage stickies).
        store: The persisted runtime state (intents, breadcrumbs, kill-switch, events).
        seeder: The issue-body read/patch side (``update_body``).
        pinned_issue: The agent's own issue number; every write tool refuses any other (DESIGN §7).
        columns: The board column model the ``move`` tool resolves a destination against.
        transitions: The transition whitelist the ``move`` tool's anti-loop pre-flight reads.
        root: The runtime root the read serializers read PAUSE/heartbeat/queue markers from.
        clone_paths: The SERVER-RESOLVED ``(base_clone, dev_repo)`` the ``update_main`` tool refreshes
            (DESIGN §6 — zero agent input: the client supplies NO paths). ``main`` resolves them from
            the registry; ``None`` (the default, used by tests that never call ``update_main``) makes
            ``update_main`` refuse with a clear "no clone paths resolved" message instead of running git.

    Returns:
        A configured (not-yet-running) :class:`mcp.server.Server`.
    """
    server: Server[object, object] = Server("kanban")
    ticket_uri = f"{_RESOURCE_TICKET_PREFIX}{pinned_issue}"

    # The SDK's low-level handler decorators are themselves untyped (their registration wrappers
    # return loosely-typed callables), which mypy --strict flags as untyped-decorator/no-untyped-call
    # at the boundary. Our handler bodies below ARE fully typed; the per-line ignores are scoped to
    # the SDK decorator edge only.
    @server.list_resources()  # type: ignore[no-untyped-call, untyped-decorator]
    async def _list_resources() -> list[types.Resource]:
        """Advertise the six ``kanban://`` read resources (DESIGN §5)."""
        return [
            types.Resource(uri=AnyUrl(_RESOURCE_BOARD), name="board", mimeType="application/json"),
            types.Resource(uri=AnyUrl(ticket_uri), name="ticket", mimeType="application/json"),
            types.Resource(
                uri=AnyUrl(_RESOURCE_AGENTS), name="agents", mimeType="application/json"
            ),
            types.Resource(uri=AnyUrl(_RESOURCE_QUEUE), name="queue", mimeType="application/json"),
            types.Resource(
                uri=AnyUrl(_RESOURCE_HEALTH), name="health", mimeType="application/json"
            ),
            types.Resource(
                uri=AnyUrl(_RESOURCE_EVENTS), name="events", mimeType="application/json"
            ),
        ]

    @server.read_resource()  # type: ignore[no-untyped-call, untyped-decorator]
    async def _read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        """Dispatch a ``kanban://`` URI to its pure serializer (DESIGN §5)."""
        key = str(uri)
        if key == _RESOURCE_BOARD:
            return [_json_block(resources.board(board_reader, store, root=root))]
        if key == _RESOURCE_AGENTS:
            return [_json_block(resources.agents(store))]
        if key == _RESOURCE_QUEUE:
            return [_json_block(resources.queue(store))]
        if key == _RESOURCE_HEALTH:
            return [_json_block(resources.health(store))]
        if key == _RESOURCE_EVENTS:
            return [_json_block(resources.events(store))]
        if key.startswith(_RESOURCE_TICKET_PREFIX):
            number = int(key[len(_RESOURCE_TICKET_PREFIX) :])
            return [_json_block(resources.ticket(board_reader, number))]
        raise ValueError(f"unknown resource: {key}")

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]
    async def _list_tools() -> list[types.Tool]:
        """Advertise the read + pinned-write tools (NO ``merge`` tool, DESIGN §6)."""
        return _tool_definitions()

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        """Dispatch a tool call into the pure bodies, threading the server-fixed pin/columns/root."""
        return _text(
            _dispatch_tool(
                name,
                arguments,
                board_reader=board_reader,
                board_writer=board_writer,
                store=store,
                seeder=seeder,
                pinned_issue=pinned_issue,
                columns=columns,
                transitions=transitions,
                root=root,
                clone_paths=clone_paths,
            )
        )

    return server


def _dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    board_reader: BoardReader,
    board_writer: BoardWriter,
    store: StateStore,
    seeder: Seeder,
    pinned_issue: int,
    columns: dict[str, Column],
    transitions: TransitionConfig,
    root: Path,
    clone_paths: tuple[str, str] | None = None,
) -> object:
    """Route one tool call to the matching pure body in :mod:`kanbanmate.mcp.tools` / ``resources``.

    The write tools thread ``pinned=pinned_issue`` so the pin guard (then the PAUSE guard) runs INSIDE
    the body before any I/O (DESIGN §7) — a foreign ``issue`` returns the refusal string with zero
    writes. The read tools mirror the resources.

    ``update_main`` takes NO client arguments (DESIGN §6): its ``(base_clone, dev_repo)`` are the
    SERVER-RESOLVED ``clone_paths`` (the registry pair ``main`` resolved), never client-supplied — an
    agent must not hand arbitrary git-repo paths to a write tool.

    Args:
        name: The MCP tool name from ``call_tool``.
        arguments: The client-supplied arguments mapping.
        board_reader: The board read side.
        board_writer: The board write side.
        store: The persisted runtime state.
        seeder: The issue-body read/patch side.
        pinned_issue: The server's pinned issue (the agent's own ticket).
        columns: The board column model (for ``move``).
        transitions: The transition whitelist (for ``move``'s anti-loop pre-flight).
        root: The runtime root (for the read serializers).
        clone_paths: The server-resolved ``(base_clone, dev_repo)`` for ``update_main`` (``None`` →
            the tool refuses, performing no git I/O).

    Returns:
        The tool's return value (a confirmation/refusal ``str`` or a JSON-serialisable read result).

    Raises:
        ValueError: When ``name`` is not a known tool.
    """
    # --- read tools ---
    if name in {"get_board", "get_state"}:
        return resources.board(board_reader, store, root=root)
    if name == "get_ticket":
        return resources.ticket(board_reader, int(arguments["issue"]))
    # --- write tools (pinned + PAUSE-guarded inside the body) ---
    if name == "comment":
        return tools.comment(
            board_writer,
            store,
            issue=int(arguments["issue"]),
            pinned=pinned_issue,
            body=str(arguments["body"]),
        )
    if name == "progress":
        stage = arguments.get("stage")
        return tools.progress(
            board_writer,
            store,
            issue=int(arguments["issue"]),
            pinned=pinned_issue,
            line=str(arguments["line"]),
            stage=str(stage) if stage is not None else None,
        )
    if name == "move":
        from_col = arguments.get("from_col")
        return tools.move(
            store,
            columns,
            transitions,
            issue=int(arguments["issue"]),
            pinned=pinned_issue,
            to_col=str(arguments["to_col"]),
            from_col=str(from_col) if from_col is not None else None,
        )
    if name == "done":
        return tools.done(store, issue=int(arguments["issue"]), pinned=pinned_issue)
    if name == "update_body":
        set_field = arguments.get("set_field")
        append_section = arguments.get("append_section")
        return tools.update_body(
            seeder,
            store,
            issue=int(arguments["issue"]),
            pinned=pinned_issue,
            set_field_kv=(str(set_field[0]), str(set_field[1])) if set_field else None,
            append_section_ht=(str(append_section[0]), str(append_section[1]))
            if append_section
            else None,
        )
    if name == "update_main":
        # Zero client input (DESIGN §6 / §7): the clone pair is the SERVER-RESOLVED ``clone_paths``,
        # NOT ``arguments`` — an agent must never supply arbitrary git-repo paths to a write tool.
        if clone_paths is None:
            return "refusing to refresh main: the server resolved no clone paths from the registry"
        base_clone, dev_repo = clone_paths
        return tools.update_main(store, base_clone=base_clone, dev_repo=dev_repo)
    raise ValueError(f"unknown tool: {name}")


class PinMismatchError(RuntimeError):
    """Raised at start-up when the worktree pin file disagrees with the launch ``--issue`` (§7).

    The bins pin on the worktree pin FILE (``.claude/kanban-issue``); the MCP server pins on the
    launch ``--issue``. Defense-in-depth (conduit review hardening): the two MUST agree — a server
    launched with a ``--issue`` that does not match the worktree it runs IN is misconfigured and
    every write would target the wrong ticket, so the server REFUSES to start. The CLI converts this
    into a clean non-zero exit (never a raw traceback). An ABSENT pin file is NOT a mismatch (some
    launch paths may not write it) — the server proceeds on ``--issue`` alone.
    """


def main(*, root: Path, issue: int, project: str | None, repo: str | None) -> None:
    """Start the stdio MCP board server pinned to ``issue`` (the ``kanban mcp`` entry, DESIGN §4).

    Wires the REAL board deps for the resolved project, builds the server via :func:`build_server`,
    and blocks running it over stdio until the client disconnects. Side-effect-free at import time
    (all wiring + the run happen here, mirroring :func:`kanbanmate.http.serve.main`).

    Two start-up guards run BEFORE the blocking stdio run (conduit review hardening):

    * the worktree pin FILE (``.claude/kanban-issue``, the bins' pin) is re-read and asserted equal
      to ``issue`` — a mismatch raises :class:`PinMismatchError` (the CLI exits non-zero); an absent
      pin file proceeds on ``--issue`` alone;
    * the ``update_main`` clone pair is RESOLVED SERVER-SIDE from the registry (zero client input),
      so the agent never supplies git-repo paths.

    Args:
        root: The runtime root holding ``config.yml`` / ``projects.json`` and the state markers.
        issue: The agent's pinned issue number (every write tool refuses any other; DESIGN §7).
        project: The ``--project`` Project v2 node-id selector (multi-project roots), or ``None``.
        repo: The ``--repo`` ``owner/name`` selector (multi-project roots), or ``None``.

    Raises:
        PinMismatchError: When the worktree pin file names a DIFFERENT issue than ``issue``.
    """
    # Local imports of the cli/app wiring helpers: keep the module import surface lean and avoid a
    # heavy import chain at ``import kanbanmate.mcp.server`` time (the import-purity smoke test).
    from kanbanmate.app.wiring import build_deps, build_tick_config
    from kanbanmate.cli.app import _wiring_for
    from kanbanmate.cli.init import resolve_clone_paths
    from kanbanmate.mcp.pin import read_worktree_pin

    # Start-up guard 1 (defense-in-depth, §7): align the MCP pin with the bins' worktree pin file.
    # An absent pin file is NOT a mismatch (some launch paths may not write it) — proceed on --issue.
    worktree_pin = read_worktree_pin()
    if worktree_pin is not None and worktree_pin != issue:
        raise PinMismatchError(
            f"kanban mcp: --issue {issue} disagrees with the worktree pin file "
            f"(.claude/kanban-issue names #{worktree_pin}); refusing to start on a mismatched pin"
        )

    config = _wiring_for(root, project=project, repo=repo)
    deps = build_deps(config)
    tick_config = build_tick_config(config)
    # ``build_deps`` ALWAYS wires the GithubClient into the ``seeder`` slot (app/wiring.py:182), so
    # this is never None in practice; the guard narrows the optional type for the strict checker and
    # fails loud rather than passing None into the ``update_body`` tool.
    if deps.seeder is None:  # pragma: no cover - defensive; the wiring always sets it
        raise RuntimeError("kanban mcp: the board wiring yielded no seeder (the body-edit port)")
    # Resolve the ``update_main`` clone pair SERVER-SIDE from the registry (DESIGN §6 — zero agent
    # input). The wiring already resolved WHICH project this server drives (``config.project_id``),
    # so resolve the same entry's (clone, dev_repo) the ``kanban-update-main`` bin reads. Fail-soft:
    # a missing registry entry leaves ``clone_paths`` None → ``update_main`` refuses (no git), the
    # rest of the board surface still serves.
    try:
        clone_paths: tuple[str, str] | None = resolve_clone_paths(
            root, project_id=config.project_id
        )
    except RuntimeError:
        clone_paths = None
    server = build_server(
        deps.board_reader,
        deps.board_writer,
        deps.store,
        deps.seeder,
        pinned_issue=issue,
        columns=tick_config.columns,
        transitions=tick_config.transitions or _require_transitions(),
        root=root,
        clone_paths=clone_paths,
    )

    async def _run() -> None:
        """Open the stdio transport and run the server until the client disconnects."""
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(_run)


def _require_transitions() -> TransitionConfig:
    """Fail loud when the wiring yielded no transition whitelist (never expected — defensive).

    ``build_tick_config`` ALWAYS supplies a whitelist (the explicit file or the built-in default,
    ``app/wiring.py:189``), so ``tick_config.transitions`` is never ``None`` in practice; this guards
    the ``move`` tool against a config drift rather than passing ``None`` down.

    Raises:
        RuntimeError: Always — the caller only reaches here on an unexpected ``None`` whitelist.
    """
    raise RuntimeError("kanban mcp: no transition whitelist resolved (config drift)")
