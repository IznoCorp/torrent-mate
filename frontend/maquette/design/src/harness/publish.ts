// THE SEAMS THE RULES READ — every one the product owns, under the name the
// rules already use.
//
// A seam is read by a rule and never by a component. The product imports what
// it needs from the module that owns it, and nothing in it reads `window`; what
// a rule reaches through `window` is published HERE, by a module the boot
// installs behind `__MOCKS_BUILT_IN__` — so a build without the mock layer
// publishes none of it.
//
// EACH IS A GETTER, NOT A COPY. An owner fills its seam at its own point in the
// boot, several of them after the harness installs; a getter reads the owner's
// live binding at the moment a rule asks, which is the value the rule used to
// find on `window` at that same moment.
//
// WHAT IS NOT HERE. The mock layer publishes `window.__mocks` itself, because
// only `app/` may import `mocks/`. The dying engine publishes its own names. And
// a name no rule reads is published nowhere: its readers import it.
import i18next from "../i18n";
import { dialog } from "../app/dialog-host";
import { entry, loadingDone } from "../app/entry";
import { closeLayers, registeredLayers } from "../app/layers";
import { resetLiveUpdates, unmatchedCount, unmatchedEvents } from "../app/live-updates";
import { outboxSeam } from "../app/outbox";
import { shellPages } from "../app/page-host";
import { walk } from "../app/page-switch";
import { unknownPanel, unknownProducer } from "../app/panel-host";
import { router } from "../app/router-tree";
import type { Store } from "../app/store";
import { discover } from "../features/acquisition/discover-feed";
import { followActions, suggestions } from "../features/acquisition/queries";
import { searchResults } from "../features/acquisition/search-queries";
import { deleteLibraryItems, libraryNextPage } from "../features/library/queries";
import { sortWays } from "../features/library/sorting";
import { releases } from "../features/releases/queries";
import { settingLabels } from "../features/settings/labels";
import { pressNumbers } from "../lib/press-arbitration";
import { pullNumbers } from "../lib/pull-gesture";
import { sharedQueryClient } from "../lib/query-client";
import { queueActions, queueLists } from "../lib/queue";
import { readLimits, reconnectNow, resetRelay, setLimits } from "../lib/relay";
import { forceCondition, readCondition } from "../lib/relay-condition";
import { readCursor, subscribeToEvents } from "../lib/relay-events";
import { bridge, panel, screens, toast } from "../lib/shell-doors";
import { store } from "../lib/store-access";
import { verbNames } from "../lib/verbs";

declare global {
  interface Window {
    /** The interface's store — the domain hooks and the probes read its state. */
    __store: Store;
    // The query cache. It is the one place server state lives (invariant 4), so
    // a rule asking « what does this surface hold, and did a mutation put it
    // back? » asks it here.
    __queries: import("@tanstack/react-query").QueryClient;
    /** The live relay's driving surface — what the connection is doing, a
        manual retry, the events nothing claimed, and a way back to cold. */
    __relay: {
      condition: typeof readCondition;
      reconnect: typeof reconnectNow;
      unmatched: typeof unmatchedEvents;
      unmatchedCount: typeof unmatchedCount;
      subscribe: typeof subscribeToEvents;
      cursor: typeof readCursor;
      force: typeof forceCondition;
      limits: typeof setLimits;
      readLimits: typeof readLimits;
      reset: () => void;
    };
    // THE INTERFACE'S WORDS. A rule that wants to prove what a surface does when
    // a resource is MISSING has to be able to remove one, and a rule that cannot
    // reach what it measures reports a failure it did not find.
    __i18n?: typeof i18next;
    // THE DECK'S OWN DRIVING SEAM: its order and its three moves. The feature owns
    // the answer and a rule reads it through this one named door.
    __discover?: typeof discover;
    /** The ladder's registrations — what is on it, and whether a rung is open. */
    __layers?: typeof registeredLayers;
    /** What a scrim tap closes. */
    __closeLayers?: typeof closeLayers;
    /** When the exit guard was armed, or 0 — the address alone says nothing of it. */
    armedExit?: number;
  }
}

/**
 * Publishes one seam as a getter over what its owner holds now.
 *
 * @param name The name a rule reads on `window`.
 * @param read What the owner holds at the moment of the read.
 */
function publish(name: string, read: () => unknown): void {
  Object.defineProperty(window, name, { configurable: true, enumerable: true, get: read });
}

/** Publishes every seam a rule reads, under the name the rules already use. */
export function publishSeams(): void {
  // The relay's surface is composed of the relay's own verbs, so a rule that
  // asks what the connection is doing does not reach inside the module.
  const relay: Window["__relay"] = {
    condition: readCondition,
    reconnect: reconnectNow,
    unmatched: unmatchedEvents,
    unmatchedCount,
    subscribe: subscribeToEvents,
    cursor: readCursor,
    force: forceCondition,
    limits: setLimits,
    readLimits,
    reset: () => {
      resetLiveUpdates();
      resetRelay();
    },
  };
  publish("__store", () => store);
  publish("__queries", () => sharedQueryClient);
  publish("__relay", () => relay);
  publish("__i18n", () => i18next);
  publish("__toast", () => toast);
  publish("__panel", () => panel);
  publish("__bridge", () => bridge);
  publish("__screens", () => screens);
  publish("__unknownPanel", () => unknownPanel);
  publish("__unknownProducer", () => unknownProducer);
  publish("__dialog", () => dialog);
  publish("__layers", () => registeredLayers);
  publish("__closeLayers", () => closeLayers);
  publish("armedExit", () => walk.armedExit);
  publish("__entry", () => entry);
  publish("__loadingDone", () => loadingDone);
  publish("__outbox", () => outboxSeam);
  publish("__routeur", () => router);
  publish("__shellPages", () => shellPages);
  publish("__discover", () => discover);
  publish("__followActions", () => followActions);
  publish("__suggestions", () => suggestions);
  publish("__searchResults", () => searchResults);
  publish("__libraryNextPage", () => libraryNextPage);
  publish("__deleteLibraryItems", () => deleteLibraryItems);
  publish("__sortWays", () => sortWays);
  publish("__releases", () => releases);
  publish("__settingLabels", () => settingLabels);
  publish("__queue", () => queueLists);
  publish("__queueActions", () => queueActions);
  publish("__verbNames", () => verbNames);
  // Two gestures each own their numbers, and a rule reads them as one table —
  // present once the gesture that owns them has been installed, as before.
  publish("__gestures", () => {
    const numbers: Record<string, Record<string, number>> = {};
    if (pressNumbers) numbers.press = pressNumbers;
    if (pullNumbers) numbers.pull = pullNumbers;
    return Object.keys(numbers).length > 0 ? numbers : undefined;
  });
}
