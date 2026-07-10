# Phase 4 — Frontend Page

## Gate

- [ ] `make check` — backend gate (Phase 1–2 routes still green)
- [ ] `cd frontend && npm run lint` — zero errors
- [ ] `cd frontend && npm run typecheck` — zero errors
- [ ] `cd frontend && npx vitest run` — all tests pass (including new page tests)
- [ ] Commit with `chore(acq-watch): phase 4 gate — frontend page`

## Prerequisites

- Phase 3 SHIPPED — typed client + hooks available.
- `frontend/src/api/schema.d.ts` regenerated (Phase 1–2 openapi regen).
- Nav entry already active (`nav.ts:71`, Radar icon, `/acquisition` path,
  `BOTTOM_TAB_PATHS` includes `"/acquisition"`). No nav changes needed.

## Objectives

1. Replace the `ComingSoon` stub at `router.tsx:68` with a real `AcquisitionPage`.

2. Build the page with 4 panels (tabs or stacked sections mirroring
   `Maintenance.tsx`):
   - **Followed** — table of followed series + add form (tvdb_id + title
     input) + per-row unfollow button + per-row edit-cadence dialog.
   - **Wanted** — paginated status table with status filter.
   - **Obligations** — seed/ratio panel (table of obligations per tracker
     with status badges).
   - **Watcher** — status card: last successful run timestamp, enabled
     toggle (calls `setWatcher` from `api/client.ts`), recent watcher runs
     as a mini history list.

3. Live updates via `useEventStreamContext` — filter acquisition events and
   invalidate matching queries using the R13 new-events-only ref pattern
   (NOT `events.some` over the ring).

4. Vitest: renders each panel, add/unfollow flow, empty states, a11y.

## DESIGN gotchas

- **Reuse existing watcher toggle** — the Watcher panel's enable/disable switch
  calls `setWatcher({enabled: bool})` from `api/client.ts` (i.e.
  `POST /api/pipeline/watcher`). No new route, no new client function.
- **No quality-profile editor** — the Followed table may show the quality
  profile as a read-only badge/tag, but there is NO edit dialog for it
  (RP3a deferred). Only `cadence` gets an edit dialog.
- **R13 new-events-only ref pattern** — `useEventStreamContext()` returns the
  full event ring (`events`). The page holds a `const lastSeenRef = useRef(0)`
  and iterates `events.slice(lastSeenRef.current)` on each render, updating
  `lastSeenRef.current = events.length` after processing. This avoids
  `events.some(...)` which re-scans the ring on every render and risks
  missing events if the ring wraps between renders.
- **Web-side event emission for follow writes is OUT of scope** — the acting
  client invalidates its own queries on mutation success. Cross-client live
  update comes from the acquisition event stream (pipeline/watcher emits
  `SeriesFollowed` etc. → Redis → WS → `useEventStreamContext`). A web-side
  follow write does NOT emit `SeriesFollowed` — it just refetches.
- **Empty states for every panel** — "No followed series" / "No wanted items" /
  "No obligations" / "Watcher never run" — each with a descriptive message,
  not a blank white space.

## Files to create

| File                                          | Purpose                                           |
| --------------------------------------------- | ------------------------------------------------- |
| `frontend/src/pages/AcquisitionPage.tsx`      | Main page with 4 panels, forms, WS invalidation   |
| `frontend/src/pages/AcquisitionPage.test.tsx` | Vitest: renders panels, flows, empty states, a11y |

## Files to modify

| File                      | Change                                                      |
| ------------------------- | ----------------------------------------------------------- |
| `frontend/src/router.tsx` | Replace `ComingSoon` stub at line 68 with `AcquisitionPage` |

## router.tsx change

```diff
 import ComingSoon from "@/pages/ComingSoon";
+import AcquisitionPage from "@/pages/AcquisitionPage";

   {
     path: "acquisition",
-    element: <ComingSoon title="Acquisition" wave="S7" />,
+    element: <AcquisitionPage />,
   },
```

The `ComingSoon` import can be removed if `acquisition` was its last use —
check that no other route still references it (currently only S7 was using
it as a stub; all prior waves have their real pages).

## AcquisitionPage.tsx — component structure

```typescript
/**
 * Acquisition + Watcher page (acq-watch feature).
 *
 * Four tabbed panels: Followed (CRUD), Wanted (status queue),
 * Obligations (seed/ratio), Watcher (status + toggle + recent runs).
 *
 * Live updates: the acquisition event stream (via useEventStreamContext)
 * invalidates the matching query when a relevant event arrives, using
 * the R13 new-events-only ref pattern.
 */

import { useState, useRef, useCallback } from "react";
// shadcn/ui imports: Card, Tabs, Table, Button, Input, Badge, Dialog, Switch, Label
// TanStack: useQueryClient
// Custom hooks: useFollowed, useWanted, useObligations, useAcquisitionStatus,
//   useFollow, useUpdateFollow, useUnfollow, acqKeys
// Context: useEventStreamContext
// API: setWatcher (for watcher toggle)
// Types from @/api/acquisition
```

### Panel 1: Followed

- **Table**: columns = Title, TVDB ID, Active (badge), Cadence (formatted),
  Wanted Pending (count), Quality (read-only tag), Actions (unfollow button
  - edit-cadence button).
- **Add form**: inline at top — tvdb_id (number input), title (text input),
  "Follow" submit button. Calls `useFollow().mutate({tvdb_id, title})`.
  On success: clear form, invalidate.
- **Edit-cadence dialog**: opens on per-row "Edit cadence" button. Contains
  a number input for `interval_minutes`. Calls
  `useUpdateFollow().mutate({id, body: {cadence: {interval_minutes}}})`.
- **Unfollow**: per-row button → `useUnfollow().mutate(id)`.

### Panel 2: Wanted

- **Status filter**: tabs or dropdown — All, Pending, Searching, Grabbed,
  Done, Abandoned.
- **Paginated table**: columns = Title, Kind, Season, Episode, Status
  (colored badge), Attempts, Enqueued (relative time), Last Search
  (relative time).
- **Pagination**: previous/next buttons with "Page X of Y" label.
- The hook: `useWanted({status, page, page_size})` — page and status are
  component state.

### Panel 3: Obligations

- **Status filter**: All, Pending, Breached, Satisfied.
- **Table**: columns = Info Hash (truncated), Tracker, Path (truncated),
  Min Seed Time, Min Ratio, Observed Ratio, HnR Count, Status (badge:
  pending/satisfied/breached).

### Panel 4: Watcher

- **Status card**: last successful run (formatted datetime or "Never"),
  watcher enabled/disabled (Switch component).
- **Enabled toggle**: calls `setWatcher({enabled: !current})`, then
  invalidates `acqKeys.status()`.
- **Recent runs**: small table of the last N watcher-triggered pipeline
  runs from `useAcquisitionStatus().data.recent_runs` — columns = Run UID
  (truncated), Started, Ended, Outcome (badge).

### Live invalidation (R13 pattern)

```typescript
// Inside AcquisitionPage:
const { events } = useEventStreamContext();
const lastSeenRef = useRef(0);
const queryClient = useQueryClient();

// Process new events only (not the whole ring every render):
const newEvents = events.slice(lastSeenRef.current);
lastSeenRef.current = events.length;

for (const msg of newEvents) {
  switch (msg.type) {
    case "SeriesFollowed":
    case "SeriesUnfollowed":
      queryClient.invalidateQueries({ queryKey: acqKeys.all });
      break;
    case "WantedEnqueued":
    case "WantedAbandoned":
    case "GrabSucceeded":
    case "GrabFailed":
      queryClient.invalidateQueries({ queryKey: acqKeys.wanted({}) });
      queryClient.invalidateQueries({ queryKey: acqKeys.followed({}) });
      break;
    case "SeedObligationRecorded":
    case "SeedObligationBreached":
    case "SeedObligationSatisfied":
      queryClient.invalidateQueries({ queryKey: acqKeys.obligations({}) });
      break;
    case "RatioMeasured":
      queryClient.invalidateQueries({ queryKey: acqKeys.obligations({}) });
      break;
    case "WatcherRunTriggered":
      queryClient.invalidateQueries({ queryKey: acqKeys.status() });
      break;
  }
}
```

Note: `SeriesFollowed`/`SeriesUnfollowed` events from the pipeline/watcher
invalidate the full `acqKeys.all` namespace because a series change can
affect the wanted queue too. The web-side follow write does NOT emit these
events (out of scope) — it refetches on the mutation response.

## Tests

### AcquisitionPage.test.tsx

Use `render` with `QueryClientProvider` + `MemoryRouter` + mocked hooks.
Mock `useEventStreamContext` to return an event ring.

Key test cases:

1. **Renders the Followed panel by default** — table headers visible, "No
   followed series" empty state when data is empty.

2. **Renders followed series in table** — mock `useFollowed` returning 2
   items; assert title and tvdb_id columns rendered.

3. **Add form** — fill tvdb_id + title, click "Follow", assert
   `useFollow().mutate` called with correct body.

4. **Unfollow button** — click unfollow on a row, assert
   `useUnfollow().mutate(id)` called.

5. **Edit-cadence dialog** — click edit-cadence button, fill interval,
   click save, assert `useUpdateFollow().mutate` called.

6. **Wanted panel with pagination** — mock `useWanted` with 55 items;
   assert page 1 shows 50 rows, "Page 1" label, next button exists.

7. **Status filter on wanted** — select "Pending" filter, assert
   `useWanted` called with `{status: "pending"}`.

8. **Obligations panel** — mock `useObligations` with 2 items; assert
   info_hash and tracker rendered.

9. **Watcher panel — toggle** — mock `useAcquisitionStatus` with
   `watcher_enabled: true`; click toggle, assert `setWatcher({enabled:
false})` called (mocked).

10. **Watcher panel — recent runs** — mock `useAcquisitionStatus` with 3
    `recent_runs`; assert run UIDs rendered.

11. **Empty states** — mock every hook returning empty/undefined data;
    assert each panel shows its empty message, not blank.

12. **Live invalidation (R13)** — mock `useEventStreamContext` returning
    `{events: [{type: "WantedEnqueued", ...}], ...}`; assert
    `queryClient.invalidateQueries` called with `acqKeys.wanted({})`.

13. **a11y** — use `axe` or `@testing-library/jest-dom` role assertions:
    tabs have `role="tablist"`, table has `role="table"`, form inputs have
    labels.

## Styling notes

- Mirror `Maintenance.tsx` layout: `Card` per panel inside `Tabs`.
- Use shadcn/ui components: `Card`, `Tabs`, `Table`, `Button`, `Input`,
  `Badge`, `Dialog`, `Switch`, `Label`, `Select`.
- Status badges use the existing color convention (e.g. green for
  success/satisfied, red for breached/abandoned, yellow for pending).
- Mobile-responsive: tables scroll horizontally on narrow viewports
  (`overflow-x-auto` wrapper). The add form stacks vertically on mobile.
