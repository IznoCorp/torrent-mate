/**
 * useLastPipelineRun — the most recent pipeline run's interpreted summary.
 *
 * Powers the idle Pipeline view (webui-ux Phase 2.4): when no run is active the
 * page shows the last run's interpreted summary (reconstructed from the
 * persisted per-step counts, Phase 2.2) rather than a blank feed. Fetches the
 * newest ``kind=pipeline`` run via ``GET /api/pipeline/history?limit=1`` then
 * its detail via ``GET /api/pipeline/history/{run_uid}``, and folds the steps
 * into interpreted lines with {@link summariseSteps}.
 *
 * The detail query only runs once a run_uid is known (``enabled`` gate). The
 * summary is re-fetched whenever the caller's ``refetchKey`` changes (e.g. the
 * live run_uid changes) so a freshly-finished run supersedes the previous one.
 */

import { useQuery } from "@tanstack/react-query";

import {
  getPipelineHistory,
  getPipelineRunDetail,
  pipelineKeys,
} from "@/api/pipeline";
import type { InterpretedLine } from "@/components/pipeline/interpretRun";
import type { StepReasonsEntry } from "@/components/pipeline/StalledPanel";
import { summariseSteps } from "@/components/pipeline/summariseSteps";

/** Result of {@link useLastPipelineRun}. */
export interface LastPipelineRun {
  /** The last run's unique id, or ``null`` when there is no history yet. */
  readonly runUid: string | null;
  /** The last run's interpreted summary lines (empty when none / loading). */
  readonly lines: InterpretedLine[];
  /**
   * Per-step skip/defer/error reasons, derived from the same filter+map used by
   * {@link RunDetail} — fed directly to {@link StalledPanel}.
   */
  readonly stepReasons: StepReasonsEntry[];
  /** Whether either underlying query is still loading. */
  readonly isLoading: boolean;
  /** Whether the history or detail query failed (API unreachable). */
  readonly isError: boolean;
  /** The trigger that started the run, or ``null`` when no history yet. */
  readonly trigger: string | null;
  /** ISO 8601 UTC start timestamp, or ``null`` when no history yet. */
  readonly startedAt: string | null;
  /** ISO 8601 UTC end timestamp, or ``null`` when still running / no history. */
  readonly endedAt: string | null;
  /** Final outcome, or ``null`` when still running / no history. */
  readonly outcome: string | null;
  /** Total items processed across all steps. */
  readonly totalProcessed: number;
  /** Total items skipped across all steps. */
  readonly totalSkipped: number;
}

/**
 * Fetch + interpret the most recent pipeline run.
 *
 * Args:
 *   refetchKey: An opaque value folded into the query keys; changing it forces
 *     a re-fetch so a newer run replaces the shown summary. Defaults to a
 *     constant (no forced refetch).
 *
 * Returns:
 *   The last run's id + interpreted summary lines + loading flag.
 */
export function useLastPipelineRun(refetchKey = "idle"): LastPipelineRun {
  const historyQuery = useQuery({
    queryKey: pipelineKeys.historyLast(refetchKey),
    queryFn: () => getPipelineHistory({ limit: 1, kind: "pipeline", sort: "-started_at" }),
  });

  const lastSummary = historyQuery.data?.runs[0] ?? null;
  const runUid = lastSummary?.run_uid ?? null;

  const detailQuery = useQuery({
    queryKey: pipelineKeys.historyLastDetail(runUid),
    // ``enabled`` gates execution to a non-null run_uid; the queryFn narrows it
    // once more so neither a non-null assertion nor a cast is needed (eslint
    // bans both).
    queryFn: () => {
      if (runUid === null) {
        return Promise.reject(new Error("no run to fetch"));
      }
      return getPipelineRunDetail(runUid);
    },
    enabled: runUid !== null,
  });

  const lines =
    detailQuery.data !== undefined ? summariseSteps(detailQuery.data.steps) : [];

  // §8 — per-step skip/defer/error reasons, same derivation as RunDetail (the
  // 'queue' pseudo-step is excluded — it has its own banner in the run detail).
  const stepReasons: StepReasonsEntry[] =
    detailQuery.data !== undefined
      ? detailQuery.data.steps
          .filter((s) => s.name !== "queue" && (s.reasons?.length ?? 0) > 0)
          .map((s) => ({ step: s.name, reasons: s.reasons ?? [] }))
      : [];

  // Aggregate counts across all steps for the LastRunDigest summary.
  let totalProcessed = 0;
  let totalSkipped = 0;
  if (detailQuery.data !== undefined) {
    for (const step of detailQuery.data.steps) {
      totalProcessed += step.success_count ?? 0;
      totalSkipped += step.skip_count ?? 0;
    }
  }

  return {
    runUid,
    lines,
    stepReasons,
    isLoading: historyQuery.isLoading || (runUid !== null && detailQuery.isLoading),
    isError: historyQuery.isError || (runUid !== null && detailQuery.isError),
    trigger: lastSummary?.trigger ?? null,
    startedAt: lastSummary?.started_at ?? null,
    endedAt: lastSummary?.ended_at ?? null,
    outcome: lastSummary?.outcome ?? null,
    totalProcessed,
    totalSkipped,
  };
}
