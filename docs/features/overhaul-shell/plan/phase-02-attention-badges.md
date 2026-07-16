# Phase 02 — Attention badges (data sources + WS refresh)

## Gate

- [ ] Phase 01 complete: sidebar is sticky with independent scroll.
- [ ] `cd frontend && npm run lint && npm run typecheck && npx vitest run` passes clean.

## Scope

Replace the single decisions-based badge (`/scraping` = `pending_count` from
`GET /api/decisions`) with three independent badge sources, all rendered through
the existing `badges: Record<path, ReactNode>` mechanism and `NavCountBadge`:

| Route          | Source                                  | Renderer        | Zero state |
| -------------- | --------------------------------------- | --------------- | ---------- |
| `/scraping`    | `counts.awaiting_action` from staging   | `NavCountBadge` | Hidden     |
| `/pipeline`    | Running dot when `state !== 'idle'`     | `StatusDot`     | Hidden     |
| `/acquisition` | Pending wanted `total` from `useWanted` | `NavCountBadge` | Hidden     |

**Files touched:**

- `frontend/src/components/layout/AppShell.tsx` — `AppShellInner` component
- `frontend/src/components/layout/BottomTabBar.tsx` — no change needed (already renders `badges[item.to]`)

### Sub-phase 2.1 — Replace badge data sources in AppShellInner

**Commit:** `feat(overhaul-shell): switch nav badges to staging/pipeline/acquisition sources`

**Change — `frontend/src/components/layout/AppShell.tsx:1-92`:**

Replace the entire `AppShellInner` body. The new version:

- Removes the decisions-based badge query (`useDecisions`, `pendingCount`).
- Adds three lightweight queries: staging counts (page_size=1), pipeline status, pending wanted (page_size=1).
- Computes three badge entries in `useMemo`.

**New imports to add (after line 18):**

```tsx
import { usePipelineStatus } from "@/hooks/usePipelineStatus";
import { useStagingMedia } from "@/hooks/useStagingMedia";
import { useWanted } from "@/hooks/useAcquisition";
import { StatusDot } from "@/components/ds/StatusDot";
```

**(Remove line 18-19 — `decisionsKeys` and `useDecisions` are no longer needed):**

```tsx
// REMOVE:
import { decisionsKeys } from "@/api/decisions";
import { useDecisions } from "@/hooks/useDecisions";
```

**Replace the body of `AppShellInner` (lines 32-92):**

```tsx
function AppShellInner(): ReactElement {
  const [navOpen, setNavOpen] = useState<boolean>(false);
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  // ── Badge 1: /scraping = awaiting_action count from staging ──────────
  // page_size=1 so we pull only the counts aggregate, not the full list.
  const { data: stagingData } = useStagingMedia({ page_size: 1 });
  const awaitingAction: number = stagingData?.counts?.awaiting_action ?? 0;

  // ── Badge 2: /pipeline = running dot when a run is active ────────────
  const { snapshot: pipelineStatus } = usePipelineStatus();
  const pipelineRunning: boolean = pipelineStatus.state !== "idle";

  // ── Badge 3: /acquisition = pending wanted count ─────────────────────
  const { data: wantedData } = useWanted({ status: "pending", page_size: 1 });
  const pendingWanted: number = wantedData?.total ?? 0;

  // ── WS listener: invalidate staging counts + pipeline history on ─────
  // ItemProgressed status changes and run-finished events. The pipeline-
  // status invalidation is handled by usePipelineStatus's own listener;
  // acquisition badge has no WS dependency (wanted state changes on its
  // own poll cycle).
  const lastProcessedRef = useRef(0);
  useEffect(() => {
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;
    const shouldInvalidate = fresh.some(
      (e) =>
        isEvent(e) &&
        (e.type === "ItemProgressed" ||
         e.type === "PipelineEnded" ||
         e.type === "PipelineStarted"),
    );
    if (shouldInvalidate) {
      void queryClient.invalidateQueries({ queryKey: ["staging", "media"] });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", "history"] });
    }
  }, [events, queryClient]);

  // ── Badge map — NavCountBadge at zero renders nothing ────────────────
  const badges = useMemo<Record<string, ReactNode>>(() => {
    const map: Record<string, ReactNode> = {};
    if (awaitingAction > 0) {
      map["/scraping"] = <NavCountBadge count={awaitingAction} />;
    }
    if (pipelineRunning) {
      map["/pipeline"] = (
        <StatusDot status="running" showLabel={false} label="Pipeline en cours d'exécution" />
      );
    }
    if (pendingWanted > 0) {
      map["/acquisition"] = <NavCountBadge count={pendingWanted} />;
    }
    return map;
  }, [awaitingAction, pipelineRunning, pendingWanted]);

  return (
    <div className="flex min-h-screen bg-background font-sans text-foreground">
      <Sidebar badges={badges} />
      {/* ... rest of JSX unchanged from line 82-91 ... */}
```

**Key decisions:**

- **Pipeline badge = `StatusDot`** (not `NavCountBadge`) — a running dot is a binary state, not a
  count. Real props contract (`StatusDot.tsx:18-26`): `status="running"` (PipelineStatus), `label`
  for accessible text, `showLabel={false}` for dot-only — there is no `tone`/`aria-label` prop.
- **Badge map always defined** — passes the object even when empty (Sidebar/BottomTabBar/NavSections already handle missing keys gracefully via `badges?.[item.to]`). This avoids the `undefined` → no-props spread pattern that was used for the single-decisions badge.
- **WS listener replaces the old decisions-only listener** — now invalidates staging counts on `ItemProgressed` (any status, not just `queued_for_decision`) and on `PipelineEnded`/`PipelineStarted` (run boundaries that change what is blocked). The pipeline running dot already has its own WS invalidation in `usePipelineStatus`.
- **Badge staging query polls at 60 s (DESIGN §1.1 — guarantor realignment).** Do NOT inherit
  `useStagingMedia`'s 8 s page interval for a badge that lives on every screen: the endpoint runs a
  filesystem scan per request. The badge query passes an explicit override
  (`useStagingMedia({ page_size: 1 }, { refetchInterval: 60_000, staleTime: 55_000 })` — if the hook
  does not yet accept a query-options second argument, add that optional argument in this same commit;
  page-level callers keep their current cadence). Freshness between polls comes from the WS
  invalidations above. If measurement still shows chattiness, `GET /api/attention/counts` ships per
  DESIGN.
- **No new backend endpoint** — this phase defers `GET /api/attention/counts` to measurement.

### Verification

1. **Typecheck + lint:**

   ```bash
   cd frontend && npm run typecheck && npm run lint
   ```

   Expected: zero errors. Verify the removed imports (`decisionsKeys`, `useDecisions`) have no residual references.

2. **Residual import grep:**

   ```bash
   rg "useDecisions|decisionsKeys" -g '*.tsx' frontend/src/components/layout/AppShell.tsx
   ```

   Expected: zero matches (both removed).

3. **Retarget `AppShell.test.tsx` badge mocks IN THIS SAME COMMIT (per-commit vitest gate —
   guarantor realignment).** The existing badge tests mock `/api/decisions`; switch those mocks to
   the three new sources (staging counts / pipeline status / wanted) with minimal assertions so the
   suite is green at this commit. Phase 04 then extends coverage (helpers, count-based rendering,
   zero states); Phase 05 adds the pipeline-dot + WS-refresh tests.

   ```bash
   cd frontend && npx vitest run src/components/layout/AppShell.test.tsx
   ```

   Expected: green (never commit on a red gate).

4. **Commit:**
   ```bash
   git add frontend/src/components/layout/AppShell.tsx frontend/src/components/layout/AppShell.test.tsx frontend/src/hooks/useStagingMedia.ts
   git commit -m "feat(overhaul-shell): switch nav badges to staging/pipeline/acquisition sources"
   ```

## Completeness check

- [ ] `/scraping` badge reads `counts.awaiting_action` from staging (page_size=1).
- [ ] `/pipeline` badge shows running `StatusDot` when `state !== 'idle'`.
- [ ] `/acquisition` badge reads pending wanted `total` (status=pending, page_size=1).
- [ ] WS listener invalidates staging counts on `ItemProgressed` + `PipelineEnded` + `PipelineStarted`.
- [ ] `NavCountBadge` renders nothing at zero (unchanged behavior).
- [ ] `Badge` component import is removed (no longer used in AppShell).
- [ ] `cd frontend && npm run typecheck` clean (new imports resolve, removed imports don't leave dangling refs).
