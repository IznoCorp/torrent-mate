# Phase 6 — EventStream hook + Dashboard

## Gate

- Phase 5 complete: shell renders, auth flow works end-to-end
  (login → protected routes → logout).
- Backend WS relay functional (Phase 3), auth-guarded handshake working.

## Sub-phases

### 6.1 — `useEventStream` hook (WebSocket, replay, reconnect)

**Commit**: `feat(tm-shell): add typed useEventStream WebSocket hook`

**Files**:

| Action | Path                                   |
| ------ | -------------------------------------- |
| Create | `frontend/src/api/events.ts`           |
| Create | `frontend/src/hooks/useEventStream.ts` |

**Work**:

1. `api/events.ts` — discriminated union of WS message types:
   `EventMessage {id: string, type: string, data: unknown}`,
   `HelloMessage {type: "ws.hello", build_commit: string}`,
   `PingMessage {type: "ws.ping"}`. Type-narrowing helper
   `isEventMessage(msg)`, `isHello(msg)` etc.
2. `hooks/useEventStream.ts`:
   - Opens `wss://<host>/ws/events?last_id=<persisted>` (reads/writes
     `localStorage` key `torrentmate:last_event_id`).
   - On `ws.hello` → stores `build_commit`, sets `connectionState` to
     `'connected'` (used by StatusDot).
   - On `ws.ping` → replies `pong`. Missed ping for 45 s → reconnect
     with exponential backoff (1 s → 30 s max).
   - Persists last `id` to localStorage per `EventMessage`.
   - Replay: reconnect with `last_id` → server-side `XRANGE` replay.
   - Returns `{events: EventMessage[], connectionState, lastEventId}`.
   - Cleanup: close WS on unmount.

**Verification**: vitest: mock WS → `hello` sets connected → `event` message
pushes to events array → close → reconnect with `last_id` in URL.

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
