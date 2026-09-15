// THE SEASONS READ, and the one derivation every season row is drawn from.
//
// Two features draw season rows about one medium — the media sheet and the
// follow panel — and features never import each other. Written once here, so
// the key, the projection and the arithmetic are the same object on both
// surfaces rather than two copies that part company on the first change (§13).
import { read } from "./query-client";

/** What the seasons read answers: the catalogue, and what we hold of it. */
export type SeasonsAnswer = {
  seasons: { number: number; episodes?: number | null }[];
  owned: Record<string, number[]>;
  /**
   * How many episodes of each season have AIRED, keyed by season number: the
   * layer's derivation from the catalogue's own dates, and the denominator of
   * every season row. The catalogue's `ep` is its TOTAL, announced episodes
   * included, which is not the same question.
   */
  aired: Record<string, number | null>;
};

/**
 * The seasons read at one address, as a query the cache and a producer share.
 *
 * @param provider The provider, as the address names it.
 * @param identifier The identifier at that provider.
 * @returns The query's key and function.
 */
export function seasonsQuery(provider: string, identifier: string) {
  return {
    queryKey: ["/api/media", provider, identifier, "seasons"] as const,
    queryFn: async (): Promise<SeasonsAnswer> => {
      const answered = await read<Record<string, unknown>>(
        `/api/media/${encodeURIComponent(provider)}/${encodeURIComponent(identifier)}/seasons`);
      // The catalogue is the sheet's own, so it wears the sheet's names — the
      // contract's.
      return {
        seasons: (answered.seasons ?? []) as SeasonsAnswer["seasons"],
        owned: (answered.owned ?? {}) as SeasonsAnswer["owned"],
        aired: (answered.aired ?? {}) as SeasonsAnswer["aired"],
      };
    },
  };
}

/**
 * Crosses a season catalogue with what we hold, once.
 *
 * ONE DERIVATION PER QUESTION (§13). « How complete is this season » is asked on
 * the sheet, on the matrix and in the popover; the engine answered it in
 * `seasonsOf`, and this is that answer moved rather than a second one written.
 *
 * WHAT AIRED IS THE LAYER'S ANSWER, never the catalogue's total. `ep` counts
 * the episodes a provider has ANNOUNCED, and a « manquant » is an episode that
 * has aired and is not held: dividing by the total drew « 6/10 · 4 manquants »
 * over a season of which seven had aired, three episodes missing that nobody
 * could have (B-380). A season the answer gives no count for is not a season
 * that aired zero: the interface then draws « n owned » rather than « n of m ».
 * And an owned number ABOVE what aired is not counted — a season of which ten
 * have aired cannot be eleven-tenths complete.
 *
 * @param held What the layer answered.
 * @returns One entry per season: its number, what aired, and what we hold.
 */
export function seasonsHeld(held: SeasonsAnswer | undefined): [number, number | null, number][] {
  if (held === undefined) return [];
  const owned = held.owned ?? {};
  if (held.seasons.length) {
    return held.seasons.map((season) => {
      // A SET: an episode held twice is one episode held.
      const numbers = [...new Set(owned[String(season.number)] ?? [])];
      const aired = held.aired[String(season.number)] ?? null;
      const own = aired ? numbers.filter((one) => one <= aired).length : numbers.length;
      return [season.number, aired, own];
    });
  }
  // No catalogue: the owned seasons are known, the totals are not.
  return Object.keys(owned)
    .map(Number)
    .sort((left, right) => left - right)
    .map((number) => [number, null, new Set(owned[String(number)]).size]);
}
