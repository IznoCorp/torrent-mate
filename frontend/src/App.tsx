import type { ReactElement } from "react";

/**
 * Root application placeholder for TorrentMateUI.
 *
 * Renders a French "under construction" screen. The real shell (navigation,
 * routing, auth flow, dashboard) and the design-system branding arrive in the
 * design-system sub-phase (4.2) and the shell phase (phase 5).
 *
 * @returns The placeholder application element.
 */
export default function App(): ReactElement {
  return (
    <main>
      <h1>TorrentMate — interface en construction</h1>
      <p>Le tableau de bord arrive bientôt.</p>
    </main>
  );
}
