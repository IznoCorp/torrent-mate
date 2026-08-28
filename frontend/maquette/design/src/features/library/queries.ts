// What the Médiathèque asks the server for.
//
// THE LISTING IS PAGED BY THE SERVER, and the ORDER is part of the question.
// The interface used to hold the whole filtered set and sort it itself, which is
// the only arrangement under which a page index means nothing: a page of an
// unsorted set, sorted afterwards, is a page of the wrong rows. The order moved
// to the layer that pages it, and `sort` / `reversed` are declared in the
// contract.
//
// FOUR SERVER-STATE KEYS LEAVE WITH THIS (invariant 4). `libCount` was a page
// cursor, `libLoading` and `libErr` were query state, and `libFailedOnce`
// remembered whether the simulated failure had already fired. All four lived in
// the interface's own store; the cache owns every one of them now.
import { useInfiniteQuery, useQuery, type QueryClient } from "@tanstack/react-query";
import { read, send } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { IncompleteShow, LibraryCategory, LibraryRow } from "./reference";

/** One page of the listing: the rows, and how many there are in all. */
export type LibraryPage = {
  /** What the library claims, or the size of the result set when filtered. */
  total: number;
  /** How many rows this question matches — the set a page is a page OF. */
  matching: number;
  /** What the source really holds, whatever is filtered for. */
  loaded: number;
  items: LibraryRow[];
};

/**
 * The listing, one page at a time, in the order the interface asks for.
 *
 * THE KEY CARRIES THE WHOLE QUESTION. A key that left the order out would serve
 * a page of the previous order the moment a sort changed — the cache would be
 * right about what it holds and wrong about what was asked.
 *
 * @param query What is being searched for.
 * @param category Which category, as the pills name it.
 * @param sort Which order.
 * @param reversed Whether that order is read the other way round.
 * @returns The infinite query, its rows already in the engine's names.
 */
export function useLibraryListing(
  query: string,
  category: string,
  sort: string,
  reversed: boolean,
) {
  return useInfiniteQuery({
    queryKey: ["/api/library/items", query, category, sort, reversed],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const parameters = new URLSearchParams({ page: String(pageParam) });
      if (query) parameters.set("query", query);
      if (category) parameters.set("category", category);
      if (sort) parameters.set("sort", sort);
      if (reversed) parameters.set("reversed", "1");
      const answer = await read<{
        total: number; matching: number; loaded: number; items: unknown;
      }>("/api/library/items", parameters);
      return {
        total: answer.total,
        matching: answer.matching,
        loaded: answer.loaded,
        items: toEngineShape<LibraryRow[]>("LIBRARY", answer.items),
      } satisfies LibraryPage;
    },
    // THE NEXT PAGE EXISTS WHEN THE ROWS SO FAR ARE FEWER THAN WHAT THE
    // QUESTION MATCHES, and never « when the last page was full » — a last page
    // that happened to be exactly full would promise one more that answers
    // nothing. It compared against `total` first, and that is a different
    // number: the library claims 1 861 titles and the source holds 345, so the
    // end was never reached, `hasNextPage` stayed true over empty pages, and
    // the end mark was never drawn.
    getNextPageParam: (last, pages) => {
      const held = pages.reduce((count, page) => count + page.items.length, 0);
      return held < last.matching ? pages.length : undefined;
    },
  });
}

/** The category pills, with the count each claims. */
export function useLibraryCategories() {
  return useQuery({
    queryKey: ["/api/library/categories"],
    queryFn: async () =>
      toEngineShape<LibraryCategory[]>("CATS", await read("/api/library/categories")),
  });
}


/** The shows the index knows are incomplete. */
export function useLibraryIncomplete() {
  return useQuery({
    queryKey: ["/api/library/incomplete"],
    queryFn: async () =>
      toEngineShape<IncompleteShow[]>("INCOMPLETE", await read("/api/library/incomplete")),
  });
}

// What the list registers when it is on screen, and null when it is not.
let askListingForOneMore: (() => void) | null = null;

/**
 * Records the list's own « one more page », or takes it back.
 *
 * @param ask The function, or null when the list leaves.
 */
export function registerListingPaging(ask: (() => void) | null): void {
  askListingForOneMore = ask;
}

/**
 * Installs the door a named state asks one more page through.
 *
 * WHY IT EXISTS. `lib-error-more` names a state the interface really has — the
 * list loaded, and then the next page did not — and it cannot be reached by
 * setting a flag any more: the failure belongs to the layer, and the layer only
 * fails a page somebody asks for. Driving the scenario alone leaves the list
 * whole and the error nowhere.
 *
 * IT WAITS, AND THE WAITING IS HERE RATHER THAN IN THE STATE. Three things have
 * to be true before « one more » means anything: the list must be mounted, it
 * must have registered its own function, and the FIRST page must have landed —
 * asking for one more than nothing does nothing at all, silently, which is
 * exactly how the state looked reached while showing no error. Putting that in
 * the state left the same wait to be written again for the next surface.
 *
 * A NAMED STATE IS NOT A JOURNEY, which is why this is a door rather than a
 * scripted scroll: the state says « ask for one more » and the layer answers
 * with the failure the scenario armed, from a known cache.
 *
 * @param queryClient The cache the listing lives in.
 */
export function installLibraryPaging(queryClient: QueryClient): void {
  window.__libraryNextPage = () => {
    let framesLeft = 60;
    const attempt = () => {
      const listing = queryClient
        .getQueryCache()
        .getAll()
        .find((query) => query.queryKey[0] === "/api/library/items");
      const landed =
        ((listing?.state.data as { pages?: unknown[] } | undefined)?.pages ?? []).length > 0;
      if (askListingForOneMore !== null && landed) {
        askListingForOneMore();
        return;
      }
      if (--framesLeft > 0) requestAnimationFrame(attempt);
    };
    attempt();
  };
}

declare global {
  interface Window {
    /** Asks the listing for one more page. Registered by the list, read by a named state. */
    __libraryNextPage?: () => void;
  }
}

/**
 * Installs the library's delete, for the dying engine's delegation to call.
 *
 * WHY IT HAD TO MOVE. `actionDelete` filtered `world.lib`, and the world stopped
 * holding the library the moment the listing converted — so deleting removed
 * nothing at all, silently, on a surface whose whole subject is what is there.
 * No named state deletes, so the oracle could not see it.
 *
 * THE OPTIMISTIC PATH IS THE LISTING'S OWN PAGES. The rows leave the screen in
 * the same task as the tap; the layer is asked afterwards; a refusal puts back
 * exactly what was there.
 *
 * NE-DOIT-PAS-6 IS THE ENGINE'S STILL: the confirmation happens before this is
 * called, and it stays where it is drawn.
 *
 * @param queryClient The cache the surfaces read.
 */
export function installLibraryDelete(queryClient: QueryClient): void {
  window.__deleteLibraryItems = (titles) => {
    const listings = queryClient
      .getQueryCache()
      .getAll()
      .filter((query) => query.queryKey[0] === "/api/library/items");
    const before = listings.map((listing) => [listing.queryKey, listing.state.data] as const);
    const gone = new Set(titles);
    for (const [key, data] of before) {
      const held = data as { pages: LibraryPage[] } | undefined;
      if (held === undefined) continue;
      queryClient.setQueryData(key, {
        ...held,
        pages: held.pages.map((page) => ({
          ...page,
          items: page.items.filter((row) => !gone.has(String(row.t))),
        })),
      });
    }
    void send("DELETE", "/api/library/items", { titles })
      .catch((refusal) => {
        for (const [key, data] of before) queryClient.setQueryData(key, data);
        throw refusal;
      })
      .finally(() => {
        void queryClient.invalidateQueries({ queryKey: ["/api/library/items"] });
      });
  };
}

declare global {
  interface Window {
    /** Removes titles from the library. Called by the dying engine's delegation. */
    __deleteLibraryItems?: (titles: string[]) => void;
  }
}
