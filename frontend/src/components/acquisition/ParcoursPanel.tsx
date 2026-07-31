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

import { acqKeys, getJourneys, type JourneyItem } from "@/api/acquisition";
import { relativeTime } from "@/components/acquisition/meta";
import { EmptyState } from "@/components/ds/EmptyState";
import { Badge } from "@/components/ui/badge";

/** The four pipeline stages, in order, keyed by their provenance timestamp field. */
const STAGES = [
  { key: "grabbed_at", label: "Récupéré" },
  { key: "ingested_at", label: "Ingéré" },
  { key: "scraped_at", label: "Scrapé" },
  { key: "dispatched_at", label: "Rangé" },
] as const;

/** A human-readable label for a journey: the follow title, else an id, else the hash. */
function journeyTitle(j: JourneyItem): string {
  if (j.follow_title) return j.follow_title;
  const id = j.media_ref.tvdb_id ?? j.media_ref.tmdb_id;
  if (id != null) return `#${String(id)}`;
  return j.info_hash.slice(0, 8);
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
              return (
                <li key={stage.key}>
                  <Badge tone={done ? "success" : "muted"}>
                    {stage.label}
                    {done ? ` · ${relativeTime(at)}` : ""}
                  </Badge>
                </li>
              );
            })}
          </ol>
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
