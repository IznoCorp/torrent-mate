# Phase 4 — Frontend /decisions Page + Badge + Typed Client

## Gate

- [ ] Phase 3 complete — all 5 REST endpoints functional, OpenAPI regenerated
- [ ] `frontend/openapi.json` + `frontend/src/api/schema.d.ts` committed and CI-green
- [ ] Frontend lint + typecheck + vitest green on clean checkout

---

### Sub-phase 4.1 — API client + typed hooks

**Creates:** `frontend/src/api/decisions.ts`
**Test:** `frontend/src/api/decisions.test.ts`

**DESIGN ref:** §7 typed client helpers via `apiFetch` `params` (R15 — no raw fetch)

Export typed functions using `apiFetch` from `@/api/client`:

- `fetchDecisions(params: { status?, page?, page_size? }) → DecisionsResponse`
- `fetchDecisionDetail(id: number) → DecisionDetail`
- `searchDecisionCandidates(id: number, body: SearchRequest) → SearchResponse`
- `resolveDecision(id: number, body: ResolveRequest) → ResolveResponse`
- `dismissDecision(id: number) → void`

TanStack Query hooks:

- `useDecisions(status?, page)` — `queryKey: ['decisions', { status, page }]`
- `useDecisionDetail(id)` — `queryKey: ['decisions', id]`
- `useResolveDecision()` — `useMutation` with `onSuccess` invalidation of
  `['decisions']` + `['pipeline', 'history']`
- `useDismissDecision()` — `useMutation` with `onSuccess` invalidation of
  `['decisions']`
- `useSearchCandidates()` — `useMutation` (no query key invalidation; search is
  read-only)

Test: mock `apiFetch`, verify query keys, mutation invalidation, error paths (401, 404,
409, 410).

**Commit:** `feat(scrape-arbiter): add typed decisions API client and TanStack hooks`

---

### Sub-phase 4.2 — /decisions page + components

**Creates:**

- `frontend/src/pages/Decisions.tsx`
- `frontend/src/pages/Decisions.test.tsx`
- `frontend/src/components/decisions/DecisionList.tsx`
- `frontend/src/components/decisions/DecisionList.test.tsx`
- `frontend/src/components/decisions/DecisionDetail.tsx`
- `frontend/src/components/decisions/DecisionDetail.test.tsx`
- `frontend/src/components/decisions/CandidateCard.tsx`
- `frontend/src/components/decisions/CandidateCard.test.tsx`

**DESIGN ref:** §7 — mobile-first, shadcn/TanStack, DS components; candidate cards
(poster, title, year, score bar); actions Choisir / Re-chercher / Ignorer; RunLogFeed reuse

**Decisions.tsx** (page): two states — list view (default) and detail view (when a
decision is selected). Uses `useDecisions('pending')` to fetch pending list, renders
`DecisionList` + `DecisionDetail` side-by-side on desktop, stacked on mobile. Filter chip
row for status (`pending` / `resolved` / `dismissed` / `superseded`). Uses design-system
components: `Card`, `Badge` (for trigger chip), `Button`.

**DecisionList.tsx**: renders scrollable list of `DecisionListItem`. Each row:
extracted title, folder path (truncated), trigger chip (`Badge` with variant per trigger
— `below_threshold` = red, `mid_band` = yellow, `ambiguous` = orange), candidate count.
Click → select detail.

**DecisionDetail.tsx**: full detail panel. Shows extracted title/year, trigger explanation
text, candidate cards grid. Search override form: `Input` for title, `Input` for year →
`Button` "Re-chercher" triggers `useSearchCandidates()`. Results replace current
candidates in the UI (live search, no persistence). Action buttons: `Button` "Choisir"
(primary, triggers `useResolveDecision()` on selected candidate), `Button` "Ignorer"
(secondary, triggers `useDismissDecision()`). Live resolve output: renders `RunLogFeed`
(reused from S3, `@/components/pipeline/RunLogFeed`) with the `run_uid` from the resolve
response. On resolve success, item leaves the list.

**CandidateCard.tsx**: `Card` with poster image (lazy-loaded, fallback placeholder),
title, year, score bar (progress bar component), provider badge. Click → selects
candidate for resolve.

**Commit:** `feat(scrape-arbiter): add /decisions page with list, detail, and candidate cards`

---

### Sub-phase 4.3 — Badge in AppShell + route registration

**Modifies:**

- `frontend/src/router.tsx` (replace ComingSoon for `/scraping` with `Decisions`)
- `frontend/src/components/layout/AppShell.tsx` (add pending-count badge to nav)
- `frontend/src/components/layout/nav.ts` (optional: update icon/label if needed)

**Test:** `frontend/src/components/layout/AppShell.test.tsx`,
`frontend/src/router.test.tsx`

**DESIGN ref:** §7 — badge shows pending count; WS `queued_for_decision` triggers refetch;
`invalidateQueries(['decisions'])` + `['pipeline','history']`

In `router.tsx`: replace `{ path: "scraping", element: <ComingSoon ... /> }` with `{ path:
"scraping", element: <Decisions /> }`.

In `AppShell.tsx`: add a `useDecisions('pending')` query (or a lightweight
`fetchDecisions({ status: 'pending', page_size: 1 })` for count-only) to display a badge
on the "Scraping" nav item. The badge component uses `Badge` with `variant="destructive"`
when count > 0. Subscribe to `ItemProgressed` events from the existing
`useEventStream()` — on receiving `step="scrape"` + `status="queued_for_decision"`,
invalidate the decisions query to refresh the badge count.

The existing WS event stream (`EventStreamProvider` → `useEventStream()`) already delivers
`ItemProgressed` envelopes. Listen for the `queued_for_decision` status in the
`AppShell`'s event handler and call `queryClient.invalidateQueries(['decisions'])`.

Test: badge renders 0 (hidden) when no pending; badge shows count when pending > 0;
`/scraping` route renders Decisions page (no longer ComingSoon); mobile bottom tab
"Scraping" navigates to decisions.

**Commit:** `feat(scrape-arbiter): wire /decisions route and pending-count badge in shell`
