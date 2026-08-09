/**
 * posterThumb — swap a provider poster URL for its thumbnail variant.
 *
 * List surfaces render posters at ≤ 120 CSS px, but the API hands back
 * full-size artwork (TVDB originals weigh ~370 KB; a 20-row list pulls
 * megabytes on a phone). Both providers publish pre-generated small
 * variants addressable by URL alone — no extra API call needed.
 */

/** TMDB size segment that covers every acquisition surface at DPR 2. */
const TMDB_THUMB_SIZE = "w342";

/**
 * Rewrite a poster URL to its provider thumbnail variant.
 *
 * Unknown hosts pass through untouched — worst case is the current
 * behavior, never a broken image.
 *
 * Args:
 *   url: Full-size poster URL, or null.
 *
 * Returns:
 *   The thumbnail URL, or the input unchanged when no variant is known.
 */
export function posterThumb(url: string | null): string | null {
  if (url == null) return null;
  // TVDB: every artwork has a `_t` thumbnail before the extension (legacy
  // banners/ paths and v4 paths alike).
  if (
    url.startsWith("https://artworks.thetvdb.com/") &&
    !/_t\.\w+$/.test(url)
  ) {
    return url.replace(/\.(\w+)$/, "_t.$1");
  }
  // TMDB: the size lives in the path — swap whatever variant for the thumb.
  const tmdb = /^https:\/\/image\.tmdb\.org\/t\/p\/[^/]+(?<rest>\/.+)$/.exec(
    url,
  );
  const rest = tmdb?.groups?.rest;
  if (rest != null) {
    return `https://image.tmdb.org/t/p/${TMDB_THUMB_SIZE}${rest}`;
  }
  return url;
}
