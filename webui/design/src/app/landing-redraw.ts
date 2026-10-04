// Redrawing what React does not draw, when the data it reads arrives.
//
// WHY THIS IS NEEDED AT ALL. A React surface re-renders when its query lands —
// that is the whole of what a query cache is for. The discovery deck's content
// is not React's (`app/redraw.ts`: a replaced node cannot animate the gesture
// that spends it), so it is drawn once from whatever the cache answered at that
// instant, and a cache that has not answered yet answers empty.
//
// Measured: the discover deck drew 311.8 px where the reference held 4 626.2 —
// an empty deck, because `applyState` runs before the suggestions land and
// nothing redrew afterwards.
//
// IT WAS `engine-redraw.ts` while the engine drew those surfaces; the engine
// left at L13r, the deck's content is the last thing it answers for (B-543).
//
// IT REDRAWS ON A LANDING, never on every notification. A cache notifies for
// fetches starting, for observers attaching, for garbage collection; redrawing
// on all of that would put the deck's markup through a loop for every one of
// them. What matters here is a query that HAS data.
//
// AND IT DOES NOT DEDUPLICATE ON THE TIMESTAMP, which a first version did and
// which is invisible until it is fatal. `dataUpdatedAt` comes from `Date.now()`,
// and the ORACLE MEASURES UNDER A FROZEN CLOCK — every landing carries the same
// instant, so « skip what I have already seen » skipped every redraw after the
// first, and the discover deck measured at 311.8 px where the page really draws
// 4 497. The live page was right and the instrument saw an empty deck; a
// timestamp is not an identity when something is allowed to stop time.
import type { QueryClient } from "@tanstack/react-query";
import { redraw } from "../lib/shell-doors";

/**
 * Redraws the page whenever a query lands with new data.
 *
 * @param queryClient The cache the seams read.
 */
export function installLandingRedraw(queryClient: QueryClient): void {
  queryClient.getQueryCache().subscribe((event) => {
    if (event.type !== "updated") return;
    if (event.query.state.data === undefined) return;
    // THE PAGE'S REDRAW, through its door (`app/redraw.ts`).
    redraw();
  });
}
