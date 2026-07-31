/**
 * « Vue d'ensemble » — the unified « état de la machine » rollup (provenance F5 capstone).
 *
 * One page over the F0–F4 spine (GET /api/acquisition/overview): acquisitions by stage,
 * items stuck, décisions en attente. Each actionable tile deep-links to the URL-addressable
 * detail view (product-intent §2 pipeline lisible / §5 acquisitions / §8 « toute vue de
 * détail est adressable par URL »). Read-only; fail-soft (em-dash / EmptyState).
 */

import { type ReactElement } from "react";
import { Link } from "react-router-dom";

import { relativeTime } from "@/components/acquisition/meta";
import { EmptyState } from "@/components/ds/EmptyState";
import { StatPanel } from "@/components/ds/StatPanel";
import { useOverview } from "@/hooks/useAcquisition";

/**
 * OverviewPanel — the machine-state rollup tab.
 *
 * Returns:
 *   The « Vue d'ensemble » tab: KPI tiles + a watcher/last-run line.
 */
export function OverviewPanel(): ReactElement {
  const query = useOverview();

  if (query.isLoading) {
    return (
      <p className="text-sm text-muted-foreground">
        Chargement de l'état de la machine…
      </p>
    );
  }
  if (query.isError || query.data == null) {
    return (
      <p className="text-sm text-danger">
        Impossible de charger l'état de la machine.
      </p>
    );
  }

  const d = query.data;
  const byStatus: Record<string, number> = d.by_status;
  const total = Object.values(byStatus).reduce((a, b) => a + b, 0);
  if (total === 0) {
    return (
      <EmptyState
        title="Rien en vol"
        description="Aucune acquisition suivie en cours. Les grabs issus d'un suivi apparaîtront ici, agrégés par étape."
      />
    );
  }

  const grabbed = byStatus.grabbed ?? 0;
  const ingested = byStatus.ingested ?? 0;
  const scraped = byStatus.scraped ?? 0;
  const dispatched = byStatus.dispatched ?? 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Link
          to="/acquisition?tab=parcours"
          aria-label="Voir les parcours en vol"
        >
          <StatPanel
            label="En vol"
            value={d.in_flight}
            secondary={`${String(grabbed)} récupérés · ${String(ingested)} ingérés · ${String(scraped)} scrapés`}
          />
        </Link>
        <Link
          to="/acquisition?tab=parcours"
          aria-label="Voir les items bloqués"
        >
          <StatPanel
            label="Bloqués"
            value={d.stuck}
            secondary={d.stuck > 0 ? "à reprendre" : "aucun"}
          />
        </Link>
        <Link to="/medias" aria-label="Voir les décisions en attente">
          <StatPanel
            label="En attente de résolution"
            value={d.awaiting_resolution}
            secondary={d.awaiting_resolution > 0 ? "à résoudre" : "aucune"}
          />
        </Link>
        <StatPanel label="Dispatchés" value={dispatched} secondary="rangés" />
      </div>
      <p className="text-xs text-muted-foreground">
        {d.watcher_enabled ? "Veille active" : "Veille en pause"}
        {d.last_successful_run_at != null
          ? ` · dernier run réussi ${relativeTime(d.last_successful_run_at)}`
          : ""}
      </p>
    </div>
  );
}
