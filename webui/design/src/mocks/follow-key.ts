// THE KEY THE LAYER ANSWERS A FOLLOW'S OPERATIONS BY (K3-G1, the operator's ruling O-1 A).
//
// `<provider>:<providerId>`, TVDB first for a show and TMDB first for a film: the
// medium's own identity, which addresses a medium followed or not and a removed
// follow. The layer reads it as a server does — from the records it holds — and
// keeps no copy of the interface's own reading (`lib/follow-key.ts`): two
// implementations of one rule are what lets a test of the pair catch either one
// being wrong.
import ACCOUNTS from "./seeds/accounts.json";
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

/** The cards of the queue, whatever stage they stand at. */
function queueCards(): { title: string; ids?: unknown; kind?: string | null }[] {
  const state = mockState();
  return [...state.takeable, ...state.blocked, ...state.inFlight, ...state.inFlightReel, ...state.moving];
}

/**
 * Whether an acquisition of one kind stands under a key, as a server holds them.
 *
 * A FOLLOW is a standing follow. A CARD is a follow too, or a card of the queue. A medium the
 * layer only knows a sheet of was asked for by nobody, so no acquisition answers to its key.
 *
 * @param kind What the key is said to name: `follow` or `card`.
 * @param key The medium's key.
 * @returns True when such an acquisition stands.
 */
export function acquisitionStands(kind: string, key: string): boolean {
  if (followForKey(key) !== undefined) return true;
  if (kind !== "card") return false;
  const drawn = new Set(titlesOfKey(key).map(withoutYear));
  return queueCards().some((card) => drawn.has(withoutYear(card.title)));
}

/**
 * Every title the layer holds one medium under: its follow's, and the ones its cards carry.
 *
 * A DATED TITLE AND A BARE ONE ARE ONE MEDIUM (« Silo (2023) », « Silo »), and the layer keeps
 * who asked for an acquisition under the title a row is drawn with. A server keeps it under the
 * medium, so an act addressed by the key reaches every row that medium is drawn as.
 *
 * @param key What the address carried.
 * @returns The titles, the follow's first when there is one; empty when nothing known answers to the key.
 */
export function titlesOfKey(key: string): string[] {
  const cards = queueCards();
  const known = [
    followForKey(key)?.title,
    ...cards.filter((one) => keyOfMedium(one) === key).map((one) => one.title),
    mediumOfKey(key)?.title,
  ].filter((title): title is string => title !== undefined);
  // A CARD THAT CARRIES NO IDENTITY OF ITS OWN is the same medium under its dated title, and so
  // is a title the accounts' requests are recorded under.
  const bare = new Set(known.map(withoutYear));
  const requested = Object.values(ACCOUNTS.requests as Record<string, string[]>).flat();
  const dated = [...cards.map((one) => one.title), ...requested].filter((title) => bare.has(withoutYear(title)));
  return [...new Set([...known, ...dated])];
}

/** A title without its trailing year: « Silo (2023) » and « Silo » name one medium. */
function withoutYear(title: string): string {
  return title.replace(/\s*\(\d{4}\)\s*$/, "");
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
  const card = queueCards().find((one) => keyOfMedium(one) === key);
  if (card !== undefined) return { title: card.title };
  const incomplete = (INCOMPLETE_SHOWS as { title: string; ids: unknown; kind?: string }[])
    .find((one) => keyOfMedium({ ids: one.ids, kind: one.kind ?? "show" }) === key);
  if (incomplete !== undefined) return { title: incomplete.title };
  const cut = key.indexOf(":");
  if (cut <= 0) return null;
  const known = knownMedium({ [key.slice(0, cut)]: key.slice(cut + 1) });
  return known === null ? null : { title: known.title };
}
