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
import { popover } from "../app/popover-host";
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
import { changeSetting } from "../features/settings/pending-edits";
import { pressNumbers, pressSwallowClick } from "../lib/press-arbitration";
import { openRow } from "../lib/swipe-arbitration";
import { resetPullIndicator } from "../app/pull-indicator";
import { pullNumbers } from "../lib/pull-gesture";
import { sharedQueryClient } from "../lib/query-client";
import { queueActions, queueLists } from "../lib/queue";
import { readLimits, reconnectNow, resetRelay, setLimits } from "../lib/relay";
import { forceCondition, readCondition } from "../lib/relay-condition";
import { readCursor, subscribeToEvents } from "../lib/relay-events";
import { bridge, panel, redraw, screens, toast } from "../lib/shell-doors";
import { go } from "../lib/navigate";
import { CARRIED_KEY } from "../lib/navigation-entry";
import { store } from "../lib/store-access";
import { today } from "../lib/clock";
import { verbNames } from "../lib/verbs";

declare global {
  interface Window {
    /** The interface's store — the domain hooks and the probes read its state. */
    __store: Store;
    /** The frame's popover door — how a rule closes a popover it opened. */
    __popover: typeof popover;
    /** Files a setting's pending edit — how a rule stages a change it does not type. */
    __changeSetting: typeof changeSetting;
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
    /** The store, and the state it holds now — the two names every rule reads bare. */
    store?: Store;
    state?: Record<string, unknown>;
    /** The page's scrollport content, as the rules have always named it. */
    view?: Element | null;
    /** Redraws the page, as a rule asks for it. */
    render?: () => void;
    /** Says a message. */
    toast?: (message: string) => void;
    /** Closes the panel, popping its entry or not. */
    closeSheet?: (pop?: boolean) => void;
    /** Shows the sign-in gate; a driven state never touches history. */
    showSignIn?: (withError: boolean, silent?: boolean) => void;
    /** The page's today — what every « à venir » and « diffusé le » is compared with. */
    __today?: typeof today;
    /** Opens a medium's screen on an entry carrying exactly what a rule hands it. */
    __openCarrying?: (provider: string, id: string, carried: Record<string, unknown>) => void;
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
  publish("__changeSetting", () => changeSetting);
  publish("__relay", () => relay);
  publish("__i18n", () => i18next);
  publish("__toast", () => toast);
  publish("__panel", () => panel);
  publish("__bridge", () => bridge);
  publish("__screens", () => screens);
  publish("__unknownPanel", () => unknownPanel);
  publish("__unknownProducer", () => unknownProducer);
  publish("__dialog", () => dialog);
  publish("__popover", () => popover);
  publish("__layers", () => registeredLayers);
  publish("__closeLayers", () => closeLayers);
  publish("__today", () => today);
  // THE BARE NAMES THE RULES HAVE ALWAYS READ, published under those names from
  // the modules that own them now. `state` is a LIVE read — the getter goes to
  // the store each time — so a rule reading `state.page` reads what is on screen.
  publish("store", () => store);
  publish("state", () => store.read().state);
  publish("view", () => document.querySelector("#view"));
  publish("render", () => redraw);
  publish("toast", () => (message: string) => toast?.show({ message }));
  publish("closeSheet", () => (pop?: boolean) => panel.close(pop));
  publish("showSignIn", () => (withError: boolean, silent?: boolean) =>
    entry?.showSignIn(withError, silent === true || walk.driven));
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
  // WHAT A TAP KNEW, WRITTEN BY THE RULE. The screen primes from what its entry
  // carries, and the product's writer copies three fields of a list item; a rule
  // measuring how the screen draws a THINNER or a RICHER knowledge — a title
  // alone, a year without its kind — writes the carried object itself.
  publish("__openCarrying", () => (provider: string, id: string, carried: Record<string, unknown>) =>
    go({ to: "/media/$provider/$id", params: { provider, id }, state: { [CARRIED_KEY]: carried } }));
  /* THE TWO GESTURE NAMES A RULE ACTUALLY READS, and only those two. The engine
     published seven on `window` — `cardDrag`, `openCard`, `openCardDx`,
     `clickAfterDrag`, `swallowClick`, `deckDrag`, `sugDrag` — and five of them
     were read by NOTHING, measured rule file by rule file. A driving surface
     nobody drives through is a surface that does not exist, so the five went
     with the engine's `defineProperties` block and these two are published from
     the modules that now own them: the open row (`pause_verb.py` asks whether a
     row came back to rest) and the press's swallow (`press.py` asks whether the
     lift's click was marked). */
  publish("openCard", () => openRow());
  /* THE INDICATOR'S RESET, which five holds drive between measurements: a
     refresh in flight outlives a change of state, so a rule that did not put it
     back inherited the previous state's spinner. It was `window.__reposPTR`,
     written by the engine; it is published here from the frame's indicator. */
  publish("__reposPTR", () => resetPullIndicator);
  publish("swallowClick", () => pressSwallowClick?.() === true);
  // Two gestures each own their numbers, and a rule reads them as one table —
  // present once the gesture that owns them has been installed, as before.
  publish("__gestures", () => {
    const numbers: Record<string, Record<string, number>> = {};
    if (pressNumbers) numbers.press = pressNumbers;
    if (pullNumbers) numbers.pull = pullNumbers;
    return Object.keys(numbers).length > 0 ? numbers : undefined;
  });
}
