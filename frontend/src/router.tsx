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

import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RouterBridge } from "@/components/RouterBridge";
import ComingSoon from "@/pages/ComingSoon";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import NotFound from "@/pages/NotFound";

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
