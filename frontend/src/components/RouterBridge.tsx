/**
 * RouterBridge — the router-aware glue that {@link AuthProvider} cannot be.
 *
 * Extracted from ``router.tsx`` to satisfy the
 * ``react-refresh/only-export-components`` lint rule — the route-table module
 * exports ``routes`` and ``router``; the component lives in its own file.
 *
 * ``AuthProvider`` is mounted above ``RouterProvider``, so it has no access to
 * ``useNavigate``. This pathless layout route runs *inside* the router and, on
 * mount, registers the global 401 handler ({@link setUnauthorizedHandler}) with
 * a router navigation: when any query/mutation answers 401, the user is sent to
 * ``/login`` (preserving the current path in ``?redirect=``) without a full page
 * reload — replacing the default hard ``window.location.assign`` fallback.
 *
 * The handler **invalidates the ``me`` cache** on any 401: a session that expired
 * mid-use leaves ``me`` cached as a stale success, so without clearing it the app
 * would keep reading as authenticated (and ``Login`` would bounce the user back
 * onto the protected route — ping-pong). ``removeQueries`` drops the cached
 * identity; the ``AuthProvider`` observer refetches, answers 401 too, and settles
 * ``me`` into an error state → ``isAuthenticated`` becomes false and {@link
 * ProtectedRoute} redirects to ``/login`` (preserving ``?redirect=``) from that
 * *settled* state. Driving the redirect through the guard rather than an eager
 * ``navigate()`` here avoids a race where ``Login`` reads a not-yet-updated
 * authenticated state and bounces back.
 *
 * The one route the guard does not cover is the public ``/login`` page itself: a
 * 401 there (a background request after the session lapsed) is handled by
 * re-navigating to ``/login`` while **preserving the current ``?redirect=``**, so
 * the intended post-login destination is not lost.
 *
 * Returns:
 *   The nested route ``<Outlet />``.
 */

import { useEffect, useRef, type ReactElement } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { setUnauthorizedHandler } from "@/api/client";
import { authKeys } from "@/hooks/useAuth";

export function RouterBridge(): ReactElement {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  // Keep the live location in a ref so the (stable, registered-once) 401 handler
  // reads the path at the moment the 401 fires — not the path at registration.
  const locationRef = useRef(location);
  locationRef.current = location;

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Invalidate the (possibly stale-success) `me` cache so its observer
      // refetches: the session has lapsed, so the refetch answers 401 too and
      // settles `me` into an error state → `isAuthenticated` becomes false and
      // ProtectedRoute redirects to /login off that settled state (no eager
      // navigate here → no stale-auth bounce, and the `me` 401 is exempt from
      // this handler, so no loop). `removeQueries` alone would not re-run the
      // observer; invalidation forces the refetch that produces the 401.
      void queryClient.invalidateQueries({ queryKey: authKeys.me });

      // On the public /login page the guard isn't mounted, so redirect here —
      // preserving any `?redirect=` target rather than stripping it.
      const { pathname, search } = locationRef.current;
      if (pathname === "/login") {
        void navigate(`/login${search}`, { replace: true });
      }
    });
  }, [navigate, queryClient]);

  return <Outlet />;
}
