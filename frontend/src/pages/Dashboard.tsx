import type { ReactElement } from "react";

/**
 * Dashboard — the authenticated home page (`/`).
 *
 * Sub-phase 5.2 ships a placeholder that proves the shell mounts a route at the
 * index path. The real dashboard — live event feed (TanStack Virtual), recent-
 * events table, and health/version cards wired to the WebSocket relay — lands in
 * phase 6.
 *
 * @returns The dashboard placeholder element.
 */
export default function Dashboard(): ReactElement {
  return (
    <section className="mx-auto flex max-w-3xl flex-col gap-2">
      <h1 className="text-xl font-semibold tracking-tight">Tableau de bord</h1>
      <p className="text-sm text-muted-foreground">
        Le tableau de bord temps réel — flux d’événements, cartes santé et
        version — arrive à la phase 6.
      </p>
    </section>
  );
}
