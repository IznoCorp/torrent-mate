# DESIGN — health-field (per-card "Health" GitHub single-select field)

## 1. Context & problem

KanbanMate already maintains a rolling GitHub Project **"Status updates"** pill (the live dashboard,
`core/status_update.py`). That pill's enum is GitHub's **fixed** `ProjectV2StatusUpdateStatus`
(`INACTIVE / ON_TRACK / AT_RISK / OFF_TRACK / COMPLETE`) — verified in
`adapters/github/_queries.py` (`create_status_update` / `update_status_update` both type the variable
`$status: ProjectV2StatusUpdateStatus`) and `adapters/github/client.py` (`_HEALTH_TO_GITHUB_STATUS`
maps the domain names onto it at the wire boundary). GitHub renders that enum with its OWN labels and
colours; there is **no rename mutation**, so the operator's own vocabulary
(`INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE`) never shows on the pill.

## 2. Decision

Add a NEW **per-card single-select FIELD named "Health"** whose 5 option NAMES are exactly the
operator's vocabulary, with operator-chosen colours. GitHub renders single-select options with custom
names + colours as native chips on each card — so the operator's words DO appear. The daemon sets each
card's Health value every tick, **ON CHANGE only**, fully **fail-soft** (observability, never a launch
blocker).

This is additive: the status-update pill is unchanged; the Health field is a second, complementary
surface that carries the operator's wording at the per-card level.

## 3. The 5 values + colours

The vocabulary is REUSED from `core/status_update.py` (`StatusValue` / `STATUS_VALUES`) — no parallel
set. Colours are from GitHub's fixed `createProjectV2Field` palette (`GRAY / BLUE / GREEN / YELLOW /
ORANGE / RED / PINK / PURPLE`):

| Value    | Colour | Meaning |
|----------|--------|---------|
| ACTIVE   | GREEN  | a live agent is working the card |
| WAITING  | YELLOW | a live agent is awaiting human input |
| BLOCKED  | RED    | no agent, card parked in the Blocked column |
| INACTIVE | GRAY   | idle card (Backlog / Spec / Cancel / no agent) |
| COMPLETE | PURPLE | no agent, card in the Done column |

(`core/health.py`: `HEALTH_OPTION_COLORS` + `HEALTH_OPTIONS_ORDER`.)

## 4. Pure mapping `compute_health`

`core/health.compute_health(*, is_running, is_waiting, column_key, blocked_column, done_column)` —
PURE, no I/O. Precedence (FIRST MATCH WINS):

1. live agent WAITING → **WAITING** (wins over the column).
2. live agent RUNNING → **ACTIVE** (wins over the column).
3. no live agent AND `column_key == blocked_column` → **BLOCKED**.
4. no live agent AND `column_key == done_column` → **COMPLETE**.
5. otherwise → **INACTIVE**.

The Blocked/Done keys are PASSED IN (the app layer threads them from `TickConfig.blocked_column` /
`done_column`), so the function is not hardcoded to the default board labels. The app layer derives
`is_running` / `is_waiting` from `TicketStatus` (RUNNING vs WAITING), so `core/` never imports
`ports.store`.

## 5. Module map / layering

```
cli/init (best-effort ensure) ─┐
daemon → app/tick (Step 4e) ───┼─▶ app/health_reporter.apply_health  ──▶ core/health.compute_health
                               │        │                                 (pure)
                               │        ├─▶ ports.board.ProjectHealthReporter (Protocol)
                               │        └─▶ ports.store.StateStore   (health markers)
                               │
            adapters/github/client.GithubClient ──▶ adapters/github/_health (ensure/reconcile)
                                                  ──▶ _queries / _parsers / types.HealthField
            adapters/store/fs_store.FsStateStore ──▶ adapters/store/fs_health_state.HealthStateMixin
```

Import direction is downward only (the layering guard passes unchanged): `core/health` imports only
`core` (`status_update`); `app/health_reporter` imports `core` + `ports` (+ the `HealthField` adapter
value object, on the existing ports→adapter-value-object precedent); adapters implement ports.

New files: `core/health.py`, `app/health_reporter.py`, `adapters/github/_health.py`,
`adapters/store/fs_health_state.py`. The `HealthField` value object lives in
`adapters/github/types.py` (twin of `StatusField`).

## 6. GraphQL surface — ONE new mutation, everything else REUSED

- **NEW**: `_queries.create_project_field_single_select(project_id, name, options)` →
  `createProjectV2Field(dataType: SINGLE_SELECT, singleSelectOptions: [...])`. The ONLY new query.
- **READ — reuse `status_option_map`**: that query already reads EVERY `ProjectV2SingleSelectField`
  (only the Status parsers filter by name). The new `_parsers.parse_health_field` filters to
  `name == "Health"` + the presence of an `options` node; absent → `None` (caller creates).
- **SET — reuse `move_item`**: the Health write is the SAME `updateProjectV2ItemFieldValue { value: {
  singleSelectOptionId } }` mutation, only against the Health field id. **Do NOT invent a new set
  mutation.** `client.set_item_health` calls `_queries.move_item(...)` directly.
- **RECONCILE — reuse `update_status_field_options`**: despite the name, a generic single-select
  option REPLACE. Passing existing option ids preserves cards' chips. Parsed with the existing
  `parse_updated_field_options`.

`parse_created_single_select_field` parses the `createProjectV2Field` response into a `HealthField`.
Every parser raises `GraphQLError` on a non-empty `errors` array.

## 7. Idempotent provisioning (zero manual step)

Field ids are persisted in the STORE (board-wide, per kanban-root) under `<root>/health/`, NOT in
`projects.json` — because the daemon does not thread `projects.json` field ids into the tick
(`daemon/loop.py` builds `WiringConfig` from `project_id` + `repo` + `clone` + `columns_yaml` only).
The store IS carried into every tick via `Deps.store`, keyed per root, so persisting there is the
route that auto-appears for BOTH daemons with zero wiring change.

Flow:
1. **First tick post-merge/restart**: `apply_health` → `_ensure_field_cached` → store cache empty →
   `health_reporter.ensure_health_field(project_id)` → client reads single-select fields → "Health"
   absent → `createProjectV2Field` once → ids returned → store persists `field_id` + `options.json` +
   `project_id`. Field visible. ZERO manual step.
2. **Every later tick**: store cache hit → no field read; per-card on-change diff via
   `health/last/<item>` → only changed cards get a `set_item_health` mutation.
3. **`kanban init`**: best-effort `ensure_health_field` after `ensure_columns` (failure logged, never
   fatal — the daemon self-heals on tick 1).
4. **Reconcile**: a pre-existing "Health" field with missing options → `update_status_field_options`
   REPLACE preserving existing option ids. A non-single-select "Health" field has no `options` node →
   treated as absent (a duplicate-name create then fails → caught by the whole-step fail-soft).

The client caches the resolved `HealthField` in `self._health_field` (one read per process); the
store cache is the cross-restart cache the daemon reuses every tick.

## 8. On-change discipline + fail-soft contract

- **On-change**: `apply_health` writes a card only when the computed value DIFFERS from the persisted
  `health/last/<item>` value — no per-tick API spam. Health writes happen only on a tick that
  SNAPSHOTTED (`snapshot is None` → early return), which is the only tick a column could have changed;
  the per-card diff suppresses repeats even across snapshots.
- **Fail-soft**: the whole step is wrapped (any create/parse/network error logged WARNING, swallowed);
  each per-card write is INDIVIDUALLY guarded so one bad card never drops the rest. It NEVER raises
  into `tick` or blocks a launch — byte-for-byte the `report_status` posture. Placed as tick Step 4e,
  AFTER `report_status`, so both observability steps are last.

## 9. Multi-root behaviour

Markers live under each daemon's own `<root>/health/`; the field is per-project, ids stored per-root.
A project-rebind guard (`get_health_project_id() != deps.project_id` → `clear_health_markers()` +
`set_health_project_id(...)`) drops stale ids when the registry is re-pointed. Both `~/.kanban` and
`~/.kanban-km` get their own field + own last-written cache. No shared state.

## 10. Risks & reconciliation

- **LOC ceilings**: `actions.py` was AT 1000. The `_NullHealthReporter` body was extracted into
  `app/health_reporter.py` (only the import + field land in `actions.py`), AND `_NullStatusReporter`
  was moved to `app/status_reporter.py` (same pattern), so `actions.py` dropped to ~967. The client's
  ensure/reconcile logic was extracted into `adapters/github/_health.py` (free functions taking the
  injected transport) so `client.py` stays under the ceiling (~975). No module exceeds 1000.
- **Rate-limit interaction**: Health writes are on-change only + on snapshot ticks only, so they add
  at most one field-value write per changed card per snapshot — they respect the §6 move/rate
  discipline and are fail-soft, never blocking a launch.
- **Field-name clash**: a non-single-select "Health" field is treated as absent (see §7); the
  resulting duplicate-name create failure is swallowed by the whole-step fail-soft.

## 11. Test plan

- **Pure** (`tests/core/test_health.py`): table-driven `compute_health` (each state→health, precedence
  WAITING>Blocked / RUNNING>Done, non-default Blocked/Done keys, every output ∈ `STATUS_VALUES`,
  option specs cover the 5 values with palette colours).
- **Adapters** (`tests/adapters/github/test_health_field.py`): the query builder shape; both parsers
  (present / absent / non-single-select / errors); the client `ensure_health_field` (create / existing
  / reconcile-preserving-ids / cached) + `set_item_health` (right mutation + option id; raises on
  errors).
- **Store** (`tests/adapters/test_fs_health_state.py`): get/set round-trip for field_id / options /
  project_id / per-item value; absent → None/`{}`; poison file → degrade; `clear_health_markers`;
  item-id sanitisation confines to `health/last/`; atomic write leaves no temp.
- **App** (`tests/app/test_health_reporter.py`): snapshot-None early return; idempotent provisioning +
  store cache; on-change dedup; running-state mapping; fail-soft (whole step + per card); rebind guard;
  multi-root independent caches.
- **Tick** (`tests/app/test_tick.py`): a snapshotting tick calls `apply_health` (chip write for a
  changed card via a fake reporter); a raising health step does NOT fail the tick.
- **Layering** (`tests/test_layering.py`): unchanged-green.

## 12. Phase gate checklist

- ISOLATED worktree + ISOLATED venv; the live PM2 daemons (editable install from the MAIN worktree)
  untouched, never restarted (the operator merges + redeploys).
- `make check` (ruff + ruff format --check + mypy + pytest + size guard) exit 0.
- `python -c "import kanbanmate"`; `compute_health` / `ProjectHealthReporter` import.
- `make size` confirms NO module > 1000 (actions.py, client.py, tick.py, fs_store.py).
- `docs/features/health-field/DESIGN.md` present + `IMPLEMENTATION.md` row added.
