// What the dying engine reads, asked for by the frame.
//
// WHY THIS EXISTS, and it is the cost of an engine that draws. A React surface
// asks for what it draws: mount the deck and its follows are fetched. The engine
// draws too — its nav badges, its addressed-panel validation, its discover deck
// — and it asks through SYNCHRONOUS accessors over the cache, which answer empty
// until something has filled it. Nothing had: no component was mounted that
// wanted those resources on that address.
//
// Measured: a cold load at `/acquisition?panel=follow:Silo` refused the panel
// and cleaned the address, because the follows had never been asked for. The
// address was right, the subject was real, and the interface said it held
// nothing.
//
// IT IS ONE LIST, IN ONE PLACE. Writing the prefetch beside each accessor is
// writing it four times and forgetting it on the fifth, and the fifth is the one
// that fails on an address nobody tests.
//
// IT IS RE-ASKED AFTER A RESET, because a named state clears the cache so no
// measurement inherits a previous one's pages — and a query with an OBSERVER is
// re-asked by that observer while one without is not. These have none.
//
// It goes with the engine at L13, and it goes in one file.
import type { QueryClient } from "@tanstack/react-query";
import { read } from "../lib/query-client";
import { toEngineShape } from "../engine/engine-shape";
import { queueKey, stagingKey } from "../lib/queue";

/** What the engine reads with no component to ask for it. */
const NEEDED = [
  {
    key: ["/api/acquisition/followed"],
    address: "/api/acquisition/followed",
    family: "FOLLOWS",
  },
  {
    key: ["/api/maintenance/actions"],
    address: "/api/maintenance/actions",
    family: "MAINT_ACTIONS",
  },
] as const;

/**
 * Installs the door that asks for what the engine reads.
 *
 * @param queryClient The cache the accessors read.
 */
export function installEngineData(queryClient: QueryClient): void {
  window.__refillEngineData = () => {
    for (const { key, address, family } of NEEDED) {
      void queryClient.prefetchQuery({
        queryKey: key,
        queryFn: async () => toEngineShape<unknown>(family, await read(address)),
      });
    }
    // THE QUEUE, in whichever world is in force. The engine's nav badges and
    // its journey panel read it, and neither is a component.
    const scenario =
      String(window.__store?.read().state.scen ?? "") === "loaded" ? "loaded" : "";
    const parameters = new URLSearchParams(scenario ? { scenario } : {});
    void queryClient.prefetchQuery({
      queryKey: stagingKey(scenario),
      queryFn: async () => {
        const answer = await read<Record<string, unknown[]>>(
          "/api/staging/media", parameters);
        return {
          stuck: toEngineShape("STUCK_REAL", answer.stuck),
          moving: toEngineShape("MOVING", answer.moving),
          settled: toEngineShape("SETTLED_REAL", answer.settled),
        };
      },
    });
    void queryClient.prefetchQuery({
      queryKey: queueKey(scenario),
      queryFn: async () => {
        const answer = await read<Record<string, unknown[]>>(
          "/api/acquisition/to-handle", parameters);
        return {
          takeable: toEngineShape("TAKEABLE", answer.takeable),
          blocked: toEngineShape("BLOCKED", answer.blocked),
          inFlight: toEngineShape("INFLIGHT", answer.inFlight),
          notFound: toEngineShape("NOTFOUND_REAL", answer.notFound),
          doneToday: toEngineShape("DONE_TODAY", answer.doneToday),
        };
      },
    });
    window.__refillSuggestions?.();
  };
  window.__refillEngineData();
}

declare global {
  interface Window {
    /** Re-asks for what the engine reads and no component observes. */
    __refillEngineData?: () => void;
    /** The discover deck's own reserve, asked for by its feature. */
    __refillSuggestions?: () => void;
  }
}
