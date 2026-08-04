/**
 * Single-source-of-truth link builder for the media sheet route (DESIGN D8).
 *
 * Every surface that links to a media detail page MUST go through
 * {@link mediaSheetHref} — a constitution rule applied in multiple places needs
 * one point of truth or it drifts. Both path segments are URI-encoded; the
 * optional ``kind`` hint is appended as a query parameter so the backend skips
 * the wasteful TV-first probe for a known movie (phase-2 call contract).
 */

/** A reference to a media item by provider identity. */
export interface MediaRef {
  /** Provider name (e.g. ``"tmdb"``, ``"tvdb"``). */
  readonly provider: string;
  /** Provider-specific media identifier. */
  readonly providerId: string;
  /** Optional media kind hint — saves a wasted provider round-trip. */
  readonly kind?: "movie" | "tv";
}

/**
 * Build the media-sheet route URL from a provider reference.
 *
 * Args:
 *   ref: The provider identity plus optional kind hint.
 *
 * Returns:
 *   A relative URL path: ``/media/{provider}/{providerId}[?kind=movie|tv]``.
 */
export function mediaSheetHref(ref: MediaRef): string {
  const base = `/media/${encodeURIComponent(ref.provider)}/${encodeURIComponent(ref.providerId)}`;
  if (ref.kind !== undefined) {
    return `${base}?kind=${encodeURIComponent(ref.kind)}`;
  }
  return base;
}
