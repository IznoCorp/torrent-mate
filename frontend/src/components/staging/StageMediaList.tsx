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

import { useState, type ReactElement } from "react";

import type { StagingMediaParams } from "@/api/client";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
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

/** The eight stage keys accepted by the ``stage`` query param. */
export type StageKey = NonNullable<StagingMediaParams["stage"]>;

/** Props for {@link StageMediaList}. */
export interface StageMediaListProps {
  /** The stage key to list media for. */
  readonly stageKey: StageKey;
  /** Invoked to open the resolution deck for an ambiguous media. */
  readonly onOpenResolution?: () => void;
  /** Invoked to open a media's detail (unblock actions live there). */
  readonly onOpenMedia?: (mediaId: string) => void;
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
  onOpenMedia,
}: StageMediaListProps): ReactElement {
  const [limit, setLimit] = useState(50);
  const query = useStagingMedia({ stage: stageKey, page_size: limit });

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton
            key={`stage-media-sk-${String(i)}`}
            className="h-10 w-full"
          />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        title="Impossible de charger les médias de cette étape."
        {...(query.error instanceof Error
          ? { message: query.error.message }
          : {})}
        onRetry={() => {
          void query.refetch();
        }}
      />
    );
  }

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? items.length;
  if (items.length === 0) {
    return <EmptyState compact title="Aucun média à cette étape." />;
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-[length:var(--text-2xs)] uppercase tracking-wide text-muted-foreground">
        {total} média{total > 1 ? "s" : ""}
      </span>
      <Accordion className="flex flex-col gap-1">
        {items.map((item) => {
          const badge = matchBadge(item.match);
          return (
            <AccordionItem
              key={item.id}
              className="rounded-md border border-border"
            >
              <AccordionTrigger className="px-3 py-2">
                <div className="flex w-full min-w-0 items-center justify-between gap-2">
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {item.title}
                    {item.year != null && (
                      <span className="ml-1 font-mono text-xs text-muted-foreground">
                        {item.year}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0">
                    <StatusBadge tone={badge.tone} label={badge.label} />
                  </span>
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-3 pb-3">
                {/* A blocked media says WHY, in French, right where it is
                    listed (A.5) — with the unblock action when one exists (A.4). */}
                {item.blocked_reason != null && (
                  <p className="mb-2 text-sm text-danger">
                    {item.blocked_reason}
                  </p>
                )}
                <MediaTimeline stages={item.stages} />
                {item.match === "ambiguous" &&
                  onOpenResolution !== undefined && (
                    <Button
                      type="button"
                      size="sm"
                      className="mt-2"
                      onClick={onOpenResolution}
                    >
                      Résoudre l'identification
                    </Button>
                  )}
                {item.match !== "ambiguous" &&
                  item.position_state === "blocked" &&
                  onOpenMedia !== undefined && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      onClick={() => {
                        onOpenMedia(item.id);
                      }}
                    >
                      Ouvrir la fiche média
                    </Button>
                  )}
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>
      {items.length < total && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          onClick={() => {
            setLimit((n) => n + 50);
          }}
        >
          Voir plus
        </Button>
      )}
    </div>
  );
}
