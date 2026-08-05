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
  const spineTotal = Object.values(byStatus).reduce((a, b) => a + b, 0);
  // Empty state ONLY when EVERY pillar is zero — a manual-drop item raises a pending
  // decision with NO spine row, so it must never be hidden by a spine-only check
  // (§méthode rule 6: don't under-count what needs attention).
  if (spineTotal === 0 && d.awaiting_resolution === 0) {
    return (
      <EmptyState
        title="Rien en vol"
        description="Aucune acquisition ni décision en attente. Les grabs issus d'un suivi apparaîtront ici, agrégés par étape."
      />
    );
  }

  const grabbed = byStatus.grabbed ?? 0;
  const ingested = byStatus.ingested ?? 0;
  const scraped = byStatus.scraped ?? 0;
  const dispatched = byStatus.dispatched ?? 0;

  return (
    <div className="flex flex-col gap-3">
      {/*
        §12 — au doigt : chaque tuile actionnable est cliquable ENTIÈREMENT. `<Link>` rend
        un `<a>` `display:inline`, dont la boîte se réduit au contenu : sans `block h-full`
        la cible tactile n'était qu'une fraction de la carte, et la carte ne s'étirait pas
        à sa piste de grille — d'où la rangée inégale à côté de « Dispatchés », la seule
        tuile sans lien. `h-full` sur l'ancre porte la hauteur de piste, `h-full` sur la
        tuile la transmet jusqu'à la carte.
      */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Link
          to="/acquisition?tab=parcours"
          aria-label="Voir les parcours en vol"
          className="block h-full"
        >
          <StatPanel
            className="h-full"
            label="En vol"
            value={d.in_flight}
            secondary={`${String(grabbed)} récupérés · ${String(ingested)} ingérés · ${String(scraped)} scrapés`}
          />
        </Link>
        <Link
          to="/acquisition?tab=parcours"
          aria-label="Voir les items bloqués"
          className="block h-full"
        >
          <StatPanel
            className="h-full"
            label="Bloqués"
            value={d.stuck}
            secondary={d.stuck > 0 ? "à reprendre" : "aucun"}
          />
        </Link>
        <Link
          to="/medias"
          aria-label="Voir les décisions en attente"
          className="block h-full"
        >
          <StatPanel
            className="h-full"
            label="En attente de résolution"
            value={d.awaiting_resolution}
            secondary={d.awaiting_resolution > 0 ? "à résoudre" : "aucune"}
          />
        </Link>
        <StatPanel
          className="h-full"
          label="Dispatchés"
          value={dispatched}
          secondary="rangés"
        />
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
