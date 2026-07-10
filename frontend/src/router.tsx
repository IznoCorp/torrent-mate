/**
 * Application route table for TorrentMateUI.
 *
 * `/login` is a public, chrome-less route. Every authenticated route nests under
 * {@link ProtectedRoute} → {@link AppShell} (TopBar + responsive nav +
 * `<Outlet />`), so the guard runs once and the shell renders once, swapping only
 * the page. The S5–S7 slots resolve to the shared {@link ComingSoon} placeholder
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
import Decisions from "@/pages/Decisions";
import Login from "@/pages/Login";
import Maintenance from "@/pages/Maintenance";
import Config from "@/pages/Config";
import NotFound from "@/pages/NotFound";
import Pipeline from "@/pages/Pipeline";
import RegistryPage from "@/pages/RegistryPage";

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
                element: <Pipeline />,
              },
              {
                path: "maintenance",
                element: <Maintenance />,
              },
              {
                path: "config",
                element: <Config />,
              },
              {
                path: "scraping",
                element: <Decisions />,
              },
              {
                path: "registry",
                element: <RegistryPage />,
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
