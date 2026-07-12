/**
 * Typed fetch-based API client for TorrentMateUI.
 *
 * Built on the OpenAPI-generated ``paths`` types from ``./schema``.
 * Every request sends ``credentials: "include"`` so the JWT session
 * cookie is attached automatically.  401 handling is deferred to the
 * app layer (phase 5) — this module just throws on non-OK responses.
 */

import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import type { components, paths } from "./schema";

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

/** Structured error thrown by :func:`apiFetch` on a non-OK HTTP response. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  /** True for the staging read-only write guard (403 `read-only`). */
  readonly isReadOnly: boolean;

  constructor(status: number, detail: string) {
    const isReadOnly = status === 403 && detail.toLowerCase().includes("read-only");
    // The staging read-only guard is a *consultation* state, not an error the
    // operator did wrong — surface a clean French notice instead of the raw
    // "403: read-only" so a write click on the read-only staging instance reads
    // as "not available here", never a broken action.
    super(
      isReadOnly
        ? "Instance de consultation (staging) — écriture désactivée."
        : `${String(status)}: ${detail}`,
    );
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.isReadOnly = isReadOnly;
  }
}

// ---------------------------------------------------------------------------
// Unwrap the 200 application/json content type from openapi-fetch shape
// ---------------------------------------------------------------------------

/**
 * Extract the ``200 application/json`` response body from an
 * openapi-typescript response map.
 *
 * Example::
 *
 *     type HealthBody = SuccessBody<
 *       paths["/api/health"]["get"]["responses"]
 *     >;
 *     // → { [key: string]: unknown }
 */
type SuccessBody<T> = T extends {
  200: {
    content: {
      "application/json": infer B;
    };
  };
}
  ? B
  : T extends {
        202: {
          content: {
            "application/json": infer B;
          };
        };
      }
    ? B
    : never;

// ---------------------------------------------------------------------------
// Path/method binding to the generated OpenAPI `paths` (DESIGN §5.3)
// ---------------------------------------------------------------------------

/** The HTTP verbs openapi-typescript emits as keys on every path item. */
type HttpMethod =
  | "get"
  | "put"
  | "post"
  | "delete"
  | "options"
  | "head"
  | "patch"
  | "trace";

/**
 * The verbs a path actually **defines** — the operation objects, excluding the
 * ``verb?: never`` slots openapi-typescript stamps for every absent method.
 *
 * A defined verb's value is an operation object; an absent verb's indexed value
 * collapses to ``undefined`` (optional ``never``). Passing a method a path does
 * not declare therefore fails the constraint at compile time.
 */
type MethodOf<P extends keyof paths> = {
  [M in HttpMethod]: paths[P][M] extends undefined ? never : M;
}[HttpMethod];

/** The ``application/json`` request body of an operation, or ``never`` if none. */
type RequestBodyOf<Op> = Op extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : never;

/**
 * The **required** path parameters of an operation, or ``never`` when the
 * operation declares none (openapi-typescript stamps ``path?: never`` on
 * parameterless operations, which fails the required-property match below).
 */
type PathParamsOf<Op> = Op extends { parameters: { path: infer P } }
  ? P
  : never;

/**
 * The optional query parameters of an operation, or ``never`` when the
 * operation declares none.  Query params are always optional in the generated
 * types (``query?: {...}``), so the match strips the ``undefined`` arm.
 */
type QueryParamsOf<Op> = Op extends { parameters: { query?: infer Q } }
  ? NonNullable<Q>
  : never;

/** The 2xx ``application/json`` response body inferred from an operation. */
type ResponseBodyOf<Op> = Op extends { responses: infer R }
  ? SuccessBody<R>
  : never;

// ---------------------------------------------------------------------------
// Error detail normalisation
// ---------------------------------------------------------------------------

/**
 * Extract a human-readable detail string from a JSON error response body.
 *
 * FastAPI 422 responses carry ``detail`` as an **array** of
 * ``{loc, msg, type}`` objects rather than a plain string.  Other
 * endpoints (or non-Pydantic errors) return a string.  This helper
 * normalises both shapes so every :class:`ApiError` carries a string
 * that downstream code can reliably ``JSON.parse`` when needed.
 *
 * Args:
 *   body: The parsed JSON body (``unknown`` — no ``any``).
 *   fallback: Value to return when ``body`` is not an object or has no
 *       ``detail`` key (typically ``response.statusText``).
 *
 * Returns:
 *   A string suitable for ``ApiError.detail``.
 */
function extractDetail(body: unknown, fallback: string): string {
  if (body !== null && typeof body === "object" && "detail" in body) {
    const detail: unknown = (body as Record<string, unknown>).detail;
    if (typeof detail === "string") return detail;
    return JSON.stringify(detail);
  }
  return fallback;
}

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

/**
 * Make a typed HTTP request to the TorrentMate API.
 *
 * The ``path`` and ``method`` are bound to the generated OpenAPI ``paths``
 * (DESIGN §5.3): a mistyped path or a verb the path does not declare is a
 * **compile error**, and the resolved response type is inferred from the
 * operation's 2xx ``application/json`` schema — no manual type parameter and no
 * ``any`` at any call site. Also wraps the standard ``fetch`` with:
 *
 * - Automatic ``credentials: "include"`` (sends the ``tm_session`` cookie).
 * - ``Content-Type: application/json`` set only when a body is present.
 * - An ``ApiError`` thrown on any non-OK status (401 handled in the app layer).
 *
 * Parameterized routes (R15): ``init.params.path`` carries the operation's
 * path parameters (interpolated into the ``{name}`` placeholders of the
 * literal ``paths`` key, URI-encoded) and ``init.params.query`` its query
 * parameters (serialised to a query string, ``undefined`` entries skipped).
 * Both are typed from ``paths[P][M]["parameters"]`` — passing a param the
 * operation does not declare, or omitting a required path param, is a
 * compile error.
 *
 * Type parameters:
 *   **P**: The API path — a key of the generated ``paths``.
 *   **M**: An HTTP verb the path ``P`` actually declares ({@link MethodOf}).
 *
 * Args:
 *   path: The API path (e.g. ``"/api/health"``), checked against ``paths``.
 *   init: The request method plus, for body-carrying operations, a ``body``
 *       typed to that operation's ``requestBody`` JSON shape, optional
 *       ``params`` (path/query, schema-typed), and optional extra
 *       ``headers``.
 */
export async function apiFetch<P extends keyof paths, M extends MethodOf<P>>(
  path: P,
  init: {
    method: M;
    body?: RequestBodyOf<paths[P][M]>;
    headers?: Record<string, string>;
    params?: {
      path?: PathParamsOf<paths[P][M]>;
      query?: QueryParamsOf<paths[P][M]>;
    };
  },
): Promise<ResponseBodyOf<paths[P][M]>> {
  // Build headers — only set Content-Type when there is a body.
  const requestHeaders: Record<string, string> = {};
  if (init.body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }
  if (init.headers !== undefined) {
    Object.assign(requestHeaders, init.headers);
  }

  // Build the fetch init manually to avoid exactOptionalPropertyTypes
  // conflicts (spreading undefined into RequestInit properties is illegal).
  // The schema verb keys are lowercase; `fetch` wants the canonical uppercase.
  const fetchInit: RequestInit = {
    method: init.method.toUpperCase(),
    credentials: "include",
    headers: requestHeaders,
  };
  if (init.body !== undefined) {
    fetchInit.body = JSON.stringify(init.body);
  }

  // Resolve the concrete URL: interpolate {name} path params, append query.
  let url: string = path;
  const pathParams = init.params?.path;
  if (pathParams !== undefined) {
    for (const [key, value] of Object.entries(
      pathParams as Record<string, string | number>,
    )) {
      url = url.replace(`{${key}}`, encodeURIComponent(String(value)));
    }
  }
  const queryParams = init.params?.query;
  if (queryParams !== undefined) {
    const sp = new URLSearchParams();
    for (const [key, value] of Object.entries(
      queryParams as Record<string, string | number | boolean | undefined>,
    )) {
      if (value !== undefined) sp.set(key, String(value));
    }
    const qs = sp.toString();
    if (qs) url = `${url}?${qs}`;
  }

  const response = await fetch(url, fetchInit);

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body: unknown = await response.json();
      detail = extractDetail(body, response.statusText);
    } catch {
      // Body is not JSON or is empty — keep statusText.
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content — no body to parse (login / logout). The cast is forced: the
  // schema types the body, but a 204 carries none.
  if (response.status === 204) {
    return undefined as ResponseBodyOf<paths[P][M]>;
  }

  // `Response.json()` is untyped (`Promise<any>`); assert the schema-derived
  // body — the only cast the generated types force on us.
  return (await response.json()) as ResponseBodyOf<paths[P][M]>;
}

// ---------------------------------------------------------------------------
// Per-endpoint typed helpers
// ---------------------------------------------------------------------------

/** Login: POST /api/auth/login.  204 on success, 401 on bad credentials. */
export async function login(
  body: paths["/api/auth/login"]["post"]["requestBody"]["content"]["application/json"],
): Promise<void> {
  await apiFetch("/api/auth/login", { method: "post", body });
}

/** Logout: POST /api/auth/logout.  Requires auth. */
export async function logout(): Promise<void> {
  await apiFetch("/api/auth/logout", { method: "post" });
}

/** Get current user: GET /api/auth/me.  Requires auth. */
export function getMe(): Promise<
  SuccessBody<paths["/api/auth/me"]["get"]["responses"]>
> {
  return apiFetch("/api/auth/me", { method: "get" });
}

/** Health: GET /api/health.  Public. */
export function getHealth(): Promise<
  SuccessBody<paths["/api/health"]["get"]["responses"]>
> {
  return apiFetch("/api/health", { method: "get" });
}

/** Version: GET /api/version.  Requires auth. */
export function getVersion(): Promise<
  SuccessBody<paths["/api/version"]["get"]["responses"]>
> {
  return apiFetch("/api/version", { method: "get" });
}

// ---------------------------------------------------------------------------
// Pipeline endpoints
// ---------------------------------------------------------------------------

/**
 * Shared header required by EVERY mutating endpoint (the backend's
 * `require_x_requested_with` guard returns 400 without it). Exported so the
 * decisions helpers reuse the exact same value (coherence study F00).
 */
export const XRW_HEADERS: Record<string, string> = {
  "X-Requested-With": "TorrentMate",
};

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

// ---------------------------------------------------------------------------
// Staging read-model endpoints (webui-overhaul OBJ2A)
// ---------------------------------------------------------------------------

/** Response type for ``GET /api/staging/media``. */
export type StagingMediaResponse = SuccessBody<
  paths["/api/staging/media"]["get"]["responses"]
>;

/** One staged media item (grid card / timeline row). */
export type StagingMediaItem = StagingMediaResponse["items"][number];

/** One stage of a staged media's per-item pipeline timeline. */
export type StagingStageStep = StagingMediaItem["stages"][number];

/**
 * Query parameters accepted by ``GET /api/staging/media`` — derived from the
 * generated schema so a backend parameter change breaks compilation here (R15).
 */
export type StagingMediaParams = QueryParamsOf<
  paths["/api/staging/media"]["get"]
>;

/**
 * Fetch the staged-media read-model: GET /api/staging/media.
 *
 * Session-guarded read — no ``X-Requested-With`` header (R15). Returns one item
 * per staged media folder with NFO metadata, matching state, and a per-media
 * pipeline timeline, plus aggregate filter counts.
 *
 * Args:
 *   params: Optional pagination / sort / filter query parameters.
 *
 * Returns:
 *   A {@link StagingMediaResponse} for the requested page.
 */
export function getStagingMedia(
  params: StagingMediaParams = {},
): Promise<StagingMediaResponse> {
  return apiFetch("/api/staging/media", {
    method: "get",
    params: { query: params },
  });
}

/** Response of POST /api/staging/media/{id}/enqueue. */
export type EnqueueDecisionResponse = SuccessBody<
  paths["/api/staging/media/{media_id}/enqueue"]["post"]["responses"]
>;

/**
 * Enqueue a non-identified staged item as a pending scrape decision so it shows
 * up in the resolution deck: POST /api/staging/media/{id}/enqueue. Mutating —
 * carries ``X-Requested-With``.
 *
 * Args:
 *   mediaId: The stable staged-media id.
 *
 * Returns:
 *   The {@link EnqueueDecisionResponse}.
 */
export function enqueueStagingDecision(
  mediaId: string,
): Promise<EnqueueDecisionResponse> {
  return apiFetch("/api/staging/media/{media_id}/enqueue", {
    method: "post",
    params: { path: { media_id: mediaId } },
    headers: XRW_HEADERS,
  });
}

// ---------------------------------------------------------------------------
// Maintenance endpoints (S3 — maint-dash)
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

// ---------------------------------------------------------------------------
// Config editor endpoints (S4 — config-editor)
// ---------------------------------------------------------------------------

/** Response type for ``GET /api/config/schema``. */
export type ConfigSchemaResponse = SuccessBody<
  paths["/api/config/schema"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/files``. */
export type FilesResponse = SuccessBody<
  paths["/api/config/files"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/files/{name}``. */
export type FileContent = SuccessBody<
  paths["/api/config/files/{name}"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/status``. */
export type ConfigStatusResponse = SuccessBody<
  paths["/api/config/status"]["get"]["responses"]
>;

/** Response type for ``GET /api/config/secrets``. */
export type SecretsResponse = SuccessBody<
  paths["/api/config/secrets"]["get"]["responses"]
>;

/** A single file entry in the config files listing. */
export type FileInfo = components["schemas"]["FileInfo"];

/** A single secret key entry from the catalog. */
export type SecretEntry = components["schemas"]["SecretEntry"];

/** Request body for ``PUT /api/config/files/{name}``. */
export type PutFileRequest = components["schemas"]["PutFileRequest"];

/** Response body for ``PUT /api/config/files/{name}`` and ``PUT /api/config/secrets``. */
export type PutFileResponse = components["schemas"]["PutFileResponse"];

/** Request body for ``PUT /api/config/secrets``. */
export type SecretsPutRequest = components["schemas"]["SecretsPutRequest"];

/** Request body for ``POST /api/config/validate``. */
export type ValidateRequest = components["schemas"]["ValidateRequest"];

/** Response body for ``POST /api/config/validate``. */
export type ValidateResponse = components["schemas"]["ValidateResponse"];

/** Response body for ``POST /api/config/restart-web``. */
export type RestartResponse = components["schemas"]["RestartResponse"];

/** Fetch the JSON Schema, key ownership, and restart-impact map: GET /api/config/schema. */
export function getConfigSchema(): Promise<ConfigSchemaResponse> {
  return apiFetch("/api/config/schema", { method: "get" });
}

/** Fetch metadata for every config file: GET /api/config/files. */
export function getConfigFiles(): Promise<FilesResponse> {
  return apiFetch("/api/config/files", { method: "get" });
}

/**
 * Fetch the parsed contents of a single config file.
 *
 * Sends ``GET /api/config/files/{name}`` through the typed {@link apiFetch}
 * (R15 — ``name`` is a schema-typed path param).
 *
 * Args:
 *   name: Config file basename (e.g. ``"paths.json5"``).
 *
 * Returns:
 *   A {@link FileContent} with parsed values, SHA-256, and shadowed keys.
 *
 * Raises:
 *   ApiError: 404 if *name* is not a recognised config file.
 */
export function getConfigFile(name: string): Promise<FileContent> {
  return apiFetch("/api/config/files/{name}", {
    method: "get",
    params: { path: { name } },
  });
}

/** Fetch deployment status and stale file detection: GET /api/config/status. */
export function getConfigStatus(): Promise<ConfigStatusResponse> {
  return apiFetch("/api/config/status", { method: "get" });
}

/** Fetch the secret key catalog with ``is_set`` flags: GET /api/config/secrets. */
export function getConfigSecrets(): Promise<SecretsResponse> {
  return apiFetch("/api/config/secrets", { method: "get" });
}

/**
 * Validate and atomically write a config overlay file.
 *
 * Sends ``PUT /api/config/files/{name}`` with the ``X-Requested-With`` header
 * through the typed {@link apiFetch} (R15 — ``name`` is a schema-typed path
 * param).
 *
 * Args:
 *   name: Config file basename (e.g. ``"paths.json5"``).
 *   body: The request payload with ``values`` and ``base_sha256``.
 *
 * Returns:
 *   A {@link PutFileResponse} with warnings and restart_required flag.
 *
 * Raises:
 *   ApiError: 403 (staging read-only), 404 (not a writable file),
 *     412 (SHA-256 mismatch), or 422 (validation failure).
 */
export function putConfigFile(
  name: string,
  body: PutFileRequest,
): Promise<PutFileResponse> {
  return apiFetch("/api/config/files/{name}", {
    method: "put",
    body,
    headers: XRW_HEADERS,
    params: { path: { name } },
  });
}

/**
 * Write secret values to ``.env`` via atomic upsert.
 *
 * Sends ``PUT /api/config/secrets`` with the ``X-Requested-With`` header.
 *
 * Args:
 *   body: Mapping of ``{KEY: value, ...}`` to upsert into ``.env``.
 *
 * Returns:
 *   A {@link PutFileResponse} with ``restart_required=True``.
 *
 * Raises:
 *   ApiError: 403 (staging read-only) or 422 (unknown key).
 */
export function putConfigSecrets(
  body: SecretsPutRequest,
): Promise<PutFileResponse> {
  return apiFetch("/api/config/secrets", {
    method: "put",
    body,
    headers: XRW_HEADERS,
  });
}

/**
 * Validate a candidate config file without writing to disk.
 *
 * Sends ``POST /api/config/validate`` with the ``X-Requested-With`` header.
 *
 * Args:
 *   body: The file name and candidate values to validate.
 *
 * Returns:
 *   A {@link ValidateResponse} with validation warnings.
 *
 * Raises:
 *   ApiError: 422 if the candidate fails Pydantic validation.
 */
export function validateConfig(
  body: ValidateRequest,
): Promise<ValidateResponse> {
  return apiFetch("/api/config/validate", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

/**
 * Schedule a PM2 restart of the web process.
 *
 * Sends ``POST /api/config/restart-web`` with the ``X-Requested-With`` header.
 * The restart is handed off to a detached subprocess; the 202 response confirms
 * scheduling only.
 *
 * Returns:
 *   A {@link RestartResponse} with ``status: "scheduled"``.
 *
 * Raises:
 *   ApiError: 403 (staging) or 404 (PM2 name not configured).
 */
export function restartWeb(): Promise<RestartResponse> {
  return apiFetch("/api/config/restart-web", {
    method: "post",
    headers: XRW_HEADERS,
  });
}

// ---------------------------------------------------------------------------
// Global 401 policy seam
// ---------------------------------------------------------------------------

/**
 * Handler invoked when the API answers ``401 Unauthorized`` on any query or
 * mutation (except mutations that opt out via {@link SKIP_AUTH_REDIRECT}).
 *
 * Deliberately injectable: sub-phase 5.3 (auth guard) replaces the default
 * hard redirect with a router-aware navigation that preserves the target path
 * (``?redirect=<current>``) via {@link setUnauthorizedHandler}.
 */
export type UnauthorizedHandler = () => void;

/**
 * Mutation ``meta`` flag opting a mutation out of the global 401 → redirect
 * policy.  The login mutation sets it: a 401 there means "bad credentials",
 * which must surface inline on the login form, not trigger a redirect loop.
 */
export const SKIP_AUTH_REDIRECT = "skipAuthRedirect";

// Current handler.  Assigned its real default once ``queryClient`` exists (see
// below) so the default can close over it; swapped at runtime by phase 5.3.
let unauthorizedHandler: UnauthorizedHandler | null = null;

/** True when ``error`` is an :class:`ApiError` carrying HTTP 401. */
function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/**
 * True when ``query`` is the ``me`` identity query (``['auth', 'me']``).
 *
 * Mirrors ``authKeys.me`` in ``hooks/useAuth.ts`` — kept as a structural check
 * here to avoid a ``client`` ↔ ``useAuth`` import cycle.
 */
function isMeQuery(query: { readonly queryKey: readonly unknown[] }): boolean {
  const key = query.queryKey;
  return key.length === 2 && key[0] === "auth" && key[1] === "me";
}

/** Invoke the currently-registered unauthorized handler, if any. */
function runUnauthorizedHandler(): void {
  unauthorizedHandler?.();
}

/**
 * Register a custom unauthorized handler, replacing the default hard redirect.
 *
 * Sub-phase 5.3 (auth guard) calls this at app boot to swap in a router-aware
 * redirect. Idempotent — the last registered handler wins.
 *
 * Args:
 *   handler: The replacement handler invoked on any unhandled 401.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler;
}

// ---------------------------------------------------------------------------
// TanStack Query client
// ---------------------------------------------------------------------------

/**
 * Shared TanStack Query client.
 *
 * - ``staleTime: 5_000`` — data is fresh for 5 seconds; avoids redundant
 *   refetches on focus/remount.
 * - ``retry: 1`` — one automatic retry on failure, then surface the error.
 * - **Global 401 policy**: the query cache and mutation cache both invoke
 *   {@link runUnauthorizedHandler} on an :class:`ApiError` with status 401.
 *   Mutations carrying the {@link SKIP_AUTH_REDIRECT} ``meta`` flag (the login
 *   mutation) are exempt so bad-credential 401s stay on the login form.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      retry: 1,
    },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      // The `me` query's own 401 is the canonical "not authenticated" signal —
      // AuthProvider + ProtectedRoute react to its error directly. Routing it
      // through the redirect handler would, once the handler clears `me` and its
      // observer refetches, re-enter on the refetch's 401 and loop forever, so
      // exempt it (pairs with RouterBridge clearing the `me` cache on 401).
      if (isUnauthorized(error) && !isMeQuery(query)) {
        runUnauthorizedHandler();
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _onMutateResult, mutation) => {
      if (mutation.meta?.[SKIP_AUTH_REDIRECT] === true) {
        return;
      }
      if (isUnauthorized(error)) {
        runUnauthorizedHandler();
      }
    },
  }),
});

// Default handler: drop all cached data and hard-redirect to the login page.
// Assigned here (not at declaration) so it can close over ``queryClient``.
unauthorizedHandler = () => {
  queryClient.clear();
  window.location.assign("/login");
};
