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
import { currentEntryState } from "../../lib/navigate";
import { carriedBy } from "../../lib/navigation-entry";
import { seasonsHeld, seasonsQuery, type SeasonsAnswer } from "../../lib/season-rows";

/** One sheet, as the layer composes it. */
export type MediaSheetPayload = Record<string, unknown>;

/** What the seasons read answers — written once, in `lib/season-rows.ts`. */
export type MediaSeasons = SeasonsAnswer;
export { seasonsHeld };

/**
 * What the current entry carries about the sheet at one address.
 *
 * ONLY WHEN IT IS ABOUT THIS ADDRESS. An entry opened on one medium must not
 * prime a read about another, which a panel over the screen can issue.
 *
 * @param provider The provider, as the address names it.
 * @param identifier The identifier at that provider.
 * @returns What the tap knew, in the sheet's own names, or undefined.
 */
export function carriedSheet(provider: string, identifier: string): MediaSheetPayload | undefined {
  const carried = carriedBy(currentEntryState());
  const ids = carried?.ids as Record<string, unknown> | null | undefined;
  if (carried === undefined || !ids || String(ids[provider] ?? "") !== identifier) return undefined;
  return { ...carried };
}

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
  // WHAT THE TAP KNEW TRAVELS ON THE ENTRY. The item a card is drawn from carries
  // its title, its poster and its provider identity; the crossing writes those
  // three onto the navigation entry, and this reads them back — so a Back or a
  // reload onto the entry primes the same way the tap did. An address typed or
  // pasted carries nothing, and the screen then waits for its read with no
  // placeholder at all: its ids are the address, its title a skeleton.
  //
  // `placeholderData`, not `initialData`: initial data is written INTO the cache
  // and would be indistinguishable from a served answer forever after — a
  // screen that never enriched would look identical to one that did. Placeholder
  // data stays outside the cache and is flagged `isPlaceholderData`, which is
  // what lets a rule tell PRIMED content from SERVED content. A rule that cannot
  // is green on a screen that never enriches.
  return useQuery({
    queryKey: ["/api/media", provider, identifier],
    placeholderData: () => carriedSheet(provider, identifier),
    queryFn: async () => {
      const answered = await read<MediaSheetPayload | null>(
        `/api/media/${encodeURIComponent(provider)}/${encodeURIComponent(identifier)}`);
      return answered;
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
    ...seasonsQuery(provider, identifier),
    enabled: provider !== "" && identifier !== "",
  });
}

/**
 * The episode numbers held of one season, as the seasons read answered them.
 *
 * NULL WHEN THE LIBRARY KNOWS NOTHING OF THE SERIES: an answer naming no season
 * at all claims nothing, and the caller falls back to the count. A series the
 * library knows but whose season it holds nothing of is an EMPTY set, which is
 * a claim — every episode of that season is missing.
 *
 * @param owned The seasons read's `owned` answer, when it has landed.
 * @param season The season number.
 * @returns The held numbers, or null.
 */
export function ownedSeason(
  owned: MediaSeasons["owned"] | undefined,
  season: number,
): Set<number> | null {
  if (owned === undefined || Object.keys(owned).length === 0) return null;
  return new Set(owned[String(season)] ?? []);
}

/**
 * The dates of a season's episodes announced after today, earliest first.
 *
 * What has not aired is INFORMATION: it cannot be held, so it is never counted
 * missing and offers no act — the sheet draws it beside the fraction (B-380).
 *
 * @param episodes The season's episode list, when the sheet has one.
 * @param today The referential's today.
 * @returns The announced dates, sorted.
 */
export function announcedAfter(
  episodes: { airDate?: string | null }[] | null,
  today: string,
): string[] {
  return (episodes ?? [])
    .map((episode) => episode.airDate)
    .filter((air): air is string => Boolean(air) && String(air) > today)
    .sort();
}

