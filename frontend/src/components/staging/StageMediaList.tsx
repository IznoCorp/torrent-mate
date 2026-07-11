/**
 * StageMediaList — per-media drill-down for a Flow Board stage (OBJ1 tail).
 *
 * Given a stage key, lists the staged media currently at / awaiting that stage
 * (``GET /api/staging/media?stage=…``) as an accordion: each row expands to
 * reveal that media's full pipeline {@link MediaTimeline}, provider ids, and —
 * for an ambiguous match — a jump to the resolution deck. Mounted only while
 * the stage drawer is open, so the query runs on demand rather than in the
 * background.
 */

import type { ReactElement } from "react";

import type { StagingMediaParams } from "@/api/client";
import { StatusBadge } from "@/components/ds/StatusBadge";
import { MediaTimeline } from "@/components/staging/MediaTimeline";
import { matchBadge } from "@/components/staging/meta";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useStagingMedia } from "@/hooks/useStagingMedia";

/** The nine timeline stage keys accepted by the ``stage`` query param. */
export type StageKey = NonNullable<StagingMediaParams["stage"]>;

/** Props for {@link StageMediaList}. */
export interface StageMediaListProps {
  /** The stage key to list media for. */
  readonly stageKey: StageKey;
  /** Invoked to open the resolution deck for an ambiguous media. */
  readonly onOpenResolution?: () => void;
}

/**
 * StageMediaList — the per-media accordion for one Flow Board stage.
 *
 * Args:
 *   stageKey: The stage to list media at/awaiting.
 *   onOpenResolution: Optional handler to open the resolution deck.
 *
 * Returns:
 *   The stage media list element.
 */
export function StageMediaList({
  stageKey,
  onOpenResolution,
}: StageMediaListProps): ReactElement {
  const query = useStagingMedia({ stage: stageKey, page_size: 50 });

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={`stage-media-sk-${String(i)}`} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <p className="text-sm text-danger" role="alert">
        Impossible de charger les médias de cette étape.
      </p>
    );
  }

  const items = query.data?.items ?? [];
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Aucun média à cette étape.</p>
    );
  }

  return (
    <Accordion className="flex flex-col gap-1">
      {items.map((item) => {
        const badge = matchBadge(item.match);
        return (
          <AccordionItem key={item.id} className="rounded-md border border-border">
            <AccordionTrigger className="px-3 py-2">
              <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                <span className="truncate text-sm">
                  {item.title}
                  {item.year != null && (
                    <span className="ml-1 font-mono text-xs text-muted-foreground">
                      {item.year}
                    </span>
                  )}
                </span>
                <StatusBadge tone={badge.tone} label={badge.label} />
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-3 pb-3">
              <MediaTimeline stages={item.stages} />
              {item.match === "ambiguous" && onOpenResolution !== undefined && (
                <Button
                  type="button"
                  size="sm"
                  className="mt-2"
                  onClick={onOpenResolution}
                >
                  Résoudre le matching
                </Button>
              )}
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
