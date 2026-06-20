# DESIGN — `helm`: KanbanMate Configuration Interface

> **Status:** prepared (ahead-of-time, not yet implemented). Authored while `genesis`
> (PR #1) is pending human merge. This is a roadmap preparation artifact under
> `docs/superpowers/roadmap/helm/`; it will be moved to its canonical path by
> `/implement:feature helm` once `genesis` merges.

**Codename:** `helm`
**Type:** minor (new, additive subsystem; no change to the daemon hot-path)
**Provenance of decisions:** converged operator brainstorm (2026-06-09) — see §2.

---

## 1. Purpose & scope

`helm` is a **configuration interface** for the KanbanMate pipeline. Today the pipeline
lives in two hand-edited YAML files (`transitions.yml` + `columns.yml`); `helm` gives the
operator a guided way to **author, validate, and persist** that pipeline, and — over three
staged PRs — grows into a local surface that can eventually **host the kanban board itself**.

It is delivered in **three independent PRs** (§9). This document designs the **full arc** so
the three steps compose coherently; the accompanying `plan/` covers **PR 1 only** (the
headless config core + a local HTTP API). PRs 2 and 3 get their own branch/plan later via
`/implement:feature`.

### In scope (the arc)

- **PR 1 — Config core + HTTP API.** A backend-neutral, headless config model + validator +
  serializer, exposed over a **local HTTP API** (and a thin CLI). Round-trips with the
  existing YAML loaders. A JSON Schema for editor-guided editing falls out for free.
- **PR 2 — Web interface (Vue.js).** A local web UI consuming the PR-1 HTTP API: a visual
  pipeline builder (choose/order columns, configure carrier transitions, behaviors, agent
  mode, validate, save).
- **PR 3 — Board repatriation.** A native board-state adapter behind the board port so the
  interface hosts columns + card positions. **Tickets remain GitHub Issues**; GitHub keeps
  repos, issues, and PRs.

### Out of scope (permanently or for this arc)

- Replacing GitHub as the **code forge** (repos / branches / PRs / CI). The agent always
  pushes and opens PRs on GitHub; **merge stays human-only** (see §8, §10).
- A native **ticket store**. Tickets are GitHub Issues throughout the arc; `helm` only
  _surfaces and pilots_ them (PR 3).
- Configuring the GitHub **board-view layout** (grouping field, column visibility) — not
  exposed by the GitHub API (§9, PR 3 caveats).
- Multi-user / hosted deployment, auth/RBAC. `helm` is a **local, single-operator** tool
  bound to loopback.

---

## 2. Motivation & the GitHub-native dead end

The pipeline model is expressive but YAML-only: per-`(from,to)` transitions, wildcard
sources/destinations, large multiline prompts with `{{placeholders}}`, fail-loud semantics.
Hand-editing is error-prone and the failure mode is a daemon crash _at launch time_, not at
edit time.

The first instinct — "configure it through GitHub's own UI" — was investigated and
**invalidated** by an API study (2026-06-09). Summary of why GitHub cannot host this
configuration natively:

- **No transition concept.** A Projects v2 board is a single-select `Status` field; there is
  no first-class edge/transition object between two option values. Transitions are inferred
  client-side by diffing the persisted status against the snapshot.
- **Per-column ≠ per-`(from,to)`.** Two transitions can land in the same column with
  _different_ prompts (e.g. `PRCI→InProgress` carries a fix-CI prompt, `PrepareFeature→
InProgress` carries the implement prompt). Single-select **option descriptions** are
  per-column, so they cannot represent the per-pair model.
- **No native automation runs code.** Built-in Projects automations only mutate fields
  (set Status, close/reopen, auto-add, auto-archive). The `projects_v2_item` event is an
  **org-level webhook only**, _not_ an Actions `on:` trigger — so GitHub cannot launch the
  agent on a card move. This _confirms_ KanbanMate's "no webhook, no n8n" polling design.

Therefore a **bespoke configuration interface** is the retained path. The operator's
explicit goal: a visual builder that produces a correct `transitions.yml`, where the UI is
**complete** (not partial/awkward) — otherwise it loses its point.

---

## 3. Architecture

`helm` slots into the existing hexagonal architecture without bending it. Import direction
stays **downward only**.

```
            ┌─────────────────────────────────────────────────────────┐
  PR 2  ───▶│  web/ (Vue.js SPA, local)  ── HTTP ──▶                   │
            └─────────────────────────────────────────────────────────┘
  PR 1      cli/ · http/ (FastAPI entrypoint)  ──▶  app/ (config service) ──▶ core/ (pure:
                                                     ▲                          config model,
                                                     └── ports/ (Protocols)     validator,
                                                          ▲                     serializer)
  PR 3                                 adapters/board ────┘  (github · native)
```

Three layering facts that make the arc cheap:

1. **`core/` already takes YAML _strings_.** `load_transitions(yaml_text: str)` and
   `load_columns(yaml_text: str)` are pure functions over strings (a deliberate divergence
   from the PoC's path-based loader, enforced by the layering guard). Feeding them a string
   built by the UI vs. read from disk is identical — **no `core/` I/O is introduced**.
2. **The HTTP API is an _entrypoint_, not an adapter** (the load-bearing layering fix). It
   imports `app.config_service`, so it CANNOT live under `adapters/` — `tests/test_layering.py`
   forbids `adapters → app`. It is therefore homed as a top-level entrypoint
   (`src/kanbanmate/http/`, sibling to `cli/`/`daemon/`/`bin/` — the un-constrained entrypoint
   tier in the layering guard's `FORBIDDEN` table). It is started on demand via the
   `kanban config serve` CLI command. It must **not** pull web dependencies into the daemon
   hot-path (which stays `urllib`-based): FastAPI ships as an **optional extra**
   (`pip install -e ".[ui]"`), and a **new runtime test** (not the static guard) imports
   `kanbanmate.daemon` and asserts FastAPI was not transitively imported.
3. **The board is already behind a port.** Replacing "GitHub as board" (PR 3) is a _new
   adapter_, not a rewrite — the daemon consumes a board snapshot + emits moves through the
   port regardless of who implements it.

### 3.1 New modules (PR 1)

| Module                        | Layer       | Responsibility                                                                                                                                                                     |
| ----------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `core/config_model.py`        | core (pure) | The **editable** pipeline model (mutable draft) + the pipeline-definition ↔ backend-binding split (§4).                                                                            |
| `core/config_serialize.py`    | core (pure) | `render_pipeline(draft) -> yaml` for transitions **and** columns. Generalizes today's `render_transitions_yaml` (which renders the default 20-entry flow).                         |
| `core/config_validate.py`     | core (pure) | Structural + semantic validation (§5) and the **move-resolution simulation** (§5.3). Reuses the authoritative loaders as a validation oracle. Owns the new value objects (§3.1.a). |
| `app/config_service.py`       | app         | Imperative shell: takes **resolved** config paths, validates a proposed draft, writes atomically (temp→rename), seeds-from-default. Owns `ConfigInvalid` (§3.1.a).                 |
| `http/app.py` (FastAPI)       | entrypoint  | Local HTTP surface (§7). Imports `app.config_service` → **entrypoint, not adapter** (layering: `adapters → app` is forbidden). Optional `[ui]` extra. Transport only.              |
| `cli` `config` sub-app        | cli         | `kanban config get \| validate \| render \| serve` — a Typer **sub-app** (`add_typer`), thin wrappers over `app/config_service`.                                                   |
| `assets/pipeline.schema.json` | asset       | JSON Schema for `transitions.yml`/`columns.yml` (editor-guided editing). Packaged via `assets/*.json` package-data (§5.4).                                                         |

#### 3.1.a New value objects (JSON-friendly, owning module)

These small records cross the core→app→http boundary, so they are plain dataclasses
(JSON-serializable: `str`/`int`/`bool`/`list`/`dict`/`None` only — no frozen runtime
objects leak):

| Value object         | Owning module             | Shape / purpose                                                                                                               |
| -------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `Finding`            | `core/config_validate.py` | `Finding(code: str, message: str, locus: dict \| None)` — one validation result with a best-effort field locus (§5.2).        |
| `ValidationResult`   | `core/config_validate.py` | `ValidationResult(valid: bool, errors: list[Finding], warnings: list[Finding])` — the `validate()` return.                    |
| `ResolvedTransition` | `core/config_validate.py` | The JSON-friendly projection of a matched transition (the move-resolution simulation result, §5.3); `None` = not whitelisted. |
| `ConfigInvalid`      | `app/config_service.py`   | `ConfigInvalid(findings: list[Finding])` — the exception `write()` raises when validation fails before any disk write (§4.3). |

### 3.2 New port (PR 3, designed now) — and its overlap with the existing `Seeder`

`ports/board.py` already abstracts board reads/moves for the daemon AND already carries a
**`Seeder`** Protocol (genesis phases 21/33) used solely by the per-repo installer tier
(`kanban init` / `kanban seed`). `Seeder` already does most of column provisioning:
`ensure_project` / `link_to_repo` / `ensure_columns(project_id, columns) -> {name: option_id}`
(**preserving existing option ids** so cards are never orphaned) / `ensure_labels` /
`create_issue` / `add_to_project` / `move_card`. PR 3 must therefore **reconcile** with it
rather than introduce a parallel surface:

- **`Seeder` already owns columns + issues + labels** (the one-shot `init`/`seed` lifecycle).
  Its `ensure_columns` is the idempotent option-set shaper PR 3 needs for "create/rename
  columns".
- PR 3's only genuinely **new** capabilities are **reorder** and **per-card placement**
  (`updateProjectV2ItemPosition` + `afterId`), which `Seeder` lacks.

**Decision:** PR 3 does NOT add a competing `BoardProvisioner`. It **extends `Seeder`** with the
two missing operations (or splits them into a small `BoardOrdering` Protocol the same
`GithubClient` satisfies), so the existing `Seeder.ensure_columns` **subsumes** the column
provisioning and the daemon-side board adapter gains only ordering:

```python
# Added to the existing Seeder (or a sibling BoardOrdering the same client satisfies):
def reorder_columns(self, project_id: str, ordered_keys: Sequence[str]) -> None: ...
def place_item(self, project_id: str, item_id: str, after_item_id: str | None) -> None: ...
```

GitHub adapter implements these now (PR 3 §9 caveats); a native adapter implements the whole
seeding + ordering surface later. (Detailed at §9, PR 3.)

---

## 4. The config model (backend-neutral)

The single most important design decision for the extensibility goal: **separate the
pipeline definition from the backend binding.**

```
PipelineConfig
├── definition            # 100% backend-neutral — portable to any board backend
│   ├── columns: [ ColumnDef(key, column_class) ]   # ordered; column_class ∈ {'reactive','inert'}
│   ├── transitions: [ TransitionDef(... ) ]        # the per-(from,to) edges
│   └── defaults: Defaults(concurrency_cap, move_rate_limit_per_hour)
└── binding               # adapter-specific — how the definition maps onto a backend
    └── github: GithubBinding(project, column_names: {key: "GitHub label"})
```

`ColumnDef.column_class` is a **string** mirroring the core `ColumnClass` enum values —
`'reactive'` (`action: teardown`, the Cancel column) or `'inert'` (everything else) — NOT a
bool. This keeps the draft 1:1 with `core/domain.ColumnClass` (whose `.value`s are exactly
`"reactive"`/`"inert"`) so a third class never forces a model migration, and matches how
`load_columns` derives the class from the `action:` flag.

- **`definition`** carries **zero** GitHub-isms. A `TransitionDef` is exactly the runtime
  transition fields, all UI-friendly:

  | Field             | Type                             | UI widget                      | Notes                                   |
  | ----------------- | -------------------------------- | ------------------------------ | --------------------------------------- |
  | `from_`           | `str \| list[str] \| "*"`        | multi-select + "any"           | cartesian-expanded at serialize         |
  | `to`              | `str \| list[str] \| "*"`        | multi-select + "any"           | cartesian-expanded at serialize         |
  | `profile`         | enum `docs/prepare/dev/check`    | dropdown                       | required on any prompt-bearing row (§5) |
  | `prompt`          | `str \| None` (large, multiline) | textarea + placeholder palette | makes the row a _launch_                |
  | `script`          | `str \| None`                    | path field                     | gate (with prompt) or action (without)  |
  | `advance`         | `stop \| auto:<col>`             | radio + column dropdown        | fast-forward on success                 |
  | `on_fail`         | `"" \| move:<col> \| rollback`   | dropdown + column dropdown     | rollback / re-trigger on fail           |
  | `permission_mode` | enum (5 values)                  | dropdown                       | `bypass*` banned (§5, §8)               |

- **`binding`** holds `project: owner/repo` and the `key → GitHub label` map (today's
  `columns.yml` `name` field). Explicitly: each `Column.name` produced by `load_columns`
  projects into `binding.github.column_names[key]` (the GitHub-facing label), while the
  backend-neutral `ColumnDef` in `definition` carries only `key` + `column_class` — the `name`
  is a binding concern, never a definition concern. When a native board adapter arrives
  (PR 3), it gets its own binding (e.g. a local board id); the `definition` is untouched.

> **Why this split now (PR 1):** it is the one schema evolution the extensibility goal
> _requires_. The current YAML mixes `project:` + column `name:` into the same documents as
> the neutral pipeline; isolating them makes the pipeline rejouable on any backend and makes
> the UI's "pipeline" view backend-agnostic. The on-disk YAML stays compatible — the split
> is structural in the model, and the serializer still emits valid `transitions.yml` +
> `columns.yml` (see §6 for back-compat).

### 4.1 Editable draft vs frozen runtime objects

The runtime model (`TransitionConfig`, `Column`) is **frozen** and produced by the loaders.
`helm` needs a **mutable draft** to edit. The draft is a plain, JSON-serializable structure
(dataclasses with `list`/`dict`) that maps 1:1 to the YAML. The round-trip is:

```
disk YAML ──load──▶ draft ──edit──▶ draft ──validate──▶ draft ──render──▶ YAML ──write──▶ disk
                                                  │
                                                  └─ validation oracle = the real loaders
```

This deliberately **reuses the authoritative loaders as the validation oracle** (§5.1): a
draft is valid iff `load_transitions(render(draft))` and `load_columns(render(draft))`
succeed _and_ the extra UI checks pass. No second, drifting parser is introduced.

> **`from_loaded` re-parses the RAW YAML — the loaders are the oracle, not the source.**
> A subtlety the implementation MUST honour: `TransitionConfig` exposes **no transition list**
> — only `get(from, to)`, `launch_target_columns()`, and the private `_explicit`/`_wild_to`/
> `_wild_from` lookup tables. So `PipelineConfig.from_loaded` **cannot** reconstruct the
> `TransitionDef` rows from a `TransitionConfig`; it must re-parse the **raw `transitions.yml`
> string** (a plain `yaml.safe_load` of the `transitions:` sequence) to populate the draft's
> ordered, list-shape-preserving rows, while still calling `load_transitions` purely to
> **validate** (the oracle). `load_columns` similarly validates; the draft's `column_class`
> is read from the same `action:` flag. Because the draft is rebuilt from the raw document,
> the round-trip is **semantic equivalence**, not field-for-field byte fidelity: list-sugar
> rows MAY be preserved or cartesian-expanded as long as `load(render(load(X))) == load(X)`
> (§6). The loaders never become a serialization source — they stay validation-only.

---

## 5. Validator — turn runtime fail-loud into save-time errors

The validator is the heart of "the UI is complete, not awkward." Every footgun that today
crashes the daemon _at launch_ becomes a **save-time error with a field locus**.

### 5.1 Oracle pass (free, authoritative)

Render the draft, run it through `load_transitions` + `load_columns`, and surface any
`ValueError` verbatim (mapped to a field where possible). This catches: duplicate concrete
`(from,to)` pairs after list expansion, `* → *`, empty lists, malformed `permission_mode`
YAML types, unknown wildcard combinations, etc. — because the loaders already enforce them.

### 5.2 Semantic checks (UI-friendly, with field loci)

| #   | Rule                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Failure locus                 |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| V1  | Every `{{placeholder}}` in `prompt` resolves against the known set: `code, title, ticket_body, issue_body, comments, codename, design_path, plan_paths, script_output, branch, base_clone, dev_repo_path`.                                                                                                                                                                                                                                                                                                                                                                                         | the prompt field, char offset |
| V2  | Every `/implement:*` (and other) slash-command referenced in a prompt is preserved verbatim (warn if a known command name is mistyped).                                                                                                                                                                                                                                                                                                                                                                                                                                                            | prompt field                  |
| V3  | `permission_mode ∈ {default, acceptEdits, auto, dontAsk, plan}` and contains no `bypass` substring.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | mode dropdown                 |
| V4  | `profile` is non-empty on any **prompt-bearing** (launch) transition. No column/global fallback (purely a transition concern).                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | profile dropdown              |
| V5  | `advance`/`on_fail` targets reference an **existing** column key.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | behavior dropdowns            |
| V6  | `from`/`to` reference an existing column key or `"*"` (`"*"` not allowed inside a list).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | from/to selectors             |
| V7  | Wildcard precedence is legible: explicit `(from,to)` > `(from,*)` > `(*,to)`; flag _shadowed_ rows (an explicit row that a wildcard can never override, or a wildcard fully masked by explicit rows) as **warnings**, not errors.                                                                                                                                                                                                                                                                                                                                                                  | row badge                     |
| V8  | `launch_target_columns()` invariant preserved: the anti-loop guard keys on prompt-bearing explicit + `(*,to)` rows; script-only / no-op rows are excluded. The canonical example is **`Review→Merge`** — a script **gate** (no prompt), so `Merge` is NOT a launch target. The check's purpose is **preventing `Merge` from ever becoming a launch target** (which would make the bot re-fire on a card moved into Merge). Note V8 is a defense-in-depth signal only: the actual merge ban lives in the perms `deny`-list (`gh pr merge` & co.) + GitHub branch protection, not in this validator. | (global)                      |

Errors block save; warnings (V2 typo, V7 shadow) inform but allow save.

> **V3/V4 source-of-truth (HEAD-verified).** V3's allowed set is exactly
> `core/transitions.py::_ALLOWED_PERMISSION_MODES = {default, acceptEdits, auto, dontAsk,
plan}`; the validator MUST **import that frozenset** (export a public alias from
> `transitions.py`, e.g. `ALLOWED_PERMISSION_MODES`) rather than re-list the values, so the two
> can never drift. V4's `profile` enum is exactly `adapters/perms.PROFILES =
('docs','prepare','dev','check')` — V4 validates `profile ∈ perms.PROFILES` (the four PoC
> profiles, genesis phase 22; the historical `safe`/`trusted` naming the review flagged is
> already RESOLVED in HEAD). V1's placeholder set is exactly the dict built by
> `app/actions.LaunchAction._build_context` (`code, title, branch, ticket_body, script_output,
issue_body, comments, codename, design_path, plan_paths, base_clone, dev_repo_path`).

### 5.3 Move-resolution simulation (the "complexity → legible" endpoint)

`resolve(draft, from_key, to_key) -> ResolvedTransition | None` returns which transition
fires for a given move, applying the precedence rules. The UI uses it to render a "what
happens when a card moves X→Y" preview, so wildcard precedence is never a mystery. `None`
means the move is not whitelisted → the daemon would **rollback** the card.

> **Fidelity caveat vs `decide()` (HEAD-verified).** The daemon's real verdict is **not** the
> whitelist alone: `core/decide.decide()` applies **reactive routing FIRST** — a move INTO a
> reactive (Cancel) column is intercepted as `TEARDOWN`, and `Cancel→Backlog` as `RESET`,
> **before** the whitelist `get()` is ever consulted. The whitelist's `(*, Cancel)` /
> `(Cancel, Backlog)` rows are bookkeeping-only (they keep those moves from rolling back); they
> are never the actual action. So `resolve()` has two honest options, and PR 1 picks one:
> **PR 1 scopes `resolve()` to whitelist resolution only** (it answers "which `(from,to)` row
> matches, with wildcard precedence" — exactly `TransitionConfig.get` semantics), and the UI
> labels Cancel/Backlog edges as "reactive: handled by the engine (teardown/reset)" rather than
> claiming they fire a transition. Layering the reactive interception into `resolve()` (to
> mirror `decide()` end-to-end) is explicitly deferred — it would have to import the column
> model's `ColumnClass` and duplicate `decide()`'s precedence, which is PR-3 territory (the UI
> hosts columns then). A test asserts `resolve()` agrees with `TransitionConfig.get` across all
> column pairs for the default config; it does NOT claim to agree with `decide()` on the
> reactive edges.

---

## 6. Serializer & the dual-defaults home

`render_pipeline(draft)` emits two documents:

- `transitions.yml` — the `project:` header (from `binding.github`), a `defaults:` block, and
  the transition list. Prompts are emitted as YAML block scalars via
  `yaml.safe_dump(sort_keys=False, allow_unicode=True, width=120)`, preceded by the existing
  3-line `# permission_mode …` comment header.
- `columns.yml` — the bare column set with `key` + `name` (from `binding.github.column_names`)
  - the `action: teardown` marker for the reactive column.

**Round-trip property (tested):** `load(render(load(yaml))) == load(yaml)` — semantic
idempotence (comments/formatting are _not_ preserved; the file is generated from the default
template at `kanban init` and thereafter **owned by `helm`**, per the operator's decision).

### 6.1 The defaults home (already resolved in HEAD — `transitions.yml` is authoritative)

> **Reality refresh (genesis phase 30 / #4).** An earlier draft of this design described a
> dual-defaults footgun where `columns.yml` `BoardDefaults` was the effective home and
> `transitions.yml` `defaults:` was dead config, with a loader=2 / template=3 asymmetry. **That
> is no longer the state of the engine.** Genesis phase 30 (#4) made **`transitions.yml`'s
> `defaults:` block AUTHORITATIVE**: `app/wiring.build_tick_config` now reads
> `concurrency_cap` / `move_rate_limit_per_hour` from the parsed `TransitionConfig`
> (`transitions.concurrency_cap` / `.move_rate_limit_per_hour`), the loader fallback was aligned
> to **3** (matching the rendered template — no more 2/3 asymmetry), and the `columns.yml`
> `defaults:` block was **demoted to a commented-out fallback** in the template (it is still
> parseable by `load_board_defaults` but the daemon no longer reads it). There is already ONE
> authoritative knob.

**Decision (corrected):** `helm` binds `definition.defaults` to the **`transitions.yml`
`defaults:` block** — the single effective home the daemon actually reads. Consequences:

- The serializer writes `defaults:` into `transitions.yml` from `definition.defaults`
  (authoritative), and does NOT emit an active `defaults:` block into `columns.yml` — it leaves
  the columns template's commented-out fallback as-is (matching the shipped template).
- The validator may emit a **warning** if a hand-edited `columns.yml` carries an _uncommented_
  `defaults:` block that disagrees with `transitions.yml` (it is dead config that will mislead
  the operator), but `transitions.yml` always wins.
- This is now the **no-behavior-change** choice (the opposite of the earlier draft): binding to
  `transitions.yml` matches what `build_tick_config` reads today, so `helm` introduces no
  daemon-behavior change. A round-trip test asserts `build_tick_config` reads the rendered
  `transitions.yml` defaults unchanged.

---

## 7. HTTP API (PR 1)

A **local, loopback-bound** FastAPI app, homed as a top-level **entrypoint**
(`src/kanbanmate/http/`, NOT under `adapters/` — it imports `app.config_service`, and the
layering guard forbids `adapters → app`), started on demand via `kanban config serve`. It is
the contract the Vue UI (PR 2) consumes. Endpoints:

| Method + path               | Body                    | Returns                         | Notes                                       |
| --------------------------- | ----------------------- | ------------------------------- | ------------------------------------------- |
| `GET /api/config`           | —                       | current `PipelineConfig` (JSON) | reads the live files via `config_service`   |
| `POST /api/config/validate` | draft JSON              | `{valid, errors[], warnings[]}` | runs §5; never writes                       |
| `POST /api/config`          | draft JSON              | `{written, path}`               | validates then **atomic** temp→rename write |
| `GET /api/config/render`    | draft JSON (query/body) | `text/yaml`                     | preview the serialized YAML                 |
| `POST /api/config/resolve`  | `{from, to}` + draft    | `ResolvedTransition \| null`    | §5.3 simulation                             |
| `GET /api/schema`           | —                       | the JSON Schema                 | for editor / UI form generation             |
| `GET /api/health`           | —                       | `{ok, version}`                 | liveness                                    |

Constraints (hard):

- **Loopback only** (`127.0.0.1`), no auth in v1 (single-operator local tool); never bind
  `0.0.0.0`. Documented as a non-goal to expose remotely.
- **No write outside the config files.** The only mutation is the atomic write of
  `transitions.yml` / `columns.yml` under the configured kanban config dir.
- **Optional dependency.** FastAPI/uvicorn are in the `[ui]` extra; importing the daemon does
  not import them. This is enforced by a **NEW runtime test** (not the static
  `tests/test_layering.py` guard — that one only checks the downward-only import direction): it
  imports `kanbanmate.daemon`, then asserts `"fastapi" not in sys.modules`, proving the daemon
  hot-path never transitively pulls the `[ui]` extra.
- **Validate-before-write is server-enforced**, not just client-side: `POST /api/config`
  re-runs §5 and refuses on any error (the UI cannot bypass it).

---

## 8. Security & invariants preserved

`helm` introduces no new authority and weakens none of the existing guarantees:

- **Merge = human-only.** The config UI cannot express, and the validator forbids, anything
  that would let an agent merge (V8 keeps `Merge`/gate rows out of launch targets; `bypass*`
  banned by V3). `helm` never calls `gh pr merge`.
- **Layering guard.** `core/` stays I/O-free; the HTTP surface is a downward-only **entrypoint**
  (`http/` imports `app`, never the reverse); the static layering test keeps direction honest
  and a separate **runtime** test asserts the daemon never transitively imports the `[ui]` extra
  (FastAPI).
- **Non-root, local, loopback.** The HTTP surface is bound to `127.0.0.1`; no remote
  ingress; no privilege escalation.
- **Atomic writes.** Config is written temp→rename so a crash never leaves a half-written
  `transitions.yml` that would fail-closed the daemon.
- **Kill-switch unaffected.** `~/.kanban/PAUSE` semantics are orthogonal; `helm` does not
  touch runtime state in PR 1.

---

## 9. Staging — the three PRs

### PR 1 — Config core + HTTP API _(this prep's plan)_

The headless model + validator + serializer + local HTTP API + JSON Schema + thin CLI.
Backend-neutral `definition`/`binding` split. No UI, no board mutation. Delivers a complete,
tested, scriptable config surface. **The plan in `plan/` covers this PR only.**

### PR 2 — Web interface (Vue.js) _(design-level here)_

A local Vue 3 SPA served alongside the API. The visual pipeline builder:

- pick + **order** columns (drag), mark the reactive (teardown) column;
- per **carrier transition**: prompt and/or script, profile, permission_mode, `advance`
  (fast-forward) and `on_fail` (rollback/move) behaviors;
- live **validation** (calls `POST /validate`) and a **resolution preview** (calls
  `/resolve`) so wildcard precedence is visible;
- **save** → `POST /config` (server validates + atomic write).

Stack: **Vue.js** (operator's expertise; chosen over React for maintenance). Types generated
from the API's OpenAPI schema. No backend logic in the SPA — it is a pure client of PR 1.

### PR 3 — Board repatriation _(design-level here)_

A **native board-state adapter** behind the board port: the interface hosts columns + card
positions; the daemon's snapshot/move flow is unchanged (it still diffs a snapshot and
decides). **Tickets remain GitHub Issues** — `helm` surfaces and pilots them, it does not
store them; GitHub keeps repos, issues, PRs (the forge). Only the _column assignment_
(Status) leaves Projects v2.

GitHub-side provisioning caveats (already researched, to honor when the GitHub board-ordering
methods are written — **reusing the existing `Seeder`, not a new `BoardProvisioner`**; §3.2):

- **Columns = single-select options.** The existing `Seeder.ensure_columns(project_id, columns)`
  already shapes the auto Status field's option set in board order, **always preserving existing
  option ids** (replacing the set without ids orphans every card). PR 3 reuses it as-is —
  column create/rename is **already solved** by genesis phases 21/33.
- **Card position + reorder = the only genuinely new operations.** `reorder_columns` (reorder
  the Status options) and `place_item` (`updateProjectV2ItemPosition` + `afterId`) are NOT on
  `Seeder` today; PR 3 adds them (extending `Seeder` or a sibling `BoardOrdering` the same
  `GithubClient` satisfies). `updateProjectV2ItemPosition` is a **single global manual order**,
  not an independent per-column position (the fidelity gap a native adapter can later close).
- **Board-view layout** (which field groups the board, column visibility) is **not** exposed
  by the API — a human configures the view once; provisioning cannot fully build a board from
  zero.

This PR essentially automates the remaining ordering that `genesis` phases 21/33 left to a
human, behind the existing `Seeder` port (NOT a parallel provisioning surface).

---

## 10. Non-goals

- Auto-merge (permanently forbidden; merge is human-only).
- Replacing the GitHub forge (repos/branches/PRs/CI).
- A native ticket store (tickets stay GitHub Issues).
- Remote/multi-user hosting, auth/RBAC, TLS — `helm` is a local single-operator tool.
- Editing runtime state ("disable triggers during a desync") in PR 1 — that is **operational
  runtime state** adjacent to the `PAUSE` kill-switch, not config; if pursued it is a separate,
  later item (it does not belong in `transitions.yml`).
- Preserving hand-written YAML comments through the round-trip (the file is helm-owned).
- **Resolving arbitrary `explicit-config.yml` config paths in PR 1.** The config service takes
  **injected resolved paths**; the CLI/entrypoint resolves only the **registry/clone path** (the
  clone's `.claude/kanban/{columns,transitions}.yml`, mirroring the daemon). Resolving an
  operator-supplied arbitrary config path is deferred to a later PR (§3.1, phase-04).

---

## 11. Risks & open questions

| #   | Risk / question                                                                                                                                                      | Mitigation / note                                                                                                                                                                                            |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| R1  | The `definition`/`binding` split changes how config is _modeled_ — could drift from the on-disk YAML.                                                                | Serializer keeps emitting today's valid `transitions.yml`/`columns.yml`; round-trip idempotence test (§6) guards against drift. The split is in-memory, not a new file format.                               |
| R2  | FastAPI/uvicorn dependency footprint.                                                                                                                                | Isolated to the `[ui]` extra; the `http/` surface is an entrypoint (not under `adapters/`, so it may import `app`) and a **runtime** test asserts the daemon never transitively imports FastAPI.             |
| R3  | An operator who hand-edited an (uncommented) `columns.yml` `defaults:` block expects it to take effect, but HEAD reads defaults from `transitions.yml` (genesis #4). | `helm` binds `definition.defaults` to the authoritative `transitions.yml` block (§6.1); validator **warns** when an uncommented `columns.yml` `defaults:` disagrees (it is dead config). No behavior change. |
| R4  | The validator must stay in lock-step with the loaders (oracle reuse helps, but the semantic checks V1–V8 duplicate some loader rules).                               | Oracle pass is authoritative; V1–V8 add _loci_ on top. A test asserts every loader `ValueError` is also caught (or gracefully surfaced) by the validator.                                                    |
| R5  | PR 3 card-position fidelity (global order vs per-column) may not perfectly mirror a native board.                                                                    | Documented limitation; native adapter can model per-column order independently; GitHub adapter accepts the global-order approximation.                                                                       |
| R6  | Codename `helm` collides with Kubernetes Helm in prose.                                                                                                              | Internal codename only; rename trivially if desired before PR 1 (uncommitted).                                                                                                                               |

---

## 12. Acceptance shape (for PR 1)

Per the project's executable-ACCEPTANCE rule, PR 1's `ACCEPTANCE.md` will express each
criterion as a shell command with documented expected output, e.g.:

- `kanban config validate <good.yml>` exits 0; `kanban config validate <bad.yml>` exits non-0
  and names the offending field.
- `kanban config render <draft.json>` emits a YAML that `load_transitions` accepts.
- `curl -s localhost:PORT/api/config/validate -d @bad.json | jq .valid` → `false` with a
  non-empty `errors[]`.
- A round-trip test: `render(load(X)) ≡ load(X)` semantically. **Use a PURPOSE-BUILT fixture**,
  not the live `personal-scraper` config — the live config currently _equals_ the shipped
  default (`default_transition_config()`), so it exercises no non-default shape. The fixture
  must include the round-trip's hard cases: a **list-expansion** row (`[a,b] → c`), **two
  prompts landing in the same column** (e.g. `PrepareFeature→InProgress` vs `PRCI→InProgress`,
  different prompts — the per-`(from,to)` discriminator), and a **wildcard-shadowing** case
  (an explicit row plus a `(*,to)` that the explicit row shadows).
- A **runtime** check: importing `kanbanmate.daemon` does not pull FastAPI
  (`"fastapi" not in sys.modules` after the import).

---

## Review reconciliation (2026-06-11)

This prep was re-verified against HEAD (`feat/genesis`, post phases 22-35) and an adversarial
review. Folded fixes (each verified against `src/`):

1. **HTTP API re-homed as an entrypoint, not an adapter.** The HTTP surface imports
   `app.config_service`, and `tests/test_layering.py` forbids `adapters → app`; so it moves to a
   top-level `http/` entrypoint started via `kanban config serve`. The daemon-no-FastAPI check
   is a NEW **runtime** test (`"fastapi" not in sys.modules`), not the static guard. (§3, §3.1,
   §7, §8, phase-05.)
2. **`from_loaded` re-parses the RAW YAML.** `TransitionConfig` exposes no transition list (only
   `get`/`launch_target_columns`/private tables), so the draft is rebuilt from the raw
   `transitions.yml` string; `load_transitions` stays the validation **oracle** only. Round-trip
   weakened from "field-for-field" to **semantic equivalence**. (§4.1, phase-01/02.)
3. **`ColumnDef.column_class`** is a string `'reactive'|'inert'` mirroring core `ColumnClass`,
   not a bool; `Column.name` explicitly projects into `binding.column_names`. (§4, phase-01.)
4. **Defaults home corrected to current reality.** Genesis phase 30 (#4) made `transitions.yml`'s
   `defaults:` AUTHORITATIVE (`build_tick_config` prefers `TransitionConfig` cap/rate; the
   `columns.yml` block is a commented-out fallback). §6.1 + R3 + phase-02 2.1/2.3 rewritten —
   the earlier "`columns.yml` is the effective home" was stale.
5. **Config-path resolution injected, not imported.** `CLONE_*_RELPATH` live in `cli/init.py`,
   which `app/` may not import; the config service takes **resolved paths** as inputs (each
   atomic temp→rename in the target file's own parent dir). PR 1 scoped to the registry/clone
   path; arbitrary `explicit-config.yml` paths deferred (non-goal). (phase-04.)
6. **`resolve()` scoped whitelist-only.** `decide()` intercepts reactive Cancel/reset BEFORE the
   whitelist; PR 1's `resolve()` is explicitly `TransitionConfig.get`-equivalent only (reactive
   layering deferred to PR 3). (§5.3, phase-03.)
7. **`BoardProvisioner` reconciled with the existing `Seeder`.** `Seeder.ensure_columns` already
   provisions columns (id-preserving); PR 3 only adds reorder + per-card placement (extends
   `Seeder`, no parallel surface). (§3.2, §9.)
8. **New value objects defined** with owning modules: `Finding` / `ValidationResult` /
   `ResolvedTransition` (core/config_validate), `ConfigInvalid` (app/config_service). (§3.1.a.)
9. **Minor fixes:** `assets/*.json` package-data for the schema; `kanban config` is a Typer
   sub-app (`add_typer`); V3 imports the loader's allowed-mode frozenset (public alias) instead
   of re-listing; the round-trip fixture is purpose-built (list-expansion / two-prompts-same-
   column / wildcard-shadowing) since the live config equals the default; the anti-loop guard
   path is `src/kanbanmate/bin/kanban_move.py`; V8's example is `Review→Merge` (the gate), its
   purpose preventing `Merge` becoming a launch target (the merge ban itself lives in perms deny
   - branch protection).
10. **Reality refresh vs HEAD:** profile enum is `docs/prepare/dev/check` (4 PoC profiles, phase
    22 — the `safe`/`trusted` conflict is RESOLVED; V4 validates against `perms.PROFILES`); the
    flow is now **14 columns** (Brainstorming + Plan added, phase 26) with skip-to-Done and
    recovery edges (phase 30 #12: `Review→InProgress`, `Planned→Spec`, `Done→Backlog`);
    `kanban-update-body` now EXISTS (phase 29); the V1 placeholder set was re-verified against
    `app/actions.py` (unchanged). Stale "12 columns" / "14 built-in defaults" counts corrected
    (the default `DEFAULT_TRANSITIONS` list is now 20 raw entries).
