# Phase 2 — MCP pure shell: pin, resources, tools (SDK-free) + unit tests

**Goal**: build the **SDK-free** functional core of the MCP layer — `mcp/__init__.py`, `mcp/pin.py`,
`mcp/resources.py`, `mcp/tools.py` — as thin wrappers over already-wired ports and existing
`core`/`app` functions. Every function takes ports + plain values and returns JSON-serialisable
`dict`s (resources) or result/refusal values (tools), so they are unit-testable **without** the MCP SDK
(DESIGN §3.2, §5, §6).

`server.py` (the only module that imports `mcp` the SDK) is **Phase 3** — this phase imports no SDK.

## Module: `src/kanbanmate/mcp/__init__.py`

Layer docstring mirroring `src/kanbanmate/http/__init__.py:1-13`: state that `mcp` sits at the top of
the import hierarchy alongside `cli`/`daemon`/`http`, may import `app`/`adapters`/`core`/`ports`/`cli`,
and must NOT import `daemon`/`bin`.

## Module: `src/kanbanmate/mcp/pin.py` (pure)

One pure helper (DESIGN §7):

```python
def pin_violation(requested: int, pinned: int) -> str | None:
    """Return a refusal message when ``requested`` != ``pinned`` write target, else ``None``."""
```

This mirrors the comparison `bin/_pin.check_pin` does (`bin/_pin.py:244-252`) but is a **shell-local
one-line `!=`** — the `mcp` layer may **not** import `bin/_pin` (forbidden by §3.1) and does not need
to: the pinned value is supplied to the server at launch via `--issue`. No relocation needed.

## Module: `src/kanbanmate/mcp/resources.py` (pure serializers)

Each function takes already-wired ports + plain values and returns a JSON-serialisable `dict`. Read the
backing read-models first and serialize their **real** fields (DESIGN §5):

| Function (sketch) | Backed by | Returns |
| --- | --- | --- |
| `board(...)` | `cli.state.state(board_reader, store, root=root, ttl=HEARTBEAT_TTL_FLOOR, as_json=True)` (`cli/state.py:190`) → parse/return its JSON, **or** `build_state(...)` (`cli/state.py:57`) + `render_state_json` (`cli/state.py:108`) | `health, paused, degraded, board{columns,total}, agents[], queue[], events[], daemon` |
| `ticket(board_reader, n)` | `board_reader.issue_context(n)` (`ports/board.py:68`) + the `Ticket` from `board_reader.snapshot()` (`ports/board.py:41`) | `{issue_number, title, column_key, body, comments[], linked_issue_body}` (the enrichment `app/launch_context.py:70-77` builds) |
| `agents(store)` | `store.list_running()` (`ports/store.py:293`) | one row per LIVE `TicketState`: `issue_number, item_id, session_id, status, heartbeat, stage, profile, …` |
| `queue(store)` | `store.dequeue_pending()` (`ports/store.py:667`) + `store.load_queued(n)` (`ports/store.py:687`) | `[{issue_number, stage, enqueued_at}]` |
| `health(store)` | `store.get_status_last_enum()` (`ports/store.py:805`) | the last-posted status enum, or `null` |
| `events(store)` | `store.read_status_events()` (`ports/store.py:873`) | the recent-events ring (≤10), newest-first: `[{ts, kind, issue, detail}]` (kinds = `EVENT_EMOJI` keys, `core/status_update.py:86-103`) |

**Implementer grounding**: open each backing method's real return type and serialize its actual fields —
`TicketState` (`ports/store.py:81-161`), the `kanban://board` shape (`cli/state.py:108-155`),
`read_status_events` rows (`ports/store.py:873-890`). Do not invent field names.

For `board`, prefer reusing the imperative shell `cli.state.state(...)` (it already reads
`PAUSE`/`DEGRADED`/daemon heartbeat/queue off `root` and renders the stable shape). `HEARTBEAT_TTL_FLOOR`
is imported from `cli/state.py` (verify its exact import name there before use).

## Module: `src/kanbanmate/mcp/tools.py` (thin write/read tool bodies)

Read tools (not pinned) just call the matching `resources.py` serializer (DESIGN §6.1):
`get_board()`, `get_ticket(issue)`, `get_state()` (alias of `get_board()`).

Write tools (DESIGN §6.2) — **each** first calls `pin.pin_violation(requested, pinned)` and returns the
refusal (performing **zero** I/O) on mismatch, then checks `store.kill_switch_active()`
(`ports/store.py:491`) and refuses under PAUSE, then routes through the **identical** function the bin
uses:

| Tool | Routes through (exact, grounded) |
| --- | --- |
| `comment(issue, body)` | `board_writer.comment(issue, body)` (`ports/board.py:113`) — parity `bin/kanban_comment.py:207` |
| `progress(issue, line, stage=None)` | `app.stage_signal.upsert_stage_comment(writer, issue, stage, append=line, now=…)` (signature `app/stage_signal.py:48-56`: `(writer, issue, stage, *, header=None, append=None, now=None)`); free-form fallback `board_writer.comment(issue, stamped)` when `stage is None` — parity `bin/kanban_progress.py:200,222` |
| `move(issue, to_col)` | resolve via `core.columns.resolve_target_column(columns, to_col)` (relocated, Phase 1) → `store.enqueue_intent(intent_id, payload)` (`ports/store_intents.py:24`) + `store.nudge_daemon()` (`ports/store_intents.py:78`). `intent_id = uuid.uuid4().hex[:12]`; payload **exactly** `{"kind":"move","issue":issue,"args":{"to_col":column.key},"requested_at":now,"caller":"agent"}` — parity `bin/kanban_move.py:233-246` (column **KEY**, not name) |
| `done(issue)` | `store.record_agent_done(issue, now=…)` (`ports/store.py:413`, signature `(self, issue_number, *, now)`) — parity `bin/kanban_done.py:66` |
| `update_body(issue, set_field=(key,value) \| append_section=(heading,text))` | `core.body_edit.set_field(body,key,value)` (`core/body_edit.py:66`) / `append_section(body,heading,text)` (`core/body_edit.py:103`) → `core.body_edit.validate_roadmap_matches_title(new_body, title)` (`core/body_edit.py:258`) → on `None` (no mismatch) `board_writer.update_issue_body(node_id, new_body)` (`ports/board.py:289`); on a non-`None` message **refuse** and surface it — parity `bin/kanban_update_body.py:210-227` |
| `update_main()` | `adapters.workspace.base_sync.fetch_base(...)` + `ff_dev_clone(...)` (relocated, Phase 1) — parity `bin/kanban_update_main.py` (or DROPPED per the §11.2 scope lever) |

Node-id resolution for `comment`/`progress`/`update_body`: resolve the issue's GraphQL node id the way
the bins do — `board_writer.fetch_issue(issue)` (`ports/board.py:306`) exposes the node id /
`update_issue_body(node_id, body)`. Match the bin's real flow (`bin/kanban_update_body.py:205,227`).

`move` also mirrors the bin's **UX-only** pre-flight pair-aware anti-loop guard
(`bin/kanban_move.py:209-230`): refuse when `(from_col, to_col)` is itself a prompt-bearing launch
transition. The **authoritative** gate stays the daemon's `validate_intent` (`app/intents.py:166`,
`core/intent.py:124-222`) under derived authority — the shell does **not** re-implement R1 / the Merge
deny / the re-fire guard; it enqueues and lets the daemon decide (DESIGN §6, §7).

The `columns` model the `move`/`resolve_target_column` path needs is read from the wired board config
via `build_tick_config(config)` (`app/wiring.py:189`) — wired and passed in by `server.py` (Phase 3),
not constructed inside `tools.py`.

**No `merge` tool is defined.**

## Tests — `tests/mcp/test_resources.py` and `tests/mcp/test_tools.py`

Create `tests/mcp/` (new dir, mirroring the layer-named test tree). Use the existing fakes for
`BoardReader` / `BoardWriter` / `StateStore` (DESIGN §12 — locate them under the current suite, e.g.
`tests/app/` / `tests/cli/` fakes; reuse, do not re-fake from scratch).

`tests/mcp/test_resources.py` — each serializer against fakes pre-seeded with **real** values: real
column **keys** (not display labels), a snapshot with ≥1 `Ticket`, a non-empty events ring, a live
`TicketState`. Assert the produced `dict` matches the documented shape — **never** assert two empty
sides (DESIGN §12).

`tests/mcp/test_tools.py` — for each write tool:
1. **Pinning**: a tool called with `issue != pinned` returns the refusal and performs **zero** writes on
   the fake (assert the fake recorded no `comment`/`enqueue_intent`/`update_issue_body`/`record_agent_done`).
2. **PAUSE**: with the fake store reporting `kill_switch_active() is True`, the tool refuses.
3. **Routing**:
   - `move` → exactly **one** `enqueue_intent` with the expected payload (real column **key** for
     `to_col`) + exactly one `nudge_daemon`.
   - `update_body` with a roadmap/title mismatch refuses via `validate_roadmap_matches_title` and
     **never** calls `update_issue_body`; a coherent edit calls `update_issue_body` once.
   - `done` calls `record_agent_done` once (with a real `now`).
   - `comment` calls `board_writer.comment` once.

## Gate for Phase 2

- `pytest tests/mcp/test_resources.py tests/mcp/test_tools.py -q` green.
- `pytest tests/test_layering.py -q` green — `mcp/` imports nothing from `daemon`/`bin` (the AST walk now
  has real `mcp/*.py` files to scan).
- `make check` green; no `mcp/` module exceeds the 1000-LOC ceiling.

## Commit

`feat(conduit): phase 2 — MCP pure shell (pin, resources, tools) + unit tests`
