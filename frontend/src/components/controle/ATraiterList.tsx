/**
 * ATraiterList — the "À traiter" attention panel for the Contrôle dashboard.
 *
 * Lists every staged media currently ``position_state === "blocked"`` — the
 * unified cross-stage blocked inventory. Each row shows a mini poster, the
 * title, a French human-readable reason (``blocked_reason`` when present, else
 * the match-state label), and a « Résoudre → » link that opens the media sheet
 * (or the resolution deck for an ambiguous item).
 *
 * There is **no** ``awaiting_action`` server-side filter param (the original plan
 * added one, but it was deferred — see IMPLEMENTATION.md « Open items »). The
 * component fetches all staging items at a generous page size and filters
 * ``position_state === "blocked"`` client-side.
 */

import { AlertCircle } from "lucide-react";
import { type ReactElement } from "react";
import { Link } from "react-router-dom";

import type { StagingMediaItem, StagingMediaResponse } from "@/api/staging";
import { ErrorState } from "@/components/ds/ErrorState";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { matchBadge } from "@/components/staging/meta";
import { Skeleton } from "@/components/ui/skeleton";
import { useStagingMedia } from "@/hooks/useStagingMedia";

/** Page size for the staging fetch — generous enough for the typical blocked
 *  inventory (usually < 20 items) without pagination overhead. */
const BLOCKED_PAGE_SIZE = 100;

/**
 * Format a continuation-requested epoch timestamp as a relative-time label.
 *
 * Args:
 *   ts: The epoch seconds, or ``null``/``undefined``.
 *
 * Returns:
 *   A French relative-age string like ``"Reprise demandée il y a 3 min"``,
 *   or ``null`` when ``ts`` is absent.
 */
function continuationRequestedLabel(
  ts: number | null | undefined,
): string | null {
  if (ts == null) return null;
  const diff = Date.now() - ts * 1000;
  if (diff < 60_000) return "Reprise demandée à l'instant";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `Reprise demandée il y a ${String(mins)} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `Reprise demandée il y a ${String(hours)} h`;
  const days = Math.floor(hours / 24);
  return `Reprise demandée il y a ${String(days)} j`;
}

/** Poll interval in ms — same rationale as the nav badge (filesystem scan
 *  latency). */
const REFETCH_MS = 60_000;

/**
 * Build the resolve link for a blocked media item.
 *
 * Ambiguous items link to the resolution deck (``/medias?decision=<id>``);
 * matched and absent items link to the media detail sheet
 * (``/medias?media=<id>``).
 *
 * Args:
 *   item: The blocked staging media item.
 *
 * Returns:
 *   A router ``to`` value for the resolve link.
 */
function resolveLink(item: StagingMediaItem): string {
  if (item.match === "ambiguous" && item.decision_id != null) {
    return `/medias?decision=${String(item.decision_id)}`;
  }
  return `/medias?media=${item.id}`;
}

/**
 * Return the French blocked-reason label for an item.
 *
 * Prefers ``blocked_reason`` (the ``verify``-gate human-readable message) when
 * present; falls back to the match-state label from {@link matchBadge}.
 *
 * Args:
 *   item: The blocked staging media item.
 *
 * Returns:
 *   A French reason string.
 */
function reasonLabel(item: StagingMediaItem): string {
  if (item.blocked_reason != null && item.blocked_reason !== "") {
    return item.blocked_reason;
  }
  return matchBadge(item.match).label;
}

/**
 * Extract blocked items from a staging response, filtering client-side.
 *
 * Args:
 *   data: The raw staging response, or ``undefined``.
 *
 * Returns:
 *   The subset of items where ``position_state === "blocked"``.
 */
function blockedItems(
  data: StagingMediaResponse | undefined,
): StagingMediaItem[] {
  if (data == null) return [];
  if (!Array.isArray(data.items)) return [];
  return data.items.filter((i) => i.position_state === "blocked");
}

/**
 * ATraiterList — the unified blocked-items inventory for the Contrôle dashboard.
 *
 * Heading « À traiter » with the live count, each row a compact blocked-media
 * card with the reason and a resolve link.  Empty state → one calm row « Rien à
 * traiter ».  Polls every 60 s (same rationale as the nav badge).
 *
 * Returns:
 *   The à-traiter list element.
 */
export function ATraiterList(): ReactElement {
  const query = useStagingMedia(
    { page_size: BLOCKED_PAGE_SIZE },
    { refetchInterval: REFETCH_MS },
  );

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <Skeleton className="h-6 w-32" />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={`at-sk-${String(i)}`} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        title="Impossible de charger les éléments à traiter."
        {...(query.error instanceof Error
          ? { message: query.error.message }
          : {})}
        onRetry={() => {
          void query.refetch();
        }}
      />
    );
  }

  const items = blockedItems(query.data);

  return (
    <div className="flex flex-col gap-2">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <AlertCircle className="size-4 text-warning" aria-hidden="true" />À
        traiter
        {items.length > 0 && (
          <span className="inline-flex size-5 items-center justify-center rounded-full bg-warning/15 text-[length:var(--text-2xs)] font-bold text-warning">
            {items.length}
          </span>
        )}
      </h2>

      {items.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">Rien à traiter</p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-center gap-3 rounded-md px-2 py-1.5 hover:bg-muted/50"
            >
              {/* 32 px mini poster */}
              <MediaPoster
                title={item.title}
                src={item.poster_url ?? null}
                {...(item.media_kind === "movie"
                  ? ({ kind: "movie" } as const)
                  : item.media_kind === "tvshow"
                    ? ({ kind: "tv" } as const)
                    : {})}
                className="w-8 shrink-0 rounded-sm"
              />

              {/* Title + reason */}
              <div className="min-w-0 flex-1">
                <span className="truncate text-sm">{item.title}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {reasonLabel(item)}
                </span>
                {/* A1: durable deferral trace chip */}
                {continuationRequestedLabel(item.continuation_requested_at) !==
                  null && (
                  <span className="ml-2 inline-flex items-center rounded border border-border px-1.5 py-0.5 text-2xs font-medium text-muted-foreground">
                    {continuationRequestedLabel(item.continuation_requested_at)}
                  </span>
                )}
              </div>

              {/* Resolve link */}
              <Link
                to={resolveLink(item)}
                className="shrink-0 text-xs font-medium text-primary hover:underline"
              >
                Résoudre →
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
