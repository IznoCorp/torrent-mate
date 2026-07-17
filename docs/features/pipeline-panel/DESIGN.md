# DESIGN — pipeline-panel (Design overhaul V3: Pipeline)

**Wave 3 of 5** — epic #304, ticket #307. Merge mode: **auto** (operator directive 2026-07-17).
**Binding shared spec:** `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §2.3 + the §1.1
redirect rule scoped to this wave (`/maintenance?run=` conditional). Spec wins on conflict; constitution
(`docs/reference/product-intent.md`) wins over all.
**Constitution served:** §1/§2 (l'instrument du pipeline, états FR), §8/DOIT-2 (le signal d'anomalie
JAMAIS hors-écran), DOIT-3 (agir là où l'on observe), DOIT-9 (mobile), DOIT-10 (`?run=` adressable,
redirect conditionnel), NE-DOIT-PAS-4 (légende compréhensible, tap-accessible).

## 1. Scope

### 1.1 Stepper that fits (fix C1/C2 of the findings doc)

`frontend/src/components/pipeline/PipelineStepper.tsx` (or the FlowBoard header rail — read the real
composition first): compressed responsive rail that NEVER overflows its container at any width:

- Per step: icon + count; the ACTIVE and any ANOMALOUS step (blocked>0 / error) render expanded
  (label + count + state chip); quiet steps stay icon+count.
- Anomalous step = red, clickable → the EXISTING `?stage=` FlowBoard drawer (kept, it works).
- The whole rail wraps or compresses (flex-wrap or overflow hidden with priority to anomalies) —
  the red signal is ALWAYS visible without horizontal scroll, desktop AND mobile (DOIT-2/§8).
- Mobile (<md): compact vertical list, ~40px/row (icon + FR label + count + state), replacing the
  8×90px card stack (finding C4).

### 1.2 Run history repatriated (fix C3/F1)

- `RunHistoryTable kind="pipeline"` + the `?run=` `RunDetail` drawer move from Maintenance to the
  Pipeline page (components REUSED as-is; Maintenance keeps kind="maintenance" — its own history until
  V5 moves it into Système).
- « Dernière exécution » card sizes to content (no reserved void).
- Trigger legend chip-paragraph → tap-accessible popover (`?` button) on the history header (C5,
  DOIT-9: no hover-only reason).
- RunDetail on Pipeline renders ANY uid (backend serves both kinds) with a cross-link « Voir les
  exécutions de maintenance → /maintenance » when the uid is a maintenance run.

### 1.3 Redirect (§1.1 scoped): `/maintenance?run=<uid>` → `/pipeline?run=<uid>`

Via the existing `<LegacyRedirect>` mechanics — but CONDITIONAL: only when `?run=` is present;
`/maintenance` without `?run=` stays served by the Maintenance page (untouched this wave — V5 does
`/systeme`). Implement as a tiny wrapper route component (reads searchParams, either renders
`<Maintenance/>` or `<Navigate to=/pipeline?run=…>`), unit-tested both ways (DOIT-10).

## 2. Hard non-goals

- No changes to Maintenance content beyond REMOVING the pipeline-runs table (kind="pipeline") that
  moved (the page keeps état système + event feed + maintenance history + actions + journal panels).
- No route removals; `/maintenance` stays a live page. No V4/V5 surfaces. No backend changes
  (`GET /api/pipeline/history` already serves everything; NO openapi run needed unless a route
  signature actually changes — it must not).

## 3. Acceptance (executable per-wave proof)

- Desktop 1440px: with a blocked step, the red step is visible WITHOUT any horizontal scroll
  (screenshot); clicking it opens the `?stage=` drawer.
- Mobile 390px iframe: overflow 0 on `/pipeline`; the vertical step list shows the red state
  on-screen.
- `/pipeline` shows the pipeline run history; `?run=<uid>` opens RunDetail (pipeline AND maintenance
  uid); `/maintenance?run=<uid>` redirects with the uid; `/maintenance` alone renders Maintenance.
- Legend popover opens on tap/click.
- Gates: frontend lint+lint:ds+typecheck+vitest; `make lint && make test` (no backend change);
  version 0.52.0 served post-merge (SW cache-bust protocol).
