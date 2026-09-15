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
import { queueKey, stagingKey } from "../lib/queue";
import { store } from "../lib/store-access";
import { refillSuggestions } from "../features/acquisition/queries";
import { refillProducers } from "./panel-host";

/** What the engine reads with no component to ask for it.
 *
 * IT SHRINKS AS THE PRODUCERS MOVE. Every entry here existed because a
 * surface the engine DRAWS asked through a synchronous accessor and no
 * component wanted the resource on that address. A producer that has moved into
 * its feature declares what it needs beside itself
 * (`registerProducer`'s `needs`), so its family leaves this list rather than
 * being asked for twice. `MAINT_ACTIONS` left with the maintenance panel.
 */
const NEEDED = [
  {
    key: ["/api/acquisition/followed"],
    address: "/api/acquisition/followed",
  },
] as const;

/** Re-asks for what the engine reads and no component observes — filled at install. */
export let refillEngineData: (() => void) | undefined;

/**
 * Installs the door that asks for what the engine reads.
 *
 * @param queryClient The cache the accessors read.
 */
export function installEngineData(queryClient: QueryClient): void {
  refillEngineData = () => {
    for (const { key, address } of NEEDED) {
      void queryClient.prefetchQuery({
        queryKey: key,
        queryFn: async () => read(address),
      });
    }
    // THE QUEUE, in whichever world is in force. The engine's nav badges and
    // its journey panel read it, and neither is a component.
    const scenario =
      String(store?.read().state.scen ?? "") === "loaded" ? "loaded" : "";
    const parameters = new URLSearchParams(scenario ? { scenario } : {});
    void queryClient.prefetchQuery({
      queryKey: stagingKey(scenario),
      queryFn: async () => {
        const answer = await read<Record<string, unknown[]>>(
          "/api/staging/media", parameters);
        return {
          stuck: answer.stuck,
          moving: answer.moving,
          settled: answer.settled,
        };
      },
    });
    void queryClient.prefetchQuery({
      queryKey: queueKey(scenario),
      queryFn: async () => {
        const answer = await read<Record<string, unknown[]>>(
          "/api/acquisition/to-handle", parameters);
        return {
          takeable: answer.takeable,
          blocked: answer.blocked,
          inFlight: answer.inFlight,
          notFound: answer.notFound,
          doneToday: answer.doneToday,
        };
      },
    });
    refillSuggestions?.();
    // AND WHAT THE MOVED PRODUCERS READ. A producer is called from a click and
    // cannot await, so its reads are asked for here with the rest — beside the
    // list this file exists to hold rather than inside it, because a producer
    // that has moved declares its own needs and this file is the one that dies.
    refillProducers?.();
  };
  refillEngineData();
}
