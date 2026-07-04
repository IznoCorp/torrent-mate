# Phase 5 — Shell + auth flow

## Gate

- Phase 4 complete: frontend scaffold builds, typed API client generated,
  CI frontend job green.
- Backend running (dev mode) with auth + WS relay functional.
- `frontend/src/api/client.ts` exports typed `fetcher` + `queryClient`.

## Sub-phases

### 5.1 — Login page (TanStack Form + zod)

**Commit**: `feat(tm-shell): add login page with form validation and auth API`

**Files**:

| Action | Path                                    |
| ------ | --------------------------------------- |
| Create | `frontend/src/pages/Login.tsx`          |
| Create | `frontend/src/components/LoginForm.tsx` |
| Create | `frontend/src/hooks/useAuth.ts`         |
| Modify | `frontend/src/api/client.ts`            |

**Work**:

1. `hooks/useAuth.ts` — TanStack Query: `useLogin` mutation (POST `/api/auth/login`,
   `credentials: 'include'`), `useLogout` mutation, `useMe` query (GET
   `/api/auth/me`). Exposes `{login, logout, user, isAuthenticated, isLoading}`.
2. `components/LoginForm.tsx` — TanStack Form + zod adapter:
   `username` (min 1, max 64), `password` (min 1). Submit → `login()`.
   Loading spinner, inline error on 401. Mobile-first centered card.
3. `pages/Login.tsx` — TorrentMate wordmark + logo, form card, no shell chrome.
4. `api/client.ts` — add global `onError`: 401 on any query → clear cache →
   redirect `/login`.

**Verification**: `npx tsc --noEmit && npm run lint`; login form renders, bad
creds → error, valid → redirect.

**As-built notes (5.1)**:

- Shipped as **two commits** (`feat(tm-shell): add auth hooks and 401 redirect
seam`, then `feat(tm-shell): add login page with form validation`) rather than
  the single commit above.
- `useAuth.ts` exports **three hooks** (`useMe`, `useLogin`, `useLogout`) plus a
  stable `authKeys.me = ['auth','me']`. The composed
  `{ user, isAuthenticated, isLoading, login, logout }` shape is intentionally
  deferred to the 5.3 `AuthProvider`, which layers over these hooks.
- **401 seam** lives in `api/client.ts` as `QueryCache`/`MutationCache` `onError`
  handlers + an injectable `setUnauthorizedHandler(fn)` and a
  `SKIP_AUTH_REDIRECT` mutation-`meta` flag (login opts out). 5.3 calls
  `setUnauthorizedHandler` to make the redirect router-aware.
- **DS-adherence lint resolution (resolved 2026-07-04)**: the `no-restricted-syntax`
  prop-whitelist selectors for `Input`/`Button`/`Card`/`Switch` in
  `eslint.config.js` were removed (commit below). This project ships shadcn/ui
  components of the same names (DESIGN-mandated — stock shadcn inherits the theme
  per DS INTEGRATION.md), so the design-system primitive whitelists only produced
  false positives. Aliasing workarounds (`TextField`, `SubmitButton`) are no
  longer needed. The token/hex/px/font-family guards and selectors for the app's
  own DS primitives (StatusDot, LogLine, StatPanel, …) remain active.
- **Pending spinner**: `lucide-react`'s `LoaderCircle` with
  `className="size-4 animate-spin"` (token-safe; no raw px), not a ported DS
  `Spinner`.
- Tests use RTL `fireEvent` (no `@testing-library/user-event` dep installed) and
  must call `cleanup()` in `afterEach` (vitest `globals: false` ⇒ no auto-cleanup).

### 5.2 — App shell (layout, nav, router, placeholders)

**Commit**: `feat(tm-shell): add mobile-first app shell with navigation and route slots`

**Files**:

| Action | Path                                              |
| ------ | ------------------------------------------------- |
| Create | `frontend/src/components/layout/AppShell.tsx`     |
| Create | `frontend/src/components/layout/BottomTabBar.tsx` |
| Create | `frontend/src/components/layout/Sidebar.tsx`      |
| Create | `frontend/src/components/layout/TopBar.tsx`       |
| Create | `frontend/src/components/layout/UserMenu.tsx`     |
| Create | `frontend/src/router.tsx`                         |
| Modify | `frontend/src/App.tsx`                            |
| Modify | `frontend/src/main.tsx`                           |

**Work**:

1. `router.tsx` — React Router `createBrowserRouter`: `/login` public,
   protected layout (`ProtectedRoute` wrapper), routes: `/` (Dashboard),
   `/pipeline`, `/maintenance`, `/config`, `/scraping`, `/registry`,
   `/acquisition` → stubbed "À venir" placeholder pages (S2–S7 slots).
2. `AppShell.tsx` — `BottomTabBar` (< md) or `Sidebar` (≥ md) + `TopBar` +
   `<Outlet />`. TopBar: wordmark left, StatusDot + UserMenu right.
3. `BottomTabBar.tsx` — Lucide icons: Home, Activity, Wrench, Settings.
   Inactive slots dimmed. Active slot highlighted (DS amber).
4. `Sidebar.tsx` — same nav items, collapsible, desktop-only.
5. Copy: French-leading, `font-mono tabular-nums`, emoji only 🔥🌤❄️⛔.

**Verification**: `npx tsc --noEmit && npm run lint`; mobile → bottom tabs,
desktop → sidebar; all slots navigate without errors.

**As-built notes (5.2)**:

- **No auth guard** (deferred to 5.3, per scope bound): the layout route mounts
  **without** `ProtectedRoute`/`AuthProvider`. `/login` stays public and the shell
  is reachable at `/`. 5.3 wraps the layout route in the guard.
- Shipped as **two commits**, layout before router (router imports `AppShell`, so
  the layout must land first for each intermediate commit to build):
  `feat(tm-shell): add mobile-first app shell layout`, then
  `feat(tm-shell): add router with S2-S7 placeholder slots`.
- **Extra files beyond the plan's Files table** (implied by the Work items):
  `pages/Dashboard.tsx` (index placeholder — real dashboard is phase 6),
  `pages/ComingSoon.tsx` (shared « À venir » stub, `title` + `wave` props),
  `pages/NotFound.tsx` (French 404, outside the shell), and
  `components/layout/nav.ts` — a single source of nav truth (`NAV_ITEMS` +
  `BOTTOM_TAB_ITEMS`) shared by `Sidebar` and `BottomTabBar`.
- **`router.tsx`** exports the `routes` (`RouteObject[]`) table alongside the
  `createBrowserRouter` `router`, so tests build a `createMemoryRouter` over the
  exact same table.
- **Wave-tag mapping** for the `ComingSoon` slots: `/pipeline`→S2,
  `/maintenance`→S3, `/config`→S4, `/scraping`→S5, `/registry`→S6,
  `/acquisition`→S7.
- **`main.tsx` unchanged**: it already renders `<App />` in `StrictMode`; all
  provider wiring (`QueryClientProvider` > `RouterProvider`, client from
  `api/client`) lives in `App.tsx` (the plan listed `main.tsx` as _Modify_, but no
  edit was needed).
- **TopBar `StatusDot`**: WS transport arrives in phase 6, so 5.2 shows a neutral
  `status="idle"` / label « Hors ligne » placeholder. The tooltip lives on a
  wrapping `<span title=…>` — the DS-adherence lint whitelist rejects a `title`
  prop passed directly to `<StatusDot>`.
- **`UserMenu`**: shadcn `DropdownMenu` + `Avatar` (static « — » fallback until
  5.3 provides the username initial); « Se déconnecter » →
  `useLogout().mutate()` + `window.location.assign('/login')` (5.3 refines to a
  router-aware redirect).
- **`Sidebar` collapse** persists to `localStorage` (`tm-sidebar-collapsed`) via a
  typed hook; read/write failures fall back to in-memory state.
- **Active-state** styling uses NavLink's default `aria-current="page"` (asserted
  in tests) with DS amber `text-primary`; inactive = `text-muted-foreground`.
- **Tests** (`router.test.tsx`, `createMemoryRouter` over exported `routes`):
  shell + Dashboard at `/`, `ComingSoon` + wave tag `S2` at `/pipeline`,
  bottom-tab active state via `aria-current`, and the French 404 on an unknown
  path. `App.test.tsx` updated (old « interface en construction » assertion
  replaced). RTL `cleanup()` in `afterEach` (vitest `globals: false`).

### 5.3 — Auth guard wiring (ProtectedRoute, AuthProvider)

**Commit**: `feat(tm-shell): wire auth guard and login redirect flow`

**Files**:

| Action | Path                                         |
| ------ | -------------------------------------------- |
| Create | `frontend/src/components/ProtectedRoute.tsx` |
| Create | `frontend/src/components/AuthProvider.tsx`   |
| Modify | `frontend/src/router.tsx`                    |
| Modify | `frontend/src/App.tsx`                       |

**Work**:

1. `AuthProvider.tsx` — wraps app root: calls `useMe()` on mount, provides
   `{user, isAuthenticated, isLoading, login, logout}` via React context.
2. `ProtectedRoute.tsx` — reads `isAuthenticated` / `isLoading` from
   AuthProvider context: loading → spinner, unauthenticated → Navigate to
   `/login?redirect=<current>`, authenticated → `<Outlet />`.
3. `router.tsx` — wrap protected routes in `ProtectedRoute`; login route
   redirects to `/` if already authenticated.
4. `UserMenu.tsx` → logout calls `logout()`, clears query cache, navigates
   to `/login`.
5. `App.tsx` — `<AuthProvider>` > `<RouterProvider>`.

**Verification**: `/` unauthenticated → redirected `/login`; login →
redirected back; logout → `/login`; manual cookie deletion → 401 on
next `/me` poll → redirect.

## Verification

```bash
cd frontend && npx tsc --noEmit && npm run lint && npm run test -- --run
```

**Manual**: boot backend → `cd frontend && npm run dev` → login flow
end-to-end (invalid creds, valid → dashboard shell visible, logout).
