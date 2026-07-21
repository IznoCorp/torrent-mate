/**
 * Typed fetch wrappers for the pipeline API (control + status + run history).
 *
 * Every helper binds through {@link apiFetch} so path, method, request body and
 * query params are all checked against the OpenAPI-generated ``schema.d.ts`` —
 * no ``any`` at any call site. Mutating endpoints carry the ``X-Requested-With``
 * header (``XRW_HEADERS`` from client.ts); reads are header-free.
 */

import type {
  QueryParamsOf,
  RequestBodyOf,
  ResponseBodyOf,
  SuccessBody,
} from "./_schema-helpers";
import type { paths } from "./schema";
import { XRW_HEADERS, apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Stable TanStack Query keys
// ---------------------------------------------------------------------------

/**
 * Stable React-Query keys for the pipeline domain (status + run history).
 *
 * The ONE home for pipeline query keys (FRONTEND-DATA-05): the run-history keys
 * were hand-assembled as ``["pipeline", "history", …]`` literals in 8+ places
 * with only string-coincidence coherence. Every site now derives its key from
 * this factory so a shape change is made once and mutations invalidate the
 * exact same cache entries the queries read.
 *
 * ``history`` is the shared prefix: invalidating it partial-matches every
 * detail / list / last-run key beneath it (the existing invalidation contract).
 * The Flow-Board ``stages`` key keeps its own factory in ``usePipelineStages``.
 */
export const pipelineKeys = {
  /** Pipeline-status query key: ``['pipeline', 'status']``. */
  status: ["pipeline", "status"] as const,

  /** Run-history prefix key: ``['pipeline', 'history']`` (invalidation root). */
  history: ["pipeline", "history"] as const,

  /** Run-history list key: ``['pipeline', 'history', params]``. */
  historyList: (params: HistoryParams) =>
    ["pipeline", "history", params] as const,

  /** Single-run detail key: ``['pipeline', 'history', runUid]``. */
  historyDetail: (runUid: string | null) =>
    ["pipeline", "history", runUid] as const,

  /** Last-run summary key: ``['pipeline', 'history', 'last', refetchKey]``. */
  historyLast: (refetchKey: string) =>
    ["pipeline", "history", "last", refetchKey] as const,

  /** Last-run detail key: ``['pipeline', 'history', 'last-detail', runUid]``. */
  historyLastDetail: (runUid: string | null) =>
    ["pipeline", "history", "last-detail", runUid] as const,
};

// ---------------------------------------------------------------------------
// Pipeline control endpoints
// ---------------------------------------------------------------------------

/** Launch a pipeline run: POST /api/pipeline/run.  Requires ``X-Requested-With``. */
export async function runPipeline(
  body: RequestBodyOf<paths["/api/pipeline/run"]["post"]>,
): Promise<ResponseBodyOf<paths["/api/pipeline/run"]["post"]>> {
  return apiFetch("/api/pipeline/run", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

/** Pause the running pipeline: POST /api/pipeline/pause.  Requires ``X-Requested-With``. */
export function pausePipeline(): Promise<
  SuccessBody<paths["/api/pipeline/pause"]["post"]["responses"]>
> {
  return apiFetch("/api/pipeline/pause", {
    method: "post",
    headers: XRW_HEADERS,
  });
}

/** Resume a paused pipeline: POST /api/pipeline/resume.  Requires ``X-Requested-With``. */
export function resumePipeline(): Promise<
  SuccessBody<paths["/api/pipeline/resume"]["post"]["responses"]>
> {
  return apiFetch("/api/pipeline/resume", {
    method: "post",
    headers: XRW_HEADERS,
  });
}

/** Kill the running pipeline: POST /api/pipeline/kill.  Requires ``X-Requested-With``. */
export function killPipeline(): Promise<
  SuccessBody<paths["/api/pipeline/kill"]["post"]["responses"]>
> {
  return apiFetch("/api/pipeline/kill", {
    method: "post",
    headers: XRW_HEADERS,
  });
}

/** Enable or pause the directory watcher: POST /api/pipeline/watcher.  Requires ``X-Requested-With``. */
export function setWatcher(
  body: RequestBodyOf<paths["/api/pipeline/watcher"]["post"]>,
): Promise<SuccessBody<paths["/api/pipeline/watcher"]["post"]["responses"]>> {
  return apiFetch("/api/pipeline/watcher", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

/** Get the live pipeline status: GET /api/pipeline/status.  Session-guarded read — no ``X-Requested-With`` header. */
export function getPipelineStatus(): Promise<
  SuccessBody<paths["/api/pipeline/status"]["get"]["responses"]>
> {
  return apiFetch("/api/pipeline/status", { method: "get" });
}

/** Response type for ``GET /api/pipeline/stages`` (OBJ1 Flow Board). */
export type StagesResponse = SuccessBody<
  paths["/api/pipeline/stages"]["get"]["responses"]
>;

/**
 * Fetch the aggregated Flow Board state: GET /api/pipeline/stages.
 *
 * Session-guarded read — no ``X-Requested-With`` header (R15). Returns the
 * nine pipeline stages with live counts + derived ring states.
 *
 * Returns:
 *   A {@link StagesResponse} with the nine stages in flow order.
 */
export function getPipelineStages(): Promise<StagesResponse> {
  return apiFetch("/api/pipeline/stages", { method: "get" });
}

// ---------------------------------------------------------------------------
// Pipeline history endpoints (S2 Phase 5)
// ---------------------------------------------------------------------------

/** Response type for ``GET /api/pipeline/history``. */
export type HistoryResponse = SuccessBody<
  paths["/api/pipeline/history"]["get"]["responses"]
>;

/** Response type for ``GET /api/pipeline/history/{run_uid}``. */
export type RunDetail = SuccessBody<
  paths["/api/pipeline/history/{run_uid}"]["get"]["responses"]
>;

/**
 * Query parameters accepted by ``GET /api/pipeline/history`` — derived from
 * the generated schema so a backend parameter change breaks compilation here
 * (R15), not at runtime.
 */
export type HistoryParams = QueryParamsOf<
  paths["/api/pipeline/history"]["get"]
>;

/**
 * Fetch a single page of pipeline run history.
 *
 * Sends ``GET /api/pipeline/history`` with optional query params through the
 * typed {@link apiFetch} (R15). Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional pagination/sort query parameters.
 *
 * Returns:
 *   A {@link HistoryResponse} with the page of {@link RunSummary} items.
 */
export function getPipelineHistory(
  params: HistoryParams = {},
): Promise<HistoryResponse> {
  return apiFetch("/api/pipeline/history", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch full detail for a single pipeline run.
 *
 * Sends ``GET /api/pipeline/history/{run_uid}`` through the typed
 * {@link apiFetch} (R15 — ``run_uid`` is a schema-typed path param).
 * Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   runUid: The unique run identifier (uuid4 hex).
 *
 * Returns:
 *   A {@link RunDetail} with step timings parsed from ``steps_json``.
 *
 * Raises:
 *   ApiError: 404 if no run with the given ``runUid`` exists.
 */
export function getPipelineRunDetail(runUid: string): Promise<RunDetail> {
  return apiFetch("/api/pipeline/history/{run_uid}", {
    method: "get",
    params: { path: { run_uid: runUid } },
  });
}
