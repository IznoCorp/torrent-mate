/**
 * CompletenessAccordion — the §5 per-season / per-episode completeness matrix
 * for one followed series ("ce qui est déjà sorti vs ce qui est en médiathèque").
 *
 * Lazy: the completeness query only fires when the accordion is opened (it hits
 * the provider catalog). An empty provider catalog renders an explicit message
 * (the Top Chef case), never a misleading all-missing grid.
 */

import { useState, type ReactElement } from "react";

import type { SeasonCompleteness } from "@/api/acquisition";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompleteness } from "@/hooks/useAcquisition";

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

/** One season's per-episode chips + aggregate readout. */
function SeasonRow({ season }: { season: SeasonCompleteness }): ReactElement {
  return (
    <div className="flex flex-col gap-1.5 border-t border-border py-2 first:border-t-0">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Saison {season.season}</span>
        {/* ``queued`` counts what is IN MOTION — « à récupérer » + « en cours
            d'acquisition ». The former « N en file » wording described a queue
            volume, which is precisely the number that let « rows queued » pass
            for « progress »; « N en cours » names the movement instead, and the
            tooltip spells out the two states it sums. */}
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
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {season.episodes.map((ep) => {
          // The reason is appended to the chip tooltip, in French, mapped —
          // the machine verdict never reaches the operator (NE-DOIT-PAS-4).
          const reason = searchOutcomeReason(ep.state, ep.last_search_outcome);
          return (
            <span
              key={ep.episode}
              title={`E${String(ep.episode)} — ${EPISODE_STATE_LABEL[ep.state]}${ep.title ? ` · ${ep.title}` : ""} — ${EPISODE_STATE_HINT[ep.state]}${reason != null ? ` (${reason})` : ""}`}
            >
              <Badge tone={EPISODE_STATE_TONE[ep.state]}>E{ep.episode}</Badge>
            </span>
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
                <SeasonRow key={s.season} season={s} />
              ))}
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
