# bridge — helm PR 2: config GUI (visual pipeline builder) — DESIGN

> **Codename**: `bridge` · **Arc**: helm PR 2 (the web interface) · **Ticket**: TBD (board card) ·
> **Type / SemVer**: minor (additive `web/` subsystem + one additive endpoint) ·
> **Branch**: `feat/bridge`
>
> _Helm steers; the bridge is where you steer from._ PR 1 (`helm`, #5/#33) shipped the headless
> config core + HTTP API. **bridge** is the visual surface on top of it: a local single-operator
> web app that authors, validates and saves a correct `transitions.yml` + `columns.yml`, so the
> pipeline is configured by clicking instead of by hand-editing YAML.
>
> Every claim about the shipped engine is grounded against `main` (`d61e522`, v0.8.0) and cited as
> `path:line`. Where a brainstorm decision and the code disagree, the code wins and the divergence
> is called out.

---

## §1 — Problem & motivation

helm PR 1 turned the daemon's launch-time fail-loud into **save-time** structured validation behind
a backend-neutral config core, exposed over a loopback HTTP API (`http/config_api.py`, 7 endpoints +
Swagger `/docs`, started by `kanban config serve` — `cli/config.py:34`). But the only consumer today
is `curl`/Swagger. The operator still authors the pipeline by editing two YAML files by hand:

- `transitions.yml` — the order-sensitive `(from, to)` whitelist carrying `profile` /
  `permission_mode` / `advance` / `on_fail` / `prompt` per row.
- `columns.yml` — the column SET (board order).

Hand-editing is hostile: a wrong `permission_mode`, a prompt with an unknown `{{placeholder}}`, or a
transition into a reactive column is invisible until the next daemon tick. The PR-1 API can already
_tell_ the operator what is wrong (structured `Finding`s with a field locus); **bridge** makes those
findings visible and the whole config directly editable, with the UI as the source of truth.

The brainstorm also surfaced two capabilities the YAML workflow never had and that a GUI makes
natural:

1. **A rich prompt editor** — `{{placeholder}}`-aware syntax highlighting, validation against the
   known placeholder set, and a filled-in preview. Prompts are the highest-leverage, most
   error-prone part of the config (a stray `{{baze}}` silently degrades an autonomous stage).
2. **An explicit "Sync board" action** — re-provision the GitHub Projects v2 Status options to match
   `columns.yml` from inside the editor, via the _already-shipped_ `Seeder.ensure_columns`
   (`ports/board.py:243`) — so editing the column set in the GUI can be reflected onto the live
   board in one audited, diff-previewed click.

---

## §2 — Goals / non-goals

### Goals

1. A **local single-operator web app** (loopback) that loads the live config via the PR-1 API,
   lets the operator edit columns / transitions / defaults / prompts visually, validates on demand
   and on save, and writes back the config — UI is the source of truth, replacing hand-edited YAML.
2. **Rich prompt editor**: `{{placeholder}}` highlighting, validation against the engine's known
   placeholder set, unknown-placeholder findings with a did-you-mean, and a sample-filled preview.
3. **Columns are first-class config**: add / rename / reorder / mark inert, in board order. Editing
   the column set is **board configuration** (PR 2), distinct from PR-3 board _repatriation_.
4. An explicit **"Sync board"** action that previews a diff (ADD / RENAME / REORDER, never silent
   removals) then provisions the GitHub Status options via `Seeder.ensure_columns` — gated, never
   automatic, never touching cards or merges.
5. **Validation findings panel** with field locus and click-to-locate (jump to the offending
   transition row / column / default).
6. **Served by `kanban config serve`** — the built static SPA is mounted by the existing FastAPI
   app; **no Node at runtime**, no new long-running process, no new port. Vite builds to a static
   bundle that ships in the wheel under the `[ui]` extra.

### Non-goals

- **No board repatriation** (PR 3 / ticket #43): native column/card _positions_ off Projects v2 is
  out of scope. bridge mutates only the Status **option set** (via the shipped seeder), never card
  positions, never card content.
- **No new authority**: merge stays human-only; `core/` stays I/O-free; the daemon hot-path stays
  `urllib`-only; FastAPI/uvicorn/static assets stay isolated to the `[ui]` extra (the bare `kanban`
  CLI must import without them — `cli/config.py:49` lazy-import pattern preserved).
- **No auth / multi-user / remote exposure**: loopback-only, single operator, same trust model as
  PR 1. TLS/public exposure is the operator's reverse proxy concern (as with `kanban serve`).
- **No live daemon control** from the GUI (no start/stop/pause, no agent reaping) — bridge edits
  _config_, not _runtime_. `~/.kanban/PAUSE` is never read or written.
- **No new validation semantics in the SPA**: all validation is the PR-1 validator over the API.
  The SPA mirrors the known-placeholder set for _instant_ in-editor feedback, but save-time truth is
  always the server's `Finding` list (the SPA never blocks a save the server would accept, nor
  accepts one the server rejects).

---

## §3 — Framework decision (resolves the PR-1 tension)

helm PR-1 DESIGN §3 recorded PR 2 as **Vue 3** (operator's Vue expertise). That is **superseded**:
the operator has since built a **KanbanMate design system on shadcn/ui + React** and authored the
full config interface against it (`.claude/skills/kanbanmate-design/ui_kits/config/`). bridge is
built in **React + shadcn**, reusing that design system directly.

- **Rationale**: the design system is React/shadcn (oklch token layer, Geist/Geist Mono, brand
  `--health-*` / `--col-*` extensions, ~20 components incl. `AppShell`, `TransitionRow`, `Dialog`,
  `KeyChip`, `ProfileTag`, `FindingItem`, `HealthPill`). The config interface is already laid out in
  it (`ui_kits/config/index.html` + `AppShell.jsx` / `ColumnsPanel.jsx` / `TransitionsPanel.jsx` /
  `SidePanels.jsx`). Re-deriving it in Vue would discard finished design work and split the brand.
- **Cost accepted**: the operator's Vue preference is set aside for design-system fidelity. Recorded
  here so the divergence from PR-1 DESIGN §3 is explicit, not silent.

The two new pieces (rich prompt editor + Sync-board dialog) were mocked on the same system and
approved (`ui_kits/config/new-pieces.html`).

---

## §4 — Architecture at a glance

```
                         build time (dev only)
  web/  ──vite build──▶  web/dist/  (static JS/CSS/HTML, committed-or-packaged under [ui])
                                   │
                                   ▼ (FastAPI StaticFiles mount, runtime)
  browser ◀── kanban config serve (http/config_api.py FastAPI app) ──▶ config core (PR 1)
     │            GET /            → SPA index.html                         core/config_model
     │            GET /assets/*    → built JS/CSS                           core/config_validate
     └── fetch ── /api/* (7 existing) + /api/board/provision (new) ─────▶  core/transitions, columns
                                   │
                          POST /api/board/provision ──▶ app/board_provision ──▶ Seeder.ensure_columns
                                                          (dry-run → diff; apply → mutate Status opts)
```

- **`web/`** — the React/shadcn SPA source (new top-level dir, dev-time only; not imported by any
  Python module). Built by Vite to `web/dist/`.
- **`http/config_api.py`** — the existing FastAPI app gains (a) a `StaticFiles` mount serving the
  built SPA at `/`, guarded so a missing build degrades gracefully, and (b) one new endpoint
  `POST /api/board/provision` (dry-run diff + apply).
- **`app/board_provision.py`** — NEW thin imperative-shell wrapper computing the column diff
  (pure, in `core/`) and calling `Seeder.ensure_columns` on apply. Mirrors how `cli/seed.py`
  drives the seeder; reuses the registry token resolution.
- **`core/columns_diff.py`** — NEW pure function: `diff_columns(current, desired) -> [ColumnChange]`
  (ADD / RENAME / REORDER; never REMOVE — removals are surfaced as a _blocked_ finding, not applied).

Layering unchanged: `http` is a top entrypoint (may import `app`/`adapters`/`core`); `core` stays
pure; `web/` is outside the Python import graph entirely.

---

## §5 — Screens & components (on the shipped design system)

The shell and panels already exist as the approved design (`ui_kits/config/`). bridge wires them to
live API data. One `AppShell` with a left/bottom nav switching five panels:

| Panel           | Source component             | Responsibility                                                                           |
| --------------- | ---------------------------- | ---------------------------------------------------------------------------------------- |
| **Columns**     | `ColumnsPanel.jsx`           | Add / rename / reorder / mark inert; board order; **Sync board** action lives here       |
| **Transitions** | `TransitionsPanel.jsx`       | Order-sensitive `(from,to)` rows; edit-in-`Dialog` (profile/perm/advance/on_fail/prompt) |
| **Defaults**    | `SidePanels.DefaultsPanel`   | `concurrency_cap`, `move_rate_limit_per_hour`                                            |
| **Validation**  | `SidePanels.ValidationPanel` | Findings list with severity + field locus + click-to-locate (`onGoto`)                   |
| **YAML**        | `SidePanels.YamlPanel`       | Read-only rendered `transitions.yml` + `columns.yml` (from `GET /api/config/render`)     |

Desktop + mobile both ship (the kit already has a `MobileNav` + phone frame + `SegmentedControl`
toggle in `index.html`). Header carries: error count (blocks save), dirty indicator, **Save**.

### §5.1 Rich prompt editor (new piece, approved)

Opened from a Transition row's prompt field (replaces the basic `<Textarea>` at
`TransitionsPanel.jsx:69`). Per `new-pieces.html`:

- **Known-placeholder chips** (`KeyChip`) — click to insert. The set is **fetched from the server**
  (see §6.2), not hard-coded in the SPA, so it can never drift from the engine.
- **Highlighted editor** — mono editor; `{{placeholder}}` spans styled `.ph` (known) /
  `.ph.bad` (unknown, wavy-underlined).
- **Findings `Banner`** — "N unknown placeholders", listing each unknown with a did-you-mean
  (nearest known by edit distance).
- **Preview line** — placeholders filled with sample values; "N placeholders · M known".

### §5.2 Sync board dialog (new piece, approved)

Opened from the Columns panel's **Sync board** button. Per `new-pieces.html`:

- Neutral `Banner` — _"This mutates the GitHub board"_ — states scope: re-provisions Status options
  to match `columns.yml`; tickets & card positions untouched; merge stays human-only.
- **Diff rows** — ADD / RENAME / REORDER tags + `KeyChip`s, from `POST /api/board/provision`
  `{dry_run: true}`. "No removals" reassurance; renamed columns carry cards over by option id.
- **Apply to board** — `POST /api/board/provision` `{dry_run: false}`, then re-fetch config.

---

## §6 — API surface

### §6.1 Existing (PR 1, reused unchanged)

`GET /api/health` · `GET /api/config` · `GET /api/config/render` · `GET /api/schema` ·
`POST /api/config/validate` · `POST /api/config` (save) · `POST /api/config/resolve`
(`http/config_api.py:157-273`). The SPA loads via `GET /api/config`, validates via
`POST /api/config/validate`, saves via `POST /api/config` (which re-validates server-side and
refuses a save with error-severity findings), renders YAML via `GET /api/config/render`.

### §6.2 New: known-placeholder set

The rich editor needs the engine's canonical placeholder set. Rather than hard-code it in JS, expose
it. **Decision**: extend `GET /api/schema` (or add `GET /api/placeholders`) to return the known
placeholder names + a one-line description each, sourced from the single engine definition (the
prompt-rendering substitution map in `core/transitions_defaults`). One source of truth; the SPA is a
dumb mirror. _(Self-review note: confirm during planning where the substitution keys are defined —
`grep` `{{` in `core/transitions_defaults.py` — and export from there.)_

### §6.3 New: `POST /api/board/provision`

The "Sync board" backend. Request: `{dry_run: bool}` (no draft body — operates on the **saved**
config + live board, so the operator saves first, then syncs; the dialog disables Sync while dirty).

- **`dry_run: true`** → compute `diff_columns(live_board_options, columns.yml)` and return
  `{changes: [{kind: "add"|"rename"|"reorder", column, ...}], removals: [...], applied: false}`.
  Removals are reported but **never applied** (a removal would orphan cards — surfaced as a warning,
  the operator removes via GitHub if intended). Read-only: lists Status options, no mutation.
- **`dry_run: false`** → call `Seeder.ensure_columns(project_id, columns)` (preserves existing
  option ids → cards never orphaned, `ports/board.py:243-258`); return the applied change set +
  the fresh `{column: option_id}` map. Token + project resolved from the registry exactly as
  `cli/seed.py:393-405` (registry-by-repo, explicit override).

This is the **only** new board-mutating path bridge adds, and it reuses the shipped, tested seeder —
no new GraphQL. It writes Status options only; never cards, never merges.

---

## §7 — Serving & packaging

- **Build**: `web/` is a Vite + React + shadcn project. `npm run build` → `web/dist/`. Node is a
  **dev/build** dependency only.
- **Ship**: `web/dist/` is packaged under the `[ui]` extra (it already gates FastAPI/uvicorn —
  `cli/config.py:49-58`). Decision to confirm in planning: commit `web/dist/` vs build-in-CI-and-
  package. Default: build in CI, include in the wheel; committing the build is the fallback if the
  packaging step is fiddly.
- **Mount**: `http/config_api.py` mounts `StaticFiles(directory=web_dist, html=True)` at `/`, found
  relative to the package. **Guarded**: if `web/dist` is absent (source checkout without a build),
  `/` returns a friendly "run `npm run build` / install the `[ui]` extra" message instead of a 500,
  and `/api/*` keeps working. SPA routes (client-side) fall back to `index.html`.
- **No new port / process**: bridge is served by the _same_ `kanban config serve` the operator
  already runs for PR 1. `kanban config serve` then prints the URL to open.

---

## §8 — Validation, state & data flow

- **State**: the SPA holds one `PipelineDraft` (the `GET /api/config` shape: `{definition: {columns,
transitions, defaults}, binding}`) as the single in-memory source of truth, plus `dirty` and the
  latest `findings`. Edits mutate the draft locally; **Validate** (and **Save**) POST the draft and
  refresh `findings`.
- **Save gate**: Save is disabled while `findings` contains any `error`-severity item (mirrors the
  shipped server behaviour — `POST /api/config` refuses an error-bearing draft). The SPA disabling
  it is UX; the server is the gate.
- **Instant feedback**: the rich editor validates placeholders client-side against the fetched known
  set for _immediate_ squiggles, but every Save round-trips through the server validator, which is
  authoritative.
- **Round-trip fidelity**: `POST /api/config` → server renders YAML via the PR-1 serializer;
  `load(render(draft))` is semantically equal to source (PR-1 guarantee). The SPA never writes YAML
  text; it always posts the structured draft.
- **Sync board ordering**: Sync operates on the **saved** config (not the in-memory draft) — the
  dialog is disabled while dirty, forcing Save-then-Sync. This keeps "what's on the board" tied to
  "what's persisted", never to an unsaved edit.

---

## §9 — Error handling

- **API unreachable** (server not running / wrong port) → full-screen banner with the
  `kanban config serve` hint; no partial editing of a phantom config.
- **Save rejected** (server returns error findings) → findings panel populates, Save stays disabled,
  draft is preserved (no data loss); the offending row is highlighted (`invalidIdx` already wired in
  `TransitionsPanel.jsx:14-16`).
- **Sync board failure** (GitHub error / token scope) → the dialog surfaces the seeder's error
  verbatim in an error `Banner`; no partial application is claimed (the seeder is idempotent —
  re-run is safe).
- **Missing build** → §7 friendly message, `/api/*` unaffected.

---

## §10 — Testing

- **Pure core** (`core/columns_diff.diff_columns`) — unit tests: add/rename/reorder/no-op,
  removal-detection, order sensitivity, id preservation expectations.
- **App shell** (`app/board_provision`) — tests with a fake `Seeder` (the existing test seeder
  pattern, `cli/seed.py` tests): dry-run computes diff without mutating; apply calls
  `ensure_columns` with the right column list/order; registry token resolution.
- **HTTP** — FastAPI `TestClient`: `POST /api/board/provision` dry-run vs apply; placeholder
  endpoint shape; static mount present-and-absent (guarded 200 vs friendly message); `/api/*` still
  works without a build.
- **SPA** — component-level (placeholder highlighter known/unknown, diff-row rendering, save-gate
  disabling). Kept light; the heavy invariants live server-side and are tested there.
- **Live exercise** (manual, ACCEPTANCE): isolated `kanban config serve` on a **copied** config +
  mirrored registry entry (never the live kanban-mate clone) — load, edit a prompt with a bad
  placeholder (see squiggle + finding), fix, save (YAML re-renders), Sync-board dry-run against a
  throwaway project shows the diff.

---

## §11 — Open decisions for planning (writing-plans resolves these)

1. **Placeholder endpoint**: extend `GET /api/schema` vs new `GET /api/placeholders` (§6.2) — and
   the exact engine source of the substitution keys (`core/transitions_defaults`).
2. **`web/dist` packaging**: build-in-CI-and-package vs commit the build (§7).
3. **Ticket/branch**: codename `bridge` **confirmed**; branch `feat/bridge`. Implementation path
   **confirmed**: `writing-plans` → **manual interactive execution** (not the autonomous `/implement`
   pipeline). Opening a board card is optional (manual run).
4. **Editor depth**: contentEditable highlight overlay vs a light CodeMirror dependency for the rich
   editor (the mock uses a styled `<div>`; a real editor needs caret-stable highlighting).

---

## §12 — Out of scope (explicit)

PR 3 board repatriation (#43); auth/multi-user/remote; live daemon control; card-position mutation;
any new merge authority; Vue (superseded by §3).

---

## §13 — Iteration 2 (operator feedback, 2026-06-20)

After the first live look, four design changes (operator-directed). These supersede the matching
parts of §2/§5/§6.

### §13.1 Multi-board switching (was single-project)

The daemon drives **N boards** (live: `kanban-mate` + `personalscraper` under one `kanban-km`
daemon). The interface MUST let the operator pick a board and edit **its** config independently.
This supersedes PR-1's "first registry entry" assumption (`http/config_api.py:_get_service` used
`next(iter(registry.values()))`).

- **`GET /api/projects`** — list the registry entries the daemon manages:
  `{projects: [{project_id, repo, enabled, ingress}]}`. Backs the switcher + the Daemon section.
- **Project selector** — every config endpoint (`/api/config`, `/api/config/validate`,
  `/api/config`, `/api/config/render`, `/api/config/resolve`, `/api/board/provision`) accepts an
  optional `?project=<project_id>`. Resolution: explicit id → that entry (404 if unknown); absent +
  N==1 → that entry (back-compat); absent + N>1 → **400** with the project list (the SPA always
  sends it). `_get_service(project_id=...)` resolves via
  `core.registry_resolve.resolve_by_project_id`.
- **Frontend** — a board switcher in the shell; selecting a board re-fetches that board's config.
  Board-scoped tabs are badged with the board name.

### §13.2 Daemon scope, editable (was: registry read-only)

A visually distinct **Daemon** section (separate from the per-board tabs) edits the daemon-scoped
registry fields, so "this is daemon-wide, not board-wide" is obvious at a glance.

- **`PATCH /api/projects/<project_id>`** — set `enabled` (drive this project) and/or `ingress`
  (`webhook`|`polling`), persisted via the existing `cli/init._upsert_project` write path
  (atomic-ish JSON rewrite, keyed by project node id). Other registry fields stay read-only (repo,
  clone, project_id, token_ref — set by `kanban init`).
- **Caveat surfaced in the UI**: the running daemon picks up `enabled`/`ingress` changes on its
  **next config reload / restart** (the daemon builds one wiring per enabled entry; it is not a
  live hot-swap of the project set). The UI states this; it does not claim instant effect.
- This narrows PR-1's "no registry mutation" non-goal to exactly these two safe toggles; it does
  **not** add card/merge authority and does not touch the clone config files.

### §13.3 No modal — master-detail transition editing

The transition editor moves out of the `Dialog` (operator dislikes modals). Layout: **master-detail**
— the transition list on the left, the selected transition's editor in a right-hand panel. Long
markdown prompts get the room a modal denied them. The Sync-board action stays a focused confirm
(discrete action, not editing).

### §13.4 Rich markdown prompt editor (GitHub-style)

The prompt field becomes a **Write / Preview** editor (one field, toggled — GitHub-inspired):
- **Write** — the markdown source, with the known-placeholder chips + `{{placeholder}}` validation
  (the unknown-placeholder finding + did-you-mean from §5.1 are retained).
- **Preview** — the markdown rendered in the **same** box (toggle), with `{{placeholders}}` still
  visibly highlighted (known vs unknown) so the operator sees both the formatting and the binding.
- Adds a small markdown renderer (`marked`) as a `web/` build dependency (runtime-free, bundled).

### §13.5 Out of scope (unchanged)

Still excluded: PR-3 repatriation, auth/multi-user/remote, card-position mutation, merge authority,
editing non-toggle registry fields (repo/clone/token), live daemon process control (start/stop).

---

## §14 — Iteration 3 (operator feedback, 2026-06-20): UI login

The UI is exposed over the internet (`km.iznogoudatall.xyz`, Caddy/TLS → loopback). An optional
single-operator login protects it. This narrows the §2 "no auth" non-goal: auth is now supported,
opt-in via credentials.

- **Credentials** from the operator's gitignored `.env` (`KANBAN_MATE_UI_LOGIN` /
  `KANBAN_MATE_UI_PASSWORD` / optional `KANBAN_MATE_UI_SESSION_SECRET` / `KANBAN_MATE_UI_PORT`),
  loaded by `cli/config.py serve` (`--env-file`, default `.env`). `.env` is gitignored; a committed
  `.env.example` documents the keys. **Empty password ⇒ login DISABLED (open — loopback/dev).**
- **Mechanism** (`http/auth.py`, pure stdlib): signed expiring session token (HMAC-SHA256 over
  `login:expiry`), carried in an `HttpOnly` cookie (`Secure` when behind TLS via `X-Forwarded-Proto`,
  `SameSite=Lax`); constant-time credential compare; no server-side session store.
- **Endpoints**: `GET /api/session` (auth_enabled / authenticated), `POST /api/login`,
  `POST /api/logout`. An `http` middleware guards every other `/api/*` route (401 without a valid
  cookie) when auth is enabled; `/api/health` + the login/session endpoints stay open; the static
  SPA shell is served and renders the login screen when `/api/session` reports unauthenticated.
- **SPA**: `LoginScreen` (i18n) shown until authenticated; a "Sign out" action in the shell (only
  when auth is enabled). Session checked on boot.
- **Deployment**: `kanban config serve` runs as the PM2 app `kanban-km-config` against the real
  `~/.kanban-km` root, **bound to loopback** (`--host 127.0.0.1`), fronted by Caddy (TLS) at
  `km.iznogoudatall.xyz`. pm2-saved (survives reboot). Binding loopback (not `0.0.0.0`) keeps the
  plain-http port closed so credentials only ever travel over Caddy's TLS.
- **Out of scope (unchanged)**: multi-user, roles, account management, password reset — single
  operator, one credential pair.
