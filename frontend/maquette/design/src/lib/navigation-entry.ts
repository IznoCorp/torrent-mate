// THE SHAPE OF A NAVIGATION ENTRY — what a page's entry carries in history.
//
// EVERY dial the address model declares travels on the entry, and that is the
// whole of the list: a dial left off is one a back cannot put back, so the
// address loses it while the interface keeps showing it — measured on
// `maintTopic`, which was the one missing.
//
// A pure read of the store, and it lives here rather than beside the page
// switch because four parties write an entry of this shape — the page switch,
// the boot, the sign-in gate and the rubric verbs — and one shape written from
// four places is the seam, not any one of them.
import { store } from "./store-access";

/* The dials an entry carries beside its page, in the order it writes them —
   written ONCE, because the entry is written in one place and read back in
   another, and two lists of one fact are one list waiting to lose a member. */
const ENTRY_DIALS = ["acqTab", "libLens", "libMode", "libCat", "maintTopic"] as const;

/* WHAT A TAP KNEW about the item it opened, and nothing else: its title, its
   poster and its provider identity. The screen it opens reads them while its own
   read is out, so the first frame draws what the finger was on.

   THREE FIELDS AND NEVER A BODY. An entry's state lives in the browser's
   history, which has a size ceiling of its own — a whole sheet written there is
   an entry a browser may refuse. So the writer below copies exactly these three,
   whatever the object handed to it carries, and a rule reads that it did.

   Carried under ONE key, so a pop that reads the page's dials never mistakes
   them for a dial, and so the three travel or go missing together. */
export const CARRIED_KEY = "carried";
const CARRIED_FIELDS = ["title", "poster", "ids"] as const;

/** What a tap knew: a title, a poster address or null, and the provider identifiers. */
export type CarriedIdentity = {
  title: string;
  poster: string | null;
  ids: Record<string, number | string>;
};

/**
 * The state an entry carries for an arrival that knows what it opened.
 *
 * Args:
 *     known: What the tap knew. Only its three carried fields are copied.
 *
 * Returns:
 *     The state to write on the entry.
 */
export function carryingState(known: CarriedIdentity): Record<string, unknown> {
  return {
    [CARRIED_KEY]: Object.fromEntries(
      CARRIED_FIELDS.map((field) => [field, known[field] ?? null]),
    ),
  };
}

/**
 * What an entry carries about the item it was opened on, if anything.
 *
 * Args:
 *     state: An entry's state, as the history holds it.
 *
 * Returns:
 *     The carried fields, or undefined for an entry no tap wrote — an address
 *     typed, pasted or restored from a bookmark.
 */
export function carriedBy(state: unknown): Record<string, unknown> | undefined {
  const held = (state as Record<string, unknown> | null | undefined)?.[CARRIED_KEY];
  return held !== null && typeof held === "object" ? (held as Record<string, unknown>) : undefined;
}

/**
 * The page and the dials an entry carries, read off any object that holds them.
 *
 * Args:
 *     holder: The store's state when an entry is written, or the entry itself
 *         when a Back restores the page it names.
 *
 * Returns:
 *     The page, then every dial, each present even when it holds nothing.
 */
export function entryPatch(holder: Record<string, unknown>): Record<string, unknown> {
  return {
    page: holder.page,
    ...Object.fromEntries(ENTRY_DIALS.map((dial) => [dial, holder[dial]])),
  };
}

/**
 * The state a navigation entry carries, read from the store now.
 *
 * Returns:
 *     The entry's marker and every dial the address model declares.
 */
export function navigationState(): Record<string, unknown> {
  return { tm: "nav", ...entryPatch(store.read().state) };
}
