/**
 * Parcours tab (provenance F1) — each acquisition's journey through the pipeline.
 *
 * Reads the F0 provenance registry via ``GET /api/acquisition/journeys`` and shows,
 * per acquisition, a compact stage stepper: Récupéré → Ingéré → Scrapé → Rangé,
 * lit up to the stage actually reached (from the per-stage timestamps). Makes the
 * pipeline legible (product-intent §pipeline lisible). Read-only; mobile-first.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy } from "lucide-react";
import { useCallback, useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  acqKeys,
  getJourneys,
  requeueJourney,
  rescrapeJourney,
  type JourneyItem,
} from "@/api/acquisition";
import { relativeTime } from "@/components/acquisition/meta";
import { EmptyState } from "@/components/ds/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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
    // `neutral`, not `muted`: « Résolu » / « Écarté » are SETTLED verdicts, and
    // the dashed no-fill `muted` chip now means « je ne sais pas » (it lost its
    // tint when « Non vérifié » moved onto it). `neutral` is exactly the settled
    // low-salience grey — it was freed when « En attente de torrent » took its
    // own teal tone.
    <Badge tone="neutral" className="self-start">
      {state === "resolved" ? "Résolu" : "Écarté"}
    </Badge>
  );
}

/**
 * Per-journey targeted actions (spine-actions F4): a « Bloqué » badge for a stuck item,
 * plus « Re-scraper » / « Requeue » buttons that trigger the spine-driven CLI actions.
 *
 * Shown only for an IN-FLIGHT item (not yet dispatched) — a dispatched item's staging
 * folder is gone, so a re-scrape would no-op. On success the journeys query is
 * invalidated so the card reflects the new state on the next poll.
 *
 * Returns:
 *   The action row, or ``null`` for a dispatched/terminal item.
 */
function JourneyActions({ j }: { j: JourneyItem }): ReactElement | null {
  const qc = useQueryClient();
  const onSuccess = (label: string) => (): void => {
    void qc.invalidateQueries({ queryKey: acqKeys.all });
    toast.info(`${label} lancé.`); // 202 = launched (tracked to its numeric result), not done
  };
  // Never fail silently (product-intent §pipeline-lisible / « rien silencieux »): a 409
  // (already in flight) is an information, a 404/500 an error.
  const onError = (err: unknown): void => {
    if (err instanceof ApiError) {
      if (err.status === 409) {
        toast.info("Une action est déjà en cours pour cet item.");
      } else if (err.status === 404) {
        toast.error("Acquisition introuvable.");
      } else {
        toast.error(err.detail);
      }
    } else {
      toast.error("Erreur lors du lancement de l'action.");
    }
  };
  const rescrape = useMutation({
    mutationFn: () => rescrapeJourney(j.info_hash),
    onSuccess: onSuccess("Re-scrape"),
    onError,
  });
  const requeue = useMutation({
    mutationFn: () => requeueJourney(j.info_hash),
    onSuccess: onSuccess("Requeue"),
    onError,
  });
  const inFlight = j.dispatched_at == null;
  if (!inFlight) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {j.stuck ? (
        <Badge tone="warning" dot>
          Bloqué
        </Badge>
      ) : null}
      <Button
        variant="outline"
        size="sm"
        disabled={rescrape.isPending}
        onClick={() => {
          rescrape.mutate();
        }}
      >
        Re-scraper
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={requeue.isPending}
        onClick={() => {
          requeue.mutate();
        }}
      >
        Requeue
      </Button>
    </div>
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

  // ACQUISITION-5 (ticket 250): the truncated hash gets a copy affordance —
  // check icon for ~1.5 s + a toast naming the outcome (same recipe as the
  // Obligations table).
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const handleCopyHash = useCallback((hash: string): void => {
    void navigator.clipboard
      .writeText(hash)
      .then(() => {
        setCopiedHash(hash);
        toast.success("Hash copié.");
        setTimeout(() => {
          setCopiedHash((prev) => (prev === hash ? null : prev));
        }, 1500);
      })
      .catch(() => {
        toast.error("Copie du hash impossible");
      });
  }, []);

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
            {/* X5 — id/hash fallbacks are machine tokens: mono + full hash in
                title (the resolved follow title stays proportional). */}
            <span
              className={
                j.follow_title
                  ? "min-w-0 flex-1 truncate text-sm font-medium"
                  : "min-w-0 flex-1 truncate font-mono text-sm font-medium"
              }
              // Truthiness (not ??) on purpose: an empty follow_title falls
              // back to the hash, mirroring journeyTitle().
              // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing
              title={j.follow_title || j.info_hash}
            >
              {journeyTitle(j)}
            </span>
            {/* ACQUISITION-5: copy the full info_hash (the visible title may
                be a truncated fallback of it). X4: 44px touch minimum below
                md, compact on desktop — the icons stay size-3, only the hit
                target grows. */}
            <Button
              variant="ghost"
              size="icon"
              className="min-h-11 min-w-11 shrink-0 md:min-h-8 md:min-w-8"
              aria-label={`Copier le hash ${j.info_hash}`}
              onClick={() => {
                handleCopyHash(j.info_hash);
              }}
            >
              {copiedHash === j.info_hash ? (
                <Check className="size-3 text-success" />
              ) : (
                <Copy className="size-3" />
              )}
            </Button>
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
          <JourneyActions j={j} />
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
