// THE KEY A FOLLOW IS ADDRESSED BY (K3-G1, the operator's ruling O-1 A).
//
// Every operation that names a follow — its pause, its quality, its search, its
// grab, its completeness, a season of it — carries `<provider>:<providerId>` in
// its path: the medium's own identity, TVDB first for a show and TMDB first for
// a film. It names a medium followed or not, and a removed follow; a title does
// neither (two media may share one), and the contract refuses it.
//
// A SURFACE HOLDS A TITLE as often as a follow: a card's markup, a panel's
// subject and a verb's value carry nothing else. The title is crossed to the key
// at the act's door, here, from what the cache already knows (a follow, then any
// landed answer carrying the identity) and from the follows' own read otherwise.
import { heldIdentity } from "./held-identity";
import { mediaRefOf, refKey } from "./membership";
import { read } from "./query-client";
import { baseTitle } from "./titles";
import type { Schemas } from "./contract-schemas";

/** The follows' own read — the address every list of follows is cached under. */
const FOLLOWS_ADDRESS = "/api/v1/acquisition/followed";

/**
 * The key one medium is addressed by in a follow's operations.
 *
 * @param medium Anything carrying the medium's provider identifiers and its kind: a follow, a card.
 * @returns `provider:providerId`, or null when the medium names no provider.
 */
export function followKeyOf(medium: { ids?: Record<string, number | string> | null; kind?: string | null }): string | null {
  const ref = mediaRefOf(medium.ids, medium.kind);
  return ref === null ? null : refKey(ref);
}

/**
 * The path segment a key travels in: its colon is encoded, as any reserved character.
 *
 * @param key The follow's key.
 * @returns The encoded segment.
 */
export function followSegment(key: string): string {
  return encodeURIComponent(key);
}

/**
 * The key of the medium one title names.
 *
 * THE CACHE FIRST, because the surface that drew the title drew it from a read
 * that landed and that read carries the identity; the follows' read otherwise (a
 * panel opened from an address, before any list has landed). A title no read
 * identifies has no key, and the act that needed it does not leave.
 *
 * @param title The title a surface drew the medium under.
 * @returns `provider:providerId`, or null when nothing identifies that title.
 */
export async function followKeyOfTitle(title: string): Promise<string | null> {
  const held = heldIdentity(title);
  const cached = held === null ? null : followKeyOf(held);
  if (cached !== null) return cached;
  const base = baseTitle(title);
  const follows = await read<Schemas["Follow"][]>(FOLLOWS_ADDRESS);
  const follow = follows.find((one) => one.title === title) ?? follows.find((one) => baseTitle(one.title) === base);
  return follow === undefined ? null : followKeyOf(follow);
}
