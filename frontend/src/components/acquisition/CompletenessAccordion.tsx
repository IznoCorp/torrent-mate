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

import { EPISODE_STATE_LABEL, EPISODE_STATE_TONE } from "./meta";

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
        <span className="text-xs text-muted-foreground">
          {season.owned}/{season.total} en médiathèque
          {season.queued > 0 ? ` · ${String(season.queued)} en file` : ""}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {season.episodes.map((ep) => (
          <span
            key={ep.episode}
            title={`E${String(ep.episode)} — ${EPISODE_STATE_LABEL[ep.state] ?? ep.state}${ep.title ? ` · ${ep.title}` : ""}`}
          >
            <Badge tone={EPISODE_STATE_TONE[ep.state] ?? "neutral"}>
              E{ep.episode}
            </Badge>
          </span>
        ))}
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
          ) : (
            <p className="py-2 text-sm text-muted-foreground">
              Aucune saison diffusée.
            </p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
