// WHAT THE CACHE ALREADY KNOWS ABOUT AN ITEM, by the title a surface drew it under.
//
// A tap names a TITLE — a card's markup carries nothing else — and the screen it
// opens is addressed by PROVIDER IDENTITY (DOIT-11). Every card is drawn from a
// read that landed, and the list schemas declare `ids` and `poster`, so that read
// already holds the identity the tap needs. The crossing asks the cache, which is
// literally what the tap knew, rather than a table keyed by title.
//
// IT NAMES NO SUBJECT. It walks every cached answer for an object whose title is
// the one asked and which carries identifiers, and takes the first: the frame
// does not know which list the item came from, and must not.
import type { CarriedIdentity } from "./navigation-entry";
import { sharedQueryClient } from "./query-client";

/* How deep an answer is walked. A list is an array (1), or an array under one
   key of an envelope (2) — `{ items }`, `{ results }`, a bucket of a queue —
   and an item's own nested arrays (a cast, a season list) hold no identity
   worth reaching, so nothing deeper is read. */
const DEPTH = 3;

/**
 * Finds the first object under a value that is the titled item and carries ids.
 *
 * Args:
 *     value: A cached answer, or a part of one.
 *     title: The title asked, NFC-normalised.
 *     depth: How many more levels may be walked.
 *
 * Returns:
 *     What that object knows, or null.
 */
function found(value: unknown, title: string, depth: number): CarriedIdentity | null {
  if (value === null || typeof value !== "object" || depth < 0) return null;
  const candidates = Array.isArray(value) ? value : [value];
  for (const candidate of candidates) {
    if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) continue;
    const record = candidate as Record<string, unknown>;
    const named = record.t ?? record.title;
    if (
      typeof named === "string" &&
      named.normalize("NFC") === title &&
      record.ids !== null &&
      typeof record.ids === "object"
    ) {
      return {
        title: named,
        poster: typeof record.poster === "string" ? record.poster : null,
        ids: record.ids as CarriedIdentity["ids"],
      };
    }
  }
  for (const candidate of candidates) {
    if (candidate === null || typeof candidate !== "object") continue;
    for (const held of Object.values(candidate as Record<string, unknown>)) {
      if (held === null || typeof held !== "object") continue;
      const match = found(held, title, depth - 1);
      if (match !== null) return match;
    }
  }
  return null;
}

/**
 * What the cache holds about the item drawn under one title.
 *
 * Args:
 *     title: The title a surface drew the item under.
 *
 * Returns:
 *     Its title, poster and identifiers, or null when no landed read carries an
 *     item of that title with identifiers — §11's explicit case, a medium
 *     nobody has identified.
 */
export function heldIdentity(title: string): CarriedIdentity | null {
  if (sharedQueryClient === undefined) return null;
  const asked = title.normalize("NFC");
  for (const query of sharedQueryClient.getQueryCache().getAll()) {
    const match = found(query.state.data, asked, DEPTH);
    if (match !== null) return match;
  }
  return null;
}

/**
 * The address one set of provider identifiers is reached at.
 *
 * TVDB first, then TMDB — the order the sheet itself displays, so the address
 * and what it shows cannot drift apart.
 *
 * Args:
 *     ids: The provider identifiers, when there are any.
 *
 * Returns:
 *     The provider and its identifier, or null when neither provider is named.
 */
export function providerAddress(
  ids: Record<string, number | string> | null | undefined,
): { provider: string; id: string } | null {
  if (!ids) return null;
  if (ids.tvdb) return { provider: "tvdb", id: String(ids.tvdb) };
  if (ids.tmdb) return { provider: "tmdb", id: String(ids.tmdb) };
  return null;
}
