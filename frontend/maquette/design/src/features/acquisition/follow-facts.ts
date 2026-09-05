// WHAT IS TRUE ABOUT ONE MEDIUM, gathered once.
//
// The follow panel's every action is derived from these facts and nothing else
// — never from the screen the panel was opened from. That is what makes the
// panel THE SAME OBJECT everywhere, instead of a family of look-alikes, and it
// is the sentence the engine's producer carried at the top of its own body.
//
// SPLIT OUT OF THE PRODUCER on a SUBJECT rather than on a line count
// — the answer this repository has now taken three times: what is true about a
// medium is one question, and what the panel OFFERS about it is another.
//
// READ FROM THE SAME DERIVATIONS the urgency sections read. A section that
// computes what is to be grabbed while the panel computes it separately is two
// answers to one question, and they part company on the first change (§13).
import { queueNow } from "../../lib/queue";
import type { PanelCache } from "../../ui/panel/contract";
import { followsQuery } from "./queries";

declare global {
  interface Window {
    /**
     * The library's rows and the season catalogue, as the dying engine
     * publishes them for the harness to drive through.
     *
     * READ HERE AND NOT THROUGH THE REFERENCE, because the reference does not
     * carry them and ADDING to it would be adding to the engine — which D5
     * forbids outside a defect that destroys data. They are the same objects
     * the engine's own producer read; both die with it.
     */
    LIBRARY: { t: string }[];
    SEASONS: Record<string, [number, number, number][]>;
  }
}

// THE FEATURE'S OWN RECORD, not a looser copy of it. A slice declared here
// would be a second shape of one thing, and the vocabulary the panel hands on —
// `stLabel`, `ST_TONE`, the seasons block — is typed against the real one. The
// fallback below therefore fills every required field rather than leaving them
// undefined, which is what the engine's object literal did in practice.
import type { Follow } from "./reference";
export type { Follow };

/** What is true about the medium a follow panel is about. */
export type FollowFacts = {
  follow: Follow;
  seasons: [number, number, number][];
  isFilm: boolean;
  /** In the library and missing episodes. */
  incomplete: boolean;
  /** Watched: something is looking for it. */
  isFollowed: boolean;
  inLibrary: boolean;
  /** Waiting to be taken. */
  toTake: boolean;
  /** Waiting for the operator to resolve it. */
  toResolve: boolean;
  /** It has a media sheet — an unidentified release has none. */
  hasSheet: boolean;
  /** Episodes held over episodes aired, or null for a film. */
  fraction: string | null;
};

/**
 * Gathers what is true about one medium.
 *
 * THE FALLBACK CHAIN IS THE ENGINE'S, unchanged: a follow if one is watched, an
 * incomplete series if the library holds one with holes, and otherwise a
 * synthetic record saying the medium is up to date. A panel opened about a
 * medium nobody follows still has facts to state.
 *
 * Args:
 *     title: The medium.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The facts, or null while the follows have not landed — the one read this
 *     panel cannot draw without.
 */
export function followFacts(title: string, cache: PanelCache): FollowFacts | null {
  const followed = cache.held<Follow[]>(followsQuery.queryKey);
  if (followed === undefined) return null;
  const reference = window.__referentiel;
  const incompleteShows = reference.INCOMPLETE as {
    t: string; o: number; a: number;
  }[];
  const follow: Follow =
    followed.find((one) => one.t === title) ??
    incompleteShows
      .map((show) => ({
        t: show.t, k: "show", y: "", st: "to_grab", own: show.o, aired: show.a,
      }))
      .find((one) => one.t === title) ??
    { t: title, k: "show", y: "", st: "up_to_date" };
  const seasons = (window.SEASONS[title] ?? [])
    .slice()
    .sort((one, other) => other[0] - one[0]);
  const isFilm = follow.k === "movie";
  const incomplete = incompleteShows.some((show) => show.t === title);
  const isFollowed = followed.some((one) => one.t === title);
  const inLibrary =
    incomplete || window.LIBRARY.some((row) => row.t === title);
  const queue = queueNow();
  const toTake = queue.takeable.some((one) => one.t === title);
  const toResolve = queue.blocked
    .concat(queue.stuck ?? [])
    .some((one) => one.t === title);
  const held = seasons.reduce((total, season) => total + season[2], 0);
  const aired = seasons.reduce((total, season) => total + season[1], 0);
  return {
    follow,
    seasons,
    isFilm,
    incomplete,
    isFollowed,
    inLibrary,
    toTake,
    toResolve,
    hasSheet: reference.sheetFor(title) != null,
    // ONE DERIVATION: the card's fraction, the header's, and the sum of the
    // season headers all read this computation.
    fraction: isFilm
      ? null
      : seasons.length
        ? `${held}/${aired}`
        : (reference.stFraction(follow) ?? "—"),
  };
}
