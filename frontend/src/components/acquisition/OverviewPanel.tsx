/**
 * « Vue d'ensemble » — the unified « état de la machine » rollup (provenance F5 capstone).
 *
 * One page over the F0–F4 spine (GET /api/acquisition/overview): acquisitions by stage,
 * items stuck, décisions en attente. Each actionable tile deep-links to the URL-addressable
 * detail view (product-intent §2 pipeline lisible / §5 acquisitions / §8 « toute vue de
 * détail est adressable par URL »). Read-only; fail-soft (em-dash / EmptyState).
 */

import { useEffect, useState, type ReactElement } from "react";
import { Link } from "react-router-dom";

import { relativeTime } from "@/components/acquisition/meta";
import { EmptyState } from "@/components/ds/EmptyState";
import { StatPanel } from "@/components/ds/StatPanel";
import { useOverview } from "@/hooks/useAcquisition";

/**
 * PendingRunLine — ce que le watcher attend, en une phrase (§8 / DOIT-2).
 *
 * Le watcher est un process séparé : sans cette ligne, l'écran reste identique qu'il
 * temporise ou qu'il soit mort, et une attente muette se lit comme une panne — le péché
 * originel du post-mortem #249. Deux situations, deux phrases, et RIEN quand le daemon
 * n'a rien publié : on ne raconte pas une attente qu'on ne connaît pas.
 *
 * @param pending - L'attente publiée par le daemon, ou null/undefined.
 * @returns La ligne d'explication, ou null.
 */
function PendingRunLine({
  pending,
}: {
  pending:
    | {
        fires_at?: number | null;
        active_downloads?: number;
        updated_at: number;
      }
    | null
    | undefined;
}): ReactElement | null {
  // Le compte à rebours doit VIVRE : une échéance figée à l'affichage vieillirait en
  // silence jusqu'au prochain rafraîchissement de la requête.
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const id = setInterval(() => {
      setNow(Date.now() / 1000);
    }, 1000);
    return () => {
      clearInterval(id);
    };
  }, []);

  if (pending == null) return null;
  const actifs = pending.active_downloads ?? 0;
  if (actifs > 0) {
    return (
      <p className="text-xs text-muted-foreground">
        {actifs} téléchargement{actifs > 1 ? "s" : ""} en cours · l'ingestion
        démarrera une fois le dernier terminé
      </p>
    );
  }
  if (pending.fires_at != null) {
    const restant = Math.max(0, Math.round(pending.fires_at - now));
    return (
      <p className="text-xs text-muted-foreground">
        Ingestion dans {restant} s · toute nouvelle arrivée relance le délai
      </p>
    );
  }
  return null;
}

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
        §2/DOIT-10 — les QUATRE tuiles mènent à LEURS items, par une URL partageable :
        une tuile qui annonce 56 sans donner accès à ces 56 est un cul-de-sac
        (NE-DOIT-PAS-9), et « Dispatchés » n'avait aucun lien du tout.

        §12 — au doigt : chaque tuile actionnable est cliquable ENTIÈREMENT. `<Link>` rend
        un `<a>` `display:inline`, dont la boîte se réduit au contenu : sans `block h-full`
        la cible tactile n'était qu'une fraction de la carte, et la carte ne s'étirait pas
        à sa piste de grille — d'où la rangée inégale à côté de « Dispatchés », la seule
        tuile sans lien. `h-full` sur l'ancre porte la hauteur de piste, `h-full` sur la
        tuile la transmet jusqu'à la carte.
      */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Link
          to="/acquisition?tab=parcours&etape=en-vol"
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
          to="/acquisition?tab=parcours&etape=bloques"
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
        <Link
          to="/acquisition?tab=parcours&etape=ranges"
          aria-label="Voir les acquisitions rangées"
          className="block h-full"
        >
          <StatPanel
            className="h-full"
            label="Dispatchés"
            value={dispatched}
            secondary="rangés"
          />
        </Link>
      </div>
      <PendingRunLine pending={d.pending_run} />
      <p className="text-xs text-muted-foreground">
        {d.watcher_enabled ? "Veille active" : "Veille en pause"}
        {d.last_successful_run_at != null
          ? ` · dernier run réussi ${relativeTime(d.last_successful_run_at)}`
          : ""}
      </p>
    </div>
  );
}
