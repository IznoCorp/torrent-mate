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
