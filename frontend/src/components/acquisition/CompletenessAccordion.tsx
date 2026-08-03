/**
 * CompletenessAccordion — the §5 per-season / per-episode completeness matrix
 * for one followed series ("ce qui est déjà sorti vs ce qui est en médiathèque").
 *
 * Lazy: the completeness query only fires when the accordion is opened (it hits
 * the provider catalog). An empty provider catalog renders an explicit message
 * (the Top Chef case), never a misleading all-missing grid.
 */

import { useState, type ReactElement } from "react";

import {
  grabSeason,
  type SeasonGrabResponse,
  type SeasonCompleteness,
  acqKeys,
} from "@/api/acquisition";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompleteness } from "@/hooks/useAcquisition";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { EpisodeDatePopover } from "./EpisodeDatePopover";
import { EpisodeStateLegende } from "./EpisodeStateLegende";
import {
  EPISODE_STATE_HINT,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
  searchOutcomeReason,
  waitingGroups,
} from "./meta";

/** Props for {@link CompletenessAccordion}. */
export interface CompletenessAccordionProps {
  readonly followedId: number;
  readonly title: string;
}

/** Props for a season-row sub-component. */
interface SeasonRowProps {
  readonly season: SeasonCompleteness;
  readonly followedId: number;
}

/** One season's per-episode chips + aggregate readout + grab button. */
function SeasonRow({ season, followedId }: SeasonRowProps): ReactElement {
  const queryClient = useQueryClient();
  // Nothing to grab when the season is fully owned OR has no aired episode
  // at all (total 0) — both disable the per-season grab button.
  const nothingToGrab = season.total === 0 || season.owned >= season.total;

  const grabSeasonMutation = useMutation({
    mutationFn: () => grabSeason(followedId, season.season),
    onSuccess: (result: SeasonGrabResponse) => {
      if (result.reused) {
        // The backend reused an existing LIVE season row (HTTP 200): nothing
        // new was enqueued, so an informational toast — never a success one
        // claiming a fresh grab (review F8).
        toast.info(`Saison ${String(season.season)} déjà en file`);
      } else {
        toast.success(
          `Saison ${String(season.season)} mise en file` +
            (result.absorbed_count > 0
              ? ` — ${String(result.absorbed_count)} épisode${result.absorbed_count > 1 ? "s" : ""} absorbé${result.absorbed_count > 1 ? "s" : ""}`
              : ""),
        );
      }
      void queryClient.invalidateQueries({
        queryKey: acqKeys.completeness(followedId),
      });
      void queryClient.invalidateQueries({ queryKey: acqKeys.wanted() });
      void queryClient.invalidateQueries({ queryKey: acqKeys.followed() });
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  return (
    <div className="flex flex-col gap-1.5 border-t border-border py-2 first:border-t-0">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Saison {season.season}</span>
        {/* ``queued`` counts what is IN MOTION — « à récupérer » + « en cours
            d'acquisition » + « absorbé (saison) ». The former « N en file »
            wording described a queue volume, which is precisely the number
            that let « rows queued » pass for « progress »; « N en cours »
            names the movement instead, and the tooltip spells out the states
            it sums. */}
        <span
          className="text-xs text-muted-foreground"
          title={
            season.queued > 0
              ? "En cours = à récupérer + en cours d'acquisition"
              : undefined
          }
        >
          {season.owned}/{season.total} en médiathèque
          {season.queued > 0 ? ` · ${String(season.queued)} en cours` : ""}
          {/* ``announced`` names the future episodes known-but-not-yet-aired
              (#10). They sit outside owned/total (which count aired only), so
              surfacing the count here makes the header honest — otherwise the
              chips show « Annoncé » but the header never says how many. */}
          {season.announced > 0
            ? ` · ${String(season.announced)} annoncé${season.announced > 1 ? "s" : ""}`
            : ""}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {season.episodes.map((ep) => {
          // The reason is appended to the chip tooltip, in French, mapped —
          // the machine verdict never reaches the operator (NE-DOIT-PAS-4).
          const reason = searchOutcomeReason(ep.state, ep.last_search_outcome);
          // Hover tooltip (desktop fallback) stays on the chip; the CLICK opens
          // the portalled date popover (#10) — usable on a phone that has no
          // hover, and not clipped by the mobile-shell guard.
          const hoverTitle = `E${String(ep.episode)} — ${EPISODE_STATE_LABEL[ep.state]}${ep.title ? ` · ${ep.title}` : ""} — ${EPISODE_STATE_HINT[ep.state]}${reason != null ? ` (${reason})` : ""}`;
          return (
            <EpisodeDatePopover
              key={ep.episode}
              state={ep.state}
              airDate={ep.air_date}
              triggerLabel={`E${String(ep.episode)} — ${EPISODE_STATE_LABEL[ep.state]}`}
              hoverTitle={hoverTitle}
            >
              <Badge tone={EPISODE_STATE_TONE[ep.state]}>E{ep.episode}</Badge>
            </EpisodeDatePopover>
          );
        })}
      </div>

      {/* Why those episodes are not acquired, spelled out under the chips: a
          phone has no hover, so a tooltip-only reason would be invisible where
          the operator actually reads this panel. */}
      {waitingGroups(season.episodes).map((group) => (
        <p key={group.reason} className="text-xs text-muted-foreground">
          E{group.episodes.map(String).join(", E")} — {group.reason}
        </p>
      ))}

      {/* Per-season grab: enqueue a season wanted (R4). Disabled when the
          season is fully owned (nothing to grab) or while the mutation is
          in flight. The backend is idempotent (returns the existing row on
          duplicate), so a double-click is harmless. */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={nothingToGrab || grabSeasonMutation.isPending}
          onClick={() => {
            grabSeasonMutation.mutate();
          }}
        >
          <Download className="mr-1 h-4 w-4" aria-hidden="true" />
          {grabSeasonMutation.isPending
            ? "Mise en file…"
            : "Récupérer la saison"}
        </Button>
      </div>
    </div>
  );
}

/**
 * CompletenessAccordion — lazy season/episode acquisition matrix.
 *
 * Args:
 *   followedId: The ``followed_series`` rowid.
 *   title: The series title (for the a11y label).
 *
 * Returns:
 *   The accordion element.
 */
export function CompletenessAccordion({
  followedId,
  title,
}: CompletenessAccordionProps): ReactElement {
  const [open, setOpen] = useState(false);
  const { data, isLoading, isError } = useCompleteness(followedId, open);

  // P0-B.1: caption the aired-catalog provenance honestly — the dated detect
  // cache ("Catalogue du JJ/MM/AAAA"). The former "live" provenance died with
  // the synchronous provider poll (acq-states phase 5): a web read never polls,
  // so the only two provenances left are the dated cache and « unknown ».
  const catalogCaption =
    data?.source === "cache" && data.catalog_refreshed_at != null
      ? `Catalogue du ${new Date(
          data.catalog_refreshed_at * 1000,
        ).toLocaleDateString("fr-FR")}`
      : null;

  return (
    <Accordion className="rounded-md border border-border bg-card px-3">
      <AccordionItem open={open} onOpenChange={setOpen}>
        <AccordionTrigger aria-label={`Détail par épisode de ${title}`}>
          Détail par épisode
        </AccordionTrigger>
        <AccordionContent>
          {isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : isError ? (
            <p className="py-2 text-sm text-muted-foreground">
              Complétude indisponible pour le moment.
            </p>
          ) : data?.provider_catalog_empty ? (
            <p className="py-2 text-sm text-muted-foreground">
              Aucun épisode au catalogue des providers (TVDB/TMDB) pour «{" "}
              {title} » — rien à comparer.
            </p>
          ) : data && data.seasons.length > 0 ? (
            <div className="flex flex-col">
              {data.seasons.map((s) => (
                <SeasonRow key={s.season} season={s} followedId={followedId} />
              ))}
              {/* Colour key under the matrix (#9) — derived from the vocabulary
                  maps, so it always matches the chips above. */}
              <EpisodeStateLegende />
            </div>
          ) : data?.source === "unknown" ? (
            /* No catalog has ever been written for this follow: we know
               NOTHING about its episodes. Saying « aucune saison diffusée »
               here would assert a fact we do not hold — the same honest
               ignorance the card reads as « Non vérifié ». */
            <p className="py-2 text-sm text-muted-foreground">
              Catalogue pas encore vérifié — l&apos;amorce ou la passe de
              détection le peuplera.
            </p>
          ) : (
            <p className="py-2 text-sm text-muted-foreground">
              Aucune saison diffusée.
            </p>
          )}
          {catalogCaption != null && (
            <p className="pt-1 text-xs text-muted-foreground">
              {catalogCaption}
            </p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
