// THE DRIVER — how a named state is reached by its id.
//
// `window.__go(id)` drives the prototype into a state without a click, and that
// is what makes a measurement deterministic: a rule names the state and
// measures, instead of knowing how to make it appear — knowledge that is exactly
// what evaporates over time. The states themselves are in `states/`, one file
// per surface; `index.ts` composes the table and hands it here.
//
// NOTHING HERE IS THE PRODUCT'S. The module is installed behind
// `__MOCKS_BUILT_IN__`, and a driver could not run without the mock layer
// anyway: every state starts by resetting it.
//
// THE HISTORY LATCH STAYS WITH ITS READERS. A driven state writes no history,
// and the writers that check the latch live in the page switch, so the driver never
// holds it: it hands each state to `drivenWithoutHistory`, the verb that does.
import { refillEngineData } from "../app/engine-data";
import { navigation } from "../app/navigation-seam";
import type { UiState } from "../app/store";
// `applyState` is the engine's — the ladder's handler restores a page through
// it — and the states start through the same verb, re-exported here beside their type.
import { drivenWithoutHistory } from "../app/page-switch";
import {
  applyState,
  resetSettings,
  screenStack,
  seedWorld,
} from "../engine/legacy.js";
import { closeHarnessPanel } from "./panel";

export { applyState };

/** One named state: the id `__go` takes, the label the ≡ panel shows, and how to build it. */
export type NamedState = [id: string, label: string, run: () => void];

// The table states are looked up in, handed over once at install.
let table: NamedState[] = [];


/**
 * Puts the interface back where every measurement starts.
 *
 * Returns:
 *     True, so a caller awaiting it reads a value.
 */
function reset(): boolean {
  seedWorld();
  /* THE CACHE IS PART OF WHAT A MEASUREMENT INHERITS. « A measurement must
     never inherit the mutations of a previous one » used to be true of the
     world alone, because every surface read a fixture. A surface reads a query
     cache now, and a cache keeps what it holds: driving one state after another
     left the library showing every page a previous state had asked for, and the
     oracle measured a 46 402 px list where the reference holds 3 388. Clearing
     it here rather than in each named state is the same decision `seedWorld()`
     embodies — a state pins what it means to show, and everything else starts
     from a known place. The mock layer's own seeds go back with it. */
  window.__queries?.clear();
  window.__mocks?.reset();
  /* AND WHAT NO COMPONENT OBSERVES IS ASKED FOR AGAIN. A cleared query with an
     observer is re-asked by that observer; the deck's cards have none, because
     the engine draws the deck. */
  refillEngineData?.();
  window.__store.write({
    /* The SCENARIO is state too, and the loudest kind: it decides which world
       every later reading is taken from. A state that switched to the dense
       scenario left it switched for the next one, so a surface measured on its
       own and the same surface measured after its neighbour answered
       differently. A named state that does not pin its scenario pins it here. */
    scen: "real",
    pill: "tout",
    filter: "",
    q: "",
    sugCount: 30,
    selMode: false,
    selected: new Set(),
    sugGone: new Set(),
    added: new Set(),
    // The deck order is state too: without this a measurement inherits the
    // card order left by the previous one.
    sugOrder: null,
  });
  // The pull indicator lives outside the state object — classes and an inline
  // height on one element — and a refresh in flight outlives a change of
  // state. Reset here, or a measurement inherits the previous one's spinner.
  if (window.__reposPTR) window.__reposPTR();
  if (typeof resetSettings === "function") resetSettings();
  // The screen stack is navigation state: a measurement must not inherit the
  // screens a previous journey left underneath the visible one.
  screenStack.length = 0;
  // The router is navigation state too: a named state is DRIVEN, not a
  // journey, so it must not inherit whichever screen route a previous one
  // navigated to. `replace`, so driving through many states never grows
  // history; `flush()` puts the address back to "/" before the state that runs
  // right after this — which may itself navigate — has a chance to.
  if (window.__routeur) {
    window.__routeur.navigate({ to: "/", replace: true });
    window.__routeur.history.flush();
  }
  return true;
}

/**
 * Drives the interface into a named state.
 *
 * Args:
 *     stateId: The state's id.
 *     options: `keep: true` chains a state onto the previous one instead of
 *         resetting first — the way an action scenario is built.
 *
 * Returns:
 *     The id, once the state is built.
 *
 * Raises:
 *     Error: When no state carries that id.
 */
function go(stateId: string, options?: { keep?: boolean }): string {
  const found = table.find((entry) => entry[0] === stateId);
  if (!found)
    throw new Error(
      table.length
        ? "état inconnu : " + stateId
        : "aucun état enregistré — la table du harnais est vide");
  closeHarnessPanel();
  if (!stateId.startsWith("signin")) window.__entry?.hideSignIn(true);
  if (stateId !== "startup") window.__entry?.hideStartup();
  if (!stateId.startsWith("pwa-")) window.__entry?.hideInstall();
  // Reset to seed by DEFAULT: a measurement must never inherit the mutations
  // of a previous one.
  if (!options?.keep) reset();
  // Driving is not a journey: a measurement must not depend on how many
  // states ran before it.
  drivenWithoutHistory(found[2]);
  return stateId;
}

/**
 * Publishes the driving seams the rules reach the prototype through.
 *
 * Args:
 *     states: Every named state, in the order `__states()` lists them.
 */
export function installDriver(states: NamedState[]): void {
  table = states;
  window.__go = go;
  window.__states = () => table.map((entry) => entry[0]);
  // The ≡ panel lists the states by NAME, so it needs the label too.
  window.__etatsDetailles = () => table.map(([id, label]): [string, string] => [id, label]);
  /* The ids the interface can actually render. Any control naming something
     else is a dead end however carefully it is drawn — a drawer entry pointed
     at one and answered a tap with a message. Reading the page table rather
     than a list written beside it is what makes that checkable at all. */
  window.__pages = () => navigation?.ids() ?? [];
  /* The media the pipeline is currently refusing. The rule that keeps them OFF
     the machine's page has to know their names, and a rule that cannot reach
     them compares against an empty list and passes whatever it is shown. */
  window.__blocked = () => (window.__queue?.() ?? { stuck: [] }).stuck.map((card) => card.t);
  /* Clears ALL harness chrome before a capture or a measurement: the harness
     buttons float above the shell, which is a measured region and must carry
     nothing that does not exist in the app. */
  window.__measure = (enabled) => {
    document.documentElement.classList.toggle("measuring", enabled !== false);
    return enabled !== false;
  };
  window.__reset = reset;
  // Rules build some states by hand, patch by patch, the way a named state does.
  window.applyState = applyState;
}

declare global {
  interface Window {
    /** Drives the prototype into a named state, without a click. */
    __go: (stateId: string, options?: { keep?: boolean }) => string;
    /** Every named state's id, in table order. */
    __states: () => string[];
    /** Every named state's id and label, for the ≡ panel. */
    __etatsDetailles: () => [string, string][];
    /** The interface back where every measurement starts. */
    __reset: () => boolean;
    /** Hides the harness chrome, or shows it again with `false`. */
    __measure: (enabled?: boolean) => boolean;
    /** The media the pipeline is refusing. */
    __blocked: () => unknown[];
    /** The page ids the interface can render. */
    __pages: () => string[];
    /** A named state's first step, for a rule that builds one by hand. */
    applyState: (patch: Partial<UiState>) => void;
    /** Puts the pull indicator back at rest, published by the engine. */
    __reposPTR?: () => void;
  }
}
