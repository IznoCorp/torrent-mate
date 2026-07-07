/**
 * Maintenance dashboard page (TorrentMateUI S3 — maint-dash).
 *
 * Replaces the former {@link ComingSoon} stub at ``/maintenance``. The page
 * renders a responsive grid of monitoring panels: disks, locks, index health,
 * and run history, plus an "Actions" placeholder slot reserved for the 5.2
 * action catalog.
 */

import type { ReactElement } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DisksPanel } from "@/components/maintenance/DisksPanel";
import { IndexHealthPanel } from "@/components/maintenance/IndexHealthPanel";
import { LocksPanel } from "@/components/maintenance/LocksPanel";

/**
 * Maintenance — the authenticated maintenance dashboard route (``/maintenance``).
 *
 * Lays out four monitoring panels in a responsive grid (1 col mobile, 2 tablet,
 * 4 desktop) plus a placeholder "Actions" section reserved for the 5.2 action
 * catalog and action-run form.
 *
 * Returns:
 *   The maintenance page element.
 */
export default function Maintenance(): ReactElement {
  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Maintenance</h1>

      {/* Monitoring panels: 1 col mobile → 2 tablet → 4 desktop */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <DisksPanel />
        <LocksPanel />
        <IndexHealthPanel />
      </div>

      {/* Run-history panel (full-width below the monitoring grid) */}
      <Card>
        <CardHeader>
          <CardTitle>Historique des exécutions</CardTitle>
          <CardDescription>
            Exécutions pipeline et maintenance — filtres et détail à venir (5.2)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Panneau d'historique — sera connecté au composant RunHistoryTable en
            5.2 avec les filtres par type (pipeline / maintenance).
          </p>
        </CardContent>
      </Card>

      {/* Actions placeholder (5.2: ActionCatalog + ActionForm) */}
      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
          <CardDescription>
            Catalogue des commandes de maintenance
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">À venir — vague 5.2.</p>
        </CardContent>
      </Card>
    </section>
  );
}
