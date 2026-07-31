/**
 * Parcours tab (provenance F1) — each acquisition's journey through the pipeline.
 *
 * Reads the F0 provenance registry via ``GET /api/acquisition/journeys`` and shows,
 * per acquisition, a compact stage stepper: Récupéré → Ingéré → Scrapé → Rangé,
 * lit up to the stage actually reached (from the per-stage timestamps). Makes the
 * pipeline legible (product-intent §pipeline lisible). Read-only; mobile-first.
 */

import { useQuery } from "@tanstack/react-query";
import { type ReactElement } from "react";
import { Link } from "react-router-dom";

import { acqKeys, getJourneys, type JourneyItem } from "@/api/acquisition";
import { relativeTime } from "@/components/acquisition/meta";
import { EmptyState } from "@/components/ds/EmptyState";
import { Badge } from "@/components/ui/badge";

/**
 * The four pipeline stages, in order — each keyed by its provenance timestamp field
 * and the per-stage run-uid (F3) that deep-links the chip to the run that did it.
 */
const STAGES = [
  { key: "grabbed_at", label: "Récupéré", runKey: "grab_run_uid" },
  { key: "ingested_at", label: "Ingéré", runKey: "ingest_run_uid" },
  { key: "scraped_at", label: "Scrapé", runKey: "scrape_run_uid" },
  { key: "dispatched_at", label: "Rangé", runKey: "dispatch_run_uid" },
] as const;

/** A human-readable label for a journey: the follow title, else an id, else the hash. */
function journeyTitle(j: JourneyItem): string {
  if (j.follow_title) return j.follow_title;
  const id = j.media_ref.tvdb_id ?? j.media_ref.tmdb_id;
  if (id != null) return `#${String(id)}`;
  return j.info_hash.slice(0, 8);
}

/**
 * The scrape-arbiter resolution projection (decisions-spine F2) as an optional chip.
 *
 * ``awaiting`` → an actionable chip deep-linking to the resolution deck
 * (``/medias?decision=<id>``, or ``/medias`` when the id is unknown) so the operator
 * can act. ``resolved`` / ``dismissed`` → a subtle terminal marker. ``null`` (a
 * confident scrape, no decision raised) → nothing.
 *
 * Returns:
 *   The resolution chip, or ``null`` when no decision was raised.
 */
function ResolutionChip({ j }: { j: JourneyItem }): ReactElement | null {
  const state = j.resolution_state;
  if (state == null) return null;
  if (state === "awaiting") {
    const to =
      j.decision_id != null
        ? `/medias?decision=${String(j.decision_id)}`
        : "/medias";
    return (
      <Link to={to} className="self-start">
        <Badge tone="warning" dot>
          En attente de résolution
        </Badge>
      </Link>
    );
  }
  return (
    <Badge tone="muted" className="self-start">
      {state === "resolved" ? "Résolu" : "Écarté"}
    </Badge>
  );
}

/**
 * ParcoursPanel — the acquisition journey view (provenance F1).
 *
 * Returns:
 *   The Parcours tab: one card per acquisition with its stage stepper.
 */
export function ParcoursPanel(): ReactElement {
  const query = useQuery({
    queryKey: [...acqKeys.all, "journeys"],
    queryFn: getJourneys,
  });

  if (query.isLoading) {
    return (
      <p className="text-sm text-muted-foreground">Chargement des parcours…</p>
    );
  }
  if (query.isError) {
    return (
      <p className="text-sm text-danger">
        Impossible de charger les parcours d'acquisition.
      </p>
    );
  }

  const journeys = query.data?.journeys ?? [];
  if (journeys.length === 0) {
    return (
      <EmptyState
        title="Aucun parcours pour l'instant"
        description="Les téléchargements issus d'un suivi apparaîtront ici, étape par étape : récupéré → ingéré → scrapé → rangé."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {journeys.map((j) => (
        <li
          key={j.info_hash}
          className="flex flex-col gap-2 rounded-lg border border-border p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="min-w-0 flex-1 truncate text-sm font-medium">
              {journeyTitle(j)}
            </span>
            <Badge tone="neutral" className="shrink-0">
              {j.kind === "movie"
                ? "Film"
                : j.kind === "episode"
                  ? "Série"
                  : "—"}
            </Badge>
          </div>
          <ol className="flex flex-wrap gap-1.5">
            {STAGES.map((stage) => {
              const at = j[stage.key];
              const done = at != null;
              const runUid = j[stage.runKey];
              const badge = (
                <Badge tone={done ? "success" : "muted"}>
                  {stage.label}
                  {done ? ` · ${relativeTime(at)}` : ""}
                </Badge>
              );
              return (
                <li key={stage.key}>
                  {/* F3: a completed stage with a known run deep-links to that run. */}
                  {done && runUid != null ? (
                    <Link
                      to={`/pipeline?run=${encodeURIComponent(runUid)}`}
                      title="Voir le run qui a effectué cette étape"
                    >
                      {badge}
                    </Link>
                  ) : (
                    badge
                  )}
                </li>
              );
            })}
          </ol>
          <ResolutionChip j={j} />
          {j.dispatch_path != null && (
            <p
              className="truncate text-xs text-muted-foreground"
              title={j.dispatch_path}
            >
              → {j.dispatch_path}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
