/**
 * Typed fetch wrappers for the maintenance API (S3 — maint-dash).
 *
 * Every helper binds through {@link apiFetch} so path, method, request body and
 * path params are all checked against the OpenAPI-generated ``schema.d.ts`` —
 * no ``any`` at any call site. The mutating action-run endpoint carries the
 * ``X-Requested-With`` header (``XRW_HEADERS`` from client.ts).
 */

import type { ResponseBodyOf, SuccessBody } from "./_schema-helpers";
import type { components, paths } from "./schema";
import { XRW_HEADERS, apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Response / component types
// ---------------------------------------------------------------------------

/** Response type for ``GET /api/maintenance/disks``. */
export type DisksResponse = SuccessBody<
  paths["/api/maintenance/disks"]["get"]["responses"]
>;

/** Response type for ``GET /api/maintenance/locks``. */
export type LocksResponse = SuccessBody<
  paths["/api/maintenance/locks"]["get"]["responses"]
>;

/** Response type for ``GET /api/maintenance/index-health``. */
export type IndexHealthResponse = SuccessBody<
  paths["/api/maintenance/index-health"]["get"]["responses"]
>;

/** Response type for ``GET /api/maintenance/destructive-log``. */
export type DestructiveLogResponse = SuccessBody<
  paths["/api/maintenance/destructive-log"]["get"]["responses"]
>;

/** Response type for ``GET /api/maintenance/actions``. */
export type ActionsResponse = SuccessBody<
  paths["/api/maintenance/actions"]["get"]["responses"]
>;

/** Response type for ``GET /api/maintenance/schedulers``. */
export type SchedulersResponse = SuccessBody<
  paths["/api/maintenance/schedulers"]["get"]["responses"]
>;

/** A single scheduled-agent entry (watcher or cron) from the overview. */
export type SchedulerItem = components["schemas"]["SchedulerItem"];

/** A single maintenance action entry from the registry. */
export type MaintenanceAction = components["schemas"]["MaintenanceAction"];

/** A single targeting option for a maintenance action. */
export type ActionOption = components["schemas"]["ActionOption"];

/** Request body for ``POST /api/maintenance/actions/{action_id}/run``. */
export type ActionRunRequest = components["schemas"]["ActionRunRequest"];

// ---------------------------------------------------------------------------
// Read endpoints
// ---------------------------------------------------------------------------

/** Fetch disk mount status and capacity: GET /api/maintenance/disks. */
export function getDisks(): Promise<DisksResponse> {
  return apiFetch("/api/maintenance/disks", { method: "get" });
}

/** Fetch pipeline lock state, sentinels, and tmp-orphans: GET /api/maintenance/locks. */
export function getLocks(): Promise<LocksResponse> {
  return apiFetch("/api/maintenance/locks", { method: "get" });
}

/** Fetch aggregate index health snapshot: GET /api/maintenance/index-health. */
export function getIndexHealth(): Promise<IndexHealthResponse> {
  return apiFetch("/api/maintenance/index-health", { method: "get" });
}

/** Fetch the static maintenance action registry: GET /api/maintenance/actions. */
export function getActions(): Promise<ActionsResponse> {
  return apiFetch("/api/maintenance/actions", { method: "get" });
}

/** Fetch the scheduler overview (watcher + crons): GET /api/maintenance/schedulers. */
export function getSchedulers(): Promise<SchedulersResponse> {
  return apiFetch("/api/maintenance/schedulers", { method: "get" });
}

/** Fetch the append-only destructive-op journal: GET /api/maintenance/destructive-log. */
export function getDestructiveLog(): Promise<DestructiveLogResponse> {
  return apiFetch("/api/maintenance/destructive-log", { method: "get" });
}

// ---------------------------------------------------------------------------
// Mutating endpoint
// ---------------------------------------------------------------------------

/**
 * Launch a maintenance action as a detached subprocess.
 *
 * Sends ``POST /api/maintenance/actions/{action_id}/run`` with the
 * ``X-Requested-With`` header (mirroring the mutating pipeline endpoints)
 * through the typed {@link apiFetch} (R15 — ``action_id`` is a schema-typed
 * path param).
 *
 * Args:
 *   actionId: The kebab-case action id (e.g. ``"library-index"``).
 *   body: The request payload with ``options`` and ``dry_run``.
 *
 * Returns:
 *   The ``202`` body narrowed to ``{run_uid}`` (the schema models it as a bare
 *   dict).
 *
 * Raises:
 *   ApiError: 404 (unknown action), 409 (lock held / already running),
 *     422 (invalid options), or 428 (destructive action without a recent
 *     successful dry-run). The ``detail`` carries the backend message.
 */
export function runMaintenanceAction(
  actionId: string,
  body: ActionRunRequest,
): Promise<
  ResponseBodyOf<paths["/api/maintenance/actions/{action_id}/run"]["post"]>
> {
  return apiFetch("/api/maintenance/actions/{action_id}/run", {
    method: "post",
    body,
    headers: XRW_HEADERS,
    params: { path: { action_id: actionId } },
  });
}
