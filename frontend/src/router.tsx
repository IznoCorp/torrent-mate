/**
 * Application route table for TorrentMateUI.
 *
 * `/login` is a public, chrome-less route. Every authenticated route nests under
 * {@link ProtectedRoute} → {@link AppShell} (TopBar + responsive nav +
 * `<Outlet />`), so the guard runs once and the shell renders once, swapping only
 * the page. The S2–S7 slots resolve to the shared {@link ComingSoon} placeholder
 * with their wave tag.
 *
 * A pathless {@link RouterBridge} wraps the whole tree: it lives *inside* the
 * router (so it may call `useNavigate`) and registers the router-aware 401
 * handler that `AuthProvider` — which sits *above* the router and therefore
 * cannot navigate — is unable to install itself.
 *
 * The {@link routes} array is exported so tests can build a `createMemoryRouter`
 * over the exact same table the production `createBrowserRouter` uses.
 */

import { useEffect, useRef, type ReactElement } from "react";
import {
  createBrowserRouter,
  Outlet,
  useLocation,
  useNavigate,
  type RouteObject,
} from "react-router-dom";

import { setUnauthorizedHandler } from "@/api/client";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import ComingSoon from "@/pages/ComingSoon";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import NotFound from "@/pages/NotFound";

/**
 * RouterBridge — the router-aware glue that `AuthProvider` cannot be.
 *
 * `AuthProvider` is mounted above `RouterProvider`, so it has no access to
 * `useNavigate`. This pathless layout route runs *inside* the router and, on
 * mount, registers the global 401 handler ({@link setUnauthorizedHandler}) with
 * a router navigation: when any query/mutation answers 401, the user is sent to
 * `/login` (preserving the current path in `?redirect=`) without a full page
 * reload — replacing the default hard `window.location.assign` fallback.
 *
 * The handler intentionally does **not** clear the `me` cache: doing so would
 * refetch `me` (its observer stays mounted in `AuthProvider` above the router),
 * re-trigger a 401, and loop. The 401 that fired the handler has already
 * invalidated the session — `AuthProvider` reflects the unauthenticated state
 * from `me`'s own error, and explicit logout clears the cache via `useLogout`.
 *
 * Returns:
 *   The nested route `<Outlet />`.
 */
function RouterBridge(): ReactElement {
  const navigate = useNavigate();
  const location = useLocation();
  // Keep the live location in a ref so the (stable, registered-once) 401 handler
  // reads the path at the moment the 401 fires — not the path at registration.
  const locationRef = useRef(location);
  locationRef.current = location;

  useEffect(() => {
    setUnauthorizedHandler(() => {
      const { pathname, search } = locationRef.current;
      // Already on the login page — stay put, never build a self-redirect loop.
      if (pathname === "/login") {
        void navigate("/login", { replace: true });
        return;
      }
      const current = `${pathname}${search}`;
      void navigate(`/login?redirect=${encodeURIComponent(current)}`, {
        replace: true,
      });
    });
  }, [navigate]);

  return <Outlet />;
}

/** The full route table (shared by the browser router and memory-router tests). */
export const routes: RouteObject[] = [
  {
    element: <RouterBridge />,
    children: [
      { path: "/login", element: <Login /> },
      {
        element: <ProtectedRoute />,
        children: [
          {
            element: <AppShell />,
            children: [
              { index: true, element: <Dashboard /> },
              {
                path: "pipeline",
                element: <ComingSoon title="Pipeline" wave="S2" />,
              },
              {
                path: "maintenance",
                element: <ComingSoon title="Maintenance" wave="S3" />,
              },
              {
                path: "config",
                element: <ComingSoon title="Configuration" wave="S4" />,
              },
              {
                path: "scraping",
                element: <ComingSoon title="Scraping interactif" wave="S5" />,
              },
              {
                path: "registry",
                element: <ComingSoon title="Registre" wave="S6" />,
              },
              {
                path: "acquisition",
                element: <ComingSoon title="Acquisition" wave="S7" />,
              },
            ],
          },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
];

/** The production browser router. */
export const router = createBrowserRouter(routes);
