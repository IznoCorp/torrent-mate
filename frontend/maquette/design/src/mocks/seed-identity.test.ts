// One provider identifier names ONE medium across the search seeds (B-549).
//
// The add screen's « star wars » answer drew a FILM, « Star Wars : The Clone
// Wars » (2008), carrying the SERIES' identifiers — `tmdb:4194`, `imdb:tt0458290`,
// `tvdb:83268` — so the film's row opened the series' sheet and a second add
// was taken for the first (`add_footer.py`, until a visit's identity was keyed
// by kind). Two rows of different KINDS sharing an identifier is a fixture that
// lies about identity, whichever surface it reaches.
import { describe, expect, it } from "vitest";
import SEARCH_RESULTS from "./seeds/search-results.json";

/** A seed row that states a kind and an identity. */
type IdentifiedRow = { title: string; kind: string; ids: Record<string, string | number> };

/**
 * Every row of a seed that states both a kind and identifiers, however nested.
 *
 * @param node The seed, or a part of it.
 * @returns The rows found.
 */
function identifiedRows(node: unknown): IdentifiedRow[] {
  if (Array.isArray(node)) return node.flatMap(identifiedRows);
  if (node === null || typeof node !== "object") return [];
  const record = node as Record<string, unknown>;
  const own =
    typeof record.kind === "string" && record.ids !== null && typeof record.ids === "object"
      ? [record as unknown as IdentifiedRow]
      : [];
  return [...own, ...Object.values(record).flatMap(identifiedRows)];
}

describe("the search seeds' identities", () => {
  it("never give one provider identifier to two kinds of medium", () => {
    const holdersById = new Map<string, Set<string>>();
    for (const row of identifiedRows(SEARCH_RESULTS)) {
      for (const [provider, identifier] of Object.entries(row.ids)) {
        const key = `${provider}:${String(identifier)}`;
        holdersById.set(key, (holdersById.get(key) ?? new Set()).add(row.kind));
      }
    }
    const shared = [...holdersById].filter(([, held]) => held.size > 1).map(([key]) => key);
    expect(shared).toEqual([]);
  });
});
