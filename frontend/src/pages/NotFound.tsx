import type { ReactElement } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

/**
 * NotFound — the French 404 page for any unmatched route.
 *
 * Rendered outside the app shell (its own full-screen surface) since an unknown
 * path may not correspond to any nav slot. Offers a single way back to the
 * dashboard.
 *
 * @returns The not-found page element.
 */
export default function NotFound(): ReactElement {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background p-6 text-center font-sans text-foreground">
      <p className="font-mono text-5xl font-semibold tabular-nums text-primary">
        404
      </p>
      <h1 className="text-lg font-semibold">Page introuvable</h1>
      <p className="text-sm text-muted-foreground">
        La page demandée n’existe pas.
      </p>
      {/* MISC-2 — DS Button primitive (focus ring + consistent sizing), not a
          raw text link. */}
      <Button asChild variant="link">
        <Link to="/">Retour au tableau de bord</Link>
      </Button>
    </main>
  );
}
