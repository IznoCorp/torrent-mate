// A surface that pushed its own history entry has to take it BACK before the
// page changes under it.
//
// THE SHAPE, AND IT NAMES NO DOMAIN (invariant 10). A surface inside a page —
// a rubric, and whatever else comes to sit at that level — is a deliberate
// arrival, so it PUSHES (D1b rule 1). The page switch beneath it was written
// against a stack of « the entry page plus at most one »: it steps back exactly
// ONE entry when a tab arrives home, and that one step now lands on the
// surface's entry instead of the floor. Measured, with the surface open and the
// tab bar tapped: the address stayed `/settings`, the page stayed `cfg`, and
// the reader who asked for Acquisition got the rubric closed and nothing else.
//
// SO THE SURFACE GIVES ITS ENTRY BACK FIRST, and the tap is replayed onto a
// stack that is the shape the switch expects. Three things make that safe:
//
//   · IT LISTENS IN CAPTURE, so it runs before the engine's own delegation,
//     which sits in the bubble phase. `stopPropagation` there stops the event
//     reaching the bubble phase and leaves every other CAPTURING listener on
//     the document alone — the tap registry among them — because propagation
//     is stopped between phases, not between listeners of one target;
//   · IT DOES NOTHING WHEN A LAYER IS OPEN. A layer's entry sits above the
//     surface's, so the entry a back would take is the layer's, and closing a
//     layer is the ladder's own business;
//   · IT REPLAYS ON THE POP, never on a timer. The pop is the signal that the
//     entry is gone; a delay chosen by hand would be a delay that outlives the
//     thing it was set against.
//
// A SWITCH MADE FROM A LAYER needs none of this: the entry's trail says where
// the page's own entry lies (`app/trail.ts`), and the switch rewinds to it.
import { bridge } from "./shell-doors";

/** The `data-*` a control carries when tapping it changes the page. */
const PAGE_CHANGING = ["page", "go", "navgo"];

/**
 * Whether this element, or an ancestor of it, changes the page when tapped.
 *
 * Walks up the way the delegations do, because the tap lands on whatever the
 * button happens to draw inside itself — an icon, a span of text — and never on
 * the button.
 */
function pageChanger(target: EventTarget | null): HTMLElement | null {
  let node = target as HTMLElement | null;
  while (node !== null && node !== document.body) {
    if (PAGE_CHANGING.some((name) => node!.dataset[name] !== undefined))
      return node;
    node = node.parentElement;
  }
  return null;
}

/**
 * Makes a page change wait for one surface to give its history entry back.
 *
 * Args:
 *     isOpen: Whether the surface is open right now, asked at the moment of the
 *         tap — the surface owns that answer, and this module never learns what
 *         the surface IS.
 *
 * Returns:
 *     What to call when the surface has PUSHED an entry of its own. Open is not
 *     the same as having an entry: a surface is open at a cold load of its own
 *     address, and when a rule drives the state, with nothing pushed — and a
 *     surface that never calls this is one nothing here will ever step over.
 */
export function giveTheEntryBackFirst(isOpen: () => boolean): () => void {
  let posed = false;
  const hasItsOwnEntry = () => {
    if (!isOpen()) posed = false;
    return posed;
  };
  document.addEventListener("click", (event) => {
    if (!hasItsOwnEntry()) return;
    if ((history.state as { layer?: unknown } | null)?.layer !== undefined) return;
    const control = pageChanger(event.target);
    if (control === null) return;
    /* NOBODY ELSE ANSWERS THIS CLICK, and `stopPropagation` was not enough to
       say so. It stops the listeners on other NODES, and the page-changing
       verbs used to live on one — the engine's delegation, in the bubble
       phase. They are answered by the tap registry now, which listens in
       CAPTURE on this very node: a listener beside this one, which propagation
       does not reach. So the switch ran here AND again on the replayed tap,
       walking history twice — and the second walk landed on the exit guard,
       whose handler pushes the current address back on and takes every forward
       entry with it. Measured: the maintenance topic's entry gone
       (`url_state.py`), `history.length` 5 → 3. */
    event.stopImmediatePropagation();
    window.addEventListener("popstate", () => {
      // THE TAP IS MADE AGAIN, not simulated: the same element, the same
      // listeners, the same delegation — over a stack that is now the shape the
      // page switch was written against.
      control.click();
    }, { once: true });
    // THROUGH THE BRIDGE: the router's history instance is named by the file
    // that creates it, and a module that steps back asks that file to.
    bridge.back();
  }, true);
  // WHAT THE SURFACE CALLS WHEN IT HAS PUSHED. Handed back rather than
  // exported, so there is no way to claim an entry for a surface that never
  // registered one.
  return () => {
    posed = true;
  };
}
