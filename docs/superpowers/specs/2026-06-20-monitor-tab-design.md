# monitoring — helm PR 2-bis: Monitoring tab (read-only board + agent observability) — DESIGN

> **Codename**: `monitoring` · **Arc**: helm PR 2-bis (monitoring) · **Branch**: `feat/monitoring` ·
> **Type / SemVer**: minor (additive read-only subsystem) · **Builds on**: bridge (helm PR 2,
> merged to `main`).
>
> A read-only **Monitoring** tab in the bridge config UI: per-project GitHub board live status,
> ticket-by-ticket detail, and live agent observability (state + a read-only terminal tail +
> timeline). **No control** — taking over agents is a deliberate later PR (2-ter). Grounded against
> `main` post-bridge; cites `path:line` where it leans on existing engine code.

---

## §1 — Problem & motivation

bridge made the pipeline **configurable** from a browser. It does not show what the pipeline is
**doing**: which tickets are where, which agents are running, what they're working on, whether one is
blocked or waiting for a human. Today that needs `kanban state` / `kanban sessions` / `tmux attach`
on the host. monitoring surfaces it in the same UI, per board, read-only — a single place to watch the
orchestration without shelling in.

The data already exists in the engine; monitoring is an **observability surface** over it, adding no new
authority.

## §2 — Goals / non-goals

### Goals

1. A **Monitoring** tab (per selected board, reusing bridge's board switcher) showing the live board:
   columns → tickets, each with its health/status and whether an agent is on it.
2. **Ticket detail** on demand: description/body, parsed markers (roadmap / codename / design /
   plans), comments, and a merged **timeline** (transitions / progress / comments).
3. **Live agent view** for running tickets: state (running / waiting / blocked), heartbeat age,
   stage, duration, branch/worktree, **plus a read-only terminal tail** (`tmux capture-pane`).
4. **Two-speed auto-refresh**: agent data (local: store + tmux) ~3 s; board overview from a
   **server-cached GitHub snapshot** (TTL ~15 s, ~1 GraphQL call / 15 s / board); ticket detail
   fetched **on demand** when a ticket is opened.
5. Read-only and **auth-protected** (behind bridge's login).

### Non-goals

- **No agent control / interaction** — no `send-keys`, no card moves, comments, cancel, or relaunch
  from this tab. `capture-pane` is non-interactive. Control is a separate future PR (2-ter).
- **No daemon change** — the config-serve process reads GitHub (cached) + the persisted store + tmux;
  it does not modify the daemon, the board, or any config.
- **No new persistence** — monitoring writes nothing (no new files in the runtime root).
- **No notifications / multi-host / history store** — point-in-time observability only.

## §3 — Data sources (all existing)

| Need                                                       | Source                             | Reuse                                                                                             |
| ---------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------- |
| Board columns → tickets (number, title, column)            | GitHub snapshot, **server-cached** | `adapters/github/client.GithubClient.snapshot()` → `core/domain.BoardSnapshot`                    |
| Per-ticket health/status                                   | persisted last_status + snapshot   | the store's status + `core/status_update` domain health                                           |
| Running agents (state, heartbeat, stage, duration, branch) | persisted running state + tmux     | `app/status_reporter` `RunningAgent` building blocks (`status_reporter.py:259-307,455`)           |
| Agent terminal tail                                        | tmux `capture-pane`                | `adapters/workspace/sessions.py:164` pattern → add a public read-only `capture_pane(name, lines)` |
| Ticket body markers                                        | ticket body                        | `core/ticket_fields.parse_ticket_fields` + `core/body_edit.roadmap_marker`                        |
| Ticket comments / timeline                                 | GitHub on demand                   | `GithubClient.issue_context` / `list_issue_comments`; progress from the store                     |

## §4 — Architecture

```
browser (Monitoring tab) ──fetch──▶ http/config_api.py (auth-guarded, bridge)
                                       │
                                       ▼
                                  app/monitor.py  (read-only orchestration service)
                                       ├─▶ adapters/github (snapshot — server-cached; issue ctx/comments — on demand)
                                       ├─▶ adapters/store  (persisted running state + heartbeat + last_status + progress)
                                       ├─▶ adapters/workspace/sessions (tmux: liveness + capture_pane)
                                       └─▶ core (ticket_fields, status_update, domain)  [pure]
```

- **`app/monitor.py`** (NEW) — the read-only monitoring service. Pure orchestration over adapters +
  core; one function per endpoint payload. Mirrors how `app/status_reporter` already assembles agent
  snapshots; monitoring reuses those building blocks rather than duplicating them.
- **`http/config_api.py`** — new auth-guarded GET endpoints (below). A small **TTL cache** for the
  board snapshot lives here (module-level, per project_id → (timestamp, snapshot)), so concurrent /
  rapid polls collapse to ~1 GitHub call per TTL window.
- **`adapters/workspace/sessions.py`** — add a public `capture_pane(name: str, lines: int) -> str`
  (read-only; the `capture-pane -p -J` invocation already exists internally) + a `session_exists`
  check (likely already present via the sessions lister).
- Layering unchanged: `http` → `app`/`adapters`/`core`/`cli.init`; `app` → `adapters`/`core`/ports;
  `core` pure. Registry/project resolution stays in `http` (reuses bridge's `_resolve_entry`).

## §5 — HTTP endpoints (all GET, auth-guarded, `?project=` selector)

1. **`GET /api/monitor/board?project=`** → board overview.
   `{"columns": [{key, name, column_class}], "tickets": [{number, title, column_key, health,
agent_state|null}], "agents_summary": {running, waiting, blocked}}`. Board from the cached
   snapshot; `agent_state` per ticket + the summary from the persisted store + tmux. No on-demand
   GitHub beyond the cached snapshot.
2. **`GET /api/monitor/agents?project=`** → live agents.
   `{"agents": [{issue, title, stage, state, heartbeat_age, duration_s, branch, session_alive}]}`.
   Local only (store + tmux) — safe to poll ~3 s.
3. **`GET /api/monitor/agent/{issue}/pane?project=&lines=N`** → read-only terminal tail.
   `{"alive": bool, "lines": "<capture-pane text>"}`. `capture-pane` snapshot; `alive=false` +
   empty when the session is gone. N bounded (default ~200, max ~500).
4. **`GET /api/monitor/ticket/{number}?project=`** → ticket detail (on demand).
   `{number, title, column_key, health, body, markers: {roadmap, codename, design, plans},
comments: [{author, created_at, body}], timeline: [{kind, at, text}]}`. From GitHub +
   store-held progress; `kind ∈ comment | progress | move`.

All return the bridge-standard errors: 503/404/400 (project resolution), 401 (unauth), and a clean
5xx/`detail` on a GitHub/tmux failure (the SPA shows last-known + a banner — §7).

## §6 — UI (Monitoring tab)

A new **Monitoring** entry in the board-scoped nav. Master-detail (consistent with Transitions):

- **Top strip** — board health summary: counts per column + running/waiting/blocked agent badges.
- **Left** — board overview: columns as groups, each ticket a compact card (number, title, health
  pill, agent badge when one is running). Click selects.
- **Right** — selected ticket detail:
  - Header: number, title, current column, health.
  - Description + **marker links** (roadmap / codename / design / plans) — render/link the artifact.
  - **Timeline**: comments + progress + moves, newest-first.
  - **Agent panel** (when an agent runs on the ticket): state / heartbeat / stage / duration /
    branch, and the **read-only terminal tail** (mono, auto-scrolling, ~3 s refresh) with a clear
    "read-only — `tmux attach` to interact" note (the seam for the future control PR).
- **Refresh**: agents + pane poll ~3 s; board ~15 s (server cache); ticket detail on open + a manual
  refresh. All pollers pause when the tab is backgrounded (visibilitychange) to spare quota/CPU.
- i18n FR/EN; design-system styled; reuses `HealthPill`, `KeyChip`, `TransitionRow`-like cards.

## §7 — Error handling

- **GitHub failure** (board/ticket): serve the last cached snapshot if any + an error banner; never a
  blank board. Ticket detail failure → inline error in the detail pane, board unaffected.
- **tmux session gone** (agent ended mid-view): pane endpoint returns `alive:false` → "session
  ended"; the agent drops from the live list on its next poll.
- **No agent on a ticket**: detail shows metadata/timeline only, no agent panel.
- **Cache staleness** is bounded by the TTL; the UI shows a "updated Ns ago" hint.

## §8 — Testing

- **`app/monitor`** — unit tests with fake board snapshot + fake store + fake tmux: board payload
  shape, agent assembly (state/heartbeat/stage), ticket detail merge (timeline ordering), pane
  passthrough, session-gone path.
- **HTTP** — FastAPI `TestClient`: each endpoint's shape, `?project=` resolution (404/400), auth
  (401 unauth), the board cache (two rapid calls → one underlying snapshot via a counting fake).
- **`capture_pane`** — adapter unit test (fake tmux runner) incl. session-absent.
- **SPA** — light component checks (board grouping, agent badge, pane render); heavy logic is
  server-side.

## §9 — Out of scope (explicit)

Agent control/interaction (send-keys, moves, cancel, relaunch — future PR 2-ter); notifications;
historical metrics/retention; multi-host aggregation; any daemon change or new runtime-root file.
