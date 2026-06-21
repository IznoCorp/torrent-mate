# tiller — Interactive agent terminal + operator control from KanbanMateUI

> **Ticket**: #47 (IznoCorp/kanban-mate) — "Interactive tmux terminal — send input to running
> agents from Monitoring" + operator requirement batches.
> **Codename**: `tiller` (the lever that steers a running vessel — here, a running agent).
> **Type**: minor feature. **Version bump**: 0.14.0 → 0.15.0 (the package's canonical version is
> 0.14.0; the stale `VERSION` file at 0.11.0 is re-synced as part of this bump).
> **Branch (to be created)**: `feat/tiller`.
> **Status**: design (brainstorm complete, plan pending).

## 1. Purpose & scope

The Monitoring tab of **KanbanMateUI** is read-only today: it shows each running agent's state and a
polled `tmux capture-pane` tail, but to actually _interact_ with an agent the operator must
`tmux attach` on the host. `tiller` lets the operator **reach into a running agent and steer it from
the browser**, and folds in the operator-requested Board/Monitoring finishes.

In scope:

1. **Interactive agent terminal** — a real in-browser terminal for an agent's `ticket-<n>` tmux
   session: read **and** write (send keystrokes), with a "take control" safety gate.
2. **Editable ticket descriptions** — edit a ticket's GitHub issue body from the UI without
   corrupting the engine's body-marker regions.
3. **UI finishes** — collapsible board columns (Board **and** Monitoring), shadcn cards with a clean
   border + polished drag effect, and a markdown-rendered timeline.
4. **Fully mobile-functional** — every part usable on a phone (soft-keyboard, quick-keys, fullscreen),
   not merely responsive-to-look-at.

Out of scope (see §12).

## 2. Decisions (brainstorm, operator-confirmed 2026-06-21)

| #   | Decision                                    | Choice                                     | Rationale                                                                                                                                                                                           |
| --- | ------------------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Terminal transport + UI                     | **WebSocket + xterm.js** (real terminal)   | Real-time bidirectional, ANSI/colour fidelity, scrollback, resize; best desktop + mobile UX. FastAPI + `uvicorn[standard]` already support WS.                                                      |
| D2  | Write safety model                          | **Explicit "take control" gate + audit**   | Read-only by default; the operator explicitly arms write per session; every send is logged. Never bypasses `merge=human-only` or agent permission profiles.                                         |
| D3  | Concurrency (human + agent drive same pane) | **Co-pilot, like `tmux attach`**           | Both write the shared pane; tmux interleaves naturally. While a human is attached-in-control, the daemon's `reaper.end_session` is suspended for that ticket so it isn't killed mid-steer.          |
| D4  | Body-edit marker safety                     | **Parse-extract-remerge + coherence gate** | Operator edits the freeform prose; protected regions are re-injected on save; `validate_roadmap_matches_title` + de-fang applied. Replaces the un-gated raw path in `intents._execute_ticket_edit`. |

## 3. Architecture overview

Respects the hexagonal layering (downward-only imports; `core/` pure, `adapters/` do I/O, `http/`
is a top entrypoint). New/changed modules:

```
core/
  body_regions.py        (NEW, pure) split/merge an issue body into protected regions + freeform
ports/
  workspace.py           (+resize on the Sessions Protocol)
adapters/workspace/
  sessions.py            (+resize; capture gains an ANSI-preserving variant for the terminal stream)
http/
  agent_terminal.py      (NEW) WS /api/monitor/agent/{issue}/attach — auth, take-control, audit, stream
  monitor_routes.py      (+PATCH /api/monitor/ticket/{number}/body — marker-safe body edit)
app/
  reaper.py              (+suspend end_session for a ticket under human control — sentinel check)
  control_state.py       (NEW, optional thin helper) read/write the per-ticket "attached" sentinel
web/src/
  components/AgentTerminal.jsx   (NEW) xterm.js terminal + control toggle + quick-keys + fullscreen
  panels/MonitoringPanel.jsx     (terminal mount, body editor, collapsible groups, markdown timeline)
  panels/BoardPanel.jsx          (0-ticket-collapsed default, shadcn cards, polished drag)
  lib/collapse.js (or inline)    (localStorage collapse helper, shared)
```

Two processes coordinate: the **daemon** (`kanban run`, PM2 `kanban-km`) and the **HTTP server**
(`kanban config serve`, PM2 `kanban-km-config`) are separate OS processes sharing the runtime root
`~/.kanban-km`. Cross-process signalling therefore uses a **filesystem sentinel** (the established
`PAUSE`/`.nudge` pattern), not in-memory state — see §4.4.

## 4. Backend terminal (WebSocket + tmux)

### 4.1 Tmux adapter additions

- **`Sessions.resize(name, cols, rows)`** (port + `TmuxSessions`): builds
  `tmux resize-window -t <name> -x <cols> -y <rows>` (argv list, no shell). Lets the browser term
  size drive the agent's tmux window so wrapping matches.
- **ANSI-preserving capture** for the stream: `capture-pane -p -J -e -t <name>` (the `-e` flag keeps
  escape sequences so xterm.js renders colour). The existing `capture()` (no `-e`) is unchanged for
  the read-only tail and other callers; the terminal path uses the `-e` variant (e.g.
  `capture(name, *, ansi=False)` or a sibling `capture_ansi`).
- `send_text` (existing) is the single write seam — literal text, key names, and a separate Enter
  event; already chunked + retried. The WS write path reuses it verbatim.

### 4.2 WebSocket endpoint `/api/monitor/agent/{issue}/attach`

New module `http/agent_terminal.py`, registered on the shared FastAPI `app` via side-effect import
(like `monitor_routes`/`board_routes`). FastAPI `@app.websocket`.

- **Auth (explicit, in-handler)**: the `@app.middleware("http")` auth guard does **not** run for the
  WebSocket scope. The handler reads the `km_ui_session` cookie and calls `verify_token(...)`; on
  failure it `await websocket.close(code=1008)` before accepting. When auth is disabled (open mode)
  the check is a no-op, consistent with the rest of `/api/*`.
- **Read loop**: a bounded server task `capture`s the pane (ANSI variant) every ~300 ms and pushes a
  text frame to the client. `alive:false` when the session is gone → the client shows "session
  ended" and the socket closes. (A future optimisation may switch to `pipe-pane`; the snapshot loop
  is the v1 and is sufficient for a bounded visible pane.)
- **Write path**: client → server JSON messages:
  - `{type:"take_control"}` / `{type:"release_control"}` — arm/disarm writing (D2).
  - `{type:"text", data:"..."}` — literal text (xterm onData).
  - `{type:"key", name:"Enter"|"Escape"|"C-c"|...}` — a tmux key name (quick-keys).
  - `{type:"resize", cols, rows}` — drives `resize`.
    Writes are **rejected with a clear error frame unless control is armed**.
- **Hardening**: per-connection idle/slow-loris timeout; cap message size; ignore unknown message
  types; the read loop and write handler are fail-soft (a tmux error closes the socket cleanly, never
  crashes the server).

### 4.3 Audit (D2)

Every armed write is logged server-side: a structured line `audit: operator key→ticket-<n>: <repr>`
(login from the verified token, ticket, payload summary). Optionally appended to a per-root
`control/audit.log`. Read-only frames are not audited.

### 4.4 Reaper coordination (D3)

- On `take_control`, the WS handler writes a sentinel `control/ticket-<n>.attached` under the project's
  resolved store root; on `release_control`/disconnect it removes it (best-effort, with a TTL/cleanup
  so a crashed client can't pin it forever — e.g. the sentinel carries a timestamp the reaper treats
  as stale after N minutes).
- `reaper.end_session` (the finished-agent graceful exit) **checks the sentinel first**: if the ticket
  is attached-in-control, it skips end_session this tick (logs "deferred: human attached"). This stops
  the reaper from killing a session the operator is actively steering. All other reaper behaviour is
  unchanged.

### 4.5 Autonomy & safety invariants

- Typing into the REPL is bounded by the agent's permission profile (`.claude/settings.json` in the
  worktree); `merge=human-only`, `git push --force`, history-rewrite bans, and profile permission
  boundaries are **never** lifted by `tiller`. The WS endpoint sends keys to the same REPL the agent
  uses — it does not grant new capability.
- **Residual risk (documented)**: a human who exits claude (e.g. `C-c`) lands on the worktree shell,
  which is broader than the agent's profile. The explicit take-control gate + per-send audit make this
  a deliberate, traced operator action. This is accepted and called out, not silently enabled.
- The `~/.kanban/PAUSE` kill-switch and non-root rules are untouched.

## 5. Frontend terminal (xterm.js)

- Add **`xterm` + `@xterm/addon-fit`** to `web/package.json` (build-time bundle; the wheel ships the
  built SPA, so CI's `npm run build` covers it).
- **`components/AgentTerminal.jsx`**: mounts an xterm instance, opens the WS (same-origin cookie),
  renders streamed frames, `onData` → `{type:"text"}`, fit-addon → `{type:"resize"}`.
- **Control toggle** ("Prendre le contrôle" / "Rendre la main") flips read-only ↔ armed (sends
  `take_control`/`release_control`); a clear visual indicator of the current mode.
- **Quick-keys**: Enter, Esc, Ctrl-C buttons (mobile-critical) sending `{type:"key"}`.
- **Fullscreen toggle**: expands the terminal to the viewport (desktop + mobile), restores on exit.
- **Mobile**: a hidden/managed input element captures soft-keyboard input so phones can type; the
  quick-keys cover the keys phones can't easily produce. Works within the v0.11.0 responsive shell.
- i18n strings (EN/FR) for all new labels.

## 6. Editable ticket descriptions (marker-safe)

### 6.1 Core (pure)

New **`core/body_regions.py`**, reusing the regexes already in `core/body_edit.py`:

- `split_body_regions(body) -> BodyRegions` with `{status_block, markers:{roadmap,codename,design,
plans}, brainstorm, freeform}`.
- `merge_body_regions(regions, *, new_freeform) -> str` — re-assembles, status block at TOP,
  markers + `## Brainstorm` preserved verbatim, operator's freeform in the middle.
- Idempotent and region-disjoint by construction (pinned by tests: split∘merge round-trips; an edit to
  freeform never alters a protected region; literal delimiters in freeform are de-fanged).

### 6.2 HTTP

New authed **`PATCH /api/monitor/ticket/{number}/body`** in `monitor_routes.py`:

- Body `{freeform: "<edited prose>"}` (bounded like other POST bodies: Content-Length, 1 MiB cap,
  422 on bad shape).
- Server fetches the current issue body, `split_body_regions`, `merge_body_regions(new_freeform=...)`,
  runs `validate_roadmap_matches_title` (reject 400 on incoherence), de-fangs delimiters, then
  `update_issue_body` via the project's `GithubClient` (direct operator write, like `/api/board/*`).
- This **replaces** the un-gated `intents._execute_ticket_edit` raw full-body replacement as the UI's
  edit path (the intent path is removed or routed through the same safe merge).

### 6.3 Frontend

- Ticket detail (MonitoringPanel) gains an **Edit** mode using **RichPromptEditor** (already markdown,
  CodeMirror + `marked` preview). Only the freeform body is editable; protected regions are shown
  read-only (or simply excluded from the editor and re-merged server-side). Save → PATCH. Mobile-ok.

## 7. UI finishes (Board / Monitoring)

### 7.1 Collapsible columns

- **Board (`BoardPanel`)**: columns with **0 tickets are collapsed by default**; the expand/collapse
  state is **persisted** in localStorage. Keep the existing key `km:board:collapsed:<project>`, but
  distinguish "collapsed because empty (default)" from an explicit operator choice (so a column that
  later gains tickets auto-expands unless the operator explicitly collapsed it). A small shared helper
  centralises the read/write (try/catch wrapped, the established pattern).
- **Monitoring (per-status groups)**: groups become collapsible + persisted
  (`bridge.monitor.collapsed`), same 0-ticket→collapsed-by-default rule.

### 7.2 Board cards (shadcn)

- Migrate the custom `.km-card` to the **design-system Card (shadcn)** with a clean border; keep and
  polish the drag effect (lift on grab, dim while dragging, the live drop-insertion indicator).
  Visual-only — no change to the move/reorder logic from PR #52.

### 7.3 Timeline

- Render comment bodies as **markdown** (`marked`) in the ticket detail timeline; **visually separate
  progress events from comments** (distinct styling per entry kind), replacing the flat plain-text
  list.

### 7.4 Deployed-version indicator

- Show the **deployed package version** at the **bottom of the sidebar** (desktop `SidebarNav` **and**
  the mobile drawer/app-bar), so the operator always knows which build is running.
- **Backend**: surface `kanbanmate.__version__` on an existing open endpoint — `GET /api/health`
  returns `{status, version}` (open path, no auth needed). The app's `FastAPI(version=...)` string is
  the API version and is NOT used for this; the package `__version__` is the source of truth (the one
  bumped at release, e.g. 0.15.0).
- **Frontend**: the API client fetches it once at boot (or reuses the session/health boot call) and the
  sidebar footer renders e.g. `v0.15.0`. Small, muted, non-interactive; present in both layouts.

## 8. Phases (implementation order)

1. **Backend terminal** — `Sessions.resize` + port, ANSI capture variant, `http/agent_terminal.py`
   (WS auth + take-control + audit + hardening), reaper sentinel coordination. Tests: WS via FastAPI
   TestClient + `_FakeSessions`; reaper-suspend unit test.
2. **Frontend terminal** — xterm.js + fit, `AgentTerminal.jsx`, control toggle, quick-keys, fullscreen,
   mobile input, i18n.
3. **Editable description** — `core/body_regions` (+ tests), `PATCH .../body` endpoint (+ tests),
   RichPromptEditor edit mode, remove/secure the raw intent path.
4. **UI finishes** — collapsible columns (Board default-empty + Monitoring), shadcn card migration +
   drag polish, markdown timeline, deployed-version indicator in the sidebar (`/api/health` version +
   sidebar footer, desktop + mobile).
5. **Version bump + final gate + ACCEPTANCE** — bump 0.14.0 → 0.15.0 (resync VERSION + pyproject +
   `__init__`), `make check` green, formalise + re-exercise ACC-NN.

## 9. Testing

- **Backend**: FastAPI `TestClient` WebSocket support drives the attach endpoint with injected
  `app.state.monitor_sessions` (`_FakeSessions`): auth-required (1008 without cookie), read frames,
  write-rejected-until-control, take-control→write→`send_text` called, resize→`resize` called, audit
  emitted. Reaper unit test: sentinel present ⇒ `end_session` skipped.
- **Core**: `body_regions` round-trip/idempotency/disjointness/de-fang/coherence-gate; mirrors the
  existing `test_body_edit.py` adversarial style.
- **HTTP**: `PATCH .../body` happy path + 400 on roadmap/title incoherence + 422 bad body + marker
  preservation assertion.
- **Front**: `npm run build` + lint (no JS test runner today); manual mobile pass folded into
  ACCEPTANCE.

## 10. ACCEPTANCE (draft — formalise as executable ACC-NN during planning)

Per SH-16, each criterion must be an executable shell command with a documented expected output.
Draft set:

- **ACC-01** — WS auth gate: `pytest tests/http/test_agent_terminal.py -k auth -q` → passes (no cookie
  ⇒ close 1008).
- **ACC-02** — write requires control: `pytest tests/http/test_agent_terminal.py -k control -q` →
  passes (text frame before `take_control` is rejected; after, `send_text` is called).
- **ACC-03** — reaper suspended under control: `pytest tests/app/test_reaper.py -k attached -q` →
  passes (sentinel present ⇒ `end_session` not called).
- **ACC-04** — body marker safety: `pytest tests/core/test_body_regions.py -q` → passes
  (split∘merge round-trips; protected regions byte-preserved; de-fang holds).
- **ACC-05** — body coherence gate: `pytest tests/http/test_monitor_api.py -k body_patch -q` → passes
  (incoherent roadmap/title ⇒ 400; coherent edit ⇒ 200 + markers intact).
- **ACC-06** — collapsible defaults: a unit/asserted check that a 0-ticket column serialises as
  collapsed-by-default and persists (front assertion or a small logic unit extracted to JS-testable
  form; otherwise a documented manual step with screenshot).
- **ACC-07** — build ships the terminal: `npm --prefix web ci && npm --prefix web run build` → exit 0,
  `xterm` present in the built bundle.
- **ACC-08** — full gate: `make check` → all green; `python -c "import kanbanmate"` → exit 0.
- **ACC-09 (manual, mobile)** — documented phone pass: open terminal, take control, type a line +
  Enter, observe the agent react; edit a description; collapse/expand a column and reload (state
  persists). Captured with a screenshot/GIF.
- **ACC-10** — version surfaced: `curl -s --connect-timeout 5 --max-time 10 localhost:<port>/api/health`
  → JSON containing `"version": "<kanbanmate.__version__>"`; the sidebar footer renders it (desktop +
  mobile) — asserted in the manual pass.

## 11. Live verification (post-merge, per operator rule)

"Delivered ≠ merged." After merge + deploy (`pip install -e .` + restart `kanban-km-config`), verify
on the live boards: open a running agent's terminal in KanbanMateUI, take control, send a keystroke,
observe the pane react; edit a ticket description and confirm the markers/status block survive on
GitHub; confirm collapsible state persists across reload. Report proven-live vs blocked-on-infra.

## 12. Out of scope / future

- `pipe-pane`-based streaming optimisation (v1 uses the snapshot loop).
- Multi-operator concurrent control arbitration (single-operator assumption holds today).
- A full JS test runner for the SPA (front coverage stays build + lint + manual ACCEPTANCE).
- Recording/replay of operator sessions beyond the audit log.
