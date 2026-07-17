/**
 * Pipeline status hook for TorrentMateUI (pipe-control §4.3).
 *
 * Thin TanStack Query wrapper over ``GET /api/pipeline/status`` with a 5 s poll
 * interval and WebSocket-driven cache invalidation: when a live event signals a
 * pipeline state transition (start, end, pause, resume, step start/complete), the
 * query is invalidated immediately so the UI reflects the new state without waiting
 * for the next poll tick.
 *
 * - {@link pipelineKeys} — stable query keys so mutations and cache resets target
 *   the same cache entry.
 * - {@link usePipelineStatus} — the hook wired into{@link PipelineControls},
 *   {@link PipelineStepper}, and {@link RunLogFeed}.
 */

import { useEffect } from "react";
import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { getPipelineStatus } from "@/api/pipeline";
import type { components } from "@/api/schema";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";

/** The status shape from ``GET /api/pipeline/status`` (OpenAPI-generated). */
type StatusResponse = components["schemas"]["StatusResponse"];

/** Pipeline-status query poll interval, in ms. */
const STATUS_REFETCH_MS = 5_000;

/**
 * Event ``type`` values that signal a pipeline state change and should trigger an
 * immediate cache invalidation.
 */
const INVALIDATE_EVENT_TYPES = new Set([
  "PipelineStarted",
  "PipelineEnded",
  "PipelinePaused",
  "PipelineResumed",
  "StepStarted",
  "StepCompleted",
]);

/**
 * Stable React-Query keys for the pipeline status domain.
 *
 * Exported so mutations ({@link PipelineControls}) invalidate the exact same cache
 * entry as the poll query.
 */
export const pipelineKeys = {
  /** Pipeline-status query key: ``['pipeline', 'status']``. */
  status: ["pipeline", "status"] as const,
};

/**
 * The flattened status shape consumed by the pipeline page components.
 *
 * Unpacks the fields the UI reads from every render so callers don't destructure
 * ``data`` themselves.
 */
export interface PipelineStatusSnapshot {
  readonly state: StatusResponse["state"];
  readonly run_uid: string | null;
  readonly step: string | null;
  readonly paused: boolean;
  readonly watcher_enabled: boolean;
  readonly pid: number | null;
}

/** Default snapshot used while the first query is in flight. */
const DEFAULT_SNAPSHOT: PipelineStatusSnapshot = {
  state: "idle",
  run_uid: null,
  step: null,
  paused: false,
  watcher_enabled: false,
  pid: null,
};

/**
 * Poll the pipeline status (``GET /api/pipeline/status``) every 5 s and
 * invalidate immediately when a state-changing live event arrives on the
 * WebSocket event stream.
 *
 * Returns:
 *   The query result enriched with a flattened {@link PipelineStatusSnapshot}
 *   under ``snapshot`` so callers read ``status.snapshot.state`` etc. without
 *   destructuring ``data`` + a default.
 */
export function usePipelineStatus(): UseQueryResult<StatusResponse> & {
  readonly snapshot: PipelineStatusSnapshot;
} {
  const queryClient = useQueryClient();
  const { events } = useEventStreamContext();

  const query = useQuery({
    queryKey: pipelineKeys.status,
    queryFn: getPipelineStatus,
    refetchInterval: STATUS_REFETCH_MS,
  });

  // Invalidate on every state-changing pipeline event so the UI reacts before
  // the next poll tick. We only look at the *newest* event on each render —
  // React's batched updates mean a replay burst triggers a single invalidation
  // rather than one per replayed event.
  useEffect(() => {
    if (events.length === 0) {
      return;
    }
    const newest = events[events.length - 1];
    if (newest !== undefined && INVALIDATE_EVENT_TYPES.has(newest.type)) {
      void queryClient.invalidateQueries({ queryKey: pipelineKeys.status });
    }
  }, [events, queryClient]);

  const data = query.data;
  const snapshot: PipelineStatusSnapshot =
    data !== undefined
      ? {
          state: data.state,
          run_uid: data.run_uid ?? null,
          step: data.step ?? null,
          paused: data.paused,
          watcher_enabled: data.watcher_enabled,
          pid: data.pid ?? null,
        }
      : DEFAULT_SNAPSHOT;

  return { ...query, snapshot };
}
