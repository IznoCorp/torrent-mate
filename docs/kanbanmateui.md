# KanbanMateUI — the web console

**KanbanMateUI** is KanbanMate's web SPA: a single-page app that is both a **config builder** and a
live **operator console** for the boards a daemon drives. It is served by `kanban config serve`, runs
in production as the PM2 app `kanban-km-config` on loopback `127.0.0.1:8796`, and is fronted by Caddy
(TLS) at **https://km.iznogoudatall.xyz**.

The same SPA covers three kinds of work:

```
┌──────────────────────────── KanbanMateUI ────────────────────────────┐
│  VIEWS            CONFIG                       DAEMON · whole host     │
│  ─────            ──────                       ───────────────────     │
│  Monitoring  ◀──  Columns      (columns.yml)   Projects (projects.json)│
│  Board       ◀──  Transitions  (transitions.yml)  Profiles (read-only) │
│  Issues           Defaults                     Admin / Ops             │
│                   Validation                                           │
│                   YAML (read-only)                                     │
└───────────────────────────────────────────────────────────────────────┘
                board-scoped tabs                daemon-scoped tabs
```

The left sidebar carries a **board switcher** (the daemon may drive several projects). Board-scoped
tabs edit the _selected_ board's config; the amber **Daemon · whole host** group edits the registry
and host operations. After login the default landing view is **Monitoring**.

---

## Architecture in one paragraph

Under the native one-way board model (codename _keel_), each project's placement authority is a
**local `board.json`** store — _not_ GitHub. The daemon writes `board.json` first, then mirrors the
move to GitHub's Status field (one-way). KanbanMateUI is the **primary** surface; the GitHub board is
secondary. Because placement lives in a local file, the Board and Monitoring views read it in
**sub-millisecond** local reads (`stat` + a tiny JSON parse), with no GitHub round-trip on the read
path. Changes are pushed to the SPA over **Server-Sent Events** so an operator drag or a daemon
auto-advance surfaces **sub-second**. (A drag made on the _GitHub_ board, the secondary surface, is
re-ingested by the `kanban serve` webhook receiver and written back into `board.json`.)

---

## Board view

The **Board** tab is a real, draggable Kanban board reading the local `board.json` directly.

**Reading.** On open it fetches `GET /api/board/state` (columns + cards + a board `version` int). The
view subscribes to the SSE change stream (`/api/monitor/stream`) and refetches on any `change` event,
backed by a **15 s visibility-gated backstop poll** so a dropped or flapping stream degrades
gracefully to polling. The board only re-renders when the `version` int actually changed, so an
unchanged refresh never disturbs a drag in progress.

**Moving a card = a native move.** A drag (desktop) or the move bottom-sheet (mobile) calls
`POST /api/board/move` (or `/place` / `/reorder`). The native store is the placement authority, so the
move is written to `board.json` first and then mirrored to GitHub — **there is no revert**: the card
stays where you dropped it. The server reads the GitHub state back after the mirror write and reports a
**verified** outcome, surfaced as an honest toast:

| `mirror_state` | Toast                                                     |
| -------------- | --------------------------------------------------------- |
| `synced`       | "Card moved and synced to GitHub ✓"                       |
| `disabled`     | "Card moved ✓" (no GitHub mirror configured)              |
| `unconfirmed`  | "Moved locally — GitHub sync not confirmed (try Refresh)" |
| `failed`       | "Moved locally — GitHub sync failed"                      |

Moves use **optimistic locking**: each request carries the board `version`; a concurrent edit returns
`409` and the UI re-syncs to server truth with a "Board changed — refreshed" notice. Dragging is
disabled while a mutation is in flight to avoid sending a stale version.

**Desktop vs mobile.** Desktop is a full-height horizontal multi-column board with HTML5
drag-and-drop, an insertion indicator, and **collapsible columns** (empty columns collapse to a thin
counter strip by default; the override is persisted per project). Mobile shows **one column at a
time** via a scrollable tab strip with counts, a full-width card list, ↑/↓ reorder buttons, and a
big **move** bottom-sheet.

**Card face.** Each card shows `#number`, a two-line title, a body excerpt, and a deep-link button
that opens that ticket in **Monitoring**. A **closed** GitHub issue carries a muted "Closed" badge
(violet, with a `CircleSlash` icon — the _Clôturé_ indicator) and its title is struck through; the
`is_closed` flag rides the GitHub identity fetch.

**Toolbar.** A `rev.` chip shows the current board revision (the optimistic-locking token), a
**Refresh** button forces a re-read, and an **Import** button (2-step confirm) re-seeds card placement
from GitHub, overwriting the local order.

> **Native-only.** The Board view requires `board_backend = native` for the selected project. A
> non-native project returns `409` and the view shows "Native board not enabled — enable the native
> board backend on the Projects page, then run Import to seed it."

---

## Monitoring view

The **Monitoring** tab is the live operator console: a read-only board overview plus a detail panel
for the selected ticket, the running agent, and its terminal. It is the default landing view.

**Live updates.** Board placement + agent list are **pushed over SSE** (`/api/monitor/stream`, which
emits when the `board.json` version or the daemon heartbeat tick changes), so an operator drag or an
engine transition surfaces **sub-second**. A 15 s backstop poll covers a dropped stream; the agent
_pane tail_ (`~3 s`) and the per-ticket _track labels_ (`~4 s`) keep their own polls. Everything
pauses while the browser tab is hidden.

**Ticket detail.** Selecting a ticket loads `GET /api/monitor/ticket/{n}`: its current column, body
(rendered markdown, with an inline editor), artifact chips/links (roadmap, codename, brainstorm,
design, plan docs — the doc links open a markdown reader), the agent panel, and the timeline of
comments and events (newest first, localized timestamps).

**Status + Track selectors** sit side by side on desktop, stacked on mobile:

- **Status** (`monitor.move_to`) — change the ticket's column. This enqueues an **operator move
  intent** the daemon drains on its next tick ("Move queued — the board updates shortly"), then the
  detail refetches so the selector reflects the new column without a manual refresh. Columns the
  workflow disallows from the current column are shown disabled (the backend's workflow-aware
  `move_targets`).
- **Track** (skiff fast-track lane) — set the ticket's lane to **Full / Lite / Express**, or **Auto**
  to clear the label. The selector writes the `track:*` label via `POST .../track`; the change is
  optimistic and then reconciled by the next board-tracks poll.

**Launching an agent.** When the selected ticket has no running agent, a **Launch an agent** box lets
you run an ad-hoc Claude agent on it _without_ a transition (no card move): a markdown prompt plus a
**profile** picker (`dev` / `check` / `prepare` / `docs`). This enqueues a `launch` intent (carrying a
verified launch token) the daemon picks up on its next tick. An empty prompt launches a bare agent you
drive by taking control of the terminal.

**Agent terminal.** When a ticket has a _live_ agent session, an **Interactive terminal** button
attaches an `xterm.js` terminal to the agent's tmux pane over a WebSocket
(`/api/monitor/agent/{issue}/attach`): raw PTY bytes stream both ways. It is **read-only until you
take control**, supports fullscreen/font-size, on-screen quick keys (Enter / Esc / Ctrl-C) for
phones, and a 2-step-confirm kill. When the agent is finished/dead the panel shows a static read-only
pane tail and "Session ended."

---

## Issues view

The **Issues** tab is the idea-capture hub: a flat, newest-first list of every ticket on the board
(reflecting the Projects v2 board), each with its column badge. **+ New ticket** opens a title +
markdown-description form; on create the issue is opened on GitHub **and** added to the board at
**Backlog** (`POST /api/board/new-ticket`), then you land on the new ticket's editor to refine it.
Opening a ticket lets you edit its description (saved back to the GitHub issue) and jump to it on
GitHub. A new ticket appears in the list immediately (the list reloads after create).

---

## Config builder

Board-scoped config edits target the _selected_ board's config files. The shell carries a draft per
board with **Validate** and **Save** actions (Save is blocked while validation has errors; the header
shows the error count and a health pill).

| Tab             | File                 | What it does                                                                                                                                                                                                                                           |
| --------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Columns**     | `columns.yml`        | The ordered set of columns (keys + display names). A separate **Sync board** action pushes this set onto the GitHub board's Status options.                                                                                                            |
| **Transitions** | `transitions.yml`    | The whitelist of allowed card moves — each edge carries `from`/`to`, a permission `profile`, an `advance` directive (e.g. `advance:auto:<col>`), the agent prompt, and `on_fail`. This is where the skiff lane behaviour and the launch/CI gates live. |
| **Defaults**    | (per-board defaults) | Scalar defaults such as the move rate-limit.                                                                                                                                                                                                           |
| **Validation**  | —                    | The semantic checks the server runs on the config (the `V1–V11` rules). Errors block Save; each finding deep-links to the offending tab.                                                                                                               |
| **YAML**        | (read-only)          | A read-only preview of the two files the config renders to, exactly as the daemon reads them.                                                                                                                                                          |

Validation runs server-side (`POST /api/config/validate`); Save (`POST /api/config`) writes the files,
then re-validates. The header **Save** button flips to "Saved" as confirmation that the write landed.

### Daemon · whole host

The amber **Daemon** group is host-wide, not per-board:

- **Projects** — the boards this daemon drives, from the host-wide registry `projects.json`. Each
  entry carries `project_id`, `repo`, `board_backend`, `ingress`, and the GitHub binding. Only two
  toggles are editable here: **enabled** (whether the daemon drives the board at all) and **ingress**
  (`polling` | `webhook`). It also hosts project **onboarding** — add an existing local clone under the
  onboarding roots (`~/dev`, `~/deploy`, `~/staging`) or clone a GitHub repo by URL — and removal.
- **Profiles** — a read-only reference of the permission profiles (`docs` / `prepare` / `dev` /
  `check`) that the daemon materializes into each agent worktree's `.claude/settings.json`.
- **Admin / Ops** — host-wide health dashboard and daemon control: per-project daemon liveness,
  PM2 app start/stop/restart with bounded log tails, the global **PAUSE** kill-switch, redeploy from
  `main`, and the recent jobs ledger.

### First-run wizard

On a fresh host with an empty registry (`GET /api/projects` returns `503`), the SPA shows an **install
wizard** instead of the normal shell: paste a GitHub token → register the first project → provision
the Projects v2 board → bootstrap the PM2 apps. On completion it reloads the registry and falls
through to the normal console.

---

## Login, exposure, and chrome

**Auth.** The config server is **loopback-bound** by default and exposed remotely only through the
operator's reverse proxy (Caddy/TLS). An optional **single-operator login** protects an exposed UI:
credentials come from the environment (`KANBAN_MATE_UI_LOGIN` / `KANBAN_MATE_UI_PASSWORD`, loaded from
the gitignored `.env`). An **empty password disables the login** (open mode — loopback/dev). When
enabled, the SPA shows a login screen; a successful `POST /api/login` sets a signed, expiring
**HttpOnly** session cookie (HMAC-SHA256 over `login:expiry`, 24 h TTL, constant-time comparison, no
server-side session store). All mutating `/api/*` requests also carry a double-submit CSRF token
(`X-KM-CSRF`, echoing the `km_csrf` cookie).

**i18n + theme.** The shell header carries an **EN/FR** language switcher (persisted in
`localStorage`; English is the fallback) and a **theme** switcher (light / dark / **system**, default
system — system follows the OS and reacts live). The active tab, selected board, sidebar
collapse-state, and the open Monitoring ticket all persist across reloads, and a PWA install button is
offered. A **STAGING** amber frame marks the staging instance
(`km-staging.iznogoudatall.xyz` → `kanban-staging-config`).

---

## Gotcha — re-import after a column change

The Board and Monitoring views read placement from the local `board.json`. If you change the columns
on the GitHub board (or via the Columns tab + Sync board), `board.json` does **not** pick up the new
column automatically — and the native placement engine cannot reconcile a column it does not know
about. After any column change, run **Import** (Board view toolbar) or `kanban board import` to re-sync
`board.json` from GitHub.
