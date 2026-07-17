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

import { useEffect } from "react";
import {
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { getPipelineStages, type StagesResponse } from "@/api/pipeline";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";

/** Flow Board query poll interval, in ms. */
const STAGES_REFETCH_MS = 5_000;

/**
 * Event ``type`` values that shift the board (run lifecycle + step boundaries)
 * and should trigger an immediate cache invalidation.
 */
const INVALIDATE_EVENT_TYPES = new Set([
  "PipelineStarted",
  "PipelineEnded",
  "PipelinePaused",
  "PipelineResumed",
  "StepStarted",
  "StepCompleted",
]);

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
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  const query = useQuery({
    queryKey: pipelineStagesKeys.stages,
    queryFn: getPipelineStages,
    refetchInterval: STAGES_REFETCH_MS,
  });

  // Invalidate on the newest board-shifting event so the board reacts before the
  // next poll tick. We look only at the latest event on each render — React's
  // batched updates collapse a replay burst into a single invalidation.
  useEffect(() => {
    if (events.length === 0) {
      return;
    }
    const newest = events[events.length - 1];
    if (newest !== undefined && INVALIDATE_EVENT_TYPES.has(newest.type)) {
      void queryClient.invalidateQueries({
        queryKey: pipelineStagesKeys.stages,
      });
    }
  }, [events, queryClient]);

  return query;
}
