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
import { drivenWithoutHistory } from "../app/page-switch";
import { hideLayers } from "../app/layers";
import { redraw } from "../lib/shell-doors";
import { resetSettings } from "./settings-reset";
import { resetPullIndicator } from "../app/pull-indicator";
import { heldIdentity, providerAddress } from "../lib/held-identity";
import type { CarriedIdentity } from "../lib/navigation-entry";

/**
 * Puts the pipeline in a state, as its verbs would have, and asks its status again.
 *
 * WHAT THE PIPELINE IS DOING IS THE LAYER'S ANSWER, never a store key: a named
 * state that shows a running or queued pipeline moves the layer's own field and
 * the bar reads it back through the status read, as a tap does.
 *
 * Args:
 *     state: The pipeline's state.
 */
function setPipeline(state: string): void {
  window.__mocks?.setPipelineState(state as Parameters<NonNullable<typeof window.__mocks>["setPipelineState"]>[0]);
  void window.__queries?.refetchQueries({ queryKey: ["/api/pipeline/status"] });
}

/**
 * Builds a state patch by patch, the way a named state does: the layers hidden
 * without touching history, the store written, the port back at the top when the
 * patch names a new place, and the page drawn.
 *
 * Args:
 *     patch: The store keys to write — and `pipe`, which moves the layer instead.
 */
export function applyState(patch: Record<string, unknown>): void {
  const { pipe, ...rest } = patch;
  if (typeof pipe === "string") setPipeline(pipe);
  hideLayers();
  window.__store.write(rest as Partial<UiState>);
  if (rest.page || rest.libLens || rest.q !== undefined) {
    const port = document.querySelector("#port");
    if (port) port.scrollTop = 0;
  }
  redraw();
}

/** One named state: the id `__go` takes, its label in words, and how to build it. */
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
  /* THE CACHE IS PART OF WHAT A MEASUREMENT INHERITS. « A measurement must
     never inherit the mutations of a previous one » used to be true of the
     engine's world alone, because every surface read a fixture. A surface reads a query
     cache now, and a cache keeps what it holds: driving one state after another
     left the library showing every page a previous state had asked for, and the
     oracle measured a 46 402 px list where the reference holds 3 388. Clearing
     it here rather than in each named state is the same decision the old
     world's re-seeding embodied — a state pins what it means to show, and everything else starts
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
    // The library's category and sort are dials a state or a rule can move; one
    // that does must not leave the next state's listing read under them.
    libCat: "all",
    sortKey: "recent",
    sortReversed: false,
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
  resetPullIndicator?.();
  resetSettings();
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
 * What a state or a rule knows of the medium one title names.
 *
 * READ FROM THE SEED THE MOCK LAYER ANSWERS FROM, never from the product: a
 * named state opens media no served list holds, and a rule compares the served
 * reads against this. A title the seed does not key is asked of the cache, which
 * is what a tap on a drawn card would have known.
 *
 * Args:
 *     title: The title, as the seed or a drawn list spells it.
 *
 * Returns:
 *     Its title, poster and provider identifiers, or null.
 */
function carriedFor(title: string): CarriedIdentity | null {
  const sheet = window.__mocks?.sheets()[title];
  const ids = sheet?.ids as CarriedIdentity["ids"] | null | undefined;
  if (ids) return { title, poster: (sheet?.poster as string | null | undefined) ?? null, ids };
  return heldIdentity(title);
}

/**
 * The sheet the mock layer answers for the medium one title names.
 *
 * PICKED THE WAY THE SERVED READ PICKS IT: the title's provider identity gives the
 * address, and the first seed sheet carrying that identity is the one answered.
 * Keys are the contract's names. Nothing the layer overlays on an answer — a
 * delete, an unavailable library database — is applied: a rule reads the facts a
 * sheet is composed from, and the screen for what it drew.
 *
 * Args:
 *     title: The title, as the seed or a drawn list spells it.
 *
 * Returns:
 *     The seed sheet, or null when the title names no identified medium.
 */
function sheetOf(title: string): Record<string, unknown> | null {
  const address = providerAddress(carriedFor(title)?.ids);
  if (address === null) return null;
  const sheets = Object.values(window.__mocks?.sheets() ?? {});
  return sheets.find((sheet) =>
    String((sheet.ids as Record<string, unknown> | undefined)?.[address.provider] ?? "") === address.id) ?? null;
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
  /* The ids the interface can actually render. Any control naming something
     else is a dead end however carefully it is drawn — a drawer entry pointed
     at one and answered a tap with a message. Reading the page table rather
     than a list written beside it is what makes that checkable at all. */
  window.__pages = () => navigation?.ids() ?? [];
  /* The media the pipeline is currently refusing. The rule that keeps them OFF
     the machine's page has to know their names, and a rule that cannot reach
     them compares against an empty list and passes whatever it is shown. */
  window.__blocked = () => (window.__queue?.() ?? { stuck: [] }).stuck.map((card) => card.title);
  /* Clears ALL harness chrome before a capture or a measurement: the harness
     buttons float above the shell, which is a measured region and must carry
     nothing that does not exist in the app. */
  window.__measure = (enabled) => {
    document.documentElement.classList.toggle("measuring", enabled !== false);
    return enabled !== false;
  };
  window.__reset = reset;
  // A medium's identity and its address, for the states and rules that open one
  // by title rather than by tapping a card that carries it.
  window.__carriedFor = carriedFor;
  window.__addressOf = (title) => providerAddress(carriedFor(title)?.ids);
  window.__sheetOf = sheetOf;
  // Rules build some states by hand, patch by patch, the way a named state does.
  window.applyState = applyState;
  // The pipeline's state for a rule, through the layer — see `setPipeline`.
  window.__pipeline = setPipeline;
}

declare global {
  interface Window {
    /** Puts the pipeline in a state through the layer, and asks its status again. */
    __pipeline: (state: string) => void;
    /** Drives the prototype into a named state, without a click. */
    __go: (stateId: string, options?: { keep?: boolean }) => string;
    /** Every named state's id, in table order. */
    __states: () => string[];
    /** The interface back where every measurement starts. */
    __reset: () => boolean;
    /** Hides the harness chrome, or shows it again with `false`. */
    __measure: (enabled?: boolean) => boolean;
    /** The media the pipeline is refusing. */
    __blocked: () => unknown[];
    /** The page ids the interface can render. */
    __pages: () => string[];
    /** What the seed, or else the cache, knows of the medium a title names. */
    __carriedFor: (title: string) => CarriedIdentity | null;
    /** The address the medium a title names is reached at, or null. */
    __addressOf: (title: string) => { provider: string; id: string } | null;
    /** The seed sheet the layer answers for the medium a title names, or null. */
    __sheetOf: (title: string) => Record<string, unknown> | null;
    /** A named state's first step, for a rule that builds one by hand. */
    applyState: (patch: Partial<UiState>) => void;
    /** Puts the pull indicator back at rest, published by the engine. */
    __reposPTR?: () => void;
  }
}
