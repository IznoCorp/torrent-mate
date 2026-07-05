/**
 * Application-wide authentication context handle for TorrentMateUI.
 *
 * The React context ({@link AuthContext}) and its consumer hook
 * ({@link useAuthContext}) live here so the component file
 * ({@link AuthProvider}) only exports the component — satisfying the
 * ``react-refresh/only-export-components`` rule.
 *
 * Boundary rule: {@link AuthProvider} never touches the router (no
 * ``useNavigate``) — it sits above ``RouterProvider``, where router hooks are
 * out of context. The router-aware pieces (post-login redirect, the 401 →
 * ``/login`` handler, the logout navigation) live *inside* the router tree
 * ({@link RouterBridge}, ``Login``, ``UserMenu``). Login itself stays in the
 * form via ``useLogin``; only the *end-of-session* action (``logout``) is
 * surfaced here.
 */

import { createContext, useContext } from "react";

import type { AuthenticatedUser } from "@/hooks/useAuth";

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
 *   logout: End the session (clears the query cache via ``useLogout``); the
 *     caller performs the router navigation afterwards.
 */
export interface AuthContextValue {
  readonly user: AuthenticatedUser | undefined;
  readonly isAuthenticated: boolean;
  readonly isLoading: boolean;
  readonly logout: () => Promise<void>;
}

/** Context handle; ``null`` until an {@link AuthProvider} is mounted above. */
export const AuthContext = createContext<AuthContextValue | null>(null);

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
      "useAuthContext doit être appelé à l'intérieur de <AuthProvider>.",
    );
  }
  return context;
}
