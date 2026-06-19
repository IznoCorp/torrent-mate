# Phase 3 — SDK server + `kanban mcp` command + roundtrip test

**Goal**: wire the pure shell (Phase 2) behind the low-level `mcp.server.Server` over stdio, and add the
`kanban mcp` CLI entry point that launches it pinned to `--issue` (DESIGN §4, §4.1).

## Module: `src/kanbanmate/mcp/server.py` (the only SDK importer)

Built on the `mcp` Python SDK, which **Phase 1 sub-phase 1d adds** as the `[mcp]` optional extra
(`mcp>=1.26`, installed via `.[dev,ui,mcp]`; `mcp 1.28.0` verified pip-installable on 3.12.4). After
Phase 1 it imports as `from mcp.server import Server`; `from mcp.server.stdio import stdio_server`. It
is **NOT** present in a bare install, so the `kanban mcp` command lazy-imports the server **behind
`try/except ImportError`** (friendly "install `.[mcp]`" message), exactly as `cli/config.py` guards the
`serve` import behind `[ui]`. Use the **low-level** `Server` (not FastMCP) so the serializers/tool
bodies stay SDK-free and explicitly testable (DESIGN §4.1).

`server.main(...)` is **side-effect-free at import time** (mirrors `http/serve.py:461`) — all wiring and
the blocking stdio run happen inside `main`:

```python
def main(*, root: Path, issue: int, project: str | None, repo: str | None) -> None:
    """Start the stdio MCP board server pinned to ``issue`` (conduit / roadmap mcp)."""
    deps = build_deps(_wiring_for(root, project=project, repo=repo))   # cli/app.py:151 + app/wiring.py:112
    tick_config = build_tick_config(...)                               # app/wiring.py:189 — for the columns model
    # The server needs exactly: deps.board_reader, deps.board_writer, deps.store (DESIGN §4).
    server = Server("kanban")
    # register four low-level handlers, each a thin dispatcher into resources.py / tools.py:
    #   @server.list_resources()   -> the 6 kanban:// URIs (DESIGN §5)
    #   @server.read_resource()    -> dispatch by URI to resources.{board,ticket,agents,queue,health,events}
    #   @server.list_tools()       -> the read + write tools (DESIGN §6; NO merge tool)
    #   @server.call_tool()        -> dispatch by name into tools.*, threading pinned_issue=issue + columns
    # then run over stdio_server() (anyio/async entry per the SDK's documented run pattern).
```

**Grounding the wiring** (match real signatures):

- `_wiring_for(root, *, project, repo)` — `cli/app.py:151`; loads the board `WiringConfig`.
- `build_deps(config) -> Deps` — `app/wiring.py:112`; constructs the `GithubClient` (satisfying both
  `BoardReader` and `BoardWriter`), the `FsStateStore`, etc. The server reads
  `deps.board_reader` / `deps.board_writer` / `deps.store`.
- `build_tick_config(config) -> TickConfig` — `app/wiring.py:189`; source of the `columns` model the
  `move` tool resolves against.
- Read `src/kanbanmate/http/serve.py` (the sibling entrypoint) for the established import-time-purity
  pattern and the anyio run shape before writing `main`; confirm the SDK's exact `Server.run` /
  `stdio_server()` call signature against the installed `mcp` package before finalising.

Keep `server.py` a thin dispatcher: it holds **no** domain logic — every handler delegates to the pure
Phase-2 functions (DESIGN §3).

## CLI: new `kanban mcp` command in `src/kanbanmate/cli/app.py`

Model it on `kanban serve` (`cli/app.py:104`) — a direct `@app.command()` that lazy-imports the server
module inside the body and delegates (DESIGN §4):

```python
@app.command()
def mcp(
    root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Kanban runtime root (default ~/.kanban)."),
    issue: int = typer.Option(..., "--issue", help="The agent's pinned issue number (write tools refuse any other)."),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Start the stdio MCP board server, pinned to ``--issue`` (conduit / roadmap mcp)."""
    from kanbanmate.mcp import server as mcp_server
    mcp_server.main(root=root.expanduser(), issue=issue, project=project, repo=repo)
```

`_DEFAULT_ROOT` (`cli/app.py:78`), `_PROJECT_OPTION` (`cli/app.py:215`), `_REPO_OPTION` (`cli/app.py:220`)
already exist — reuse them exactly (the `status` command at `cli/app.py:299` is the multi-project
template; confirm the real `_PROJECT_OPTION`/`_REPO_OPTION` default values and that `project`/`repo`
arrive as the types `_wiring_for` expects). Register the command where the other subcommands register
(end of module, per the `cli/app.py:51` note).

## Test — `tests/mcp/test_server_roundtrip.py`

An in-process MCP **client over stdio** round-trip (DESIGN §12):

- list resources / list tools (assert the 6 `kanban://` URIs and the read+write tool names are present,
  and **no `merge` tool**);
- read `kanban://board` and assert the documented top-level keys;
- call a read tool (`get_state`/`get_board`) and assert it returns the same shape;
- call a pinned **write** tool with a **foreign** issue (`issue != pin`) and assert it refuses
  end-to-end through the SDK (zero writes on the fake/in-memory deps).

Use the SDK's in-memory or stdio client per its documented test pattern; wire the server with fake
`BoardReader`/`BoardWriter`/`StateStore` deps (the same fakes Phase 2 uses) rather than a live
`GithubClient`. If injecting fakes into `server.main` is awkward (it builds real deps), factor a small
`build_server(board_reader, board_writer, store, *, pinned_issue, columns)` helper that `main` calls —
testable without GitHub — and assert through it.

## Gate for Phase 3

- `pytest tests/mcp/ -q` green (resources + tools + roundtrip).
- `pytest tests/cli/ -q` green — the new `mcp` command registers without breaking the existing CLI
  (add/extend a CLI test asserting `kanban mcp --help` lists `--issue` as **required**).
- `pytest tests/test_layering.py -q` green — `server.py` imports `mcp` (the SDK, third-party — not a
  kanbanmate layer) + `app`/`cli`/`core`; never `daemon`/`bin`.
- `python -c "import kanbanmate.mcp.server"` smoke test (import-time side-effect-free).
- `make check` green.

## Commit

`feat(conduit): phase 3 — stdio MCP server + kanban mcp command + roundtrip test`
