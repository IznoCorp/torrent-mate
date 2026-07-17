# Phase 06 — PR fixes cycle 1 (review findings, PR #310)

## Gate

- [ ] Phases 1–5 complete, PR #310 open, CI green on 086155eb.
- [ ] `cd frontend && npm run lint && npm run typecheck && npx vitest run` green.

## Scope

Fix the retained findings from review cycle 1 (4 agents: code / tests / comments / silent-failures),
filtered against `docs/features/overhaul-shell/DESIGN.md`. NO route/nav changes (spec §6 invariant
still applies). Files: `frontend/src/components/layout/AppShell.tsx`, `AppShell.test.tsx`,
`frontend/src/hooks/useStagingMedia.ts`, `frontend/src/hooks/useAcquisition.ts`,
NEW `frontend/src/hooks/useStagingMedia.test.tsx`.

### Sub-phase 6.1 — Code fixes (SF-1 regression + medium findings)

**Commit:** `fix(overhaul-shell): restore decisions WS bridge + honest badge states`

1. **SF-1 (MAJOR, regression)** — restore `void queryClient.invalidateQueries({ queryKey: decisionsKeys.all })`
   in the AppShell WS listener (re-import `decisionsKeys` from `@/api/decisions`). The old listener was the
   app's ONLY WS→decisions bridge (Decisions page live-refresh + ScrapeActivityPanel reviver, its comment
   says so). Keep the new staging/history invalidations alongside.
2. **SF-7** — replace the hardcoded `["staging", "media"]` invalidation key with the imported
   `stagingMediaKeys.all` constant.
3. **SF-6** — `stagingData?.counts.awaiting_action` → `stagingData?.counts?.awaiting_action`
   (the plan specified the optional chain; runtime schema-drift guard, no ErrorBoundary exists).
4. **SF-3** — give the acquisition badge a real refresh: extend `useWanted` (useAcquisition.ts) with the
   same optional `queryOptions?: Partial<Pick<UseQueryOptions<...>, "refetchInterval" | "staleTime">>`
   second argument as `useStagingMedia`, and pass `{ refetchInterval: 60_000, staleTime: 55_000 }` from
   AppShell. Existing `useWanted` callers compile unchanged.
5. **F2-code-review (paused ≠ running lie)** — pipeline dot: when `pipelineStatus.state === "paused"`,
   render `<StatusDot status="warning" showLabel={false} aria-label="Pipeline en pause" />`; keep
   `status="running"` + « Pipeline en cours d'exécution » only for `running`. (Truthful labels, §2.)
6. **SF-2 (error ≠ all-clear)** — read `isError` from the staging and wanted badge queries; when a query is
   in error (after its retry), render an indeterminate marker instead of nothing: a small pill with text
   `?` and `aria-label="Compteur indisponible"` (reuse NavCountBadge styling class or a minimal span with
   the same slot, `data-slot="nav-count"`, so tests can target it; do NOT show it while merely pending).
   Pipeline dot keeps its self-healing 5s poll (usePipelineStatus does not expose error — out of scope,
   documented choice).
7. **Comment/doc fixes** — AppShell docblock: the listener refreshes the staging badge + decisions +
   pipeline history (badge 2 has its own hook listener; badge 3 polls at 60s now); inline comment: events
   list = ItemProgressed + run start/end (PipelineStarted included — deliberate widening vs the DESIGN's
   "run-finished" wording); badge-map comment per F5 ("entries inserted only when non-zero/active");
   `useStagingMedia` docstring gains the `queryOptions` Args entry (same for `useWanted`).

### Sub-phase 6.2 — Test fixes (TC-1..TC-5 + new behaviors)

**Commit:** `test(overhaul-shell): badge polling, route scoping, error and paused states`

1. **TC-1** — NEW `frontend/src/hooks/useStagingMedia.test.tsx`: with `vi.useFakeTimers()`, assert the
   badge options give exactly 1 fetch before 60s and a 2nd after; control case without options refetches
   at 8s (pins backward-compat default).
2. **TC-2** — AppShell test: emitting `PipelineEnded` (WS) triggers a staging-badge refetch (duplicate the
   ItemProgressed test shape). Also assert the restored decisions invalidation: after `ItemProgressed`
   with `status: "queued_for_decision"`, the query cache for `["decisions"]` is invalidated (cache
   observation is acceptable here).
3. **TC-3** — scope badge assertions to their nav item: `within(screen.getAllByRole("link", { name: "Scraping" })[0])`
   for the staging badge, same for Acquisition — swapping the wiring must fail the tests.
4. **TC-4** — zero-state test: wait until the staging AND wanted URLs were actually fetched, then assert
   both `[data-slot="nav-count"]` absence and `queryByLabelText(/Pipeline en cours d/)` absence.
5. **TC-5 / paused** — `pipelineStatusPayload("paused")` → dot with `aria-label="Pipeline en pause"`,
   no « en cours d'exécution » label.
6. **SF-2 test** — staging query returns 500 (after retry) → the `?` indeterminate marker with
   `aria-label="Compteur indisponible"` appears (regression test for the honest error state).

### Verification (both sub-phases)

```bash
cd frontend && npm run lint && npm run typecheck && npx vitest run
```

All green. NO route/nav changes. Commit per sub-phase.

## Explicitly NOT fixed here (operator arbitration — §méthode rule 4, reported in the PR)

- SF-4 ring-saturation deafness of index-based WS scanning (PARITY with pre-PR code; polls self-heal
  badges; candidate follow-up: monotonic event-id cursor in useEventStream).
- SF-5 silent drop of malformed WS frames in parseServerMessage (pre-existing, outside diff).
- Load observation: per-item ItemProgressed invalidations refetch the staging scan more often than the
  60s poll rationale during busy runs (accepted for now; the §5.3 aggregate endpoint remains the escape).
- eslint whitelist message wording («Declared props» includes an inherited prop) + pre-existing duplicated
  `className` in the regex (cosmetic).
