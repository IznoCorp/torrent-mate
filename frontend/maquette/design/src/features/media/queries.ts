// What the media sheet asks the server for.
//
// IT ASKS BY ADDRESS, which is the whole point of DOIT-11: a sheet is reachable
// at `/media/:provider/:id` and that identity is what the request carries. The
// engine looked its sheet up BY TITLE, out of a fixture keyed by title, and the
// two are not the same question — twenty identities are carried by two title
// keys at once, which is how nine season lists came back empty.
//
// THE SEASONS ARE THEIR OWN READ. A sheet is what a provider says about a title;
// the seasons are that crossed with what we HOLD, and the layer answers both
// halves — the catalogue and the owned numbers — so the crossing happens in one
// place rather than once per surface (§13).
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShapeEntry } from "../../engine/engine-shape";

/** One sheet, as the layer composes it. */
export type MediaSheetPayload = Record<string, unknown>;

/** What the seasons read answers: the catalogue, and what we hold of it. */
export type MediaSeasons = {
  seasons: { n: number; ep?: number | null }[];
  owned: Record<string, number[]>;
};

/**
 * The sheet at one address.
 *
 * @param provider The provider, as the address names it.
 * @param identifier The identifier at that provider.
 * @returns The query.
 */
export function useMediaSheet(provider: string, identifier: string) {
  return useQuery({
    queryKey: ["/api/media", provider, identifier],
    queryFn: async () => {
      const answered = await read<MediaSheetPayload | null>(
        `/api/media/${encodeURIComponent(provider)}/${encodeURIComponent(identifier)}`);
      // ONE ENTRY of a family the projection keys by title. The markup that
      // draws a sheet is still the engine's, and it reads `ov`, `k`, `g`, `y`.
      return answered === null
        ? null
        : toEngineShapeEntry<MediaSheetPayload>("SHEETS_RAW", answered);
    },
    enabled: provider !== "" && identifier !== "",
  });
}

/**
 * The season catalogue at one address, and what we hold of it.
 *
 * @param provider The provider, as the address names it.
 * @param identifier The identifier at that provider.
 * @returns The query.
 */
export function useMediaSeasons(provider: string, identifier: string) {
  return useQuery({
    queryKey: ["/api/media", provider, identifier, "seasons"],
    queryFn: async () => {
      const answered = await read<Record<string, unknown>>(
        `/api/media/${encodeURIComponent(provider)}/${encodeURIComponent(identifier)}/seasons`);
      // The catalogue is the sheet's own, so it wears the sheet's names: one
      // entry of `SHEETS_RAW` carrying nothing but its seasons.
      const shaped = toEngineShapeEntry<Record<string, unknown>>(
        "SHEETS_RAW", { seasons: answered.seasons });
      return {
        seasons: (shaped.seasons ?? []) as MediaSeasons["seasons"],
        owned: (answered.owned ?? {}) as MediaSeasons["owned"],
      } satisfies MediaSeasons;
    },
    enabled: provider !== "" && identifier !== "",
  });
}

/**
 * Crosses a season catalogue with what we hold, once.
 *
 * ONE DERIVATION PER QUESTION (§13). « How complete is this season » is asked on
 * the sheet, on the matrix and in the popover; the engine answered it in
 * `seasonsOf`, and this is that answer moved rather than a second one written.
 *
 * A CATALOGUE THAT ANNOUNCES NOTHING is not the same as one that announces
 * zero: `ep` absent means the provider never said how many aired, and the
 * interface draws « n owned » rather than « n of m ». And an owned number ABOVE
 * what aired is not counted — a provider that has announced ten cannot be
 * eleven-tenths complete.
 *
 * @param held What the layer answered.
 * @returns One entry per season: its number, what aired, and what we hold.
 */
export function seasonsHeld(held: MediaSeasons | undefined): [number, number | null, number][] {
  if (held === undefined) return [];
  const owned = held.owned ?? {};
  if (held.seasons.length) {
    return held.seasons.map((season) => {
      const numbers = owned[String(season.n)] ?? [];
      const aired = typeof season.ep === "number" ? season.ep : null;
      const own = aired ? numbers.filter((one) => one <= aired).length : numbers.length;
      return [season.n, aired, own];
    });
  }
  // No catalogue: the owned seasons are known, the totals are not.
  return Object.keys(owned)
    .map(Number)
    .sort((left, right) => left - right)
    .map((number) => [number, null, owned[String(number)].length]);
}
