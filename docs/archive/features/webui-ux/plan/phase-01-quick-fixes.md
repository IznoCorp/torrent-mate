# Phase 1 — Quick presentation fixes

Low-risk, frontend-only. Fixes two operator-reported presentation bugs.

## Gate

- `npm run lint && npm run typecheck && npx vitest run` green.
- Maintenance index-health cards legible (no clip/overlap) at 375px + 1280px on staging.
- Registry shows `tvdb-bootstrap` grouped under `tvdb`, not as a twin card.

## 1.1 — Maintenance StatPanel legibility

**Objective**: the "Santé de l'index" stats (`ITEMS`, `FICHIERS`) no longer clip/overlap their
secondary text at any width.

**Current** (survey): `IndexHealthPanel.tsx:247` stat grid is `grid-cols-2` with no responsive
breakpoint; the custom `StatPanel` secondary line overlaps large values on desktop.

**Approach**:

- Audit the `StatPanel` component (find it under `frontend/src/components/` — design-system part):
  ensure `min-w-0`, `truncate`/wrapping on the secondary line, `tabular-nums` on the value, and a
  layout where value + unit + secondary never overlap.
- `IndexHealthPanel` inner stat grid → responsive cols (`grid-cols-1 sm:grid-cols-2` inner) so
  cards stack instead of squashing.

**Files**: `frontend/src/components/**/StatPanel.tsx`, `frontend/src/components/maintenance/IndexHealthPanel.tsx`.
**Tests**: extend/add `IndexHealthPanel` vitest — assert the stat values render + no layout-only
regressions (snapshot of the class contract where practical). Visual pass is via the Chrome loop.

## 1.2 — Registry sub-circuit grouping

**Objective**: `<provider>-bootstrap` / `<provider>-download` sub-circuits render nested under their
parent provider card with a label/tooltip, so `tvdb` + `tvdb-bootstrap` no longer look duplicated.

**Current**: `RegistryPage.tsx` maps one flat card per provider from `GET /api/registry/status`.

**Approach** (pure frontend over the existing payload):

- Group the provider list: parse each provider id; a `-bootstrap`/`-download` suffix attaches to its
  parent stem (`tvdb-bootstrap` → parent `tvdb`). Render sub-circuits inside/under the parent card
  with a small labelled section + tooltip ("Circuit d'authentification TVDB v4 — trip indépendant").
- Keep a fallback: a sub-circuit whose parent is absent from the roster renders standalone (no data
  loss).

**Files**: `frontend/src/pages/RegistryPage.tsx` (+ a small grouping helper, unit-tested).
**Tests**: `RegistryPage.test.tsx` — given a roster with `tvdb` + `tvdb-bootstrap`, assert one
parent card containing the bootstrap sub-circuit (not two top-level cards); orphan sub-circuit still
renders.
