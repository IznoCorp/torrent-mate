/**
 * Application route table for TorrentMateUI.
 *
 * `/login` is a public, chrome-less route. Every authenticated route nests under
 * {@link ProtectedRoute} → {@link AppShell} (TopBar + responsive nav +
 * `<Outlet />`), so the guard runs once and the shell renders once, swapping only
 * the page. The S5–S6 slots resolved to the shared {@link ComingSoon} placeholder;
 * S7 (acquisition) has its own fully-implemented page as of 0.47.0.
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
import { LegacyRedirect } from "@/components/LegacyRedirect";
import { MaintenanceRunRedirect } from "@/components/pipeline/MaintenanceRunRedirect";
import { RouterBridge } from "@/components/RouterBridge";
import AcquisitionPage from "@/pages/AcquisitionPage";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import Medias from "@/pages/Medias";
import Config from "@/pages/Config";
import NotFound from "@/pages/NotFound";
import Pipeline from "@/pages/Pipeline";
import SystemePage from "@/pages/SystemePage";

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
                element: <MaintenanceRunRedirect />,
              },
              {
                path: "config",
                element: <Config />,
              },
              {
                path: "medias",
                element: <Medias />,
              },
              {
                path: "scraping",
                element: <LegacyRedirect to="/medias" />,
              },
              {
                path: "systeme",
                element: <SystemePage />,
              },
              {
                path: "registry",
                element: <LegacyRedirect to="/systeme?tab=etat" />,
              },
              {
                path: "acquisition",
                element: <AcquisitionPage />,
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
