// What the Acquisition deck asks the server for, beyond the shared queue.
//
// THE QUEUE ITSELF IS `lib/queue.ts` — two surfaces read it, and invariant 7
// forbids one feature importing another. What is here is this surface's alone:
// the reserve of suggestions its deck draws, and the follows it lists.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { HELD, read, send } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { Follow } from "./reference";
import { queueNow } from "../../lib/queue";

/**
 * The suggestions the discover deck draws, as a query definition.
 *
 * ONE READ, NOT A PAGE. The layer pages them by the last title seen; the deck
 * asks for the whole batch, because its own paging is by INDEX into a list it
 * holds, and rewriting that is rewriting the deck — drawing, which is L13's.
 * What this lot takes away is the FIXTURE.
 *
 * IT IS A DEFINITION RATHER THAN A HOOK BECAUSE NO COMPONENT HOLDS IT. The deck
 * is drawn by the engine, so there is nobody to subscribe: the boot asks for it
 * once and the seam below reads what landed. A hook with no caller would be
 * machinery nobody could justify.
 */
export const suggestionsQuery = {
  queryKey: ["/api/acquisition/suggestions"],
  queryFn: async () => {
    // THE WHOLE RESERVE, batch after batch, because the deck INDEXES into it.
    // The layer pages by the last title seen and the deck's own paging is by
    // index into a list it holds: handed one batch it would hold 30 of 38, and
    // its end mark — « the reserve loaded in this prototype » — would announce
    // a reserve two thirds the size, having reached the end of a list nobody
    // shortened. Its own paging is drawing, and goes at L13; until then it is
    // given what it expects to have.
    const held: unknown[] = [];
    for (let asked = 0; asked < 20; asked += 1) {
      const parameters = new URLSearchParams();
      const last = held[held.length - 1] as { title?: string } | undefined;
      if (last?.title !== undefined) parameters.set("after", last.title);
      const batch = await read<unknown[]>("/api/acquisition/suggestions", parameters);
      if (batch.length === 0) break;
      held.push(...batch);
      if (batch.length < SUGGESTION_BATCH) break;
    }
    return toEngineShape<unknown[]>("SUGGESTIONS", held);
  },
};

// How many the layer answers with in one batch. Named so the loop above can
// tell a full batch from the last one; the layer states the same number.
const SUGGESTION_BATCH = 30;

/**
 * Publishes the suggestions for the dying engine's deck to read synchronously.
 *
 * The deck indexes into this list from a click handler that cannot await, the
 * same shape as the decision lookup. It reports an empty list before the query
 * has answered, and the deck draws nothing for an empty list — which is what it
 * already did for a batch that had been fully seen.
 *
 * @param queryClient The cache the surfaces read.
 */
export function installSuggestionsLookup(queryClient: QueryClient): void {
  window.__suggestions = () =>
    (queryClient.getQueryData(suggestionsQuery.queryKey) as unknown[] | undefined) ?? [];
  // AND IT IS ASKED FOR, because nothing else will. Every other read in this
  // file belongs to a component that subscribes; the deck belongs to the
  // engine, and a seam over a cache nobody filled answers empty for ever.
  //
  // IT IS PUBLISHED RATHER THAN CALLED ONCE, and that is `__reset`'s doing: a
  // named state clears the cache so no measurement inherits a previous one's
  // pages, and a query with an OBSERVER is re-asked by that observer while one
  // without is not. This is the door `__reset` re-asks through.
  window.__refillSuggestions = () => void queryClient.prefetchQuery(suggestionsQuery);
  window.__refillSuggestions();
}

/**
 * What the operator follows, as a query DEFINITION.
 *
 * A DEFINITION AND NOT ONLY A HOOK: the follows tab subscribes, and the follow
 * PANEL is produced from a long press — and from a cold load at
 * `?panel=follow:<title>`, where no tab has mounted. One definition, so the two
 * cannot drift into two shapes of one answer (§13).
 */
export const followsQuery = {
  queryKey: ["/api/acquisition/followed"],
  queryFn: async () =>
    toEngineShape<Follow[]>("FOLLOWS", await read("/api/acquisition/followed")),
};

/** What the operator follows. */
export function useFollows() {
  return useQuery(followsQuery);
}

/** The key the follows are cached under. */
const followsKey = followsQuery.queryKey;

/**
 * Installs the follows' verbs, for the dying engine's delegation to call.
 *
 * EACH ONE WRITES THE CACHE FIRST. Pausing a follow, removing one, adding one:
 * the list on screen changes in the same task as the tap, and the layer is
 * asked afterwards. If it refuses, what was there goes back — which is the only
 * way an optimistic path is honest rather than a lie that usually holds.
 *
 * THE UNDO IS THE ENGINE'S AND IT STAYS. A toast that offers to put something
 * back is interface, and it calls these verbs again to do it.
 *
 * @param queryClient The cache the surfaces read.
 */
export function installFollowActions(queryClient: QueryClient): void {
  const held = () => queryClient.getQueryData<Follow[]>(followsKey) ?? [];
  const write = (follows: Follow[]) => queryClient.setQueryData(followsKey, follows);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: followsKey });

  window.__followActions = {
    setStatus: (title, status) => {
      const before = held();
      write(before.map((follow) =>
        follow.t === title ? { ...follow, st: status } : follow));
      void send("PATCH", `/api/acquisition/followed/${encodeURIComponent(title)}`,
                { status })
        .catch((refusal) => { write(before); throw refusal; })
        .then((outcome) => { if (outcome !== HELD) refresh(); },
              // AND ON A REFUSAL. The `.finally` this replaced ran on both paths;
              // only the HELD skip was intended, and the refused one was dropped by
              // accident — leaving a row restored from a local snapshot and never
              // re-synced against the server that refused it.
              () => { refresh(); });
    },
    remove: (title) => {
      const before = held();
      write(before.filter((follow) => follow.t !== title));
      void send("DELETE", `/api/acquisition/followed/${encodeURIComponent(title)}`)
        .catch((refusal) => { write(before); throw refusal; })
        .then((outcome) => { if (outcome !== HELD) refresh(); },
              // AND ON A REFUSAL. The `.finally` this replaced ran on both paths;
              // only the HELD skip was intended, and the refused one was dropped by
              // accident — leaving a row restored from a local snapshot and never
              // re-synced against the server that refused it.
              () => { refresh(); });
    },
    add: (follow) => {
      const before = held();
      write([follow as Follow, ...before]);
      void send("POST", "/api/acquisition/followed", {
        title: follow.t, kind: follow.k,
      })
        .catch((refusal) => { write(before); throw refusal; })
        .then((outcome) => { if (outcome !== HELD) refresh(); },
              // AND ON A REFUSAL. The `.finally` this replaced ran on both paths;
              // only the HELD skip was intended, and the refused one was dropped by
              // accident — leaving a row restored from a local snapshot and never
              // re-synced against the server that refused it.
              () => { refresh(); });
    },
    all: () => held(),
  };
}

declare global {
  interface Window {
    /** The follows' verbs, called by the dying engine's delegation. */
    __followActions?: {
      setStatus: (title: string, status: string) => void;
      remove: (title: string) => void;
      add: (follow: { t: string; k: string; st: string; fresh: boolean }) => void;
      all: () => Follow[];
    };
    /** The discover deck's cards, read synchronously by the dying engine. */
    __suggestions?: () => unknown[];
  }
}

/**
 * What awaits the operator on this page — the navigation table's badge.
 *
 * TO GRAB PLUS TO RESOLVE, and never a neighbouring counter. The engine's own
 * table said so in a comment beside the same sum; it is one derivation now,
 * read by the tab bar, by the drawer and — while it still draws them — by the
 * engine, through the seam. §13: one derivation per question.
 *
 * SYNCHRONOUS, over the query cache, because the engine asks in the middle of
 * its own task and cannot await a hook. `queueNow()` answers what the cache
 * holds and an empty queue where it holds nothing, which is the honest answer
 * before anything has been fetched.
 *
 * Returns:
 *     How many items are waiting to be taken or to be resolved.
 */
export function acquisitionBadge(): number {
  const now = queueNow();
  return now.takeable.length + now.blocked.length;
}
