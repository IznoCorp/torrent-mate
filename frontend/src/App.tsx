import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { RouterProvider } from "react-router-dom";

import { queryClient } from "@/api/client";
import { AuthProvider } from "@/components/AuthProvider";
import { useAuthContext } from "@/hooks/useAuthContext";
import { InstallBanner } from "@/components/InstallBanner";
import { aboveBottomBar } from "@/components/layout/bottom-bar-metrics";
import { Toaster } from "@/components/ui/sonner";
import { usePwa } from "@/hooks/usePwa";
import { router } from "@/router";

/**
 * PwaLayer — mounts the single {@link usePwa} instance and its install UI.
 *
 * Rendered inside {@link AuthProvider} + the Query client (so it can gate the
 * `/api/version` poll on the session and issue the query) but **outside** the
 * router, as a sibling of `RouterProvider`, so the update toast and install
 * banner are present on every route — including the public login page, where
 * proposing installation is still valuable. Mounting the hook here exactly once
 * keeps a single service-worker registration and a single beforeinstallprompt
 * capture for the whole app. The update toast is raised by `usePwa` itself onto
 * the shared {@link Toaster} host; this layer only renders the install banner.
 *
 * @returns The PWA overlay layer (toast host + install banner).
 */
function PwaLayer(): ReactElement {
  const { isAuthenticated } = useAuthContext();
  const pwa = usePwa({ versionPollEnabled: isAuthenticated });

  return (
    <>
      <InstallBanner state={pwa} />
      {/*
        §10 — the toast sits JUST above the bottom bar, never below it.
        The previous setting was `bottom: 84px` calibrated on desktop: on iPhone
        the bar grows by env(safe-area-inset-bottom) (~34 px) and the toast slid
        underneath. The offset reads the REAL height the bar publishes (see
        aboveBottomBar), which stays correct at any bar height, on any device.

        The `0px` fallback is not a precaution: it is the NORMAL case on the two
        surfaces without a bar — the login page (outside AppShell) and every
        viewport ≥ md, where the bar is `md:hidden`. A phone-calibrated fallback
        would float the toast in empty space there.

        The Toaster stays here, inside PwaLayer, sibling of the router: this is
        what makes it visible on ALL routes, login page included. Moving it into
        AppShell (inside ProtectedRoute) would silently kill the PWA update toast
        on that page.

        Close button and 5 s: two lines were unreadable in 2.2 s, and the close
        button is the real control — nobody is forced to wait.
      */}
      <Toaster
        position="bottom-center"
        closeButton
        duration={5000}
        offset={aboveBottomBar("0.75rem")}
      />
    </>
  );
}

/**
 * App — the TorrentMateUI root.
 *
 * Provider order (outer → inner): the shared TanStack Query client (with its
 * global 401 policy) → `AuthProvider` → `RouterProvider`. `AuthProvider` sits
 * **above** the router on purpose: its single `me` observer must survive route
 * changes and drive the shell's auth guard. Because it is above the router it
 * never navigates itself — the router-aware pieces (`RouterBridge`, the guard,
 * the login redirect, the user-menu logout) do that from inside the router tree.
 *
 * {@link PwaLayer} is a router sibling so the PWA update/install UI is visible
 * on every route, login page included.
 *
 * @returns The application root element.
 */
export default function App(): ReactElement {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
        <PwaLayer />
      </AuthProvider>
    </QueryClientProvider>
  );
}
