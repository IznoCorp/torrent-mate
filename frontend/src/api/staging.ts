/**
 * Typed fetch wrappers for the staging read-model API (webui-overhaul OBJ2A).
 *
 * Every helper binds through {@link apiFetch} so path, method, request body and
 * query params are all checked against the OpenAPI-generated ``schema.d.ts`` —
 * no ``any`` at any call site. The mutating enqueue endpoint carries the
 * ``X-Requested-With`` header (``XRW_HEADERS`` from client.ts).
 */

import type { QueryParamsOf, SuccessBody } from "./_schema-helpers";
import type { paths } from "./schema";
import { XRW_HEADERS, apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Staging read-model endpoints
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
 *   mediaKind: Required for an item in an 'other' (AUTRES) category — the type the
 *     operator picks so it can be reclassed; omitted for movie/tvshow items (their
 *     kind is derived server-side from the category).
 *
 * Returns:
 *   The {@link EnqueueDecisionResponse}.
 */
export function enqueueStagingDecision(
  mediaId: string,
  mediaKind?: "movie" | "tvshow",
): Promise<EnqueueDecisionResponse> {
  return apiFetch("/api/staging/media/{media_id}/enqueue", {
    method: "post",
    params: { path: { media_id: mediaId } },
    body: mediaKind !== undefined ? { media_kind: mediaKind } : {},
    headers: XRW_HEADERS,
  });
}
