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
