/**
 * Application-wide authentication context for TorrentMateUI.
 *
 * `AuthProvider` mounts a single {@link useMe} query at the app root and exposes
 * the derived session state — `{ user, isAuthenticated, isLoading, logout }` — to
 * every descendant through React context. It is deliberately mounted **above**
 * the router (see `App.tsx`) so the session identity survives route changes and a
 * single `me` observer drives the shell's auth guard.
 *
 * Boundary rule: `AuthProvider` never touches the router (no `useNavigate`) — it
 * sits above `RouterProvider`, where router hooks are out of context. The
 * router-aware pieces (post-login redirect, the 401 → `/login` handler, the
 * logout navigation) live *inside* the router tree (`RouterBridge`, `Login`,
 * `UserMenu`). Login itself stays in the form via {@link useLogin}; only the
 * *end-of-session* action (`logout`) is surfaced here.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactElement,
  type ReactNode,
} from "react";

import { useLogout, useMe, type AuthenticatedUser } from "@/hooks/useAuth";

/**
 * The session state shared through {@link useAuthContext}.
 *
 * Attributes:
 *   user: The authenticated identity payload, or ``undefined`` when the session
 *     is absent or still loading.
 *   isAuthenticated: ``true`` once the ``me`` query has resolved successfully.
 *     A 401 (session lapsed) is surfaced by the query erroring, so ``isSuccess``
 *     flips false and the guard redirects — the ``RouterBridge`` 401 handler
 *     invalidates ``me`` so a stale success cannot keep this ``true``.
 *   isLoading: ``true`` while the initial ``me`` query is in flight (drives the
 *     guard's spinner so the app never flashes the login page on a warm reload).
 *   logout: End the session (clears the query cache via {@link useLogout}); the
 *     caller performs the router navigation afterwards.
 */
export interface AuthContextValue {
  readonly user: AuthenticatedUser | undefined;
  readonly isAuthenticated: boolean;
  readonly isLoading: boolean;
  readonly logout: () => Promise<void>;
}

/** Context handle; ``null`` until an {@link AuthProvider} is mounted above. */
const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Provide the app-wide auth context by composing the auth hooks.
 *
 * Args:
 *   children: The subtree that reads the session via {@link useAuthContext}
 *     (in practice the whole `RouterProvider`).
 *
 * Returns:
 *   The provider element wrapping ``children``.
 */
export function AuthProvider({
  children,
}: {
  children: ReactNode;
}): ReactElement {
  const meQuery = useMe();
  const logoutMutation = useLogout();

  // Stable async logout wrapper — resolves once the session cookie is cleared
  // (`useLogout` also `clear()`s the cache); navigation is the caller's job.
  const logout = useCallback(
    (): Promise<void> => logoutMutation.mutateAsync(),
    [logoutMutation],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user: meQuery.data,
      isAuthenticated: meQuery.isSuccess,
      isLoading: meQuery.isLoading,
      logout,
    }),
    [meQuery.data, meQuery.isSuccess, meQuery.isLoading, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Read the app-wide auth context.
 *
 * Returns:
 *   The current {@link AuthContextValue}.
 *
 * Raises:
 *   Error: When called outside an {@link AuthProvider} subtree (a programming
 *     error — the provider wraps the router at the app root).
 */
export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error(
      "useAuthContext doit être appelé à l’intérieur de <AuthProvider>.",
    );
  }
  return context;
}
