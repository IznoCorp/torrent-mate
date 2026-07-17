# Phase 05 — Contrôle rebuild (`/`)

**Gate:** Dashboard (`/`) becomes the 8-panel Contrôle station; all existing functionality preserved.

## Sub-phases

### 5.1 — Extract `StalledPanel` from `RunDetail`

**Commit:** `refactor(control-medias): extract StalledPanel from RunDetail as shared component`

**File (NEW):** `frontend/src/components/pipeline/StalledPanel.tsx`

Extract the « Ce qui n'a pas avancé » block from `RunDetail.tsx:414-442` into a standalone component that accepts `stepReasons: Array<{step: string, reasons: string[]}>`. The component renders the same warning-styled card with per-step skip/defer/error reasons.

**File:** `frontend/src/components/pipeline/RunDetail.tsx` — import `StalledPanel`, replace the inline block with `<StalledPanel stepReasons={stepReasons} />`. Behavior unchanged; test verifying RunDetail still renders the reasons block.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 5.2 — À traiter list (generalize PipelineActionBanner)

**Commit:** `feat(control-medias): build À traiter list — generalized PipelineActionBanner for all blocked cases`

**File (NEW):** `frontend/src/components/controle/ATraiterList.tsx`

Fetches `GET /api/staging/media` with `awaiting_action=true` filter (or filters client-side). Each row: mini poster (32px) + title + FR reason (`blocked_reason` / match state) + action link « Résoudre → » pointing to `/medias?media=<id>` (or `/medias?decision=<id>` for ambiguous). Empty state → one calm row « Rien à traiter ».

The existing `PipelineActionBanner.tsx` is NOT modified — it stays as the compact banner for other surfaces; this is a NEW component with the same data but richer presentation (rows not a banner).

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 5.3 — Contrôle page (dashboard rebuild)

**Commit:** `feat(control-medias): rebuild Dashboard into Contrôle — 8-panel attention-first layout`

**File:** `frontend/src/pages/Dashboard.tsx` → overwritten (not a new file — same route `index: true`).

New layout (order matters — DESIGN §2.1):

```tsx
export default function Dashboard(): ReactElement {
  const { data: pipelineStatus } = usePipelineStatus();
  const { data: lastRun } = useLastPipelineRun(); // GET /api/pipeline/history latest
  const { data: stagingCounts } = useStagingCounts(); // for awaiting_action count
  const awaitingActionCount = stagingCounts?.counts.awaiting_action ?? 0;

  return (
    <section className="mx-auto flex max-w-[1280px] flex-col gap-4">
      {/* 1. À traiter — all blocked cases, unified */}
      <ATraiterList />

      {/* 2. Activité scraping — ScrapeActivityPanel relocated here */}
      <ScrapeActivityPanel />

      {/* 3. Dernier run — digest card */}
      <LastRunDigest lastRun={lastRun} />

      {/* 4. Ce qui n'avance pas — StalledPanel on the last run */}
      {lastRun?.step_reasons?.length > 0 && (
        <StalledPanel stepReasons={lastRun.step_reasons} />
      )}

      {/* 5. Acquisitions — AcquisitionSummaryCard + SchedulersPanel merged */}
      <AcquisitionSummaryCard />
      <SchedulersPanel />

      {/* 6. Santé — compact rows */}
      <CompactHealth />

      {/* 7. Pipeline control — single state-dependent primary */}
      {pipelineStatus !== undefined && (
        <PipelineControls status={pipelineStatus} />
      )}
    </section>
  );
}
```

**Component relocations:**

- `ScrapeActivityPanel` import path unchanged (component stays put; only the import in `Medias.tsx` is **removed** — also in this commit).
- `DisksPanel`, `IndexHealthPanel`, `HealthCard`, `VersionCard` removed from Dashboard imports (they go into `CompactHealth` or sidebar footer).

**File:** `frontend/src/pages/Medias.tsx` — remove `ScrapeActivityPanel` import + render (the same commit).

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 5.4 — LastRunDigest + CompactHealth + Version footer

**Commit:** `feat(control-medias): add LastRunDigest, CompactHealth, and move Version to sidebar footer`

**File (NEW):** `frontend/src/components/controle/LastRunDigest.tsx` — one-card digest: trigger FR + relative time (dayjs `fromNow`) + counts summary (« 3 traités · 78 ignorés ») + link `/pipeline?run=<uid>`. Uses `GET /api/pipeline/history` latest entry. Compact, ~30 lines.

**File (NEW):** `frontend/src/components/controle/CompactHealth.tsx` — ONE compact row per domain:

- Disks: inline mini-bars (reuses `DisksPanel` data hook, presentation-only compaction)
- Index: 1 line with status dot + record count (reuses `IndexHealthPanel` data hook)
- Redis: dot (reuses `HealthCard` Redis check)
- Providers: dot + count OK (from registry status)

`DisksPanel`/`IndexHealthPanel`/`HealthCard` stay the data sources — this component only wraps them compactly. No new data paths.

**File:** `frontend/src/components/layout/Sidebar.tsx` — add `<VersionCard />` inside the sidebar footer, hidden in collapsed rail (`md:w-16`: `hidden`; expanded `md:w-56`: shown). The `VersionCard` component is imported directly (reused, not moved — it still exists at `components/dashboard/VersionCard.tsx`).

**File:** `frontend/src/pages/Dashboard.tsx` — remove `VersionCard` import (already removed in 5.3).

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 5.5 — Pipeline controls: single primary button

**Commit:** `refactor(control-medias): single state-dependent pipeline control with DropdownMenu`

**File:** `frontend/src/components/pipeline/PipelineControls.tsx`

The existing `PipelineControls` already has 5 mutations (run/pause/resume/kill + auto-trigger switch). Refactor the UI to ONE state-dependent primary button:

- Idle → « Démarrer » (amber, calls POST run)
- Running → « Arrêter » (danger, calls POST kill)
- Pause + Resume inside a single `DropdownMenu` (not 4 always-on buttons — B4).

The auto-trigger switch stays. All mutations kept — only the VISUAL layout changes.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 5.6 — Test migration: Dashboard → Contrôle

**Commit:** `test(control-medias): migrate Dashboard.test.tsx → Controle.test.tsx + new component tests`

**File:** `Dashboard.test.tsx` → renamed to `Controle.test.tsx`. Update assertions:

- Page title: « Contrôle » (not « Tableau de bord »)
- À traiter list renders when counts > 0
- ScrapeActivityPanel present
- PipelineControls present
- VersionCard NOT on the page (moved to sidebar)

**File (NEW):** `frontend/src/components/controle/ATraiterList.test.tsx` — empty state, single item, multiple items.
**File (NEW):** `frontend/src/components/controle/LastRunDigest.test.tsx` — renders trigger + counts + link.
**File:** `frontend/src/components/pipeline/PipelineControls.test.tsx` — update for the single-button layout.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`
