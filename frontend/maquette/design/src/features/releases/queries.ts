// What the release surfaces ask the server for.
//
// ONE RESOURCE, TWO READERS, AND THEY ARE ONE FEATURE. The release picker lists
// what a search turned up; the quality profile counts how many of the same
// releases a set of rules would keep. Both are `features/releases/`, so this
// stays here — the queue's move to `lib/` was forced by invariant 7 and is not
// a precedent for anything two surfaces of ONE feature share.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { Release } from "./reference";

/**
 * The releases a search turned up, for one title.
 *
 * THE TITLE IS IN THE KEY, and that is not a detail. Without it the picker
 * opened on « Ted Lasso », then on « Silo », and drew one list — the second
 * served from the cache with no request made, because two different questions
 * had the same key. A list that does not depend on what it is a list OF is not
 * a list.
 *
 * @param title The medium the releases are for. An empty title asks for all of
 *     them, which is what the quality profile counts against.
 * @returns The query, holding the releases in the engine's own shape.
 */
export function useReleases(title = "") {
  const parameters = new URLSearchParams(title === "" ? {} : { title });
  return useQuery({
    queryKey: ["/api/acquisition/releases", title],
    queryFn: async () =>
      toEngineShape<Release[]>(
        "RELEASES", await read("/api/acquisition/releases", parameters)),
  });
}

/**
 * Publishes the releases for the dying engine's « take » handler.
 *
 * It indexes into the list from a click handler that cannot await, the same
 * shape as the decision lookup and the deck's cards. It goes with the
 * delegation at L13.
 *
 * @param queryClient The cache the surfaces read.
 */
export function installReleasesLookup(queryClient: QueryClient): void {
  // WHICHEVER LIST IS IN FORCE. The engine indexes into « the releases on
  // screen », and since the key carries the title there is one entry per title
  // rather than one entry. The most recently answered is the one being looked
  // at — the same reading the redraw bridge takes, and for the same reason.
  window.__releases = () => {
    const answered = queryClient.getQueryCache().getAll()
      .filter((entry) => entry.queryKey[0] === "/api/acquisition/releases"
              && entry.state.data !== undefined)
      .sort((left, right) => right.state.dataUpdatedAt - left.state.dataUpdatedAt);
    return (answered[0]?.state.data as Release[] | undefined) ?? [];
  };
}

declare global {
  interface Window {
    /** The releases, read synchronously by the dying engine. */
    __releases?: () => Release[];
  }
}
