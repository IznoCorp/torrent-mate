// What the add screen asks the provider for.
//
// IT IS ITS OWN FILE because it is its own subject: the deck's reserve and the
// operator's follows answer « what should I take »; this answers « what exists
// under this name », which is a provider's question and not the queue's.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { SearchResults } from "./reference";

/**
 * What a provider answers for one search.
 *
 * THE QUERY IS PART OF THE KEY, so typing asks a different question rather than
 * overwriting the answer to the previous one — and the cache can still hold the
 * previous answer while the new one is in flight, which is what stops the
 * results blanking between keystrokes.
 *
 * @param query What is being searched for.
 * @returns The query, its results already in the engine's names.
 */
export function useProviderSearch(query: string) {
  return useQuery({
    queryKey: ["/api/acquisition/search", query],
    queryFn: async () => {
      const parameters = new URLSearchParams(query ? { query } : {});
      return toEngineShape<SearchResults>(
        "SEARCH", await read("/api/acquisition/search", parameters));
    },
  });
}

/**
 * Publishes the current search results for the dying engine's « add » handler.
 *
 * It indexes into the results from a click handler that cannot await. Which
 * search is CURRENT is read off the store, the same field the screen composes
 * its own query from — two derivations of one question is what §13 forbids.
 *
 * @param queryClient The cache the surface reads.
 */
export function installSearchLookup(queryClient: QueryClient): void {
  window.__searchResults = () => {
    // THE ROUTER'S OWN `q`, read the way the screen reads it. `state.addQ` is
    // the ENTRY query and is stale the moment the operator types; two readings
    // of one question is what §13 forbids, and here it would have the engine's
    // « add » handler index into a different result set from the one on screen.
    const asked = new URLSearchParams(window.location.search).get("q") ?? "";
    return (
      (queryClient.getQueryData(["/api/acquisition/search", asked]) as SearchResults | undefined)
      ?? { total: 0, shown: 0, results: [] }
    );
  };
}

declare global {
  interface Window {
    /** What the current search turned up, read synchronously by the engine. */
    __searchResults?: () => SearchResults;
  }
}
