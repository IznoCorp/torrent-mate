# Phase 6 — EventStream hook + Dashboard

## Gate

- Phase 5 complete: shell renders, auth flow works end-to-end
  (login → protected routes → logout).
- Backend WS relay functional (Phase 3), auth-guarded handshake working.

## Sub-phases

### 6.1 — `useEventStream` hook + shared `EventStreamProvider` (WebSocket, replay, reconnect) ✅

**Architecture (orchestrator mandate, DESIGN §5.3-anchored)**: ONE WebSocket per
app. The bare `useEventStream` hook owns the socket, but the public seam is an
`EventStreamProvider` (React context) mounted **inside the authenticated shell**
(`AppShell`) — so the login page never connects. TopBar's StatusDot and (6.2) the
Dashboard both read the SAME socket via `useEventStreamContext()`.

**Commits**:

- `feat(tm-shell): add typed useEventStream WebSocket hook` — `api/events.ts` + hook.
- `feat(tm-shell): share event stream via provider and wire StatusDot` — provider,
  TopBar wiring, AppShell mount, tests.

**Files**:

| Action | Path                                                   |
| ------ | ------------------------------------------------------ |
| Create | `frontend/src/api/events.ts`                           |
| Create | `frontend/src/hooks/useEventStream.ts`                 |
| Create | `frontend/src/components/EventStreamProvider.tsx`      |
| Modify | `frontend/src/components/layout/TopBar.tsx`            |
| Modify | `frontend/src/components/layout/AppShell.tsx`          |
| Create | `frontend/src/test/mockWebSocket.ts`                   |
| Create | `frontend/src/hooks/useEventStream.test.tsx`           |
| Create | `frontend/src/components/EventStreamProvider.test.tsx` |

**Work**:

1. `api/events.ts` — discriminated union mirroring the server wire shapes exactly
   (`ws/routes.py` + `ws/relay.py`): `EventMessage {id, type, data: Record<string,
unknown>}`, `HelloMessage {type: "ws.hello", data: {build_commit}}`,
   `PingMessage {type: "ws.ping"}`. Total type guards `isEvent` / `isHello` /
   `isPing` and a safe `parseServerMessage(raw): ServerMessage | null` — zero `any`.
2. `hooks/useEventStream.ts`:
   - Opens `(wss|ws)://<host>/ws/events?last_id=<persisted>` (localStorage key
     `torrentmate:last_event_id`).
   - `ws.hello` → stores `build_commit`, state `'connected'`; `ws.ping` → replies
     `pong`; 45 s missed-ping watchdog → close + reconnect; exponential backoff
     1 s → 30 s with jitter; persists each `EventMessage.id`; bounded events ring
     (cap 10 000); close `4401` → `'disconnected'` and **no** reconnect (REST 401
     flow owns the redirect); StrictMode-safe (per-effect `disposed` token);
     closes on unmount.
   - Returns `{events, connectionState, buildCommit, lastEventId}`.
3. `EventStreamProvider.tsx` — context wrapping the hook; `useEventStreamContext()`
   is the public read seam; mounted once in `AppShell` (authenticated tree only).
4. `TopBar.tsx` — StatusDot now maps `connectionState` to DS signals (connected →
   `done`/success, connecting|reconnecting → `running`/warning, disconnected →
   `error`/danger) with a French `title` tooltip.

**Verification**: vitest (mock WS via `vi.stubGlobal`): `hello` → connected +
`build_commit`; `event` → appended + id persisted; `ping` → `pong` sent; malformed
frame ignored; ring capped; missed ping → reconnect with `last_id` in URL; `4401`
→ no reconnect; StrictMode double-mount → single surviving socket; unmount closes
the socket; TopBar StatusDot reflects connecting → connected → reconnecting.

### 6.2 — Dashboard page (live feed, health, version)

**Commit**: `feat(tm-shell): add dashboard with live feed, health and version cards`

**Files**:

| Action | Path                                                      |
| ------ | --------------------------------------------------------- |
| Create | `frontend/src/pages/Dashboard.tsx`                        |
| Create | `frontend/src/components/dashboard/EventFeed.tsx`         |
| Create | `frontend/src/components/dashboard/EventRow.tsx`          |
| Create | `frontend/src/components/dashboard/HealthCard.tsx`        |
| Create | `frontend/src/components/dashboard/VersionCard.tsx`       |
| Create | `frontend/src/components/dashboard/RecentEventsTable.tsx` |

**Work**:

1. `EventFeed.tsx` — **TanStack Virtual**: scrollable list of `LogLine`
   rows from `useEventStream().events`. Each row: time (mono), type badge
   via `StatusDot`, summary text. Auto-scroll to bottom (toggle button).
   Supports 10 000+ entries at 60 fps.
2. `EventRow.tsx` — single row: `<StatusDot variant={...} />` + timestamp
   (`tabular-nums`) + event type label + truncated data preview.
3. `RecentEventsTable.tsx` — **TanStack Table**: last 50 events, typed
   columns (timestamp, type, summary), sortable.
4. `HealthCard.tsx` — `StatPanel` wrapper: TanStack Query `useHealth()`
   (GET `/api/health`, refetch 30 s). Shows Redis (green/red dot), DB
   status, uptime. Error state → degraded banner.
5. `VersionCard.tsx` — `StatPanel` wrapper: GET `/api/version` → version
   number + `build_commit` short hash.
6. `Dashboard.tsx` — mobile-first grid: health + version cards top
   (2-col ≥ md, stack < md), live feed main area, events table below.

**Verification**: `npx tsc --noEmit && npm run lint && npm run test -- --run`;
dashboard renders with live feed receiving real events, health cards
show status, version card shows commit hash.

## Verification

```bash
make lint && make test                              # backend green
cd frontend && npx tsc --noEmit && npm run lint      # frontend green
cd frontend && npm run test -- --run                  # vitest green
```

**Manual**: boot backend → `npm run dev` → login → dashboard renders,
live feed populated (publish test event via `redis-cli XADD` or trigger
a pipeline dry-run), health card Redis+DB green, reconnect check
(backend restart → WS reconnect → no lost events).
