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
        §10 — la notification se pose JUSTE au-dessus de la barre du bas, jamais
        dessous. L'ancien réglage était un `bottom: 84px` calibré sur desktop :
        sur iPhone la barre grandit de env(safe-area-inset-bottom) (~34 px) et la
        notification passait dessous. L'offset lit donc la hauteur RÉELLE que la
        barre publie (voir aboveBottomBar), ce qui reste juste à n'importe
        quelle hauteur de barre.

        Le repli `0px` n'est pas une précaution : c'est le cas NORMAL sur les
        deux surfaces sans barre — la page de connexion (hors AppShell) et tout
        écran ≥ md, où la barre est `md:hidden`. Un repli calibré téléphone y
        ferait flotter la notification dans le vide.

        Le Toaster reste ici, dans PwaLayer, frère du routeur : c'est ce qui le
        rend visible sur TOUTES les routes, page de connexion comprise. Le
        déplacer dans AppShell (à l'intérieur de ProtectedRoute) tuerait
        silencieusement le toast de mise à jour PWA sur cette page.

        Croix de fermeture et 5 s : deux lignes étaient illisibles en 2,2 s, et
        la croix est le vrai contrôle — personne n'est forcé d'attendre.
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
