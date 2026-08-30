// Where the offline queue is joined to everything it may not import.
//
// THE QUEUE KNOWS NOTHING, ON PURPOSE (MODEL Part 13): not what a mutation
// means, not that there is a query cache, not that there is a socket. Every one
// of those facts has to reach it from somewhere, and this is that somewhere —
// the same job `shell.tsx` does for the rest of the boot, in its own file
// because it is its own subject and `shell.tsx` owns WHEN rather than WHAT.
//
// FOUR JOINS, and each names the thing the outbox is forbidden to know:
//
//   THE CACHE — what a departed envelope made stale. Matched on the ADDRESS and
//       never on a domain: a query key in this tree IS an address, so comparing
//       one to the other is a string comparison and not a subject.
//   THE RELAY — the connection coming back, which `online` cannot answer: the
//       browser fires that for the network INTERFACE, not for a server becoming
//       reachable, and the outage this queue is for is most often the second.
//   THE HARNESS — a driving seam, read by rules and never by a component.
//   THE MOCK LAYER'S RESET — because the outbox is IndexedDB and survives it.
import { readCondition, subscribeToCondition } from "../lib/relay-condition";
import { HELD, send } from "../lib/query-client";
import type { QueryClient } from "@tanstack/react-query";
import {
  departOnReconnection,
  forgetOutbox,
  installOutbox,
  publishOutboxSeam,
  setRefresh,
} from "./outbox";

/**
 * Joins the outbox to the cache, the relay, the harness and the mock layer.
 *
 * @param queryClient The cache a departed envelope makes stale.
 */
export function installOutboxWiring(queryClient: QueryClient): void {
  // WHAT A DEPARTED ENVELOPE MAKES STALE, and why anything must. The optimistic
  // write that made the mutation visible lived in the PREVIOUS document's cache
  // and did not survive the reload; the cache this document booted with holds
  // pre-mutation server state, with `staleTime: Infinity`, no refetch on focus
  // and none on reconnect. Without this the queue empties, the notice says
  // everything has been sent, and the screen goes on showing the opposite of
  // what the server holds for the life of the process.
  setRefresh((path) => {
    void queryClient.invalidateQueries({
      predicate: (query) => {
        const key = query.queryKey[0];
        return typeof key === "string"
          && (path === key || path.startsWith(`${key}/`));
      },
    });
  });
  installOutbox();
  departOnReconnection(subscribeToCondition, readCondition);
  publishOutboxSeam(async (method, path, body) => {
    const answer = await send(method as "POST", path, body);
    // The seam answers what `send` answered, sentinel included: a rule that
    // could not tell « held » from « no body » would be a rule that cannot
    // measure the one behaviour this queue is about.
    return answer === HELD ? "held" : answer;
  });

  // ONE ENVELOPE LEFT BEHIND BY AN EARLIER SCENARIO puts `data-pending` on the
  // connection mark AND renders the notice — a bar with its own height — into
  // every state measured after it, attributed to whichever state was being
  // measured. `reset()` returns the world to its seeds and clears the
  // applied-key ledger; the outbox is IndexedDB and survives both.
  const mocks = globalThis.window.__mocks;
  if (mocks) {
    const resetTheWorld = mocks.reset;
    mocks.reset = () => {
      resetTheWorld();
      void forgetOutbox();
    };
  }
}
