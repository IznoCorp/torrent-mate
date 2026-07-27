# Phase 04 — Visual pass + final gate

**Goal**: Apply the transversal visual system (§4) to every surface touched in Phases 1–3.
Then run the full quality gate: frontend suite, backend suite, redirect map tests complete,
IMPLEMENTATION.md table updated.

**Constitution served**: §4 (H1–H6, amber primary, EmptyState, em-dash microcopy).

## Surface

| File                                      | Action                           |
| ----------------------------------------- | -------------------------------- |
| `frontend/src/pages/SystemePage.tsx`      | H1–H6 visual adjustments         |
| `frontend/src/pages/Config.tsx`           | H1–H6 visual adjustments         |
| `frontend/src/pages/SystemePage.test.tsx` | New assertions for visual states |
| `frontend/src/pages/Config.test.tsx`      | New assertions for visual states |
| `frontend/src/lib/outcome-labels.ts`      | (unchanged — Phase 1)            |
| `IMPLEMENTATION.md`                       | Update phases table + status     |

## Sub-phases

### 4.1 — H1–H6 visual pass on touched pages

**Commit**: `style(systeme-hub): apply H1-H6 visual pass on /systeme and /config`

**H1 — Surface hierarchy (3 levels max)**:

- **SystemePage**: The page shell already uses a flat Card layout. Verify no triple-nested borders.
  - Each tab panel is one `<Card>` → the top-level `role="tablist"` is bare background.
  - Within the état tab, panel cards (DisksPanel, LocksPanel, IndexHealthPanel) are sibling Cards — not nested inside another Card.
  - If any nested Card-in-Card exists, flatten it.

- **Config**: Two-panel layout already clean. The `rounded-md border border-border` wrapper is the Card equivalent.
  - Secrets tab restructured in Phase 3.1 already removes the bottom card nesting.

**H2 — Type scale**:

- **SystemePage h1**: `text-xl font-semibold tracking-tight` → keep (matches AcquisitionPage).
  - If any attention count renders (not expected on Système), it gets `text-3xl` or `text-4xl` display size.
  - Version/disk-free info: `text-sm font-mono text-muted-foreground` at base mono.

- **Config h1**: same `text-xl font-semibold tracking-tight`.

**H3 — Unified state vocabulary**:

Already done in Phase 1 — verify every touched surface imports `outcome-labels` and no local
map remains:

```bash
rg "OUTCOME_BADGE|outcomeLabel\s*=" frontend/src/ -g '*.tsx' --type ts
```

Expected: zero matches outside `outcome-labels.ts` and its test.

**H4 — EmptyState on touched surfaces**:

- **SystemePage état tab**: when DisksPanel data is empty, ensure it renders the existing
  empty state (not a 450px void). Each panel's own empty-state behavior is unchanged —
  these components already handle empty data correctly (verified in their test suites).

- **SystemePage journal tab**: when DestructiveLogPanel has no entries, render:

  ```tsx
  <EmptyState
    icon={ScrollText}
    title="Aucune opération destructive"
    description="Le journal des suppressions et remplacements apparaîtra ici."
  />
  ```

- **SystemePage actions tab**: ActionCatalog already handles its own empty state.

- **Config**: The placeholder "Sélectionnez un fichier dans la liste pour l'éditer." is
  no longer needed (Phase 3.1 auto-selects first file). Replace with a calmer EmptyState
  for the edge case where no files exist (stale-load / error fallback).

**H5 — Segmented controls**:

- **SystemePage tablist**: Apply the exact same segmented-control styling as AcquisitionPage:
  ```tsx
  <div
    role="tablist"
    className="flex flex-nowrap gap-1 overflow-x-auto rounded-lg bg-muted p-1"
  >
  ```
  Active tab: `bg-background text-foreground shadow-sm`.
  Inactive: `text-muted-foreground hover:text-foreground`.

**H6 — Tap-accessible em-dash placeholders**:

- **SystemePage état tab**: Every `"—"` placeholder in disks/locks/index panels gets either
  visible microcopy (e.g. "pas encore de données") or a `title` attribute that a long-press
  can trigger. No hover-only tooltip as the sole carrier of a reason (DOIT-9).

  Specifically in `DisksPanel.tsx`, `LocksPanel.tsx`, `IndexHealthPanel.tsx`:
  - Replace bare `"—"` with `"—"` wrapped in `<span title="pas encore de données">` where
    the dash is a genuine "no data yet" placeholder.
  - Where the dash is a "not applicable" (e.g. a lock type that doesn't have a timestamp),
    leave as-is — it's not a reason-carrier.

- **Config**: The restart hint already made tap-accessible in Phase 3.2.

**One amber primary per view**:

- **SystemePage**: No primary action by default — the page is informational. The ActionCatalog
  "Exécuter" buttons are already amber (Shadcn default variant).
- **Config**: "Enregistrer" button already uses the default variant (amber).

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run
```

### 4.2 — Final gate (no code changes — verification only)

**Commit**: _(no separate commit — combined with 4.1 or folded into the gate commit)_

Run the full quality gate:

```bash
# 1. Frontend suite
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run

# 2. Backend suite (zero backend changes in this feature, but verify no drift)
make lint && make test

# 3. Full gate
make check

# 4. Redirect map verification
cd frontend && npx vitest run -- src/router.test.tsx
```

**Redirect map test checklist** (verify ALL of these pass):

| From URL                     | To URL                        | Contract            |
| ---------------------------- | ----------------------------- | ------------------- |
| `/registry`                  | `/systeme?tab=etat`           | DESIGN.md §4        |
| `/maintenance`               | `/pipeline`                   | V3 (LegacyRedirect) |
| `/maintenance?run=abc`       | `/pipeline?run=abc`           | V3 contract         |
| `/maintenance?run=abc%2Fdef` | `/pipeline?run=abc%2Fdef`     | D1 encoding         |
| `/maintenance?run=`          | `/pipeline?run=`              | B2 empty param      |
| `/systeme`                   | `/systeme` (état tab renders) | default tab         |
| `/systeme?tab=etat`          | état tab renders              | URL-addressable     |
| `/systeme?tab=actions`       | actions tab renders           | URL-addressable     |
| `/systeme?tab=maintenance`   | maintenance tab renders       | URL-addressable     |
| `/systeme?tab=journal`       | journal tab renders           | §7 home             |
| `/systeme?tab=inconnu`       | état tab renders (fallback)   | graceful unknown    |

**Post-gate cleanup**:

```bash
# Verify no residual imports from deleted files
rg "from.*pages/Maintenance|from.*pages/RegistryPage|MaintenanceRunRedirect" frontend/src/ -g '*.ts' -g '*.tsx'
# Expected: zero matches

# Verify no stray "Réussi" / "Erreur" / "Arrêté" in non-test source (outcome labels)
rg "'Réussi'|'Erreur'|'Arrêté'" frontend/src/ -g '*.ts' -g '*.tsx' --type ts
# Expected: only in acquisition/meta.ts (STATUS_LABEL.killed = "Arrêté" kept)

# Verify sidebar has exactly 6 entries + 2 sections
rg "to:.*/(systeme|config)" frontend/src/components/layout/nav.ts
# Expected: { to: "/systeme", label: "Système", icon: Wrench }
#          { to: "/config", label: "Config", icon: Settings }

# Verify router has /systeme route and no /maintenance page route or /registry page route
rg "path:.*\"systeme\"|path:.*\"maintenance\"|path:.*\"registry\"" frontend/src/router.tsx
# Expected: path: "systeme" → SystemePage
#           path: "maintenance" → LegacyRedirect to /pipeline
#           path: "registry" → LegacyRedirect to /systeme?tab=etat
```

### Files-in-scope summary

| Phase | Files touched | New files | Deleted files |
| ----- | ------------- | --------- | ------------- |
| 4.1   | 2             | 0         | 0             |
| 4.2   | 0             | 0         | 0             |

**Total**: 2 files modified (visual adjustments), 0 new, 0 deleted. Verification-only sub-phase.
