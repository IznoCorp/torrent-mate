/**
 * Typed fetch wrappers for the media-sheet read endpoint (DESIGN D7).
 *
 * Every helper binds through {@link apiFetch} so path, method and query params
 * are all checked against the OpenAPI-generated ``schema.d.ts`` — no ``any`` at
 * any call site. The endpoint is a session-guarded read — no
 * ``X-Requested-With`` header.
 */

import type { QueryParamsOf, SuccessBody } from "./_schema-helpers";
import type { paths } from "./schema";
import { apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Media sheet endpoint
// ---------------------------------------------------------------------------

/** Response type for ``GET /api/media/{provider}/{provider_id}``. */
export type MediaSheetResponse = SuccessBody<
  paths["/api/media/{provider}/{provider_id}"]["get"]["responses"]
>;

/**
 * Query parameters accepted by ``GET /api/media/{provider}/{provider_id}``
 * — derived from the generated schema so a backend parameter change breaks
 * compilation here.
 */
export type MediaSheetQueryParams = QueryParamsOf<
  paths["/api/media/{provider}/{provider_id}"]["get"]
>;

/**
 * Fetch the media sheet: GET /api/media/{provider}/{provider_id}.
 *
 * Session-guarded read — no ``X-Requested-With`` header. Returns identity
 * (always present), metadata fields (null when the provider does not supply
 * them), ownership (null when the library database is unreachable), and an
 * optional degraded_reason when the provider was unreachable (D9).
 *
 * Args:
 *   provider: Provider name (``"tmdb"`` / ``"tvdb"``).
 *   providerId: Provider-specific media identifier.
 *   params: Optional query parameters — ``kind`` hint to skip wasted probing.
 *
 * Returns:
 *   A {@link MediaSheetResponse}.
 */
export function getMediaSheet(
  provider: string,
  providerId: string,
  params: MediaSheetQueryParams = {},
): Promise<MediaSheetResponse> {
  return apiFetch("/api/media/{provider}/{provider_id}", {
    method: "get",
    params: {
      path: { provider, provider_id: providerId },
      query: params,
    },
  });
}
