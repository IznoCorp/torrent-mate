/**
 * Authentication hooks for TorrentMateUI.
 *
 * Thin TanStack Query wrappers over the typed API client (``@/api/client``):
 *
 * - {@link useMe} — read the current session identity (``GET /api/auth/me``).
 * - {@link useLogin} — authenticate (``POST /api/auth/login``) and refresh it.
 * - {@link useLogout} — end the session (``POST /api/auth/logout``) + clear.
 *
 * The sub-phase 5.3 ``AuthProvider`` composes these into the app-wide
 * ``{ user, isAuthenticated, isLoading, login, logout }`` context; 5.1 ships the
 * hooks themselves plus the stable {@link authKeys} query key.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { getMe, login, logout, SKIP_AUTH_REDIRECT } from "@/api/client";

/** Credentials accepted by the login endpoint (mirrors ``LoginRequest``). */
export type LoginCredentials = Parameters<typeof login>[0];

/** Shape of the ``GET /api/auth/me`` payload when authenticated. */
export type AuthenticatedUser = Awaited<ReturnType<typeof getMe>>;

/**
 * Stable React-Query keys for the auth domain.
 *
 * Exported so every consumer (the login mutation, the logout flow, and the
 * 5.3 ``AuthProvider``) reads and invalidates the exact same cache entry.
 */
export const authKeys = {
  /** Current-user query key: ``['auth', 'me']``. */
  me: ["auth", "me"] as const,
};

/**
 * Query the currently-authenticated user (``GET /api/auth/me``).
 *
 * ``retry: false`` — a 401 means "not logged in", a definitive answer rather
 * than a transient failure worth retrying. ``staleTime`` keeps the identity
 * fresh for 30 s so route changes don't re-hit the endpoint on every render.
 *
 * Returns:
 *   The query result; ``data`` is the user payload when authenticated,
 *   ``error`` an :class:`ApiError` (status 401) when the session is absent.
 */
export function useMe(): UseQueryResult<AuthenticatedUser> {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: getMe,
    retry: false,
    staleTime: 30_000,
  });
}

/**
 * Log in (``POST /api/auth/login``) and refresh the cached identity.
 *
 * Carries the {@link SKIP_AUTH_REDIRECT} ``meta`` flag so a 401 (bad
 * credentials) surfaces on the form instead of tripping the global redirect.
 * On success the ``me`` query is invalidated so the app re-fetches the now-
 * authenticated identity.
 *
 * Returns:
 *   The mutation result; call ``mutateAsync(credentials)`` from the login form.
 */
export function useLogin(): UseMutationResult<void, Error, LoginCredentials> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: LoginCredentials) => login(credentials),
    meta: { [SKIP_AUTH_REDIRECT]: true },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: authKeys.me }),
  });
}

/**
 * Log out (``POST /api/auth/logout``) and clear all cached data.
 *
 * A full ``clear()`` drops every query so no stale, now-forbidden data lingers
 * after the session ends.
 *
 * Returns:
 *   The mutation result; call ``mutateAsync()`` from the user menu (5.3).
 */
export function useLogout(): UseMutationResult<void, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => logout(),
    onSuccess: () => {
      queryClient.clear();
    },
  });
}
