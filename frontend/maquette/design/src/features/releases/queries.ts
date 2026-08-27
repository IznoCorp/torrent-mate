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

/** The releases a search turned up. */
export function useReleases() {
  return useQuery({
    queryKey: ["/api/acquisition/releases"],
    queryFn: async () =>
      toEngineShape<Release[]>("RELEASES", await read("/api/acquisition/releases")),
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
  window.__releases = () =>
    (queryClient.getQueryData(["/api/acquisition/releases"]) as Release[] | undefined) ?? [];
}

declare global {
  interface Window {
    /** The releases, read synchronously by the dying engine. */
    __releases?: () => Release[];
  }
}
