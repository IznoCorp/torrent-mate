/**
 * Typed API client helpers for the /api/decisions REST endpoints
 * (scrape-arbiter, DESIGN §7).
 *
 * Every helper routes through {@link apiFetch} with schema-typed path and
 * query params (R15) — no raw fetch and no ``any``.  Response types are
 * inferred from the regenerated ``schema.d.ts`` so a backend signature change
 * breaks at compile time, not at runtime.
 */

import type { components, paths } from "./schema";
import { XRW_HEADERS, apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Re-export schema component types so the UI layer can import them from one
// place (per DESIGN §7 typed-client convention).
// ---------------------------------------------------------------------------

/** A single scored search-result candidate for a scrape-decision row. */
export type DecisionCandidate = components["schemas"]["DecisionCandidate"];

/** Full detail for a single ``scrape_decision`` row. */
export type DecisionDetail = components["schemas"]["DecisionDetail"];

/** Summary row for the decisions list endpoint. */
export type DecisionListItem = components["schemas"]["DecisionListItem"];

// ---------------------------------------------------------------------------
// Inline type helpers (mirror client.ts — not exported from there)
// ---------------------------------------------------------------------------

/**
 * Extract the ``application/json`` response body from an
 * openapi-typescript response map (200 or 202).
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

/** The ``application/json`` request body declared by an operation, or ``never``. */
type RequestBodyOf<Op> = Op extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : never;

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/** Paginated response for ``GET /api/decisions``. */
export type DecisionsResponse = SuccessBody<
  paths["/api/decisions/"]["get"]["responses"]
>;

/** Full detail response for ``GET /api/decisions/{decision_id}``. */
export type DecisionDetailResponse = SuccessBody<
  paths["/api/decisions/{decision_id}"]["get"]["responses"]
>;

/** Response body for ``POST /api/decisions/{decision_id}/search``. */
export type SearchResponse = SuccessBody<
  paths["/api/decisions/{decision_id}/search"]["post"]["responses"]
>;

/** Response body for ``POST /api/decisions/{decision_id}/resolve`` (202). */
export type ResolveResponse = SuccessBody<
  paths["/api/decisions/{decision_id}/resolve"]["post"]["responses"]
>;

// ---------------------------------------------------------------------------
// Parameter / request-body types
// ---------------------------------------------------------------------------

/**
 * Query parameters accepted by ``GET /api/decisions`` — derived from the
 * generated schema so a backend parameter change breaks compilation here
 * (R15), not at runtime.
 */
export type DecisionsParams = QueryParamsOf<
  paths["/api/decisions/"]["get"]
>;

/** Request body for ``POST /api/decisions/{decision_id}/search``. */
export type SearchRequest =
  RequestBodyOf<paths["/api/decisions/{decision_id}/search"]["post"]>;

/** Request body for ``POST /api/decisions/{decision_id}/resolve``. */
export type ResolveRequest =
  RequestBodyOf<paths["/api/decisions/{decision_id}/resolve"]["post"]>;

// ---------------------------------------------------------------------------
// Stable TanStack Query keys
// ---------------------------------------------------------------------------

/**
 * Stable React-Query keys for the decisions domain.
 *
 * Exported so mutations and the AppShell badge invalidate the exact same cache
 * entries.  Follows the established ``pipelineKeys`` / ``maintenanceKeys``
 * pattern.
 */
export const decisionsKeys = {
  /** Root decisions key: ``['decisions']``.  Invalidated on any mutation. */
  all: ["decisions"] as const,

  /** List query key factory: ``['decisions', { status, page, page_size }]``. */
  list: (params: DecisionsParams = {}) =>
    ["decisions", params] as const,

  /** Detail query key factory: ``['decisions', id]``. */
  detail: (id: number) => ["decisions", id] as const,
};

// ---------------------------------------------------------------------------
// Typed endpoint helpers
// ---------------------------------------------------------------------------

/**
 * Fetch a paginated list of scrape decisions.
 *
 * Sends ``GET /api/decisions`` with optional query params through the typed
 * {@link apiFetch} (R15). Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional pagination and filter query parameters (``status``,
 *       ``page``, ``page_size``).
 *
 * Returns:
 *   A {@link DecisionsResponse} with ``items``, ``pending_count``, ``total``,
 *   ``page``, and ``page_size``.
 */
export function fetchDecisions(
  params: DecisionsParams = {},
): Promise<DecisionsResponse> {
  return apiFetch("/api/decisions/", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch full detail for a single scrape decision.
 *
 * Sends ``GET /api/decisions/{decision_id}`` through the typed
 * {@link apiFetch} (R15 — ``decision_id`` is a schema-typed path param).
 *
 * Args:
 *   id: Primary key of the ``scrape_decision`` row.
 *
 * Returns:
 *   A {@link DecisionDetailResponse} with the full candidate list and
 *   optional resolution metadata.
 *
 * Raises:
 *   ApiError: 404 (not found) or 410 (superseded).
 */
export function fetchDecisionDetail(
  id: number,
): Promise<DecisionDetailResponse> {
  return apiFetch("/api/decisions/{decision_id}", {
    method: "get",
    params: { path: { decision_id: id } },
  });
}

/**
 * Search live providers for candidate matches.
 *
 * Sends ``POST /api/decisions/{decision_id}/search`` with a search title and
 * optional year. Read-only (POST body carries the query, no state change).
 *
 * Args:
 *   id: Primary key of the ``scrape_decision`` row.
 *   body: Search request with ``title`` and optional ``year``.
 *
 * Returns:
 *   A {@link SearchResponse} with fresh provider candidates.
 *
 * Raises:
 *   ApiError: 404 (not found), 410 (superseded), or 502 (provider API
 *       failure).
 */
export function searchDecisionCandidates(
  id: number,
  body: SearchRequest,
): Promise<SearchResponse> {
  return apiFetch("/api/decisions/{decision_id}/search", {
    method: "post",
    body,
    headers: XRW_HEADERS,
    params: { path: { decision_id: id } },
  });
}

/**
 * Launch a targeted re-scrape for a decision.
 *
 * Sends ``POST /api/decisions/{decision_id}/resolve`` with the chosen
 * provider identity. Returns 202 (Accepted) — the re-scrape runs
 * asynchronously.
 *
 * Args:
 *   id: Primary key of the ``scrape_decision`` row.
 *   body: The request payload with ``provider`` and ``provider_id``.
 *
 * Returns:
 *   A {@link ResolveResponse} with ``run_uid`` of the launched run.
 *
 * Raises:
 *   ApiError: 404 (not found), 409 (lock held / concurrent resolve),
 *       410 (superseded), or 500 (runner spawn failure).
 */
export function resolveDecision(
  id: number,
  body: ResolveRequest,
): Promise<ResolveResponse> {
  return apiFetch("/api/decisions/{decision_id}/resolve", {
    method: "post",
    body,
    headers: XRW_HEADERS,
    params: { path: { decision_id: id } },
  });
}

/**
 * Dismiss a decision (manual or MediaElch path).
 *
 * Sends ``POST /api/decisions/{decision_id}/dismiss``.  Returns the refreshed
 * :class:`DecisionDetail` so the UI can update the row without an extra
 * round-trip.
 *
 * Args:
 *   id: Primary key of the ``scrape_decision`` row.
 *
 * Returns:
 *   The refreshed {@link DecisionDetailResponse} with ``status='dismissed'``.
 *
 * Raises:
 *   ApiError: 404 (not found) or 410 (superseded).
 */
export function dismissDecision(
  id: number,
): Promise<DecisionDetailResponse> {
  return apiFetch("/api/decisions/{decision_id}/dismiss", {
    method: "post",
    headers: XRW_HEADERS,
    params: { path: { decision_id: id } },
  });
}
