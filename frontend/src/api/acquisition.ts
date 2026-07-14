/**
 * Typed fetch wrappers for the acquisition API (acq-watch feature).
 *
 * Every function binds through {@link apiFetch} so path, method, request body,
 * path params, and query params are all checked against the OpenAPI-generated
 * ``schema.d.ts`` — no ``any`` at any call site.
 *
 * Mutating endpoints carry the ``X-Requested-With`` header (reusing
 * ``XRW_HEADERS`` from client.ts).  Reads are header-free.
 */

import type { paths } from "./schema";
import { XRW_HEADERS, apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Inline type helpers (mirror decisions.ts / registry.ts)
// ---------------------------------------------------------------------------

/**
 * Extract the ``application/json`` response body from an openapi-typescript
 * response map (200).
 */
type SuccessBody<T> = T extends {
  200: { content: { "application/json": infer B } };
}
  ? B
  : T extends {
        202: { content: { "application/json": infer B } };
      }
    ? B
    : never;

/** The optional query parameters declared by an operation. */
type QueryParamsOf<Op> = Op extends { parameters: { query?: infer Q } }
  ? NonNullable<Q>
  : never;

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/** Response type for GET /api/acquisition/followed */
export type FollowedResponse = SuccessBody<
  paths["/api/acquisition/followed"]["get"]["responses"]
>;

/** A single FollowedSeriesItem from the array */
export type FollowedSeriesItem = FollowedResponse["items"][number];

/** Query params for GET /api/acquisition/followed */
export type FollowedParams = QueryParamsOf<
  paths["/api/acquisition/followed"]["get"]
>;

/** Response type for GET /api/acquisition/wanted */
export type WantedResponse = SuccessBody<
  paths["/api/acquisition/wanted"]["get"]["responses"]
>;

/** A single WantedItemResponse from the array */
export type WantedItem = WantedResponse["items"][number];

/** Query params for GET /api/acquisition/wanted */
export type WantedParams = QueryParamsOf<
  paths["/api/acquisition/wanted"]["get"]
>;

/** Response type for GET /api/acquisition/obligations */
export type ObligationsResponse = SuccessBody<
  paths["/api/acquisition/obligations"]["get"]["responses"]
>;

/** A single ObligationItem from the array */
export type ObligationItem = ObligationsResponse["items"][number];

/** Query params for GET /api/acquisition/obligations */
export type ObligationsParams = QueryParamsOf<
  paths["/api/acquisition/obligations"]["get"]
>;

/** Response type for GET /api/acquisition/status */
export type AcquisitionStatusResponse = SuccessBody<
  paths["/api/acquisition/status"]["get"]["responses"]
>;

/** Response type for GET /api/acquisition/search */
export type MediaSearchResponse = SuccessBody<
  paths["/api/acquisition/search"]["get"]["responses"]
>;

/** A single media search result from the array */
export type MediaSearchResult = MediaSearchResponse["results"][number];

/** Query params for GET /api/acquisition/search (``q`` required, ``kind`` optional). */
export type MediaSearchParams = QueryParamsOf<
  paths["/api/acquisition/search"]["get"]
>;

/** Request body for POST /api/acquisition/followed */
export type CreateFollowRequest =
  paths["/api/acquisition/followed"]["post"]["requestBody"]["content"]["application/json"];

/** Request body for PATCH /api/acquisition/followed/{followed_id} */
export type UpdateFollowRequest =
  paths["/api/acquisition/followed/{followed_id}"]["patch"]["requestBody"]["content"]["application/json"];

/** Response type for GET /api/acquisition/followed/{followed_id}/completeness (§5). */
export type CompletenessResponse = SuccessBody<
  paths["/api/acquisition/followed/{followed_id}/completeness"]["get"]["responses"]
>;

/** One season of the §5 completeness matrix. */
export type SeasonCompleteness = CompletenessResponse["seasons"][number];

/** A recent acquisition run (with its §5 numeric result when recorded). */
export type AcquisitionRecentRun =
  AcquisitionStatusResponse["recent_runs"][number];

// ---------------------------------------------------------------------------
// Stable TanStack Query keys
// ---------------------------------------------------------------------------

/**
 * Stable React-Query keys for the acquisition domain.
 *
 * Exported so mutations and the event-stream patch can invalidate the exact
 * same cache entries.  Follows the established ``decisionsKeys`` /
 * ``pipelineKeys`` / ``maintenanceKeys`` pattern.
 */
export const acqKeys = {
  /** Root acquisition key: ``['acquisition']``.  Invalidated on any mutation. */
  all: ["acquisition"] as const,

  /** Followed list query key: ``['acquisition', 'followed', {active}]``. */
  followed: (params: FollowedParams = {}) =>
    [...acqKeys.all, "followed", params] as const,

  /** Wanted list query key: ``['acquisition', 'wanted', {status, page, page_size}]``. */
  wanted: (params: WantedParams = {}) =>
    [...acqKeys.all, "wanted", params] as const,

  /** Obligations list query key: ``['acquisition', 'obligations', {status}]``. */
  obligations: (params: ObligationsParams = {}) =>
    [...acqKeys.all, "obligations", params] as const,

  /** Acquisition status query key: ``['acquisition', 'status']``. */
  status: () => [...acqKeys.all, "status"] as const,

  /** Media search query key: ``['acquisition', 'search', {q, kind}]``. */
  search: (params: MediaSearchParams) =>
    [...acqKeys.all, "search", params] as const,

  /** Completeness query key: ``['acquisition', 'completeness', id]`` (§5). */
  completeness: (id: number) =>
    [...acqKeys.all, "completeness", id] as const,
};

// ---------------------------------------------------------------------------
// Read endpoints
// ---------------------------------------------------------------------------

/**
 * Fetch followed series list.
 *
 * Sends ``GET /api/acquisition/followed`` with optional ``active`` filter.
 * Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional filter (``active``: ``"active"``, ``"all"``, or
 *       ``"inactive"``).
 *
 * Returns:
 *   A {@link FollowedResponse} with ``items`` array.
 */
export function getFollowed(
  params: FollowedParams = {},
): Promise<FollowedResponse> {
  return apiFetch("/api/acquisition/followed", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch paginated wanted items.
 *
 * Sends ``GET /api/acquisition/wanted`` with optional status filter and
 * pagination.  Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional filter (``status``, ``page``, ``page_size``).
 *
 * Returns:
 *   A {@link WantedResponse} with ``items``, ``total``, ``page``, and
 *   ``page_size``.
 */
export function getWanted(params: WantedParams = {}): Promise<WantedResponse> {
  return apiFetch("/api/acquisition/wanted", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch seed obligations.
 *
 * Sends ``GET /api/acquisition/obligations`` with optional ``status`` filter.
 * Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional filter (``status``: ``"all"``, ``"pending"``,
 *       ``"breached"``, or ``"satisfied"``).
 *
 * Returns:
 *   An {@link ObligationsResponse} with ``items`` array.
 */
export function getObligations(
  params: ObligationsParams = {},
): Promise<ObligationsResponse> {
  return apiFetch("/api/acquisition/obligations", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch acquisition status (watcher state + recent runs).
 *
 * Sends ``GET /api/acquisition/status``.  Read-only — no ``X-Requested-With``
 * header.
 *
 * Returns:
 *   An {@link AcquisitionStatusResponse} with ``watcher_enabled``,
 *   ``last_successful_run_at``, and ``recent_runs``.
 */
export function getAcquisitionStatus(): Promise<AcquisitionStatusResponse> {
  return apiFetch("/api/acquisition/status", { method: "get" });
}

/**
 * Search live providers for media to follow (add-by-search, OBJ3).
 *
 * Sends ``GET /api/acquisition/search`` with a title ``q`` and optional
 * ``kind``.  Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: ``q`` (title to search) + optional ``kind`` (``"movie"``/``"tv"``).
 *
 * Returns:
 *   A {@link MediaSearchResponse} with scored ``results``.
 */
export function searchMedia(
  params: MediaSearchParams,
): Promise<MediaSearchResponse> {
  return apiFetch("/api/acquisition/search", {
    method: "get",
    params: { query: params },
  });
}

// ---------------------------------------------------------------------------
// Mutating endpoints
// ---------------------------------------------------------------------------

/**
 * Follow (or reactivate) a series.
 *
 * Sends ``POST /api/acquisition/followed`` with the ``X-Requested-With``
 * header.  At least one provider ID is required.
 *
 * Args:
 *   body: The {@link CreateFollowRequest} with at least one of ``tvdb_id``,
 *       ``tmdb_id``, or ``imdb_id``, and optional ``title``.
 *
 * Returns:
 *   The created or reactivated {@link FollowedSeriesItem}.
 *
 * Raises:
 *   ApiError: 409 if the series is already actively followed.
 */
export function createFollow(
  body: CreateFollowRequest,
): Promise<FollowedSeriesItem> {
  return apiFetch("/api/acquisition/followed", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

/**
 * Update a followed series (active flag / cadence).
 *
 * Sends ``PATCH /api/acquisition/followed/{followed_id}`` with the
 * ``X-Requested-With`` header.  Every field is optional — only the provided
 * fields are updated.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *   body: The {@link UpdateFollowRequest} with optional ``active`` and
 *       ``cadence`` fields.
 *
 * Returns:
 *   The updated {@link FollowedSeriesItem}.
 *
 * Raises:
 *   ApiError: 404 if the followed_id does not exist.
 */
export function updateFollow(
  id: number,
  body: UpdateFollowRequest,
): Promise<FollowedSeriesItem> {
  return apiFetch("/api/acquisition/followed/{followed_id}", {
    method: "patch",
    body,
    headers: XRW_HEADERS,
    params: { path: { followed_id: id } },
  });
}

/** Response type for POST /api/acquisition/followed/{id}/search (OBJ3). */
export type GrabTriggerResponse = SuccessBody<
  paths["/api/acquisition/followed/{followed_id}/search"]["post"]["responses"]
>;

/**
 * Launch a targeted grab for one followed series (OBJ3 manual trigger).
 *
 * Sends ``POST /api/acquisition/followed/{followed_id}/search`` with the
 * ``X-Requested-With`` header. Returns ``202`` with the launched ``run_uid``.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *
 * Returns:
 *   The {@link GrabTriggerResponse} with the launched ``run_uid``.
 *
 * Raises:
 *   ApiError: 404 (unknown series) / 409 (a grab for this series is running).
 */
export function triggerFollowedSearch(id: number): Promise<GrabTriggerResponse> {
  return apiFetch("/api/acquisition/followed/{followed_id}/search", {
    method: "post",
    headers: XRW_HEADERS,
    params: { path: { followed_id: id } },
  });
}

/**
 * Launch the aired-episode / film discovery NOW (§5 manual watcher trigger).
 *
 * Sends ``POST /api/acquisition/detect``; returns ``202`` with the run_uid the
 * caller tracks to its numeric result (never a blind success toast).
 *
 * Returns:
 *   The launched run's identifier.
 *
 * Raises:
 *   ApiError: 409 when a detect run is already in flight.
 */
export function triggerDetect(): Promise<GrabTriggerResponse> {
  return apiFetch("/api/acquisition/detect", {
    method: "post",
    headers: XRW_HEADERS,
  });
}

/**
 * Fetch the §5 completeness matrix for one followed series.
 *
 * Sends ``GET /api/acquisition/followed/{followed_id}/completeness`` — aired
 * (provider catalog) × en_mediatheque × en_file/en_cours, per season/episode.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *
 * Returns:
 *   The {@link CompletenessResponse}.
 */
export function getCompleteness(id: number): Promise<CompletenessResponse> {
  return apiFetch("/api/acquisition/followed/{followed_id}/completeness", {
    method: "get",
    params: { path: { followed_id: id } },
  });
}

/**
 * Soft-unfollow a series (sets active=False).
 *
 * Sends ``DELETE /api/acquisition/followed/{followed_id}`` with the
 * ``X-Requested-With`` header.  Returns 204 No Content on success.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *
 * Raises:
 *   ApiError: 404 if the followed_id does not exist.
 */
export function deleteFollow(id: number): Promise<void> {
  return apiFetch("/api/acquisition/followed/{followed_id}", {
    method: "delete",
    headers: XRW_HEADERS,
    params: { path: { followed_id: id } },
  });
}
