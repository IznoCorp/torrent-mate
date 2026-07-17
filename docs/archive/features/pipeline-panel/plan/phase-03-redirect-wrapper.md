# Phase 03 — `/maintenance?run=` redirect wrapper

**Goal**: `/maintenance?run=<uid>` conditionally redirects to `/pipeline?run=<uid>`, while
`/maintenance` without `?run=` renders Maintenance normally (untouched until V5).

**Constitution served**: DOIT-10 (every detail has its URL; Back closes what it must),
§1.1 redirect rule.

## Surface

| File                                                          | Action                                              |
| ------------------------------------------------------------- | --------------------------------------------------- |
| `frontend/src/components/pipeline/MaintenanceRunRedirect.tsx` | NEW — conditional redirect wrapper                  |
| `frontend/src/router.tsx`                                     | Wire wrapper as `/maintenance` route element        |
| `frontend/src/router.test.tsx`                                | Add redirect + pass-through tests                   |
| `frontend/src/pages/Maintenance.test.tsx`                     | Assert `/maintenance` without `?run=` still renders |

## Sub-phases

### 3.1 — Create the conditional redirect wrapper

**Commit**: `feat(pipeline-panel): add MaintenanceRunRedirect conditional wrapper`

New file `frontend/src/components/pipeline/MaintenanceRunRedirect.tsx`:

```tsx
import { Navigate, useSearchParams } from "react-router-dom";
import type { ReactElement } from "react";
import Maintenance from "@/pages/Maintenance";

export function MaintenanceRunRedirect(): ReactElement {
  const [searchParams] = useSearchParams();
  const runUid = searchParams.get("run");
  if (runUid !== null && runUid !== "") {
    return <Navigate to={`/pipeline?run=${runUid}`} replace />;
  }
  return <Maintenance />;
}
```

- Uses `replace` so Back doesn't land on the redirecting URL.
- Only forwards the `run` param (not all search params) — `LegacyRedirect` forwards
  everything which is wrong here (a future `?tab=` on `/maintenance` shouldn't go to
  Pipeline).
- Renders `<Maintenance />` directly for the pass-through case — no extra wrapper DOM node.

### 3.2 — Wire into router + test migration

**Commit**: `feat(pipeline-panel): wire MaintenanceRunRedirect into /maintenance route`

In `router.tsx`:

- Change the `/maintenance` route element from `<Maintenance />` to
  `<MaintenanceRunRedirect />`.
- Import the new component.
- No other route changes.

In `router.test.tsx`:

- Add test: `createMemoryRouter` at `/maintenance?run=abc123` → assert redirect to
  `/pipeline?run=abc123` (use `waitFor` + location assertion).
- Add test: `createMemoryRouter` at `/maintenance` → assert Maintenance renders (not
  redirected). Verify the page heading "Maintenance" is present.

In `Maintenance.test.tsx`:

- Existing test renders `<Maintenance />` directly (not via router) — unaffected.
- Add a quick assertion that the page heading is "Maintenance" (if not already).

## Gate

- [ ] Both commits follow Conventional Commits with `(pipeline-panel)` scope
- [ ] `cd frontend && npm run lint && npm run lint:ds && npm run typecheck` → 0 errors
- [ ] `npx vitest run` → all passing, including new redirect + pass-through assertions
- [ ] `make lint && make test` (backend — zero changes, zero regressions)
- [ ] Manual: open `/maintenance?run=<any-uid>` → redirects to `/pipeline?run=<any-uid>`
- [ ] Manual: open `/maintenance` → renders Maintenance page normally
- [ ] Manual: Back button from Pipeline after redirect → does NOT land on `/maintenance?run=`
      (uses `replace`)
