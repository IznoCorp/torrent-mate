# Phase 01 — Outcome-labels foundation

**Goal**: Create `frontend/src/lib/outcome-labels.ts` as the single shared vocabulary module
mapping backend outcomes/states → {FR label, tone}. Migrate ALL FIVE divergent maps, resolving
the Réussi/Succès, Arrêté/Interrompu, Erreur/Échec divergences. ZERO visual change beyond
unified wording.

**Constitution served**: §4, H3/E, DOIT-2.

## Surface

| File                                                    | Action                                                      |
| ------------------------------------------------------- | ----------------------------------------------------------- |
| `frontend/src/lib/outcome-labels.ts`                    | **NEW** — shared label+tone maps, Google-style TS docblocks |
| `frontend/src/lib/__tests__/outcome-labels.test.ts`     | **NEW** — unit suite for the module                         |
| `frontend/src/components/dashboard/SchedulersPanel.tsx` | Replace `outcomeLabel()` with import from module            |
| `frontend/src/components/pipeline/RunHistoryTable.tsx`  | Replace OUTCOME_BADGE with import from module               |
| `frontend/src/components/pipeline/RunDetail.tsx`        | Replace OUTCOME_BADGE with import from module               |
| `frontend/src/components/acquisition/meta.ts`           | Replace STATUS_LABEL + RUN_OUTCOME_LABEL imports            |

## Sub-phases

### 1.1 — Create `frontend/src/lib/outcome-labels.ts` + test suite

**Commit**: `feat(systeme-hub): add shared outcome-labels module resolving 5-map divergence`

**Module shape** (`frontend/src/lib/outcome-labels.ts`):

```typescript
/**
 * Shared outcome/state vocabulary for TorrentMate UI.
 *
 * THE SINGLE SOURCE OF TRUTH for mapping backend outcomes and states to French
 * labels and design-system badge tones.  Before this module the codebase carried
 * FIVE divergent local maps — ``success`` → "Réussi" in one place, "Succès" in
 * another; ``killed`` → "Arrêté" vs "Interrompu"; ``error`` → "Erreur" vs "Échec".
 * Every surface that renders a run outcome, acquisition status, or lifecycle
 * state MUST import from here — never define a private map.
 *
 * Rendering rule (H3/E):
 * - ``OUTCOME_TONE`` → Badge tone chip (used for run outcomes).
 * - ``STATE_TONE`` → StatusDot or Badge (used for live states).
 * - ``OUTCOME_LABEL`` / ``STATE_LABEL`` → French text.
 * - Mono (no tone) = machine tokens (e.g. raw enums surfaced in dev-only views).
 *
 * @module outcome-labels
 */
```

**Exports**:

| Export                  | Type                                               | Keys                                                                                                                                                                                                                               |
| ----------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OUTCOME_LABEL`         | `Record<string, string>`                           | `success→Succès`, `error→Échec`, `killed→Interrompu`, `running→En cours`, `paused→En pause`, `queued→En file`, `blocked→Bloqué`, `pending→En attente`, `deferred→Différé`                                                          |
| `OUTCOME_TONE`          | `Record<string, BadgeTone>`                        | `success→success`, `error→danger`, `killed→warning`, `running→info`, `paused→info`, `queued→neutral`, `blocked→warning`, `pending→warning`, `deferred→neutral`                                                                     |
| `STATE_LABEL`           | `Record<string, string>`                           | `active→Actif`, `inactive→Inactif`, `pending→En attente`, `searching→En recherche`, `grabbed→Récupéré`, `done→Terminé`, `abandoned→Abandonné`, `satisfied→Respectée`, `breached→Non respectée`, `completed→Succès`, `failed→Échec` |
| `STATE_TONE`            | `Record<string, BadgeTone>`                        | `active→success`, `inactive→neutral`, `pending→warning`, `searching→info`, `grabbed→info`, `done→success`, `abandoned→danger`, `satisfied→success`, `breached→danger`, `completed→success`, `failed→danger`                        |
| `DEFAULT_OUTCOME`       | `{tone, label}`                                    | `{ tone: "neutral", label: "—" }`                                                                                                                                                                                                  |
| `outcomeLabel(outcome)` | `(outcome: string \| null \| undefined) => string` | Returns French label or "Jamais exécuté"                                                                                                                                                                                           |

**BadgeTone type**: `"success" | "danger" | "warning" | "info" | "neutral"` (imported from `@/components/ui/badge`).

**Test suite** (`frontend/src/lib/__tests__/outcome-labels.test.ts`):

- Every key in every map has a label and a tone (no missing entries).
- `outcomeLabel(null)` → "Jamais exécuté".
- `outcomeLabel(undefined)` → "Jamais exécuté".
- `outcomeLabel("unknown_key")` → "Jamais exécuté".
- Every key in `OUTCOME_LABEL` has a matching key in `OUTCOME_TONE`.
- Every key in `STATE_LABEL` has a matching key in `STATE_TONE`.
- Backward-compat: `OUTCOME_LABEL.success === "Succès"` (matches the majority pre-existing usage in RunHistoryTable + RunDetail + acquisition RUN_OUTCOME_LABEL).
- `STATUS_LABEL.killed === "Arrêté"` preserved (acquisition meta STATUS_LABEL usage is consistently "Arrêté" for the `killed` status of an individual wanted item).
- Zero React dependencies — the module is pure data.

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run -- src/lib/__tests__/outcome-labels.test.ts
```

### 1.2 — Migrate the FIVE maps

**Commit**: `refactor(systeme-hub): migrate five divergent outcome maps to shared module`

For each file, replace the local map with an import from `@/lib/outcome-labels`:

1. **`SchedulersPanel.tsx`** (~L84–95): Delete the local `outcomeLabel()` function. Import `outcomeLabel` from `@/lib/outcome-labels`. The JSX at ~L194 (`outcomeLabel(item.outcome)`) stays identical.

2. **`RunHistoryTable.tsx`** (~L53–65): Delete the local `OUTCOME_BADGE` map and `DEFAULT_OUTCOME`. Import `OUTCOME_LABEL`, `OUTCOME_TONE`, `DEFAULT_OUTCOME` from `@/lib/outcome-labels`. Reconstruct the local lookup (`OUTCOME_BADGE[outcome]?.tone`) as two lookups (`OUTCOME_TONE[outcome]`, `OUTCOME_LABEL[outcome]`) with `DEFAULT_OUTCOME` fallback. Labels change:
   - `error: "Erreur"` → `error: "Échec"` (unified)
   - `killed: "Arrêté"` → `killed: "Interrompu"` (unified)
   - `success: "Succès"` → unchanged

3. **`RunDetail.tsx`** (~L38–47): Same migration as RunHistoryTable. Identical OUTCOME_BADGE shape.

4. **`acquisition/meta.ts`** (~L100–131): Replace `STATUS_TONE` and `STATUS_LABEL` body values with imports from `@/lib/outcome-labels`. The exported names (`STATUS_TONE`, `STATUS_LABEL`) stay as re-exports to avoid a ripple across every acquisition panel import. Key changes:
   - `STATUS_LABEL.killed: "Arrêté"` → stays "Arrêté" (acquisition item status, not run outcome — DESIGN.md H3/E: "StatusDot = live states" vs "chip = outcomes")
   - `STATUS_LABEL.completed: "Succès"` → unchanged
   - `STATUS_LABEL.failed: "Échec"` → unchanged

5. **`acquisition/meta.ts`** (~L195–209): Replace `RUN_OUTCOME_TONE` and `RUN_OUTCOME_LABEL` body values with imports. Labels change:
   - `RUN_OUTCOME_LABEL.error: "Erreur"` → `"Échec"` (unified with pipeline outcome)
   - `RUN_OUTCOME_LABEL.killed: "Interrompu"` → unchanged
   - `RUN_OUTCOME_LABEL.success: "Succès"` → unchanged

**Divergence resolution table**:

| Key     | Old (Schedulers) | Old (RunHistory) | Old (RunDetail) | Old (acq STATUS) | Old (acq RUN) | **New (unified)** |
| ------- | ---------------- | ---------------- | --------------- | ---------------- | ------------- | ----------------- |
| success | Réussi           | Succès           | Succès          | —                | Succès        | **Succès**        |
| error   | Échec            | Erreur           | Erreur          | —                | Erreur        | **Échec**         |
| killed  | Interrompu       | Arrêté           | Arrêté          | Arrêté           | Interrompu    | **Interrompu**    |
| running | —                | En cours         | En cours        | —                | —             | **En cours**      |

Note: `acquisition/meta.ts` `STATUS_LABEL.killed` keeps "Arrêté" — that map serves wanted-item lifecycle statuses, not run outcomes. The H3/E rule separates outcome chips from state dots.

**Gates**:

```bash
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run
```

Verify all existing test suites stay green with the new labels — grep for the old label strings in test assertions and update them:

```bash
cd frontend && rg "Réussi|Erreur" -g '*.test.*' && echo "--- update these assertions to Succès/Échec ---"
```

The grep should confirm: SchedulersPanel test assertions referencing "Réussi" → "Succès"; RunHistoryTable + RunDetail assertions referencing "Erreur" → "Échec", "Arrêté" → "Interrompu".

### Files-in-scope summary

| Phase | Files touched | New files |
| ----- | ------------- | --------- |
| 1.1   | 0             | 2         |
| 1.2   | 5             | 0         |

**Total**: 7 files (2 new, 5 modified). All frontend-only, zero backend.
