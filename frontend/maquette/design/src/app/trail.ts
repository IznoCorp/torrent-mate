// THE TRAIL, READ AND WRITTEN — the pages under the one drawn, from the floor
// up, as every entry carries them (`lib/navigation-entry.ts`, TRAIL_KEY).
//
// The page switch (`app/page-switch.ts`) decides WHICH trail a switch leaves;
// this module reads the one standing and writes a new one's entries. The
// traversal down to where the writes start is the switch's, because the latch
// that fires the writes once it lands is.
import { addressSeam } from "../lib/addresses";
import { entryIndex, entryPatch, trailOf, TRAIL_KEY, type TrailStop } from "../lib/navigation-entry";
import { bridge } from "../lib/shell-doors";
import { store } from "../lib/store-access";

/** The history index of the entry one stands on now. */
export function standingIndex(): number {
  return entryIndex(history.state);
}

/**
 * The trail under the page being left, read off the entry one stands on.
 *
 * A DRIVEN state writes no history, so the entry may name another page than the
 * one drawn: the top of the trail is then the page drawn, at the same index.
 *
 * Args:
 *     leaving: The page the interface was on.
 *
 * Returns:
 *     The stops, floor first.
 */
export function standingTrail(leaving: string): TrailStop[] {
  const trail = trailOf(history.state, addressSeam.homePage, leaving);
  const top = trail[trail.length - 1];
  if (top.page !== leaving && trail.length > 1)
    return [...trail.slice(0, -1), { page: leaving, at: top.at }];
  return trail;
}

/**
 * Writes the entries of a trail from one history index up, where one stands now.
 *
 * The entry at `from` is REPLACED and every page after it PUSHED, so what lay
 * above `from` is gone and a Retour walks the trail back. Each page's entry
 * carries the dials the store holds now — the ones it is drawn with when a
 * Retour gives it back.
 *
 * Args:
 *     kept: The stops left as they are, floor first.
 *     pages: The pages to write above them, the arriving one last.
 *     from: The history index the first of `pages` is written at.
 *
 * Returns:
 *     Whether every entry was written.
 */
export function writeTrail(kept: TrailStop[], pages: string[], from: number): boolean {
  try {
    let trail = kept;
    pages.forEach((page, offset) => {
      const at = from + offset;
      trail = [...trail, { page, at }];
      const holder = { ...store.read().state, page };
      const state = { tm: "nav", ...entryPatch(holder), [TRAIL_KEY]: trail };
      if (at <= standingIndex()) bridge.replace(state, addressSeam.compose(holder));
      else bridge.record(state, addressSeam.compose(holder));
    });
    return true;
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error("writeTrail: writing the navigation failed", error);
    window.__navEchec = true;
    return false;
  }
}
