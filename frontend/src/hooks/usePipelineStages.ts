/**
 * Pipeline Flow Board hook (webui-overhaul OBJ1).
 *
 * Thin TanStack Query wrapper over ``GET /api/pipeline/stages`` with a poll
 * interval and WebSocket-driven cache invalidation: when a live event signals a
 * pipeline state transition or a step boundary, the query is invalidated
 * immediately so the board reflects new counts without waiting for the next poll.
 *
 * - {@link pipelineStagesKeys} — stable query keys.
 * - {@link usePipelineStages} — the hook wired into the Flow Board.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { PIPELINE_LIFECYCLE_EVENT_TYPES } from "@/api/events";
import { getPipelineStages, type StagesResponse } from "@/api/pipeline";
import { useWsInvalidation } from "@/hooks/useWsInvalidation";

/** Flow Board query poll interval, in ms. */
const STAGES_REFETCH_MS = 5_000;

/** Stable React-Query keys for the Flow Board domain. */
export const pipelineStagesKeys = {
  /** Flow Board query key: ``['pipeline', 'stages']``. */
  stages: ["pipeline", "stages"] as const,
};

/**
 * Poll the Flow Board aggregation (``GET /api/pipeline/stages``) and invalidate
 * immediately when a run-lifecycle or step-boundary event arrives on the
 * WebSocket stream.
 *
 * Returns:
 *   The TanStack Query result for the {@link StagesResponse}.
 */
export function usePipelineStages(): UseQueryResult<StagesResponse> {
  const query = useQuery({
    queryKey: pipelineStagesKeys.stages,
    queryFn: getPipelineStages,
    refetchInterval: STAGES_REFETCH_MS,
  });

  // Invalidate on every board-shifting event so the board reacts before the
  // next poll tick (the shared WS-event → invalidation map).
  useWsInvalidation([
    { types: PIPELINE_LIFECYCLE_EVENT_TYPES, keys: [pipelineStagesKeys.stages] },
  ]);

  return query;
}
