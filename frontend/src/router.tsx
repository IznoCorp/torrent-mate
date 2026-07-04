/**
 * Application route table for TorrentMateUI.
 *
 * `/login` is a public, chrome-less route. Every other route nests under the
 * {@link AppShell} layout route (TopBar + responsive nav + `<Outlet />`), so the
 * shell renders once and swaps only the page. The S2–S7 slots resolve to the
 * shared {@link ComingSoon} placeholder with their wave tag.
 *
 * NOTE (sub-phase 5.2): routes mount **without** an auth guard — `/login` stays
 * reachable and the shell is reachable at `/`. Sub-phase 5.3 wraps the layout
 * route in `ProtectedRoute`/`AuthProvider`.
 *
 * The {@link routes} array is exported so tests can build a `createMemoryRouter`
 * over the exact same table the production `createBrowserRouter` uses.
 */

import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import ComingSoon from "@/pages/ComingSoon";
import Dashboard from "@/pages/Dashboard";
import Login from "@/pages/Login";
import NotFound from "@/pages/NotFound";

/** The full route table (shared by the browser router and memory-router tests). */
export const routes: RouteObject[] = [
  { path: "/login", element: <Login /> },
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
  { path: "*", element: <NotFound /> },
];

/** The production browser router. */
export const router = createBrowserRouter(routes);
