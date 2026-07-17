# Phase 03 — `/medias` page + LegacyRedirect + nav renames

**Gate:** `/medias` renders StagingLibrary as default view with segment filters; `/scraping?media=X` → `/medias?media=X` opens the sheet; nav shows « Contrôle » + « Médias ».

## Sub-phases

### 3.1 — LegacyRedirect component

**Commit:** `feat(control-medias): add LegacyRedirect component with query-string forwarding`

**File (NEW):** `frontend/src/components/LegacyRedirect.tsx`

react-router `<Navigate>` drops query strings. A custom component reads `searchParams` from `useSearchParams` and forwards them:

```tsx
import { Navigate, useSearchParams } from "react-router-dom";
export function LegacyRedirect({ to }: { to: string }) {
  const [searchParams] = useSearchParams();
  const suffix = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  return <Navigate to={`${to}${suffix}`} replace />;
}
```

**File (NEW):** `frontend/src/components/LegacyRedirect.test.tsx` — renders with `createMemoryRouter` → asserts `?media=X`, `?decision=N`, empty params, and path without trailing `?`.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 3.2 — Medias page (content from Decisions.tsx, reorganized)

**Commit:** `feat(control-medias): create /medias page with grid default + segment filters`

**File (NEW):** `frontend/src/pages/Medias.tsx`

Copy the structure from `Decisions.tsx` with these reorganizations:

1. **Default view = library** (grid). Change `useState<"library" | "resolve" | "all">` initial to `"library"`.
2. **Tabs (not view-buttons):** « Bibliothèque · À résoudre · Décisions » — replace the current `<Button variant={view===...}>` row with a `Tabs`/segmented control.
3. **Grid segments (NEW):** When on Bibliothèque, render a `<SegmentedControl>`: `À traiter (awaiting_action) · En cours (active) · Prêts (matched+!blocked) · Tous` — the segment maps onto `StagingLibrary`'s existing `match`/`stage`/`awaiting_action` filter props.
4. **ScrapeActivityPanel** stays on this page (relocated in phase 05).
5. **Keep URL-addressability:** `?media=` opens sheet, `?decision=` opens deck/browse — identical behavior.
6. **Remove the old status-filter chips** (they're replaced by the grid segments + the Décisions tab's own filters).

**Test migration (same commit):** Rename `Decisions.test.tsx` → `Medias.test.tsx`. Update all `/scraping` references to `/medias`. Update the test for the default view = library. Green gate before commit.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 3.3 — Router wiring + `/scraping` redirect

**Commit:** `feat(control-medias): wire /medias route + /scraping → /medias redirect`

**File:** `frontend/src/router.tsx`

1. Add import: `import Medias from "@/pages/Medias";` + `import { LegacyRedirect } from "@/components/LegacyRedirect";`
2. Add route: `{ path: "medias", element: <Medias /> }`
3. Replace: `{ path: "scraping", element: <Decisions /> }` → `{ path: "scraping", element: <LegacyRedirect to="/medias" /> }`
4. The `Decisions` import can be removed once Medias.test.tsx passes.

**Update any other imports referencing `/scraping`** — grep `frontend/src/` for `"/scraping"` in href/to attributes (not in type definitions).

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`

---

### 3.4 — Nav renames + bottom tabs + badge keys

**Commit:** `feat(control-medias): rename nav labels — Contrôle + Médias`

**File:** `frontend/src/components/layout/nav.ts`

Changes:

- Line 66: `"Tableau de bord"` → `"Contrôle"` (icon stays `Home`)
- Line 68: `"Scraping"` → `"Médias"` (icon stays `ScanSearch`, path → `"/medias"`)
- Line 100 (`BOTTOM_TAB_PATHS`): `"/scraping"` → `"/medias"`

**File:** `frontend/src/components/layout/AppShell.tsx` (badge map)

The `badges` record keys: `"/scraping"` → `"/medias"` (the badge logic stays identical — it already reads `counts.awaiting_action`). Grep for `"/scraping"` in AppShell.tsx and verify no other stale path references.

**File:** `frontend/src/components/layout/AppShell.test.tsx` — update assertions: `"Tableau de bord"` → `"Contrôle"`, `"Scraping"` → `"Médias"`, verify `/medias` renders in the bottom tab bar.

**Gate:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`
