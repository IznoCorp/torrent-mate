// THE KEY THE LAYER ANSWERS A FOLLOW'S OPERATIONS BY (K3-G1, the operator's ruling O-1 A).
//
// `<provider>:<providerId>`, TVDB first for a show and TMDB first for a film: the
// medium's own identity, which addresses a medium followed or not and a removed
// follow. The layer reads it as a server does — from the records it holds — and
// keeps no copy of the interface's own reading (`lib/follow-key.ts`): two
// implementations of one rule are what lets a test of the pair catch either one
// being wrong.
import INCOMPLETE_SHOWS from "./seeds/incomplete-shows.json";
import { knownMedium } from "./handlers/media";
import { mockState } from "./state";
import type { components } from "../contract/types";

type Follow = components["schemas"]["Follow"];

/** The providers an identity is read at, in the order a show names them. */
const SHOW_ORDER = ["tvdb", "tmdb", "imdb"] as const;
/** And a film's. */
const FILM_ORDER = ["tmdb", "tvdb", "imdb"] as const;
const FILM = "movie";

/**
 * The key one medium is addressed by.
 *
 * @param medium Anything carrying provider identifiers and a kind: a follow, a card, a seeded show.
 * @returns `provider:providerId`, or null when the medium names no provider.
 */
export function keyOfMedium(medium: { ids?: unknown; kind?: string | null }): string | null {
  const ids = (medium.ids ?? {}) as Record<string, unknown>;
  for (const provider of medium.kind === FILM ? FILM_ORDER : SHOW_ORDER) {
    const held = ids[provider];
    if (held !== undefined && held !== null && String(held) !== "") return `${provider}:${String(held)}`;
  }
  return null;
}

/**
 * The follow one key names, among the follows the layer holds.
 *
 * @param key What the address carried.
 * @returns The follow, or undefined.
 */
export function followForKey(key: string): Follow | undefined {
  return mockState().follows.find((follow) => keyOfMedium(follow) === key);
}

/**
 * The follow one key names, among the ones removed and still restorable.
 *
 * @param key What the address carried.
 * @returns The position in `removedFollows`, or -1.
 */
export function removedIndexForKey(key: string): number {
  return mockState().removedFollows.findIndex((follow) => keyOfMedium(follow) === key);
}

/**
 * The medium one key names, followed or not.
 *
 * A FOLLOW FIRST, then what the queue holds, then the library's incomplete shows,
 * then what a sheet is known under: an acquisition is addressed by its medium
 * whether or not anyone follows it (a one-off season, a card), which is the whole
 * point of keying by identity.
 *
 * @param key What the address carried.
 * @returns Its title, and its follow when it has one; null when nothing known answers to the key.
 */
export function mediumOfKey(key: string): { title: string; follow?: Follow } | null {
  const follow = followForKey(key);
  if (follow !== undefined) return { title: follow.title, follow };
  const state = mockState();
  const card = [...state.takeable, ...state.blocked, ...state.inFlight, ...state.inFlightReel, ...state.moving]
    .find((one) => keyOfMedium(one) === key);
  if (card !== undefined) return { title: card.title };
  const incomplete = (INCOMPLETE_SHOWS as { title: string; ids: unknown; kind?: string }[])
    .find((one) => keyOfMedium({ ids: one.ids, kind: one.kind ?? "show" }) === key);
  if (incomplete !== undefined) return { title: incomplete.title };
  const cut = key.indexOf(":");
  if (cut <= 0) return null;
  const known = knownMedium({ [key.slice(0, cut)]: key.slice(cut + 1) });
  return known === null ? null : { title: known.title };
}
