# anchor — Board repatriation: columns + card positions off Projects v2 — DESIGN

> **Codename**: `anchor` · **Ticket**: #43 (`[helm-pr3]`) · **Type / SemVer**: minor (additive
> subsystem — a new backend behind an existing port, dark-shipped behind a default-off switch) ·
> **Branch**: `feat/anchor` (per-ticket WIP carry on `kanban/ticket-43`).
>
> `anchor` is **PR 3 of the helm config-interface arc**: PR 1 (`helm`, #5/#33) shipped the
> backend-neutral config core + HTTP API; PR 2 (`bridge`) ships the Vue 3 SPA. PR 3 repatriates the
> **board-VIEW state** — columns + per-card placement + intra-column order — into a **native backend
> behind the existing board port**, so the helm/bridge interface hosts the board natively, off
> GitHub Projects v2.
>
> Every claim about the existing engine is grounded against the worktree tree at
> `__version__ = "0.10.0"` (`src/kanbanmate/__init__.py:11`) and cited as `path:line`. Where a
> brainstorm sketch and the source disagree, the **source wins** and the divergence is called out.

---

## §1 — Problem & intent

Today **GitHub Projects v2 _is_ the board view**. A column is a Status single-select option; a
card's placement is its Status field value; intra-column order is GitHub's and is **not exposed by
the public API**. The whole engine reads placement out of one GraphQL call: the production client
maps each item's Status option name into `Ticket.column_key`
(`adapters/github/client.py:205-223`, `_to_ticket`), and the daemon's reconciliation is purely a
column-key comparison (`core/diff.py:44-56`).

`anchor` repatriates the board-VIEW state into a **native backend selected per project by a config
switch**, so:

- the operator can hold **columns + card positions** natively (in `~/.kanban[-km]/`), editable from
  the helm/bridge SPA;
- the SPA gains the one capability GitHub withholds from its API: **intra-column reorder / explicit
  card ordering**;
- nothing on GitHub's forge side moves.

### Stays on GitHub (forge — unchanged)

Tickets are **GitHub Issues**; repos / branches / PRs / CI stay on GitHub; **merge = human-only**
(CLAUDE.md autonomy floor — never weakened here). Only the *view* (columns + positions) repatriates.

### Enabled by the PR-1 `Definition ↔ Binding` split

PR 1 already separated the backend-neutral `Definition` (columns / transitions / defaults,
`core/config_model.py:133-146`) from the GitHub-specific `Binding` (`project`, `option_map`,
`core/config_model.py:109-130`). The `Binding` docstring states the load-bearing intent verbatim:

> "Separating the backend-neutral `Definition` from the GitHub `Binding` is the schema evolution
> that lets PR 3 swap the backend without touching the model." — `core/config_model.py:111-114`

`anchor` swaps the **active board backend** while the neutral `Definition` stays byte-for-byte
identical. All whitelist / guard / advance logic in `core/` is **column-key** logic
(`core/transitions.py`, `core/decide.py`) and is therefore **untouched**.

---

## §2 — Goals / non-goals

### Goals

1. A **`board_backend: github | native`** per-project switch (default `github` → zero behaviour
   change; opt-in per project), mirroring the shipped `ingress` switch (`cli/init.py:121-146`).
2. A **native board store** — a new `BoardStateStore` port + atomic, `flock`-serialised fs adapter
   holding ordered columns, the `item → column` placement map, and a per-column **ordered card
   list**, versioned by a monotonic counter.
3. A **`NativeBoardReader`** that builds a `BoardSnapshot` by **joining** the GitHub issue set
   (identity / open-closed) with the native placement store, and a **combined `cheap_probe`** that
   detects *both* a native move *and* a new/closed GitHub issue.
4. A **`NativeBoardWriter`** implementing `move_card` against the native store, plus the genuinely
   new **`reorder`** capability (set a column's ordered card list / move a card to an index).
5. A **one-way GitHub mirror** (default on) so the GitHub Projects board, the rolling status pill,
   and the Health field keep reflecting reality after cutover.
6. **helm HTTP API** board endpoints (`/api/board/*`: state read, move, reorder) — the contract
   PR 2's SPA consumes (it is being designed in parallel and needs this contract pinned here).
7. A one-shot **`kanban board import`** migration that seeds the native store from the live
   Projects v2 snapshot, idempotent on re-run.
8. Tests against the **real 14-column HYBRID table** (`core/transitions_defaults.py`).

### Non-goals

- **No new authority.** Merge stays human-only; `core/` stays I/O-free; the daemon hot path stays
  `urllib`-only on the GitHub side; the native store is stdlib-only (no new dependency, §6.4).
- **No native ticket store.** Tickets remain GitHub Issues — identity, body, comments, open/closed,
  PRs, CI all stay on GitHub.
- **No GitHub board-VIEW layout repatriation** (grouping / field visibility — not API-exposed).
- **No SPA drag-drop UX** — PR 3 ships the *API + store* the SPA consumes; the UX is PR 2's surface.
- **No abandonment of the GitHub board** (Option B, §7.2 — deferred; the mirror keeps it live).
- **No bidirectional sync engine.** native → GitHub is one-way; a direct GitHub-board move is
  reconciled only on the next `kanban board import` (§5.3, OQ2).

---

## §3 — The 3-PR arc (context)

- **PR 1 — `helm` (#5/#33, shipped).** Config core + HTTP API: the backend-neutral draft model
  (`core/config_model.py`), validator (`core/config_validate.py`), serializer
  (`core/config_serialize.py`), `ConfigService` (`app/config_service.py`), and the loopback HTTP
  API (`http/config_api.py`). The `Definition ↔ Binding` split is here.
- **PR 2 — `bridge` (in design).** The Vue 3 SPA. It already adds a board-mutating "Sync board"
  action over the **column** set (`app/board_provision.py:81-112`, `diff_columns`) and the
  `/api/board/provision` route (`http/config_api.py:440`). `anchor` extends the same `/api/board`
  namespace with placement + reorder.
- **PR 3 — `anchor` (this ticket).** Native board-state backend + the reorder capability + the
  one-way mirror + the import cutover.

---

## §4 — Architecture: a native backend behind the board port

### §4.1 — The board port is already the seam

`anchor` adds **no new port surface on the read/move side** — the existing Protocols are exactly
what a second backend implements:

| Port (in `ports/board.py`) | Methods anchor's native backend must satisfy |
| --- | --- |
| `BoardReader` (`:21`) | `cheap_probe` (`:28`), `snapshot` (`:41`), `issue_state` (`:51`), `issue_context` (`:68`) |
| `BoardWriter` (`:93`) | `move_card` (`:100`), `comment` (`:113`), `list_issue_comments` (`:122`), `update_comment` (`:140`) |

Crucially, **`comment` / `list_issue_comments` / `update_comment` / `issue_state` / `issue_context`
are forge operations** — they read/write GitHub Issues, which stay on GitHub. So the native backend
does **not** re-implement those: it composes the existing `GithubClient` for the forge half and
overrides only **placement** (`cheap_probe`, `snapshot`, `move_card`). This is a **decorator over
`GithubClient`**, not a from-scratch client.

### §4.2 — The composition root is the single switch point

`app/wiring.py:build_deps` (`:112-186`) is the **only** `app` module permitted to name concrete
adapter classes (`wiring.py:1-12`). Today it wires one `GithubClient` instance into six slots:
`board_writer`, `board_reader`, `pull_requests`, `status_reporter`, `health_reporter`, `seeder`
(`wiring.py:144-185`). `anchor` adds the switch HERE and nowhere else:

```python
github = GithubClient(config.token, project_id=config.project_id, repo=config.repo)
if config.board_backend == "native":
    board_store = FsBoardStateStore(Path(store_root))            # §6
    native = NativeBoardBackend(                                  # §4.3
        forge=github,                       # comment / issue_state / issue_context / PR-close
        store=board_store,                  # placement + order authority
        mirror=github if config.board_mirror else None,           # §5
        columns=tick_columns,               # ordered column keys (from columns.yml)
        option_name_for_key=...,            # column-key → GitHub Status option NAME (mirror)
    )
    board_reader = native            # NativeBoardReader half
    board_writer = native            # NativeBoardWriter half
else:
    board_reader = board_writer = github   # today's path, byte-identical
```

`pull_requests`, `status_reporter`, `health_reporter`, `seeder` stay wired to `github` in **both**
modes (they are forge / GitHub-Projects reporters; under `native` the reporters keep working *iff*
the mirror is on — §5, §7.5). `WiringConfig` (`wiring.py:31-93`) gains two defaulted fields so an
old caller is byte-identical:

```python
board_backend: str = "github"   # "github" | "native"
board_mirror: bool = True       # one-way GitHub mirror under native (§5)
```

### §4.3 — `NativeBoardBackend`: decorator that splits by concern

A single adapter class (under `adapters/board/native.py`, a NEW adapter package — `adapters/`
already holds `github/`, `store/`, `workspace/`) satisfying `BoardReader` **and** `BoardWriter` by
composing a forge client + the board store + an optional mirror:

| Method | Under `native` |
| --- | --- |
| `cheap_probe()` | Combined token: native store version ⊕ forge issue probe (§4.4) |
| `snapshot()` | JOIN(forge issue set, native placement) → `BoardSnapshot` (§4.5) |
| `issue_state(n)` | **Delegate to forge** (open/closed is GitHub's) |
| `issue_context(n)` | **Delegate to forge** (body/comments are GitHub's) |
| `move_card(item, key)` | Write native placement (entry column / append to column tail); then mirror (§5) |
| `comment` / `list_issue_comments` / `update_comment` | **Delegate to forge** |
| `reorder(...)` | **NEW** native-only (§4.6) — NOT on the `BoardReader`/`BoardWriter` Protocols |

The `reorder` capability is exposed via a **new dedicated `BoardOrdering` Protocol** (`ports/board.py`),
NOT bolted onto `BoardWriter` (interface segregation — the precedent set by `PullRequests` `:154`,
`ProjectStatusReporter` `:348`, `ProjectHealthReporter` `:421`). Only the helm HTTP API and
`kanban board` CLI call it; the daemon tick never does (order is not an engine input — §4.7).

### §4.4 — Combined `cheap_probe` (the highest-risk change: trigger inversion)

Today the daemon reacts to a **human Status-move on GitHub**: the move bumps the board's item
`updatedAt`, so `GithubClient.cheap_probe` (the 5-newest-items `updatedAt` token,
`client.py:157-165`) changes → `tick` snapshots → `diff` → launch (`app/tick.py:6-7`).

Under `native` the human move surface is **the helm SPA writing the native store**, which does
**not** touch GitHub `updatedAt`. So a `native` `cheap_probe` must fold **two** signals:

```
native_probe = f"{store_version}:{forge_issue_probe}"
```

- **`store_version`** — the native board store's monotonic version counter (§6.2). Bumped on every
  native `move_card` / `reorder` / import. Detects human + agent native moves. A cheap `stat`/read
  (no network).
- **`forge_issue_probe`** — a cheap GitHub probe that changes when an **issue is created or
  closed** (a new card must enter the board; a closed card must reflect). The existing
  `GithubClient.cheap_probe` (`client.py:157-165`) already tracks the 5-newest-items `updatedAt` —
  it is reused as the issue-set signal. (It also fires on a *direct GitHub-board* move; under
  `native` that is harmless — the snapshot JOIN ignores GitHub placement, §4.5/§5.3.)

Equal combined tokens ⇒ board assumed unchanged ⇒ no snapshot (the `BoardReader` contract,
`ports/board.py:28-39`). The `board_backend: github` default keeps every **live daemon
byte-identical** until an explicit per-project opt-in — the central de-risking lever.

**Fast wake.** The helm API, on any native write, bumps the **existing daemon-wake nudge sentinel**
(`IntentStore.nudge_daemon`, `ports/store_intents.py:78`; `adapters/store/fs_intents.py:139`) — the
exact mechanism the cockpit intent queue uses, which the daemon's interruptible inter-tick sleep
already wakes on (`daemon/loop.py:21-27, 89-97`). No new wake path is invented.

### §4.5 — `snapshot()` becomes a JOIN

`GithubClient.snapshot` returns every `ProjectV2Item` with its GitHub Status name as `column_key`
(`client.py:167-223`). The native snapshot is built differently:

1. **Issue set (forge):** list the project's issues with identity + open/closed + body. This reuses
   the forge client's existing item walk (`client.py:167-203` pagination) — but only `item_id`,
   `issue_number`, `title`, `body` are taken from it; **GitHub's Status column is discarded** under
   `native`.
2. **Placement (native store):** for each issue's `item_id`, read its native `column_key`.
3. **JOIN rules:**
   - issue present on GitHub **and** in the store → `Ticket(column_key = store placement)`.
   - issue present on GitHub, **absent** from the store (first sight / freshly created) →
     **register it at the entry column** (the first column in board order, §4.8) and emit it there.
     The registration is an idempotent native write (places at the column tail).
   - issue **closed** on GitHub → reflected (the JOIN reads its closed state via the forge set);
     placement is irrelevant to a closed card (the engine's terminal handling is unchanged).
   - `item_id` in the store but **gone** from GitHub (deleted/archived) → dropped from the snapshot
     (matches today's one-directional `diff`, `core/diff.py:28-31`); the store row is GC'd lazily.

The result is a `BoardSnapshot` (`core/domain.py:84-95`) of `Ticket`s
(`core/domain.py:61-80`) **structurally identical** to the GitHub path — so `diff` / `decide` /
`tick` consume it unchanged.

### §4.6 — The new capability: `reorder` / placement

`reorder` is the value-add GitHub's API cannot express. The `BoardOrdering` Protocol:

```python
class BoardOrdering(Protocol):
    def reorder_column(
        self, column_key: str, ordered_item_ids: list[str], if_version: int | None = None
    ) -> int: ...
    def place_card(
        self, item_id: str, column_key: str, index: int | None = None, if_version: int | None = None
    ) -> int: ...
```

- `reorder_column` sets a column's full ordered `item_id` list (the SPA drag-reorder persist;
  rejects an `item_id` not currently in that column, and any duplicate / missing id, fail-loud).
- `place_card` moves a card to `(column, index)` — `index=None` appends to the tail. A cross-column
  `place_card` is the placement half of a move; the engine's `move_card` (which carries no index)
  always appends to the destination tail.
- Both take an optional `if_version` optimistic-concurrency precondition (§6.2) — when supplied and
  stale, the store rejects the write (fail-loud, surfaced as `409` by the HTTP layer, §10).
- Both return the new store **version** (§6.2) so the caller can confirm the write landed and the
  SPA can detect concurrent edits.

**Order is never mirrored to GitHub** (no representation, §5) and is **never an engine input**
(§4.7).

### §4.7 — Why order is safe (OQ3, decided: native-only view metadata)

`core/diff.diff` (`:19-57`) keys persisted state and the snapshot by **`item_id`** and compares
**`column_key` only** (`diff.py:44-48`) — it never reads any position-within-column. `BoardSnapshot`
/ `Ticket` carry **no order field** (`core/domain.py:61-95`). Therefore intra-column order is, by
construction, invisible to `tick → diff → decide`. **Decision (OQ3): order is pure native view
metadata** — never sent to GitHub, never fed to the engine. Adding it requires **no** change to
`core/domain.py` (the order lives only in the native store, §6.1), keeping the pure core untouched.

### §4.8 — The entry column

The "entry column" a new issue lands in is the **first column in board order** — the same column
`kanban seed` places freshly-added items into today via `Seeder.move_card` (`ports/board.py:333-345`;
the genesis board's first column is `Backlog`). It is resolved from the ordered column list the
native store holds (seeded from `columns.yml` order at import, §6.1 / §8), not hard-coded.

---

## §5 — The mirror (OQ1, decided: one-way GitHub mirror, default on)

**Decision (OQ1 = A): native-authoritative + one-way GitHub mirror, default on**
(`WiringConfig.board_mirror = True`, §4.2). After cutover the native store is the **authority** for
placement; on every native placement change the backend **also** writes the GitHub Status option so
the familiar GitHub Projects board, the rolling status pill (`ProjectStatusReporter`,
`ports/board.py:348`), and the Health field (`ProjectHealthReporter`, `ports/board.py:421`) keep
reflecting reality.

### §5.1 — How the mirror writes

The mirror reuses the **existing** GitHub move path verbatim: `GithubClient.move_card`
(`client.py:226-249`) resolves the destination via `field.options[column_key]`
(`client.py:240-245`) where `field.options` is keyed by the Status option **display NAME** (the
`ensure_columns` return contract is `{column_name: option_id}`, `ports/board.py:255-257`; the
cockpit drain already calls `move_card(item_id, to_column.name)`, `app/intents.py:297`). So the
native backend maps its `column_key` → the GitHub option **name** via the `option_name_for_key`
function threaded at wiring (§4.2), derived from the column model (`Column.key`/`Column.name`,
`core/domain.py:56-58`).

### §5.2 — Mirror failure is fail-soft

A mirror write error is **observability, never a board-authority failure**: the native store is
already updated (authority), so a transient GitHub error is logged and swallowed (mirroring the
reporters' fail-soft call-site contract, `ports/board.py:362-365, 433-435`). The native placement
remains correct; the GitHub board lags until the next successful mirror / `kanban board import`.

### §5.3 — Drift containment (OQ2, decided: helm is the sole move surface)

native → GitHub is **one-way**. **Decision (OQ2): helm/bridge (+ the agent intent queue) is the
sole move surface** under `native`. A human moving a card *directly on the GitHub Projects board*
is **not** treated as a trigger (the snapshot JOIN ignores GitHub placement, §4.5); the drift is
reconciled only on the next operator-run `kanban board import` (§8). This deliberately avoids a
bidirectional-conflict engine (a non-goal, §2). The combined `cheap_probe`'s forge half (§4.4) may
*fire* on such a direct move, but the resulting snapshot re-asserts native placement (idempotent —
no spurious transition, since `diff` compares against native-derived persisted state).

---

## §6 — The native board store (atomicity is the hard part)

### §6.1 — On-disk shape

One JSON document per project at `<store_root>/board.json`, where `store_root` is the per-project
sub-root the wiring already computes (`<root>/projects/<safe(project_id)>` for N>1, else the flat
`<root>`, `wiring.py:127-138`):

```jsonc
{
  "version": 7,                                  // monotonic counter (§6.2)
  "columns": ["Backlog", "Brainstorming", ...],  // ordered column KEYS (seeded from columns.yml order)
  "placement": { "<item_id>": "InProgress", ... },// item_id → column key (authority)
  "order": { "InProgress": ["<item_id>", ...], ...}// per-column ordered item_id list (new capability)
}
```

`placement` and `order` are kept consistent by every write: an `item_id` appears in exactly one
column's `order` list iff it maps to that column in `placement`. The `columns` list is the ordered
column SET (the entry column is `columns[0]`, §4.8); it is the native authority for column order
(the definition's `columns.yml` seeds it at import and remains the editable source — §7.3).

### §6.2 — Versioning

`version` is a monotonic integer bumped on **every** mutating write (`move_card`, `place_card`,
`reorder_column`, import). It is what `cheap_probe` reads (§4.4) and what the API returns so the SPA
can detect a concurrent edit (optimistic-concurrency: a write may carry an `if_version` precondition
the store checks under the lock, rejecting a stale write — fail-loud `409`).

### §6.3 — Dual-writer atomicity (the named risk)

The store has **two concurrent writers**: the daemon (engine-driven `move_card` + drained agent
intents) and the helm HTTP API (human moves / reorders). It reuses the **proven** discipline already
in the codebase, NOT a new mechanism:

- **`flock` serialisation** — every read-modify-write holds an exclusive advisory `flock` for the
  duration, exactly as `FsStateStore._lock` does (`adapters/store/fs_store.py:941-965`). The
  read-bump-write of `version` happens **inside** the lock so two racing writers cannot both read
  version 7 and both write 8.
- **Atomic replace** — the new `board.json` is written to a temp file in the same directory,
  `flush` + `fsync`, then `os.replace` (same filesystem, atomic rename), exactly as
  `FsStateStore.save` (`fs_store.py:192-205`) and `ConfigService._write_temp` / `save`
  (`app/config_service.py:179-206, 143-145`) do. A concurrent reader never observes a torn file.

### §6.4 — Port + adapter placement, no new dependency

- **Port:** a new `ports/store_board.py` defining `BoardStateStore` (read `load()` → the document;
  the mutating `place_card` / `reorder_column`, each bumping `version` under the lock — a no-index
  `place_card` is the move-to-tail the backend's `move_card` calls, §7.2) **plus** the
  `BoardOrdering` Protocol re-exported for the writer side. `core/` is untouched (the store is I/O —
  it lives in `ports`/`adapters`, never `core`; the layering guard forbids `core → adapters`).
- **Adapter:** `adapters/store/fs_board.py` implementing it with stdlib `json` + `fcntl.flock` +
  `os.replace` — the **same stdlib-only** footprint as `fs_store.py`. **No new third-party
  dependency** (the `ui` extra's `fastapi`/`uvicorn` are unchanged, `pyproject.toml:28-30`; nothing
  is added to `pyproject.toml` or `.github/workflows/pr.yml`).

---

## §7 — Reconciling with the existing ports (no new authority)

### §7.1 — `Seeder` splits by concern (forge vs view)

`Seeder` (`ports/board.py:183`) mixes forge ops and one view op. Under `native`:

| `Seeder` method | Under `native` |
| --- | --- |
| `create_issue` (`:275`), `ensure_labels` (`:260`), `update_issue_body` (`:289`), `close_issue` (`:298`), `fetch_issue` (`:306`), `ensure_project` (`:200`), `link_to_repo` (`:216`), `update_project_description` (`:228`) | **GitHub** (forge / project bootstrap — unchanged) |
| `add_to_project` (`:321`) | GitHub adds the item (the issue must exist on the GitHub project for the forge item id) **and** the native backend registers the new `item_id` at the entry column (§4.8) |
| `ensure_columns` (`:243`) | Reconcile the **native** column list (the `columns` array, §6.1); under mirror, also `ensure_columns` on GitHub so the Status options track (the existing `app/board_provision.provision_board` path, `:81-112`) |
| `move_card` (`:333`) | Native placement write (+ mirror), identical to `BoardWriter.move_card` |

The seeder slot in `build_deps` stays the `GithubClient` (`wiring.py:182`) for the forge half; the
*placement* half of `add_to_project` is handled by `NativeBoardBackend.snapshot`'s first-sight
registration (§4.5), so `kanban seed` needs no special-casing — a freshly-added issue simply
appears in the entry column on the next snapshot.

### §7.2 — `BoardWriter.move_card` — single audited write path preserved

The agent-move guard ("agents may only move to non-triggering columns") is **column-key logic** —
backend-agnostic, unchanged. The single audited write path is preserved: cockpit/agent
`kanban-move` → intent queue → daemon drains → `deps.board_writer.move_card`
(`app/intents.py:297, 372`). Under `native`, `board_writer` is the `NativeBoardBackend`, so the
drained move writes native placement (+ mirror) through the **same** call site — no second write
path is introduced.

### §7.3 — Column definition stays in `columns.yml`

The `columns` array in `board.json` (§6.1) is **seeded from `columns.yml` order** at import and
kept in sync by `ensure_columns` (§7.1). `columns.yml` (parsed by `core/columns.load_columns`) and
the helm config draft (`Definition.columns`, `core/config_model.py:144`) remain the **editable
source of column identity**; the native store holds the *runtime* column order + placement. The
existing column-set diff `core/columns_diff.diff_columns` (`:52-109`, classifying
add/rename/reorder/remove) is the model the SPA already uses for column edits; `anchor` adds the
analogous **card** reorder at the placement layer (§4.6).

### §7.4 — `PullRequests` unchanged

The Cancel teardown's PR-close port (`ports/board.py:154-180`) is a pure forge op — wired to
`github` in both modes (`wiring.py:153`). Untouched.

### §7.5 — Status-pill + Health-field fate (OQ5, decided: keep, via the mirror)

**Decision (OQ5, tied to OQ1=A):** under the mirror they **keep working unchanged**. The
`ProjectStatusReporter` (`ports/board.py:348`) and `ProjectHealthReporter` (`ports/board.py:421`)
write to GitHub Projects; with the mirror on, the GitHub Status reflects native placement, so the
rolling pill + Health chips remain accurate. They stay wired to `github` in both modes
(`wiring.py:174, 178`). (Under a future Option-B "abandon" they would be disabled/rehomed — out of
scope here.)

---

## §8 — Migration / cutover (OQ4, decided: per-project, operator-run, dark-ship)

**Decision (OQ4): per-project `board_backend` switch + a one-shot operator-run
`kanban board import`, default `github`.** A new CLI sub-app `kanban board` (sibling of
`kanban config` / `kanban serve`):

```
kanban board import   [--project <id>] [--root <path>] [--dry-run]
kanban board status   [--project <id>]          # show the native store summary
```

`import` is the cutover seeder:

1. Read the **live Projects v2 snapshot** via `GithubClient.snapshot` (`client.py:167-203`).
2. Seed `board.json`: `columns` ← the board's Status options in `columns.yml` order; `placement`
   ← each card's current Status `column_key`; `order` ← per-column, items sorted by the GitHub
   `updatedAt` already fetched (a stable, deterministic initial order — refined later by SPA
   reorder).
3. Write atomically (§6.3) with `version = 1` (or bump if re-run).

`import` is **idempotent**: a re-run reconciles `placement` against the live GitHub Status (the
drift-reconcile path for OQ2, §5.3) and preserves any existing native `order` for cards still in the
same column (only newly-seen cards are appended). The operator then flips `board_backend: native`
for that project in `projects.json` and restarts the daemon. **Per-project**, so one board can pilot
`native` while the other stays `github` (`ProjectEntry.board_backend`, §9).

---

## §9 — Registry & config surface

`ProjectEntry` (`cli/init.py:88-147`) gains **one** field, defaulted so an OLD-shaped
`projects.json` loads unchanged via the established `.get(..., default)` back-compat pattern
(`cli/init.py:213-224`):

```python
board_backend: str = "github"   # "github" | "native"  — per-project, default github
```

Loaded in `_load_registry` as `board_backend=val.get("board_backend", "github")`
(`cli/init.py:206-227`, same shape as `ingress=val.get("ingress", "webhook")` `:223`). The
daemon's `_wiring_from_registry` (`daemon/registry_wiring.py:93`) threads it onto
`WiringConfig.board_backend` (§4.2), exactly as it threads `ingress` today. The mirror toggle
(`board_mirror`) defaults on and is a daemon-level `config.yml` default overridable per project on
the same pattern — but is **not** an `init`-time prompt (operators opt out rarely; default-on is the
safe path per OQ1).

`projects.json` example (one project piloting native):

```jsonc
{
  "PVT_...kanban": { "...": "...", "ingress": "webhook", "board_backend": "native" },
  "PVT_...scraper": { "...": "...", "ingress": "webhook" }        // board_backend defaults to "github"
}
```

---

## §10 — The helm HTTP API contract (the PR-2 dependency)

PR 2's SPA is being designed in parallel, so the board endpoints are pinned **here**. They extend
the existing FastAPI app (`http/config_api.py`) under the `/api/board/*` namespace (joining
`/api/board/provision`, `config_api.py:440`), select the project with the same `?project=<id>` query
param the config routes use (`config_api.py:316-409`), and are loopback/auth-gated identically (the
SPA bridge's auth, `config_api.py:65-99`). Mutating endpoints **bump the daemon nudge** (§4.4) after
a successful write. The complete set:

| Verb & path | Body / params | Returns | Notes |
| --- | --- | --- | --- |
| `GET /api/board/state` | `?project=<id>` | `{version, columns[], cards: [{item_id, issue_number, title, column_key, index}]}` | The JOINed snapshot (§4.5) projected with per-card index from `order` (§6.1) |
| `POST /api/board/move` | `{item_id, to_column, if_version?}` | `{version}` | Cross-column move → native `place_card(tail)` + mirror (§5); column-key validated against `columns` |
| `POST /api/board/reorder` | `{column_key, ordered_item_ids[], if_version?}` | `{version}` | `reorder_column` (§4.6); native-only, NOT mirrored |
| `POST /api/board/place` | `{item_id, column_key, index, if_version?}` | `{version}` | `place_card` at an explicit index (§4.6) |
| `POST /api/board/import` | `{project, dry_run?}` | `{version, summary}` | Server-side `kanban board import` (§8) for the SPA "Repatriate" action |

Error contract (mirrors the config routes' `ValueError → 400`, `config_api.py:337-356`):
- unknown `column_key` / `item_id`, or an `item_id` not in the named column → **`400`** (fail-loud);
- stale `if_version` → **`409`** (optimistic-concurrency, §6.2);
- `board_backend != "native"` for the selected project → **`409`** (the board is not repatriated;
  move/reorder are native-only — the GitHub path uses `/api/board/provision`).

The schema route (`/api/schema`, `config_api.py:557`) gains the `board.json` JSON Schema so the SPA
validates client-side.

---

## §11 — Module map (new + touched)

**New:**

- `ports/store_board.py` — `BoardStateStore` + `BoardOrdering` Protocols (§6.4).
- `adapters/store/fs_board.py` — `FsBoardStateStore` (stdlib `json` + `flock` + `os.replace`, §6.3).
- `adapters/board/__init__.py`, `adapters/board/native.py` — `NativeBoardBackend` decorator (§4.3).
- `app/board_import.py` — the `import` shell (snapshot → seed store; idempotent reconcile, §8).
- `cli/board.py` — the `kanban board {import,status}` sub-app (§8).
- `http/board_routes.py` — the `/api/board/{state,move,reorder,place,import}` routes (§10), mounted
  into the existing app like `http/monitor_routes.py` (`config_api.py:554`).
- `docs/features/anchor/plan/` — the phased plan (`/implement:plan`).

**Touched:**

- `ports/board.py` — add the `BoardOrdering` Protocol (interface-segregated, §4.3).
- `app/wiring.py` — the `board_backend` switch in `build_deps` (`:112-186`) + the two `WiringConfig`
  fields (`:71-93`).
- `cli/init.py` — `ProjectEntry.board_backend` (`:88-147`) + `_load_registry` (`:194-227`).
- `daemon/registry_wiring.py` — thread `board_backend` onto `WiringConfig` (`:93`).
- `cli/__init__.py` / entrypoint — register the `board` sub-app.
- `IMPLEMENTATION.md`, `ROADMAP.md` — tracker rows + mark helm PR 3 implemented.

`core/` is **not** in the touched list — the whole point of the `Definition ↔ Binding` split (§1).

---

## §12 — Testing strategy

Place tests mirroring the repo's `tests/<layer>/` layout (never a flat root). Every assertion
compares a genuinely-produced, non-trivial value against a real column **key**.

1. **`fs_board` store (adapter):** round-trip a `board.json`; `version` monotonic across writes;
   `flock` serialisation (a concurrent write sees a bumped version, no lost update — drive two
   writers through the lock); `place_card`/`reorder_column` reject an unknown / out-of-column /
   duplicate `item_id` (fail-loud); torn-write safety (interrupt before `os.replace` leaves the
   prior file intact).
2. **`NativeBoardReader.snapshot` (JOIN):** with a fake forge (issue set incl. one closed + one
   not-yet-in-store) and a seeded store → assert the produced `BoardSnapshot.tickets` carry the
   **native** `column_key` (NOT the fake's GitHub Status), the new issue lands in the **entry
   column** (`columns[0]`), and a store-only/GitHub-gone `item_id` is dropped. Use the **real
   14-column HYBRID** column set from `core/transitions_defaults` so keys are genuine.
3. **Combined `cheap_probe`:** a native move bumps the token with GitHub `updatedAt` frozen; a
   GitHub issue create/close bumps it with `version` frozen; neither changing ⇒ token stable.
4. **`move_card` + mirror:** under `native`, a move writes native placement AND calls the forge
   `move_card` with the **mapped option NAME** (assert the fake forge received the real Status
   name, not the key); a mirror error is swallowed and native placement still landed (fail-soft,
   §5.2).
5. **Engine integration:** drive `tick` (`app/tick.py`) with the `NativeBoardBackend` over fakes
   through a full `cheap_probe → snapshot → diff → decide` cycle on the HYBRID table; assert the
   SAME transitions/actions the GitHub path produces (order never affects the verdict, §4.7).
6. **`board_backend: github` default — back-compat:** a `WiringConfig`/`ProjectEntry` without the
   new fields wires the `GithubClient` into both board slots, byte-identical to today (the
   live-daemon safety guarantee).
7. **HTTP routes (§10):** `state` shape; `move`/`reorder`/`place` happy-path + `400` (bad key/id) +
   `409` (stale `if_version`, and `board_backend != native`); each successful mutation bumps the
   nudge. Any assertion on rendered/CLI output is terminal-width/ANSI-independent (force a wide
   width + strip ANSI, or assert on the parsed JSON).
8. **`kanban board import` (§8):** seeds `board.json` from a fake snapshot; idempotent re-run
   reconciles placement + preserves existing order; `--dry-run` writes nothing.
9. **Layering guard** (`tests/test_layering.py`): the new `ports`/`adapters`/`app` modules respect
   downward-only imports; `core/` gains no new import.

---

## §13 — Durable cross-stage carry

This design is committed to the per-ticket WIP branch (`kanban/ticket-43`) as
`docs(anchor): design` so the `/implement:plan` and `/implement:create-branch` stages (each in a
fresh worktree sharing the same `.git`) see it without a push (the hybrid-flow durable-carry
mechanism). The `design` marker on the ticket records the **repo-relative** path
`docs/features/anchor/DESIGN.md`.

---

## §14 — Open questions — resolved

All five brainstorm open questions are **decided** in-design (autonomous stage; the brainstorm
recommendations are sound and are adopted). Re-opening any of these is an operator override, not a
plan gap:

- **OQ1 — Mirror vs abandon → (A) one-way mirror, default on** (§5). Safe, incremental; GitHub
  board + pill + Health stay live.
- **OQ2 — Direct GitHub-board human moves → helm is the sole move surface** (§5.3); a direct GitHub
  move is reconciled only on `kanban board import`. No bidirectional engine.
- **OQ3 — Intra-column order → native-only view metadata** (§4.7), proven safe by `core/diff.py`
  reading `column_key` only. No `core/domain.py` change.
- **OQ4 — Cutover → per-project `board_backend` switch + one-shot operator-run
  `kanban board import`, default `github`** (§8, §9). Dark-ship / opt-in.
- **OQ5 — Status-pill + Health-field → keep, via the mirror** (§7.5), tied to OQ1=A.

---

## §15 — Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| **Trigger inversion** (§4.4) — a native move not detected, or the GitHub-only path regressed | `board_backend: github` **default** keeps every live daemon byte-identical (opt-in only); combined `cheap_probe` folds native `version` ⊕ forge issue probe; the helm API bumps the existing nudge for sub-second wake; back-compat test (§12.6) |
| **Dual-writer atomicity** (§6.3) — daemon ⨯ helm API lost update | Reuse the proven `flock` + temp-file + `os.replace` discipline (`fs_store.py:941-965, 192-205`); read-bump-write of `version` inside the lock; optimistic `if_version` `409` |
| **Mirror drift** (§5.3) — a human moves on GitHub directly | One-way mirror; helm is the sole move surface (OQ2); reconciled on `kanban board import`; the JOIN ignores GitHub placement so no spurious transition |
| **Mirror write failure** (§5.2) | Fail-soft — native authority is already updated; logged + swallowed; GitHub lags until the next mirror/import |
| **Snapshot completeness** (§4.5) — a new GitHub issue missed | The forge issue walk reuses `GithubClient.snapshot` pagination (`client.py:185-200`); first-sight registration is idempotent |
