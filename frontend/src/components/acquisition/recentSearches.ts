/**
 * recentSearches — this device's add-screen search history.
 *
 * Feeds the maquette's `.sugg` chips with HONEST data (operator arbitration
 * 2026-08-08, handoff §3.5c): the last queries actually submitted on this
 * device — never invented titles. localStorage-backed, capped, most-recent
 * first, case-insensitively deduplicated.
 */

/** Storage key — device-local, same family as `tm.follows.viewmode`. */
export const RECENT_SEARCHES_KEY = "tm.add.recentSearches";

/** Maximum stored queries — the maquette shows a single wrapped chip row. */
export const RECENT_SEARCHES_MAX = 5;

/**
 * Read the stored history.
 *
 * Returns:
 *   Most-recent-first queries; empty on missing or corrupt storage.
 */
export function readRecentSearches(): readonly string[] {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    if (raw == null) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((v): v is string => typeof v === "string");
  } catch {
    return [];
  }
}

/**
 * Record a submitted query at the head of the history.
 *
 * Args:
 *   query: The query as typed (stored verbatim; deduplicated
 *     case-insensitively so « Silo » replaces « silo »).
 */
export function pushRecentSearch(query: string): void {
  const q = query.trim();
  if (q === "") return;
  const rest = readRecentSearches().filter(
    (r) => r.toLowerCase() !== q.toLowerCase(),
  );
  try {
    localStorage.setItem(
      RECENT_SEARCHES_KEY,
      JSON.stringify([q, ...rest].slice(0, RECENT_SEARCHES_MAX)),
    );
  } catch {
    // Quota/private-mode failures lose the shortcut, never the search.
  }
}
