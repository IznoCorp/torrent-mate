// Redrawing what the dying engine draws, when the data it reads arrives.
//
// WHY THIS IS NEEDED AT ALL, and it is a transitional thing with a date. A
// React surface re-renders when its query lands — that is the whole of what a
// query cache is for. A surface the ENGINE draws does not: `render()` writes
// markup once, from whatever the accessors answered at that instant, and an
// accessor reading a cache that has not answered yet answers empty.
//
// Measured: the discover deck drew 311.8 px where the reference holds 4 626.2 —
// an empty deck, because `applyState` runs before the suggestions land and
// nothing redrew afterwards.
//
// ONE SUBSCRIPTION RATHER THAN ONE PER SEAM. Every accessor the engine reads
// through has the same problem and the same answer, and writing the answer
// beside each of them would be writing it four times and forgetting it on the
// fifth. It goes with the engine at L13, and it goes in one line.
//
// IT REDRAWS ON A LANDING, never on every notification. A cache notifies for
// fetches starting, for observers attaching, for garbage collection; redrawing
// on all of that would put the engine's markup through a loop for every one of
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

/**
 * Asks the engine to redraw whenever a query it reads has new data.
 *
 * @param queryClient The cache the seams read.
 */
export function installEngineRedraw(queryClient: QueryClient): void {
  queryClient.getQueryCache().subscribe((event) => {
    if (event.type !== "updated") return;
    if (event.query.state.data === undefined) return;
    // THE ENGINE'S OWN REDRAW, through the reference it publishes. Optional for
    // the same reason `__startEngine` is: a document served without the
    // fragment must fail visibly at the boot, not silently here.
    window.__referentiel?.render?.();
  });
}
