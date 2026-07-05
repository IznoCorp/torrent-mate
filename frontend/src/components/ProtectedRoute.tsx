/**
 * Route guard for the authenticated area of TorrentMateUI.
 *
 * `ProtectedRoute` is a pathless layout route: it reads the session from
 * {@link useAuthContext} and renders one of three outcomes —
 *
 * - **loading** (initial ``me`` query in flight) → a centered DS spinner, so a
 *   warm reload never flashes the login page before the session resolves;
 * - **unauthenticated** → `<Navigate>` to `/login`, carrying the current path in
 *   a `?redirect=` param so the user returns where they were after logging in;
 * - **authenticated** → `<Outlet />`, handing off to the app shell.
 */

import { LoaderCircle } from "lucide-react";
import type { ReactElement } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuthContext } from "@/hooks/useAuthContext";

/**
 * Guard the nested authenticated routes.
 *
 * Returns:
 *   The DS spinner while loading, a redirect to `/login` when unauthenticated,
 *   or the routed `<Outlet />` once authenticated.
 */
export function ProtectedRoute(): ReactElement {
  const { isAuthenticated, isLoading } = useAuthContext();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center bg-background"
      >
        <LoaderCircle
          className="size-8 animate-spin text-muted-foreground"
          aria-hidden="true"
        />
        <span className="sr-only">Chargement…</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Preserve the intended destination (path + query) so the login flow can
    // send the user back after authenticating.
    const current = `${location.pathname}${location.search}`;
    return (
      <Navigate
        to={`/login?redirect=${encodeURIComponent(current)}`}
        replace
      />
    );
  }

  return <Outlet />;
}
