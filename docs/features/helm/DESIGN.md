# helm — Configuration interface (PR 1: config core + HTTP API) — DESIGN

> **Codename**: `helm` · **Ticket**: #5 · **Type / SemVer**: minor (additive subsystem) ·
> **Branch**: `feat/helm`
>
> This document covers the full 3-PR `helm` arc so the steps compose, but **#5 implements PR 1
> only** (config core + headless HTTP API). PR 2 (Vue 3 SPA) and PR 3 (board repatriation) are
> design-level here and out of scope for this ticket.
>
> Every claim about the existing engine is grounded against `HEAD` (`5e880fa`, v0.5.1) and cited
> as `path:line`. Where a brainstorm decision and HEAD disagree, the source wins and the
> divergence is called out.

---

## §1 — Problem & motivation

The pipeline is configured by two hand-edited YAML files copied per-clone by `kanban init`:

- `<clone>/.claude/kanban/transitions.yml` — the per-`(from, to)` whitelist
  (`cli/init.py:84` `CLONE_TRANSITIONS_RELPATH`), rendered from
  `core/transitions_defaults.render_transitions_yaml` (`core/transitions_defaults.py:648`).
- `<clone>/.claude/kanban/columns.yml` — the bare column SET
  (`cli/init.py:79` `CLONE_COLUMNS_RELPATH`), copied from `assets/columns.yml.tmpl`.

Both are parsed by the **functional core** loaders (`core/transitions.load_transitions`,
`core/columns.load_columns`) which take a YAML *string* and fail **loud** on any defect
(`core/transitions.py:247-382`, `core/columns.py:48-96`). The failure mode is load-bearing and
hostile to hand-editing: a malformed `transitions.yml` does **not** fail at edit time — it crashes
the daemon at the next `tick → wiring.build_tick_config → load_transitions`
(`app/wiring.py:189-230`), i.e. at *launch* time, far from the edit.

Configuring the pipeline through GitHub's own UI was investigated and **invalidated** (2026-06-09
API study, recorded in the ticket brainstorm): Projects v2 has no transition concept (Status is a
single-select; transitions are diffed client-side), option descriptions are per-column not
per-`(from, to)`, and no native automation runs code on a card move (`projects_v2_item` is an
org-webhook only — which *confirms* KanbanMate's "no webhook, no n8n" polling design). A bespoke
configuration interface is therefore the retained path.

**helm** turns launch-time fail-loud into **save-time** validation with a field locus, behind a
backend-neutral, headless config core that round-trips with the existing YAML loaders and is
exposed over a local-loopback HTTP API.

---

## §2 — Goals / non-goals (PR 1)

### Goals
1. A **mutable, JSON-serializable draft** model of the pipeline (`transitions.yml` + `columns.yml`)
   that the existing frozen loaders can reproduce: `load(render(draft))` is **semantically equal**
   to the source — not byte-identical (comments are not preserved; the file is helm-owned after
   `kanban init`).
2. A **validator** that converts the loaders' launch-time `ValueError`s into structured,
   field-located save-time `Finding`s, plus 10 semantic checks (§7) the raw loaders do not perform.
3. A **move-resolution simulator** `resolve(draft, from, to)` scoped to **whitelist resolution
   only** (PR 1) — mirroring `TransitionConfig.get` precedence (`core/transitions.py:183-211`).
4. A **serializer** `render_pipeline(draft)` that emits valid `transitions.yml` + `columns.yml`.
5. A **headless HTTP API** (loopback, single-operator, no auth) exposing get / validate /
   save / render / resolve / schema / health, started via a thin `kanban config` CLI sub-app.
6. A machine-readable **JSON Schema** for the draft model.

### Non-goals (PR 1)
- **No UI** (PR 2). **No board mutation** — no column/card writes to Projects v2 (PR 3).
- **No new authority**: merge stays human-only; `core/` stays I/O-free; the daemon hot-path stays
  `urllib`-only; FastAPI is isolated to an optional extra; writes are atomic; loopback-only;
  `~/.kanban/PAUSE` is never read or written (PR 1 edits no runtime state).
- **No arbitrary `explicit-config.yml` path editing** — PR 1 is scoped to the
  registry/clone-resolved config path (the same path `daemon/registry_wiring.py:66-72` reads).
- **No mirroring of `decide()`'s reactive interception** end-to-end (§8) — deferred to PR 3.

---

## §3 — The 3-PR arc (context; only PR 1 is built here)

- **PR 1 (this ticket) — Config core + HTTP API.** Backend-neutral, headless config model +
  validator + serializer + resolve simulator, exposed over a local HTTP API + a `kanban config`
  CLI sub-app + a JSON Schema. Round-trips with the existing YAML loaders. No UI, no board mutation.
- **PR 2 — Web interface (Vue 3 SPA).** A visual pipeline builder consuming the PR-1 API (the
  operator's Vue expertise; chosen over React). Design-level only here.
- **PR 3 — Board repatriation.** A native board-state adapter behind the board port (columns +
  card positions move off Projects v2). **Tickets stay GitHub Issues; merge stays human-only;
  GitHub keeps the forge** (repos/branches/PRs/CI). Design-level only here.

The **definition ↔ binding** split (§4) is the single schema evolution that lets PR 3 swap the
backend without touching the neutral model.

---

## §4 — The config model: `definition` ↔ `binding`

The draft splits 100%-backend-neutral pipeline shape (`definition`) from the GitHub-specific
wiring (`binding`). This is the one schema evolution the extensibility goal (PR 3) requires.

### §4.1 — `definition` (backend-neutral)

```
PipelineDraft
├── definition: Definition
│   ├── columns:     list[ColumnDef]        # ordered; mirrors columns.yml order
│   ├── transitions: list[TransitionDef]    # ordered; mirrors transitions.yml rows
│   └── defaults:    Defaults
└── binding: Binding                        # GitHub-isms (§4.2)
```

- **`ColumnDef(key: str, name: str, column_class: str)`** — `column_class` is the **string**
  `"reactive"` | `"inert"`, mirroring `core.domain.ColumnClass` whose member *values* are exactly
  `"reactive"` / `"inert"` (`core/domain.py:34-35`). The string keeps the draft JSON-friendly and
  backend-neutral (no enum import across the wire); the serializer maps `"reactive"` → the
  `action: teardown` flag `core/columns._resolve_class` reads (`core/columns.py:42-45`), `"inert"`
  → no `action` key. `name` is the human GitHub label (`Column.name`, `core/domain.py:57`).
- **`TransitionDef`** — one whitelist row, mirroring `core.transitions.Transition`
  (`core/transitions.py:50-101`): `from_col: str | list[str]`, `to_col: str | list[str]`,
  `profile: str = ""`, `prompt: str | None = None`, `script: str | None = None`,
  `advance: str = "stop"`, `on_fail: str = ""`, `permission_mode: str = "auto"`. The frozen
  runtime `Transition.from_col`/`.to_col` are single post-expansion `str`s, but the **editable
  draft is the pre-expansion authoring shape**: the wildcard `"*"` is a legal scalar value, and a
  **`list[str]`** authors several edges that share one action (the loader expands a list to a
  cartesian product of edges via `_expand_side`, `core/transitions.py:47-51`; the shipped config
  uses exactly one such row — `from: [Backlog, Brainstorming, Spec, Plan, Planned, ReadyToDev]` →
  `to: Done`, `core/transitions_defaults.py`). The draft preserves this shape verbatim — a
  `list[str]` is natively JSON-friendly (no encoding sentinel) and the serializer re-emits a scalar
  or a YAML block list; **list-expansion sugar is not re-collapsed on load** (see §5/§6). The
  validators normalise `str | list[str]` through one `_col_keys` seam (§7.1).
- **`Defaults(concurrency_cap: int, move_rate_limit_per_hour: int)`** — sourced from the
  **authoritative** `transitions.yml` `defaults:` block (`TransitionConfig.concurrency_cap` /
  `.move_rate_limit_per_hour`, `core/transitions.py:170-176`; defaults `3` / `10`,
  `core/transitions.py:292-293`). See §10.

### §4.2 — `binding` (GitHub-specific)

- **`project: str`** — the `project:` header of `transitions.yml` (`TransitionConfig.project`,
  `core/transitions.py:166-168`; an `owner/repo`-style slug written by
  `render_transitions_yaml(project)`, `core/transitions_defaults.py:648-684`).
- **`option_map: dict[str, str]`** — the column-key → GitHub Status-option binding. This lives in
  the runtime **registry** (`ProjectEntry.option_map`, `cli/init.py:_load_registry` reads
  `val.get("option_map", {})`), **not** in `columns.yml`. In PR 1 the binding is **read-only
  metadata** surfaced for the future UI; the config service never writes the registry (no board
  mutation, §2). PR 3 promotes `binding` to a swappable backend descriptor.

> **Why the split is load-bearing.** PR 3 replaces `binding` (GitHub option ids) with a native
> board descriptor while `definition` stays byte-for-byte the same model. Keeping
> `column_class`/`profile`/`permission_mode` as plain strings (never GitHub ids) is what makes
> `definition` portable.

---

## §5 — Editable draft vs frozen runtime — `from_loaded` re-parses raw YAML

The core loaders produce **frozen** objects optimised for lookup, not for editing or
serialization:

- `TransitionConfig` (`core/transitions.py:156-244`) is `@dataclass(frozen=True)` and exposes
  **no ordered transition list** — only `get()` and `launch_target_columns()` over three private
  lookup dicts (`_explicit` / `_wild_to` / `_wild_from`, `core/transitions.py:179-181`). The
  original row order and the wildcard/list authoring shape are **lost** at load.
- `load_columns` returns `dict[str, Column]` (`core/columns.py:48`), preserving order via dict
  insertion but discarding the raw document.

Therefore `PipelineDraft.from_loaded(transitions_yaml: str, columns_yaml: str)` rebuilds the
**ordered, editable** draft by:

1. **Re-parsing the RAW `transitions.yml` string** with a plain `yaml.safe_load` to recover the
   ordered `transitions:` rows + `defaults:` + `project:` verbatim (the same shape
   `load_transitions` consumes at `core/transitions.py:285-299`). This is the only way to recover
   row order and wildcard shape that `TransitionConfig` does not expose.
2. Re-parsing `columns.yml` via `load_columns` (order-preserving) for the `ColumnDef` list.
3. **Calling `load_transitions(transitions_yaml)` purely as a validation oracle** — its return
   value is *discarded*; we only care that it does **not** raise. A raw re-parse that the loader
   would reject must never become an editable draft.

**Round-trip contract**: `load_transitions(render_pipeline(draft).transitions) ==semantic==
load_transitions(X)` and likewise for columns — i.e. the *parsed* configs are equivalent, not the
bytes. Comments and key order inside a row are **not** preserved; helm owns the file after
`kanban init` (the rendered file already has no user comments beyond the 3-line header, §9).

---

## §6 — Move-resolution simulation: `resolve(draft, from, to)`

`resolve(draft, from_col, to_col) -> ResolvedTransition` answers "what would the engine do for
this move?" — **PR-1 scoped to whitelist resolution only.**

It mirrors `TransitionConfig.get` precedence exactly (`core/transitions.py:183-211`): explicit
`(from, to)` wins over `(from, *)` wins over `(*, to)`; no match → not whitelisted (the engine
would ROLLBACK). To stay a single source of truth, `resolve` builds a `TransitionConfig` from the
draft (render → `load_transitions`) and calls `.get(from, to)` rather than re-implementing
precedence.

`decide()`'s **reactive interception** runs *before* the whitelist in the real engine
(`core/decide.py:212-237`): a move INTO a `REACTIVE` column (Cancel) → `TEARDOWN`; a move leaving
a reactive column back to the reset target (`DEFAULT_RESET_TARGET = "Backlog"`,
`core/decide.py:63`) → `RESET`. In PR 1 `resolve` **labels** these as
`engine_handled="teardown"` / `"reset"` (computed from `ColumnDef.column_class == "reactive"` and
the Cancel→Backlog edge) rather than claiming a firing transition — the UI shows "handled by the
engine". Mirroring the full `decide()` verdict set end-to-end is deferred to PR 3.

`ResolvedTransition` (a JSON-friendly value object) carries: `matched: bool`, the matched
`TransitionDef` (or `None`), the precedence tier (`"explicit"` | `"wild_from"` | `"wild_to"` |
`"none"`), `engine_handled: str` (`""` | `"teardown"` | `"reset"`), and `would_launch: bool`
(`matched and prompt is not None` — i.e. an agent fires).

---

## §7 — Validator: launch-time fail-loud → save-time field-located findings

`validate(draft, *, columns_yaml: str | None = None) -> ValidationResult` runs two tiers. The
keyword-only `columns_yaml` is the raw `columns.yml` string, needed **only** by V8 (defaults
coherence): the draft itself binds `Defaults` from `transitions.yml` and does not retain the
`columns.yml` `defaults:` block, so V8 re-reads the raw text. When `columns_yaml` is `None`, V8 is
skipped; the `ConfigService` always passes it (it has the file in hand, §12).

### §7.0 — Oracle pass (authoritative backstop)
Render the draft (§9) and feed both documents through the real loaders:
`load_transitions(rendered_transitions)` and `load_columns(rendered_columns)`. Any `ValueError`
they raise (`core/transitions.py:277-283`, `core/columns.py:69-72`) is captured and turned into a
`Finding` with `severity="error"`. This guarantees helm can **never** save a config the daemon
would crash on — the loader is the same code the daemon runs (`app/wiring.py:210`,
`daemon/registry_wiring.py:69-72`).

### §7.1 — Semantic checks V1–V10 (field locus the loaders lack)
On top of the oracle, helm runs 10 checks that pinpoint the offending field and add warnings the
loaders never emit:

| # | Check | Source of truth | Severity |
|---|-------|-----------------|----------|
| **V1** | **Placeholder resolution** — every `{{name}}` in every `prompt` resolves against the known dispatch context keys | the `{{ token }}` grammar `core/placeholders.py:16` (`_TOKEN`); the **12** context keys built in `app/launch_context.py:86-112`: `code`, `title`, `branch`, `ticket_body`, `script_output`, `issue_body`, `comments`, `codename`, `design_path`, `plan_paths`, `base_clone`, `dev_repo_path` | error (unknown key → empty fill / dispatch-time surprise) |
| **V2** | **Slash-command preservation** — `/implement:*` tokens in prompts survive the render round-trip | the shipped prompts embed `/implement:brainstorm`, `/implement:plan`, `/implement:create-branch`, `/implement:phase`, `/implement:pr-review` (`core/transitions_defaults.py:246,316,358,384,434`) | error if mangled |
| **V3** | **`permission_mode` ∈ allowed, no `bypass*`** | `_ALLOWED_PERMISSION_MODES = {default, acceptEdits, auto, dontAsk, plan}` (`core/transitions.py:45-47`); bypass banned (`core/transitions.py:316-322`) | error |
| **V4** | **`profile` ∈ profile set** = `docs`, `prepare`, `dev`, `check` | `PROFILES` — **relocated to `core` in PR 1** (§13); HEAD value `adapters/perms.py:337` | error |
| **V5** | **Column-target existence** — every non-`*` `from`/`to`, every `advance:auto:<col>`, every `on_fail:move:<col>` names a real `ColumnDef.key` | the draft `columns` set; advance/on_fail grammar `core/domain.py:202-205` | error |
| **V6** | **Wildcard-precedence shadow** — an explicit `(from,to)` made unreachable-by-intent, or a wildcard shadowing an explicit row | precedence `core/transitions.py:202-211` | **warning** |
| **V7** | **Launch-target invariant — `Merge` is not a launch target** — no prompt-bearing transition resolves into a `REACTIVE` column or into `Merge` | enforced on the editable draft (reactive keys from `ColumnDef.column_class == "reactive"` + the literal `Merge` key), mirroring `TransitionConfig.launch_target_columns` semantics (`core/transitions.py:213-244`) but pre-render so the finding carries a field locus; Merge stays a script gate (`core/transitions_defaults.py:600-606`) | error |
| **V8** | **Defaults coherence** — warn if an *uncommented* `columns.yml` `defaults:` block disagrees with the authoritative `transitions.yml` `defaults:` (dead config). **Presence is detected on the RAW document** (`yaml.safe_load(columns_yaml).get("defaults")` is a dict) — NOT on `load_board_defaults`, which returns `BoardDefaults()` (3/10) for *both* an absent block and a present 3/10 block (`core/columns.py:217-235`), so trusting its return would false-positive when the cap is raised in `transitions.yml` while `columns.yml`'s block stays commented (the shipped state, `assets/columns.yml.tmpl:26-28`) | `BoardDefaults` / `load_board_defaults` (`core/columns.py:139-235`); authority §10 | **warning** |
| **V9** | **Column-class membership** — every `ColumnDef.column_class` is `"reactive"` or `"inert"`. A typo silently demotes a reactive column to inert (the serializer emits no `action` key and `load_columns` accepts it, `core/columns.py:42-45`) — a silent loss of teardown semantics the oracle never catches | `ColumnClass` member values (`core/domain.py:34-35`) | error |
| **V10** | **Defaults sanity** — `concurrency_cap` and `move_rate_limit_per_hour` must be `>= 1`. The loaders coerce any int (`core/transitions.py:292-293`), so a non-positive cap (stalls every launch) or rate (blocks every bot move) is dead config; the published JSON Schema declares `minimum: 1` (§14) and V10 enforces the same bound at save time | loader coercion (`core/transitions.py:292-293`); schema §14 | error |

`Finding(field: str, message: str, severity: "error" | "warning", locus: str)` and
`ValidationResult(findings: list[Finding], ok: bool)` are JSON-friendly dataclasses in
`core/config_validate.py`. `ok` is `True` iff no `error`-severity finding exists; **errors block
save, warnings do not** (§11). `field`/`locus` point at e.g. `transitions[3].permission_mode`.

---

## §8 — Serializer: `render_pipeline(draft)`

`render_pipeline(draft) -> RenderedPipeline(transitions: str, columns: str)` emits both YAML
documents:

- **`transitions.yml`** — reuses the shipped renderer's exact shape
  (`core/transitions_defaults.render_transitions_yaml`, `core/transitions_defaults.py:648-684`):
  `yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120)` with the **3-line
  permission_mode comment header** prepended verbatim (`core/transitions_defaults.py:679-683`).
  Multiline prompts serialize as block scalars (PyYAML emits these for `\n`-bearing strings).
  `doc` is `{project, defaults: {concurrency_cap, move_rate_limit_per_hour}, transitions: [...]}` —
  the same top-level shape `load_transitions` consumes.
- **`columns.yml`** — a `{columns: [{key, name[, action: teardown]}]}` document; `column_class ==
  "reactive"` emits `action: teardown`, `"inert"` emits no `action` key (the inverse of
  `core/columns._resolve_class`, `core/columns.py:42-45`).

The render is the input to both the round-trip oracle (§5) and the validator oracle (§7.0), so a
draft that renders to something the loaders reject is caught before it ever reaches disk.

---

## §9 — The board reality: 14 columns, 1 reactive

The shipped board is **14 columns** (`assets/columns.yml.tmpl:30-95`), only **Cancel** is
reactive:

| # | key | name | class |
|---|-----|------|-------|
| 1 | `Backlog` | Backlog | inert |
| 2 | `Brainstorming` | Brainstorming | inert |
| 3 | `Spec` | Spec | inert |
| 4 | `Plan` | Plan | inert |
| 5 | `Planned` | Planned | inert |
| 6 | `ReadyToDev` | Ready to dev | inert |
| 7 | `PrepareFeature` | Prepare feature | inert |
| 8 | `InProgress` | In Progress | inert |
| 9 | `PRCI` | PR/CI | inert |
| 10 | `Review` | Review | inert |
| 11 | `Merge` | Merge | inert |
| 12 | `Cancel` | Cancel | **reactive** (`action: teardown`) |
| 13 | `Done` | Done | inert |
| 14 | `Blocked` | Blocked | inert |

The shipped whitelist (`core/transitions_defaults.DEFAULT_TRANSITIONS`,
`core/transitions_defaults.py:485-639`) drives the HYBRID lifecycle: autonomous through Plan
(`advance:auto:Spec`/`Plan`/`Planned`), a human gate at `Plan→Planned`/`Planned→ReadyToDev`
(no-ops), auto-build `ReadyToDev→PrepareFeature→InProgress→PRCI`, the `InProgress→PRCI` script
gate auto-promoting to `Review` on green CI, `Review` stopping for human, and `Review→Merge` a
script **gate** (no prompt) so `Merge` stays human-only (V7/V8). The validator's defaults and the
resolve simulator are tested against this real table (not a toy).

The name/key seam matters: a GitHub move emits the option **name** (`In Progress`, `PR/CI`) while
config uses the **key** (`InProgress`, `PRCI`) — `core/columns.resolve_column` bridges
name-first-then-key (`core/columns.py:99-136`). helm edits **keys**; the UI shows `name`.

---

## §10 — Defaults home: `transitions.yml` is authoritative

`build_tick_config` reads `concurrency_cap` + `move_rate_limit_per_hour` from the parsed
`TransitionConfig` (`app/wiring.py:229-230`), i.e. from `transitions.yml`'s `defaults:` block —
**not** from `columns.yml`. The `columns.yml` `defaults:` block (`load_board_defaults`,
`core/columns.py:197-235`) is a documented **fallback only** and ships **commented out**
(`assets/columns.yml.tmpl:26-28`).

helm therefore binds `Defaults` to the `transitions.yml` block (no daemon-behavior change) and
**warns** (V8) if a hand-uncommented `columns.yml` `defaults:` disagrees with it — a dead-config
trap the loaders silently allow today.

---

## §11 — HTTP API: an **entrypoint**, not an adapter

The API imports `app.config_service` (§12). The layering guard `tests/test_layering.py` walks the
**entire AST** of every file (`ast.walk(tree)`, `tests/test_layering.py:86`) and forbids
`adapters → app` (`tests/test_layering.py:39`) — so the API **cannot** live in `adapters`, even
behind a function-local import. It homes at the existing top-level **`http/`** entrypoint
(sibling to `cli/`/`daemon/`), which the guard already permits to import `app`/`adapters`/`core`
and the `cli.init` registry loaders (`tests/test_layering.py:42-48`). This is the same layer the
`kanban serve` webhook receiver already occupies (`http/serve.py`).

### §11.1 — Server
- **Framework**: FastAPI + uvicorn, shipped as an **optional `[ui]` extra** (§14). The config
  server is started **only** via `kanban config serve` and only when `[ui]` is installed; an
  `ImportError` there prints an actionable "install kanbanmate[ui]" message. (The existing
  `http/serve.py` webhook receiver stays **stdlib** `http.server` — `http/serve.py:41` — and gains
  no FastAPI dependency.) FastAPI is chosen here for auto JSON-Schema/OpenAPI generation that PR
  2's Vue SPA consumes.
- **Bind**: loopback `127.0.0.1` only, an unprivileged default port, **no auth, single-operator**
  (mirrors `http/serve.py` `DEFAULT_HOST = "127.0.0.1"`, `http/serve.py:54`). The operator fronts
  TLS/exposure with their own reverse proxy if ever needed; PR 1 assumes localhost.
- **Daemon-purity runtime test**: a test asserts `import kanbanmate.daemon` does **not** pull
  FastAPI (`"fastapi" not in sys.modules`) — the hot-path stays `urllib`-only (§2).

### §11.2 — Endpoints

| Verb & path | Behaviour |
|-------------|-----------|
| `GET /api/config` | Return the current draft (loaded via `from_loaded` from the resolved clone files, §12). |
| `POST /api/config/validate` | Validate a posted draft; return `ValidationResult` (never writes). |
| `POST /api/config` | **Validate-then-atomic-write** (server-enforced): reject with `422` + findings if any `error`; else atomically write both files (§12). |
| `GET /api/config/render` | Return the rendered `transitions.yml` + `columns.yml` strings for a draft (preview; no write). |
| `POST /api/config/resolve` | `resolve(draft, from, to)` → `ResolvedTransition` (§6). |
| `GET /api/schema` | The JSON Schema of the draft model (§14). |
| `GET /api/health` | Liveness probe (`{"status":"ok"}`). |

The verbs/paths are internally consistent throughout this document and the plan.

---

## §12 — Config service: injected resolved paths + atomic write

`app/config_service.py` is the layer the HTTP entrypoint calls. It is **path-injected**: `app`
may **not** import `cli/init.py` (the guard forbids `app → cli`,
`tests/test_layering.py:41`), so it can take neither `CLONE_TRANSITIONS_RELPATH` nor
`CLONE_COLUMNS_RELPATH` directly. Instead the **`http/` entrypoint** (which *may* import
`cli.init`, `tests/test_layering.py:42-48`) resolves the two absolute paths — `<clone> /
CLONE_TRANSITIONS_RELPATH`, `<clone> / CLONE_COLUMNS_RELPATH` (`cli/init.py:79,84`), exactly as
`daemon/registry_wiring.py:66-72` does — and injects them:

```
ConfigService(transitions_path: Path, columns_path: Path)
  .load() -> PipelineDraft                 # read both files → from_loaded (§5)
  .validate(draft) -> ValidationResult     # §7
  .save(draft) -> None                      # validate (raise ConfigInvalid on error) → atomic write
  .render(draft) -> RenderedPipeline        # §8
  .resolve(draft, from, to) -> ResolvedTransition   # §6
```

- **Atomic write**: temp-file → `os.replace` **within each target's own parent dir** (same
  filesystem, atomic rename), one file at a time; on a validation error nothing is written.
- **`ConfigInvalid`** (raised by `.save` when validation has an `error`) is a plain exception
  carrying the `ValidationResult`; the `http/` layer maps it to `422` + JSON findings.
- PR 1 resolves the clone path from the **registry** entry (`ProjectEntry.clone`,
  `cli/init.py:_load_registry`) via the `cli.init` helpers `_projects_path` / `_load_registry`
  (`cli/init.py:182-228`) — the same ones `daemon` and `http` already use. Arbitrary
  `explicit-config.yml` paths are a **non-goal** (§2).

---

## §13 — Layering fix: relocate the `PROFILES` name-set into `core`

V4 (§7.1) needs the canonical profile name set, but `PROFILES` lives in **`adapters/perms.py:337`**
and the validator lives in **`core/config_validate.py`** — and `core` may import **nothing** from
`adapters` (`tests/test_layering.py:31`), enforced by a full-AST walk (no function-local escape,
`tests/test_layering.py:86`).

Per the layering rule (relocate the source-of-truth to a permitted layer, never work around it),
PR 1 introduces **`core/profiles.py`**:

```python
PROFILES: tuple[str, ...] = ("docs", "prepare", "dev", "check")
```

and refactors `adapters/perms.py` to `from kanbanmate.core.profiles import PROFILES` (re-exporting
it so existing importers of `perms.PROFILES` are unaffected). The allow/deny/mode **logic** stays
in `adapters/perms.py` (genuine FS I/O); only the **pure name tuple** moves down. A test asserts
parity — `set(core.profiles.PROFILES) == set(adapters.perms._PROFILE_ALLOW)` — so the canonical
set and the per-profile allow-lists can never drift (`adapters/perms.py:278-333`).

> `_ALLOWED_PERMISSION_MODES` (V3) already lives in `core` (`core/transitions.py:45`), so the
> validator imports it directly (core → core) — no relocation needed. The oracle pass (§7.0) also
> enforces it via `load_transitions` (`core/transitions.py:325-329`), so V3 is belt-and-suspenders
> with a cleaner field locus.

---

## §14 — Packaging: the `[ui]` extra, the schema, and module homes

- **`[ui]` optional extra** in `pyproject.toml` (`[project.optional-dependencies]`,
  `pyproject.toml:18-24`): `fastapi`, `uvicorn[standard]`. Base deps stay `typer` / `PyYAML` /
  `attrs` (`pyproject.toml:12-16`) — the daemon never imports FastAPI (§11.1 runtime test).
- **`kanban config` CLI sub-app**: a new `typer.Typer()` registered via
  `app.add_typer(config_app, name="config")`, matching the existing `ticket`/`pill` sub-app
  pattern (`cli/app.py:51-67`). Sub-command `serve` (+ optional `validate`/`render`/`get` thin
  wrappers for terminal use). The `kanban config serve` import of FastAPI is lazy so the bare
  `kanban` CLI still imports with no `[ui]` extra.
- **JSON Schema** (`GET /api/schema`) is **generated** from the model (FastAPI/pydantic schema, or
  a hand-built dict over the dataclasses) — there is **no static `schema.json` asset**, so no
  `[tool.setuptools.package-data]` entry is needed (`pyproject.toml:40-41`). If a static copy is
  ever shipped it must be added there; PR 1 generates it to keep one source of truth.

### Module map (new files, PR 1)
| Layer | File | Contents |
|-------|------|----------|
| `core` | `core/profiles.py` | `PROFILES` (§13) |
| `core` | `core/config_model.py` | `PipelineDraft` / `Definition` / `ColumnDef` / `TransitionDef` / `Defaults` / `Binding` / `from_loaded` (§4–§5) |
| `core` | `core/config_serialize.py` | `render_pipeline` / `RenderedPipeline` (§8) |
| `core` | `core/config_validate.py` | `Finding` / `ValidationResult` / `ResolvedTransition` / `validate` / `resolve` (§6–§7) |
| `app` | `app/config_service.py` | `ConfigService` / `ConfigInvalid` (§12) |
| `http` | `http/config_api.py` | the FastAPI app + endpoints (§11) |
| `cli` | `cli/config.py` | the `kanban config` sub-app (§14) |
| `adapters` | `adapters/perms.py` (edit) | import `PROFILES` from `core.profiles` (§13) |

All `core/*` modules import **only** the stdlib + `yaml` + sibling `core` modules (the layering
guard holds: `core` → `core` only). `http/config_api.py`'s forbidden set is `{daemon, bin}`
(`tests/test_layering.py:48`), so importing `app`/`adapters`/`core`/`cli.init` is legal.

---

## §15 — Invariants preserved (no new authority)

- **Merge stays human-only** — V7/V8 + `perms.deny_list()` (`adapters/perms.py:206-261`) +
  branch protection; `bypass*` banned (V3, `core/transitions.py:316-322`). helm performs **no**
  board mutation and **cannot** merge.
- **`core/` stays I/O-free** — every new `core/*` module is string-in/value-out; the oracle reuses
  the existing pure loaders.
- **Daemon hot-path stays `urllib`-only** — FastAPI is isolated to `[ui]`; the §11.1 runtime test
  proves `import kanbanmate.daemon` pulls no FastAPI.
- **Writes are atomic** — temp → `os.replace` in-dir (§12).
- **Loopback-only**, single-operator, no auth (§11.1).
- **`~/.kanban/PAUSE` untouched** — PR 1 edits no runtime state; it writes only the two clone
  config files via the injected paths.

---

## §16 — Testing strategy (PR 1)

- **Round-trip** (`tests/core/`): for the shipped config (`render_transitions_yaml("owner/repo")`
  + `columns.yml.tmpl`), assert `load_transitions(render_pipeline(from_loaded(X)).transitions)`
  is **semantically equal** to `load_transitions(X)` — compare `.get()` over **every real
  `(from,to)` edge** in `DEFAULT_TRANSITIONS` (`core/transitions_defaults.py:485-639`) and
  `launch_target_columns()`; assert column dict equality. Tests use real **keys**
  (`InProgress`, `PRCI`) and edges that actually exist — never display labels, never two-`None`
  comparisons.
- **Validator** (`tests/core/`): one focused failing input per V1–V10 (e.g. a prompt with
  `{{nope}}` → V1 error at `transitions[i].prompt`; `permission_mode: bypassPermissions` → V3;
  `profile: merge` → V4; `advance: auto:Nowhere` → V5; a prompt-bearing `* → Merge` → V7) plus a
  clean-config "no findings" case. Each assertion compares a genuinely-produced `Finding`, not an
  empty list against an empty list.
- **Resolve** (`tests/core/`): explicit-wins-over-wildcard precedence on real edges; an
  un-whitelisted move → `matched=False`; a `* → Cancel` move → `engine_handled="teardown"`; a
  `Cancel → Backlog` move → `engine_handled="reset"`.
- **Service** (`tests/app/`): atomic write to a tmp clone (both files land; a forced validation
  error writes nothing and raises `ConfigInvalid`); injected-path resolution.
- **HTTP** (`tests/http/`): FastAPI `TestClient` over each endpoint incl. the `422`-on-invalid
  contract; **daemon-purity** runtime test (`"fastapi" not in sys.modules` after importing
  `kanbanmate.daemon`).
- **Layering**: `tests/test_layering.py` passes unchanged — every new module respects its layer
  (the test is the gate, not a new assertion).
- Test files mirror the existing `tests/<layer>/` layout (never a flat root).

Phase gate per CLAUDE.md: `make lint` (ruff + mypy clean), `make test`, `make check`
(lint + test + module-size guards under the 1000-LOC ceiling), residual-import grep, and a
`python -c "import kanbanmate"` smoke test.

---

## §17 — Review reconciliation (the 10 adversarial-review fixes, verified vs HEAD)

The ticket note requires the pending adversarial-review fixes to land in the design before
implementing. Each is folded above and re-verified against `HEAD`:

| # | Fix | Where in this design | HEAD evidence |
|---|-----|----------------------|---------------|
| 1 | HTTP API is an **entrypoint** (`http/`), not an adapter | §11 | guard forbids `adapters→app`, full-AST (`tests/test_layering.py:39,86`); `http` allowed (`:48`) |
| 2 | `from_loaded` **re-parses raw `transitions.yml`** (loader is oracle only) | §5 | `TransitionConfig` exposes no row list (`core/transitions.py:156-244`) |
| 3 | `column_class` is the **string** `reactive`/`inert` | §4.1 | `ColumnClass` values (`core/domain.py:34-35`) |
| 4 | **Defaults home = `transitions.yml`** (authoritative) | §10 | `build_tick_config` (`app/wiring.py:229-230`); tmpl fallback commented (`assets/columns.yml.tmpl:26-28`) |
| 5 | Config service takes **injected resolved paths** (`app` ⊅ `cli.init`) | §12 | guard forbids `app→cli` (`tests/test_layering.py:41`) |
| 6 | **Whitelist-only resolve**; `decide()` reactive labelled "engine-handled" | §6 | `decide` precedence (`core/decide.py:212-237`) |
| 7 | **Seeder reconciliation** — PR 1 does **no** board/registry mutation; `binding` is read-only metadata | §2, §4.2, §15 | registry read-only via `_load_registry` (`cli/init.py:194-228`) |
| 8 | **Value objects** `Finding`/`ValidationResult`/`ResolvedTransition` (core) + `ConfigInvalid` (app) | §7, §6, §12 | new dataclasses, JSON-friendly |
| 9 | **Schema package-data** — generated, no static asset (else add to package-data) | §14 | `pyproject.toml:40-41` |
| 10 | **14-column reality refresh** | §9 | `assets/columns.yml.tmpl:30-95` |

**New (11th) decision surfaced by this grounding pass**: the **`PROFILES` relocation to `core`**
(§13) — without it V4 cannot run in the `core` validator under the full-AST layering guard. It is
a required, minimal prerequisite refactor in PR 1.

---

## §18 — Open questions / risks

- **R6 — codename collision.** `helm` collides with Kubernetes Helm in prose. Kept as the internal
  codename (matches the roadmap dir + the `**roadmap**`/`**codename**` markers); trivially
  renamable before branch creation. **Defaulting to `helm`** absent a veto.
- **FastAPI vs stdlib.** The brainstorm picks FastAPI (auto-schema for PR 2's SPA); the existing
  `http/serve.py` uses stdlib. Chosen: FastAPI **isolated to `[ui]`** with a daemon-purity test —
  the webhook receiver keeps its stdlib server (no new dep on the hot path). Revisit only if the
  `[ui]` dependency surface becomes a packaging burden.
- **Round-trip is semantic, not byte.** Comments/row-internal key order are not preserved. Accepted
  — helm owns the file after `kanban init`; the rendered file carries only the 3-line header
  (§8/§9).
- **`binding.option_map` write path is deferred.** PR 1 surfaces it read-only; editing the
  GitHub binding (and any board mutation) is PR 3.
