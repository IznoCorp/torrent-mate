// The bottom panel's verbs, and the address an addressed panel travels at.
//
// The store arrives as an ARGUMENT rather than being read off `window`: this
// module is what a producer's `open` runs through, so the thing it writes is
// the thing the boot handed it, and no reader has to work out which of the two
// doors was meant.
import { flushSync } from "react-dom";
import { refuseBlock, type PanelDescriptor } from "../ui/panel/contract";
import { addressOf, isScreenPath, withPanel } from "../lib/addresses";
import type { Store } from "./store";

declare global {
  interface Window {
    // The probe R56 calls to prove the panel REFUSES a block nobody declared.
    // Published here because the constructor it exercises is a component now.
    __unknownPanel: () => void;
  }
}

/* The bottom panel, as the shell's verbs — what every legacy producer calls
   instead of the dead `openSheet(html)`. The descriptor of FACTS crosses
   untouched; the markup is `PanelContent`'s business.

   The store write is flushed SYNCHRONOUSLY, and that is the whole subtlety of
   moving this layer. React commits a frame later by default, while the legacy
   layer's callers were written against a DOM that was already updated when
   `openSheet`/`closeSheet` returned: `data-del` closes the sheet and opens a
   dialog on the next line, and the dialog raises the SAME shared `#scrim` — a
   commit landing after that line would clear the scrim out from under the
   dialog. Flushing keeps the ordering every caller already relies on, and the
   panel's own content changes in the same task as the class that reveals it,
   so the sheet never slides in showing the previous panel for a frame. */
/* The address an addressed panel travels at — D1 read literally. The query
   says how THIS surface is being looked at, and under a screen the surface IS
   the screen: the panel hangs off the path one is already on, with whatever
   else that address carries kept verbatim.

   Composing it from `state.page` instead is not a cosmetic difference. A
   screen is a ROUTE, mounted by the router, so pushing the page's own path
   stops the route matching and the screen the operator linked to unmounts
   behind the panel — measured on `/media/$provider/$id`. Off a screen, the
   page composes its address as it always did: the page IS the surface
   there. */
function panelAddress(address: string): string {
  if (isScreenPath(window.location.pathname))
    return (
      window.location.pathname + withPanel(window.location.search, address)
    );
  const { state } = window.__store.read();
  return addressOf(String(state.page ?? ""), state, address);
}

/* Raised while a panel is being put back onto the entry that ALREADY records
   it. It is the one case where a panel opens and history must not move: a
   Forward lands on the layer entry the first open pushed, and that entry is
   already there, already `{ layer: "sheet" }`, already carrying the panel's own
   address. Pushing a second one would leave a duplicate the next Back spends
   without taking the panel's address off. */
let onCurrentEntry = false;

/**
 * Runs a producer's open with the history write suppressed.
 *
 * The producer is called through this door rather than handed an argument,
 * because the argument would have to travel through every producer that opens
 * a panel — and they open it by describing FACTS, which is the whole of what
 * they are meant to know.
 *
 * Args:
 *     open: The producer call that opens the panel.
 */
function openPanelOnCurrentEntry(open: () => void): void {
  onCurrentEntry = true;
  try {
    open();
  } finally {
    onCurrentEntry = false;
  }
}

/**
 * Installs the panel's verbs onto the published seam.
 *
 * Called from the boot once the store exists and after the history bridge is
 * in place — `openPanel` below pushes a layer entry through it.
 *
 * Args:
 *     store: The single owner of the mutable state.
 */
export function installPanelHost(store: Store): void {
function openPanel(descriptor: PanelDescriptor): void {
  // Same order as the legacy `openSheet`: the layer first, the history entry
  // second. This file is SHELL code — the seam itself — so it writes the store
  // directly rather than through data.ts's `writeUiState` component door.
  // THE PANEL OPENS BY ITS OWN SLIDE, and the view transition that briefly
  // wrapped this is GONE (operator, 2026-08-31). It existed to carry the
  // poster from the tile into the panel; the operator watched the real
  // slow-motion and withdrew the gesture — « la transition poster entre liste
  // et panneau n'est vraiment pas fluide du tout, elle est même très
  // dérangeante ». What replaces it is being arbitrated; nothing is drawn here
  // until it is named.
  //
  // Wrapping the opening WITHOUT the carry would have been worse than nothing:
  // the sheet already slides up in its own stylesheet, and a view transition
  // over it is the same two-systems-one-element defect the hero paid for.
  flushSync(() =>
    store.write({ panelDescriptor: descriptor, panelOpen: true }),
  );
  if (onCurrentEntry) return;
  try {
    // D1's second tier: a panel whose subject is stable travels in the query,
    // so a reload reopens it. One with no `address` is transient and keeps the
    // address it opened over.
    window.__bridge.pushLayer(
      "sheet",
      descriptor.address ? panelAddress(descriptor.address) : undefined,
    );
  } catch (error) {
    // B-026's own residual: `window.__bridge` is assigned synchronously at this
    // module's top level, before any producer can call `open` — so unlike
    // the legacy `openSheet` swallow this copies, there is no boot-time
    // window where the bridge is genuinely absent. A throw here means the
    // write itself failed, and the store above already flushed the panel
    // open: silence would leave the interface showing the panel with no
    // history entry recording it, the exact URL/UI disagreement DOIT-10
    // forbids. Same wiring as `recordPath`'s and `data-navgo`'s own
    // tails.
    // ENGLISH, and not in `fr.json`: a console message is a tool message,
    // read by a developer, never by a reader of the interface.
    console.error("openPanel: navigation write failed", error);
    window.__navEchec = true;
  }
}

function closePanel(pop?: boolean): void {
  // Guarded per LAYER, exactly as `closeSheet` was: closing an already-closed
  // sheet would consume a history entry that belongs to someone else.
  if (!isPanelOpen()) return;
  flushSync(() => store.write({ panelOpen: false }));
  // `pop` means the entry is already being popped by the gesture that got us
  // here; otherwise the layer unwinds its own, through the engine's latch.
  if (!pop) window.__derouler?.("sheet");
}

// The STORE answers, never the DOM: a legacy caller asks in the middle of its
// own task ("is a layer up before I open a screen?"), and the store is right
// at that instant whatever React has painted.
function isPanelOpen(): boolean {
  return store.read().state.panelOpen === true;
}

window.__panel = {
  open: openPanel,
  close: closePanel,
  isOpen: isPanelOpen,
  openOnCurrentEntry: openPanelOnCurrentEntry,
};

/* Lets the contract check prove the refusal rather than trust the comment on
   it: a block type nobody declared must raise, not draw nothing. Called as a
   plain function, not rendered — the dispatcher refuses before it reads
   anything else, which is what makes the refusal provable from outside. */
window.__unknownPanel = () => refuseBlock({ type: "ceci-n-existe-pas" });
}
