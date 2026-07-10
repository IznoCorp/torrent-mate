# Phase 3 — Config SchemaForm redesign

Frontend-only. Keep the auto-render from `Config.model_json_schema()`; redesign for readability +
ergonomics on desktop + mobile.

## Gate

- `npm run lint && typecheck && vitest run` green.
- Config page legible + navigable at 375px + 1280px; styled collapsible sections with human labels;
  no raw unstyled `<details>`; a save still round-trips (unit/e2e — staging is read-only).

## 3.1 — Styled collapsible sections + domain grouping

**Current** (survey): `SchemaForm.tsx` already recurses with typed inputs, `humanize()` labels,
per-field 422 mapping, and native `<details>` sections. Complaint = visual/ergonomic.

**Approach**:

- Replace native `<details>`/`<summary>` with the `Accordion`/`Collapsible` primitive from Phase 2
  (consistent chevrons, spacing, chrome).
- Top-level objects render as titled, collapsible **domain sections** (with the schema description
  as section helper text) instead of an undifferentiated nested tree.
  **Files**: `frontend/src/components/config/SchemaForm.tsx`.
  **Tests**: `SchemaForm` vitest — sections render collapsible; nested objects still recurse.

## 3.2 — Labels, descriptions, typed inputs, required/shadowed markers

**Approach**: prefer schema `title`, humanize keys otherwise; always surface `description` as helper
text; keep bool→Switch, enum→Select, int/number→number Input, string→text (path-like → monospace
hint); keep the required `*` marker + the "écrasée par local.json5" shadowed chip.
**Files**: `SchemaForm.tsx` (+ leaf field components).
**Tests**: label/description rendering; shadowed-key chip at root depth.

## 3.3 — Inline validation + responsive layout

**Approach**:

- Inline validation on blur where cheap (client-side type/enum/range from the schema), keeping the
  existing server-422 mapping as the authority.
- Responsive: peer-field grid `md:grid-cols-2`, single column at mobile; the 240px FileList sidebar
  collapses to a top file selector on mobile (`Config.tsx` grid `md:grid-cols-[240px_1fr]`).
  **Files**: `frontend/src/pages/Config.tsx`, `SchemaForm.tsx`, `components/config/FileList.tsx`.
  **Tests**: `Config.test.tsx` — mobile selector renders; a validation error surfaces inline; a
  successful save path still works (mocked mutation).
