import type { ReactElement } from "react";

/**
 * Root application placeholder for TorrentMateUI.
 *
 * Renders a French "under construction" screen already dressed in the
 * PersonalScraper design system (dark control-deck surface, signal-amber
 * primary, Geist type) via the DS token layer wired into Tailwind v4. The real
 * shell (navigation, routing, auth flow, dashboard) arrives in phase 5.
 *
 * @returns The placeholder application element.
 */
export default function App(): ReactElement {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background p-6 text-center font-sans text-foreground">
      <h1 className="text-2xl font-semibold tracking-tight text-primary">
        TorrentMate — interface en construction
      </h1>
      <p className="text-sm text-muted-foreground">
        Le tableau de bord arrive bientôt.
      </p>
    </main>
  );
}
