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
import { useMediaReference } from "./reference";

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
  // OPTIMISTIC PRIMING — « A généralisée + amorçage optimiste » (operator,
  // 2026-08-31), which is the optimistic-answer property's discipline applied to an ARRIVAL: the screen
  // opens with what the tap already knows, in real content, on the first frame.
  // A dead tap becomes impossible by construction rather than by being fast.
  //
  // THE MECHANISM IS NOT THE ONE SUGGESTED, AND THE DIFFERENCE IS A FACT RATHER
  // THAN A PREFERENCE. The relay proposed seeding from the list's query cache,
  // « ces faits sont déjà dans le cache de requêtes de la liste ». They are not:
  // a `LibraryRow` is `{ t, f }` — a title and a folder — and the year, the type
  // and the poster the tapped card DISPLAYED come from the engine's own
  // projection, keyed by title. So the priming reads THAT, which is literally
  // the source the card drew from, and therefore literally what the tap knows.
  // (The operator invited a better mechanism if one was seen: this is it.)
  //
  // `placeholderData`, not `initialData`: initial data is written INTO the cache
  // and would be indistinguishable from a served answer forever after — a
  // screen that never enriched would look identical to one that did. Placeholder
  // data stays outside the cache and is flagged `isPlaceholderData`, which is
  // what lets a rule tell PRIMED content from SERVED content. A rule that cannot
  // is green on a screen that never enriches.
  const reference = useMediaReference();
  return useQuery({
    queryKey: ["/api/media", provider, identifier],
    placeholderData: () => {
      const title = reference.titleForProviderId(provider, identifier);
      if (!title) return undefined;
      return (reference.sheetFor(title) ?? undefined) as
        MediaSheetPayload | undefined;
    },
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
