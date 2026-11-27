// What the release surfaces ask the server for.
//
// ONE RESOURCE, TWO READERS, AND THEY ARE ONE FEATURE. The release picker lists
// what a search turned up; the quality profile counts how many of the same
// releases a set of rules would keep. Both are `features/releases/`, so this
// stays here — the queue's move to `lib/` was forced by invariant 7 and is not
// a precedent for anything two surfaces of ONE feature share.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { followKeyOfTitle } from "../../lib/follow-key";
import { baseTitle } from "../../lib/titles";
import type { Release } from "./types";

/** The cache key of one title's releases; the empty title is the list of every release. */
const releasesKey = (title: string) => ["/api/v1/acquisition/releases", title];

/**
 * The releases a search turned up, for one title.
 *
 * THE TITLE IS IN THE KEY, and that is not a detail. Without it the picker
 * opened on « Ted Lasso », then on « Silo », and drew one list — the second
 * served from the cache with no request made, because two different questions
 * had the same key. A list that does not depend on what it is a list OF is not
 * a list.
 *
 * THE READ IS ADDRESSED BY THE MEDIUM'S KEY (K3-G5), crossed from the title at
 * the door; a title nothing identifies has no releases to ask for.
 *
 * @param title The medium the releases are for. An empty title asks for all of
 *     them, which is what the quality profile counts against.
 * @returns The query, holding the releases in the engine's own shape.
 */
export function useReleases(title = "") {
  return useQuery({
    queryKey: releasesKey(title),
    queryFn: async () => {
      const key = title === "" ? null : await followKeyOfTitle(title);
      if (title !== "" && key === null) return [] as Release[];
      return read<Release[]>("/api/v1/acquisition/releases", new URLSearchParams(key === null ? {} : { followedId: key }));
    },
  });
}

/**
 * Publishes the releases for the dying engine's « take » handler.
 *
 * It indexes into the list from a click handler that cannot await, the same
 * shape as the decision lookup and the deck's cards. It goes with the
 * delegation at L13.
 *
 * THE LIST IS ASKED BY THE TITLE ON SCREEN, never taken as the one answered
 * last: a settled search reads every cached list again, and the last to answer
 * may be another title's, or the one counting every release. A row's index read
 * against it takes a release the person never saw (O-14).
 *
 * @param queryClient The cache the surfaces read.
 */
export function installReleasesLookup(queryClient: QueryClient): void {
  releases = (title) => queryClient.getQueryData<Release[]>(releasesKey(baseTitle(title))) ?? [];
}

declare global {
  interface Window {
    /** One title's releases, read synchronously by the dying engine. */
    __releases?: (title: string) => Release[];
  }
}

/** One title's releases, as its picker draws them — filled at install. */
export let releases: Window["__releases"];
