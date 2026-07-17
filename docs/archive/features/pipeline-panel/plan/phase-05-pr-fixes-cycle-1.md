# Phase 05 — PR fixes cycle 1 (review findings, PR #313)

## Gate

- [ ] Phases 1–4 done, PR #313 open, CI green on 44fa6fed.

### Sub-phase 5.1 — Code fixes (error paths, redirect, legend, listener)

**Commit:** `fix(pipeline-panel): honest run-detail errors + redirect/legend hardening`

1. **B2/G5** — `?run=` empty treated as null on BOTH pages: `const selectedRun = searchParams.get("run") || null;` (Pipeline.tsx + Maintenance.tsx).
2. **B3** — RunDetail error+loading branches get the « Retour » onClose button; error message branches on
   ApiError.status: 404 → « Ce run n'existe pas (ou plus). » ; else « Erreur serveur — réessayez. » with a
   retry button (reuse the ErrorState/onRetry pattern from FlowBoard); danger tone, not muted.
3. **D1** — MaintenanceRunRedirect: `encodeURIComponent(runUid)` on interpolation.
4. **B1** — Maintenance.tsx: remove the now-dead RunDetail block + openRun/closeRun wiring (the designed
   flow: row click → ?run= → redirect → detail on /pipeline with cross-link). Comment explains the teleport.
5. **C1** — TriggerLegend: drop the DropdownMenu menu-semantics; use an accessible disclosure (if
   @radix-ui/react-popover exists in deps use ui Popover; else a button with aria-expanded +
   conditionally rendered region — NO role="menu"). Keyboard (Enter/Space) must open.
6. **C2** — Maintenance passes `legend={<TriggerLegend />}` to its maintenance history table (labels stay
   decodable there — §2).
7. **A1** — FlowBoard listener: feature-detect (`"addEventListener" in mql` else `addListener`) instead of
   swallow-all catch; keep the jsdom init fallback.

### Sub-phase 5.2 — Test hardening (mutation-proven + gaps)

**Commit:** `test(pipeline-panel): mutation-proof rail invariants + error-path coverage`

- G1: anomalous station EXPANDED assertion — visible label text present (`getByText("Identification")`)
  and NOT flex-row collapsed.
- G7: quiet compact station label NOT visible as text (`queryByText("Tri")` null).
- G2: stations container class contract — has `sm:flex-wrap`, does NOT have `sm:overflow-x-auto`
  (all three render branches).
- G3/A2: matchMedia change-event test (record listener, fire {matches:false}, labels appear;
  removeEventListener on unmount); move `vi.unstubAllGlobals()` to afterEach (stub-leak).
- G4: Pipeline-page test with a maintenance-uid detail mock → cross-link rendered.
- G6: history row click → `?run=` set; « Retour » → removed, `?stage=` preserved.
- B2 tests: `/pipeline?run=` (empty) shows no drawer; `/maintenance?run=` stays on Maintenance.
- B3 tests: 404 → the not-found FR message + Retour present; 500 → server message + retry.
- D1 test: uid with reserved chars survives verbatim (encoded) without spawning extra params.
- B1 test: router-level — maintenance row click path lands on /pipeline?run= (the teleport asserted).
- C1 test: keyboard-open (Enter) on the legend disclosure.

### Sub-phase 5.3 — Docs sweep

**Commit:** `docs(pipeline-panel): comment accuracy sweep from review cycle 1`

- Pipeline.tsx « nine-stage » → « eight-stage ».
- RunDetail module docblock: displayed on /pipeline AND /maintenance→(redirected); single history table.
- StageStation docs: « icon + count + state dot » (3 places); drop the wrong « ~40 px » figure (2 places).
- RunHistoryTable Args: add `legend`.
- Maintenance.tsx docblock: three panels grid + journal + feed + maintenance history + catalog.
- FlowBoard mobile test title reworded (labels visible; stacking is CSS-driven).

## Recorded open items (operator arbitration — §méthode rule 4)

- **B4 (HIGH, backend, pre-existing)**: `GET /api/pipeline/history` swallows sqlite3.OperationalError →
  calm-empty « Aucune exécution enregistrée » with ZERO logging — a broken library.db masquerades as
  healthy on the instrument panel (§8/DOIT-2 textbook violation). Out of this wave's zero-backend scope;
  candidate immediate hotfix (log ERROR + degraded flag à la IndexHealth).
- **P2 (MEDIUM, pre-existing)**: `active` outranks `blocked` in stage state — a running stage with blocked
  items shows info-blue, red only after the run leaves it.
- P1 eternal skeleton on settled-empty stages; P3 stages-scan blanket except → all-idle board;
  P4 history table h-scroll ≤390px (scrollable-reachable, acceptable).
- C2 note: legend restored on Maintenance in 5.1 (regression closed, not deferred).
