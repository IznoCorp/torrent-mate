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
import { HELD, isRequestFailure, read, send } from "../../lib/query-client";
import { refusalWords } from "../../lib/refusal";
import { toast } from "../../lib/shell-doors";
import type { MediaRef } from "../../lib/membership";
import type { IncompleteShow, LibraryCategory, LibraryRow } from "./types";
import type { Schemas } from "../../lib/contract-schemas";
import { SORT_KEYS } from "./sorting";
import { leavesOf, lensesOf, type LeafCategory } from "./lenses";

/** The order the listing answers when none is named. */
const RECENT = SORT_KEYS[0];

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
    queryKey: ["/api/v1/library/items", query, category, sort, reversed],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const parameters = new URLSearchParams({ page: String(pageParam) });
      if (query) parameters.set("query", query);
      // THE LENS' LEAVES, never the lens: the engine knows its leaf categories
      // and nothing of how the interface groups them (K2-G5).
      for (const leaf of leavesOf(category) ?? []) parameters.append("category", leaf);
      // THE DEFAULT ORDER IS SAID BY SAYING NOTHING: the contract's `sort` names
      // the two other orders, and an absent one is the most recent first.
      if (sort && sort !== RECENT) parameters.set("sort", sort);
      if (reversed) parameters.set("reversed", "1");
      const answer = await read<{
        total: number; matching: number; loaded: number; items: LibraryRow[];
      }>("/api/v1/library/items", parameters);
      return {
        total: answer.total,
        matching: answer.matching,
        loaded: answer.loaded,
        items: answer.items,
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

/** The engine's leaf categories with their counts, as a query a surface and a panel share. */
export const libraryCategoriesQuery = {
  queryKey: ["/api/v1/library/categories"],
  queryFn: async () => read<LeafCategory[]>("/api/v1/library/categories"),
};

/** The category pills — the interface's lenses, each counted from the leaves it groups. */
export function useLibraryCategories() {
  return useQuery({ ...libraryCategoriesQuery, select: (leaves): LibraryCategory[] => lensesOf(leaves) });
}


/** The shows the index knows are incomplete, as a query a surface and the removal dialog share. */
export const libraryIncompleteQuery = {
  queryKey: ["/api/v1/library/incomplete"],
  queryFn: async () =>
    read<IncompleteShow[]>("/api/v1/library/incomplete"),
};

/** The shows the index knows are incomplete. */
export function useLibraryIncomplete() {
  return useQuery(libraryIncompleteQuery);
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
  libraryNextPage = () => {
    let framesLeft = 60;
    const attempt = () => {
      const listing = queryClient
        .getQueryCache()
        .getAll()
        .find((query) => query.queryKey[0] === "/api/v1/library/items");
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

/** Asks the listing for one more page — filled at install. */
export let libraryNextPage: Window["__libraryNextPage"];

/** What the deletion did to one medium: it went, or it was kept and why (operator ruling R2). */
export type LibraryDeletion = Schemas["LibraryDeletion"];

/**
 * What the delete answers: each medium's outcome, `HELD` when the network would
 * not take the request (it leaves when it answers), or `null` when the layer
 * refused it — the refusal already said.
 */
export type DeleteAnswer = LibraryDeletion[] | typeof HELD | null;

/**
 * Installs the library's delete, for the dying engine's delegation to call.
 *
 * WHY IT HAD TO MOVE. `actionDelete` filtered `world.lib`, and the world stopped
 * holding the library the moment the listing converted — so deleting removed
 * nothing at all, silently, on a surface whose whole subject is what is there.
 * No named state deletes, so the oracle could not see it.
 *
 * NO ROW LEAVES BEFORE THE LAYER SAYS IT WENT (operator ruling R2, 2026-10-05).
 * The deletion answers medium by medium, and a medium it KEPT — a tracker still
 * owed its seeding, its disk unplugged, a folder that would not go — is still
 * in the library: removing its row on the tap and putting it back on the answer
 * would say « gone » about what stayed, which § 8 forbids. So the rows that go
 * are the ones the answer names `deleted`, and only once it is in.
 *
 * NE-DOIT-PAS-6 IS THE ENGINE'S STILL: the confirmation happens before this is
 * called, and it stays where it is drawn.
 *
 * @param queryClient The cache the surfaces read.
 */
export function installLibraryDelete(queryClient: QueryClient): void {
  deleteLibraryItems = async (doomed) => {
    let answer: { media: LibraryDeletion[] } | undefined | typeof HELD;
    try {
      answer = await send<{ media: LibraryDeletion[] }>("DELETE", "/api/v1/library/items", {
        media: doomed.map((one) => one.ref),
      });
    } catch (refusal) {
      // THE REFUSAL IS SAID, in the interface's words for its code: nothing
      // went, and nothing left the screen.
      toast?.show({
        message: refusalWords(isRequestFailure(refusal) ? refusal : null, "verbs.library.deleteRefused"),
      });
      void queryClient.invalidateQueries({ queryKey: ["/api/v1/library/items"] });
      return null;
    }
    // HELD: the request has not left. Nothing is known to have gone, so nothing
    // leaves the screen, and refreshing would only redraw the same rows.
    if (answer === HELD) return HELD;
    const media = answer?.media ?? [];
    const gone = media.filter((one) => one.outcome === "deleted").map((one) => one.ref);
    // THE ROWS THAT GO ARE THE ONES CARRYING AN IDENTITY THE ANSWER SAYS WENT —
    // every row of it, which is one row: a duplicate never reaches here (O-5 B).
    const carries = (row: LibraryRow, ref: MediaRef) =>
      String((row.ids as Record<string, string | number> | null)?.[ref.provider] ?? "") === ref.providerId;
    for (const listing of queryClient.getQueryCache().findAll({ queryKey: ["/api/v1/library/items"] })) {
      const held = listing.state.data as { pages: LibraryPage[] } | undefined;
      if (held === undefined) continue;
      queryClient.setQueryData(listing.queryKey, {
        ...held,
        pages: held.pages.map((page) => ({
          ...page,
          items: page.items.filter((row) => !gone.some((ref) => carries(row, ref))),
        })),
      });
    }
    void queryClient.invalidateQueries({ queryKey: ["/api/v1/library/items"] });
    // AND THE SHEETS OF WHAT LEFT. The list is honest in the same task and
    // the SHEET was not: reopened after a confirmed delete it still read
    // « Possédés 24 » from its own cached answer and offered « Supprimer »
    // again, which is the surface the reader is looking at when the toast
    // says it is done. Every media read is invalidated rather than the
    // deleted ones alone — the sheet's key is the provider's identifier,
    // and nothing here maps a title to it.
    void queryClient.invalidateQueries({ queryKey: ["/api/v1/media"] });
    // AND WHAT THE LIBRARY SAYS IT HOLDS is REMOVED, not merely marked
    // stale: a producer reads the cache synchronously and would still see
    // the answer from before, so every panel opened about a removed title
    // afterwards has to ask again.
    queryClient.removeQueries({ queryKey: ["/api/v1/library/membership"] });
    void queryClient.invalidateQueries({ queryKey: libraryIncompleteQuery.queryKey });
    return media;
  };
}

declare global {
  interface Window {
    /** Removes media from the library, each by the identity its title was drawn with; answers what each did. */
    __deleteLibraryItems?: (doomed: { title: string; ref: MediaRef }[]) => Promise<DeleteAnswer>;
  }
}

/** Removes media from the library — filled at install. */
export let deleteLibraryItems: Window["__deleteLibraryItems"];
