/**
 * Application-wide authentication provider for TorrentMateUI.
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
  useCallback,
  useMemo,
  type ReactElement,
  type ReactNode,
} from "react";

import { useLogout, useMe } from "@/hooks/useAuth";
import { AuthContext, type AuthContextValue } from "@/hooks/useAuthContext";

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
