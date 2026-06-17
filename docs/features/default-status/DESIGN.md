# DESIGN — default-status (auto-assign Backlog to statusless board items)

**Codename:** default-status (patch 0.5.0 → 0.5.1).
**Branch:** `feat/default-status-backlog`.
**Module:** NEW `src/kanbanmate/app/default_status.py` + one wired call in `app/tick.py`.

## 1. Operator rule

A ticket's DEFAULT Status is the board's first/entry column (`Backlog` on the shipped template). No
item may sit in GitHub's "No Status" bucket. When the daemon snapshots an item that is on the board
WITHOUT a Status single-select value (an issue freshly added to the board, or created via the API
without setting Status), it must AUTO-ASSIGN it the default column on that tick, so "No Status"
becomes self-healing (the operator previously fixed such items by hand).

## 2. How a statusless item is represented today

A statusless item is NOT errored or skipped — it is mapped to an EMPTY STRING column and lands as a
silent dead-end:

- **GitHub read.** `adapters/github/_parsers.py` — `status_column=str(status_value.get("name") or "")`.
  A null `fieldValueByName` (No Status) → `RawItem.status_column == ""`.
- **Domain.** `client.py:_to_ticket` copies that straight through to `Ticket.column_key == ""`.
- **Diff.** A brand-new statusless item yields `Transition(from_column=None, to_column="")`. A
  pre-existing item the operator left statusless has baseline `""`, so it produces NO transition.
- **Decide.** `resolve_column(columns, "")` is `None`, so for a first-contact item
  (`from_column is None ⇒ from_key is None`) the move falls through to a **recording NOOP**
  (`core/decide.py`), which records baseline `""` and does nothing. The item sits in No Status
  forever, invisible to every later tick.

Detection key = `Ticket.column_key == ""` (empty string).

## 3. Where the normalization slots in the tick

A new post-snapshot step `normalize_default_status(...)` is wired into `app/tick.py` INSIDE the
snapshot branch (`if not probe_failed and probe_token != persisted_state.last_probe:`), immediately
AFTER `snapshot = deps.board_reader.snapshot()` and BEFORE the diff loop.

Rationale for that position:
- It must see the fresh `snapshot` (only available in the snapshot branch — it never runs on an
  unchanged probe, exactly like `apply_health`'s snapshot-gated early-return).
- Running it BEFORE the diff loop lets it pre-seed the in-memory baseline `next_columns` for any item
  it heals (see §5 double-write guard).
- It is a normalization concern, not a reactive decision, so it does NOT belong inside `decide`
  (which stays pure and per-single-transition) nor inside `process_transition`.

Because `tick.py` was at the 1000-LOC hard ceiling, the step body lives in the NEW module
`app/default_status.py`; the tick change is one import + one terse call + the double-write guard below.
The feature commit initially held tick.py at exactly 1000 LOC by condensing existing comments, which
left ZERO headroom (the next added line would trip the size guard). A follow-up polish gave it real
headroom by extracting the cohesive per-action **watchdog group** (the bounded-execution wrappers, the
per-tick thread-pool context manager, and the timeout registry) into the NEW module `app/watchdog.py`;
`tick.py` re-exports those names under their historical spellings so the reaper / drain /
transition_step lazy imports and the test monkeypatches resolve unchanged. tick.py is now comfortably
under the ceiling (~740 LOC).

## 4. Deriving the default column (NOT hardcoded)

```python
def _default_column(config: TickConfig) -> Column | None:
    return next(iter(config.columns.values()), None)
```

The default/entry column is the FIRST column in the parsed column model, which preserves
`columns.yml` source order (`core/columns.load_columns` builds an insertion-ordered dict).

- Returns `None` for an (impossible) empty column set → the step no-ops fail-soft.
- We deliberately do NOT reuse `config.reset_target` (a hardcoded `"Backlog"` literal default in
  `TickConfig`, never overridden by wiring) — deriving from `config.columns` honours the
  "derive the first/default column from columns config" constraint and is strictly more robust (a
  board whose first column is renamed still works).

### Name vs key (load-bearing)

`BoardWriter.move_card(item_id, column_key)` resolves the destination via
`StatusField.options[column_key]` where `options` is keyed by the GitHub option **NAME**
(`_parsers.parse_status_field`). Therefore the normalization passes the default column's **`.name`**
to `move_card`, NOT its `.key`. For `Backlog` key==name so it is moot on the default board, but a
first column whose key differs from its name (e.g. key `Entry` / name "Inbox") would `KeyError` if the
key were passed. The in-memory baseline (`next_columns`) records the same NAME the snapshot reports
next tick (`fieldValueByName.name`), keeping the baseline name-consistent.

## 5. The write: idempotent + fail-soft + rate-limit-aware

Per snapshot item:

- **Idempotent.** Only items with `column_key == ""` are touched; an item already in any column is
  skipped. Once healed, its snapshot column is non-empty next poll, so it is never re-written.
- **Fail-soft.** A per-item try/except (one bad card never drops the rest) plus an outer try/except so
  ANY exception is logged WARNING and swallowed — it NEVER raises into `tick` or blocks a launch
  (mirrors `apply_health`). A failed item's baseline is left UNADVANCED so it retries next tick.
- **Rate-limit-aware.** The heal is recorded with `record_move(..., bookkeeping=True)` — it refreshes
  the target-keyed dedup recency marker (runaway backstop) but is EXCLUDED from the per-ticket
  rate-limit timestamp feed. It also does NOT call `store.record_move_for_item(...)` at all, so a
  normalization never eats into either the per-issue forward-advance budget or the rate-limit budget
  the fix-CI / auto-advance loops gate on. This is the same separation the reaper's Blocked-park took
  (`app/reaper.py`, Candidate 1 rate-limit conflation fix).
- **PAUSE floor.** Under the kill-switch (`~/.kanban/PAUSE`) the daemon makes NO board moves
  (DESIGN §10 floor) — the heal is suppressed; a resume heals on a later tick.

### Double-write guard (tick.py)

The diff this tick is computed from `persisted_state.columns_by_item` (the pre-tick baseline), so a
first-contact statusless item STILL yields a `to_column=""` transition. Left alone, the recording
NOOP (`transition_step.py`) would advance the baseline back to `""` — and the NEXT tick (snapshot now
reporting the default column) would diff `""→Backlog` with a NON-None `from_column`, which
`decide` classifies as a ROLLBACK and would BOUNCE the card back to No Status, undoing the heal.

To prevent that, the diff loop skips the stale `→""` transition for any item the normalization just
healed (its `next_columns` baseline is now the default column NAME):

```python
for transition in diff(persisted_state.columns_by_item, snapshot):
    if transition.to_column == "" and next_columns.get(transition.ticket.item_id):
        continue
    ...
```

This keeps the heal durable across ticks while leaving `decide` / `process_transition` unchanged. A
non-healed statusless item (e.g. under PAUSE) has a falsy `next_columns` entry, so it is NOT skipped
and follows the unchanged recording-NOOP path.

### Edge case: operator CLEARS an item's Status later (intended self-heal, not a bug)

If an operator (or the API) later REMOVES the Status value of an item that already had one, the next
snapshot reports `column_key == ""` for it again. The normalization treats this exactly like a fresh
statusless item and **re-heals it to the entry column on that tick** — there is no "already seen this
item" memory that would let it stay in No Status. This is **intended and correct** per the §1 operator
rule ("no item may sit in No Status"): the rule is a board invariant the daemon continuously restores,
not a one-shot assignment at first contact. The mechanics mirror first contact — the diff against the
in-memory baseline (the item's prior column) yields a `<prior>→""` transition that `decide` would
otherwise treat as a backward move, but the heal pre-seeds `next_columns` to the entry column and the
double-write guard above skips that stale `→""` transition, so the card is re-assigned the entry
column with no spurious rollback and no agent launch. Net behaviour: clearing a Status is transparently
undone on the following poll, returning the card to the entry column — by design.

## 6. Why no agent fires

The default column is the board's first/entry column (`Backlog` on the shipped template), which is
**non-triggering**: there is no arrival-INTO-Backlog launch in the transition whitelist (launches ride
`from→to` edges like `Backlog → Brainstorming`). The heal records the baseline as the default column
NAME, so the next tick's diff sees the item already in the default column and emits no transition —
`decide` is never asked for that item, so no LAUNCH verdict is possible. Net: an item is assigned
Backlog and never launches an agent from the assignment.

## 7. Multi-project handling

The engine is multi-project (v0.5.0): `daemon/sweep.py` runs one `tick(deps, tick_config, persisted)`
per project, each with its OWN wired `Deps` (its `board_writer`, `project_id`, token) and its OWN
`TickConfig` (its `columns` parsed from that project's clone `columns.yml`). Because
`normalize_default_status` derives the default column from `config.columns` and writes through
`deps.board_writer` (both per-project), it is automatically multi-project-correct with NO extra
wiring: each project heals to ITS first column via ITS Status field. No global state, no shared field
id.

## 8. Files touched

| File | Change |
|---|---|
| NEW `src/kanbanmate/app/default_status.py` | `normalize_default_status` + `_default_column` |
| `src/kanbanmate/app/tick.py` | import + one call in the snapshot branch + the double-write guard; the per-action watchdog group was extracted out (see below) to give the file real headroom under the 1000-LOC ceiling (now ~740 LOC) |
| NEW `src/kanbanmate/app/watchdog.py` | the extracted per-action watchdog group (`_run_with_watchdog`, `_run_launch_with_watchdog`, `_run_value_with_watchdog`, `_run_callable_with_watchdog`, `WatchdogStatus`, `_watchdog_executor`, `_record_timed_out_action`, the timeout registry); behaviour-preserving, re-exported from `tick.py` for the lazy importers + test monkeypatches |
| NEW `tests/app/test_default_status.py` | 9 unit tests (heal, untouched, idempotent, name-vs-key, empty set, fail-soft, rate-limit budget, PAUSE, multi-project) |
| `tests/app/test_tick.py` | 1 integration test (no agent fired end-to-end, durable across two ticks) |
| `VERSION`, `pyproject.toml`, `src/kanbanmate/__init__.py`, `.claude-plugin/marketplace.json`, `plugin/.claude-plugin/plugin.json` | 0.5.0 → 0.5.1 (all 5 pins) |

## 9. Safety on the live daemons

Built in an ISOLATED git worktree + isolated venv (3.12.4). The MAIN worktree, `.claude/`, and the PM2
daemons were never touched. The change is additive and dormant until merged + redeployed; on the live
N=1 boards the derived default is `Backlog` (first column), so behaviour for already-statused items is
byte-identical and only the (previously hand-fixed) No-Status items begin healing.
