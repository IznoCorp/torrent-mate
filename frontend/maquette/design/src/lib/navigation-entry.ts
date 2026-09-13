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
