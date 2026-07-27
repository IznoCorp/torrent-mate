/**
 * Staging read-model hook (webui-overhaul OBJ2A).
 *
 * Thin TanStack Query wrapper over ``GET /api/staging/media`` with a poll
 * interval and WebSocket-driven cache invalidation: a run-lifecycle or
 * step-boundary event mutates the staging tree (items get scraped, trailers
 * appear, media are dispatched out), so the query is invalidated immediately
 * rather than waiting for the next poll.
 *
 * - {@link stagingMediaKeys} — stable, params-scoped query keys.
 * - {@link useStagingMedia} — the hook wired into the staging library grid.
 */

import {
  useQuery,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";

import { PIPELINE_LIFECYCLE_EVENT_TYPES } from "@/api/events";
import {
  getStagingMedia,
  type StagingMediaParams,
  type StagingMediaResponse,
} from "@/api/staging";
import { useWsInvalidation } from "@/hooks/useWsInvalidation";

/** Staging read-model poll interval, in ms. */
const STAGING_REFETCH_MS = 8_000;

/** Stable React-Query keys for the staging read-model domain. */
export const stagingMediaKeys = {
  /** Root key for every staging-media query: ``['staging', 'media']``. */
  all: ["staging", "media"] as const,
  /** Params-scoped list key. */
  list: (params: StagingMediaParams) =>
    ["staging", "media", params] as const,
};

/**
 * Poll the staging read-model (``GET /api/staging/media``) for a given set of
 * filters and invalidate immediately when a run-lifecycle or step-boundary
 * event arrives on the WebSocket stream.
 *
 * Args:
 *   params: Pagination / sort / filter query parameters.
 *   queryOptions: Optional ``refetchInterval`` / ``staleTime`` overrides
 *       (merged over the default 8 s poll).
 *
 * Returns:
 *   The TanStack Query result for the {@link StagingMediaResponse}.
 */
export function useStagingMedia(
  params: StagingMediaParams = {},
  queryOptions?: Partial<
    Pick<UseQueryOptions<StagingMediaResponse>, "refetchInterval" | "staleTime">
  >,
): UseQueryResult<StagingMediaResponse> {
  const query = useQuery({
    queryKey: stagingMediaKeys.list(params),
    queryFn: () => getStagingMedia(params),
    refetchInterval: STAGING_REFETCH_MS,
    ...queryOptions,
  });

  // Invalidate every staging-media query (all filter variants) on any
  // tree-mutating event, so the grid reflects a fresh scan before the next poll
  // (the shared WS-event → invalidation map).
  useWsInvalidation([
    { types: PIPELINE_LIFECYCLE_EVENT_TYPES, keys: [stagingMediaKeys.all] },
  ]);

  return query;
}
