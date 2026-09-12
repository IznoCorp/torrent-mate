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
// AND THE SWITCH MADE FROM A LAYER IS THE OTHER HALF, answered by COUNTING
// rather than by intercepting. A layer's entry sits above the surface's, so
// there is nothing here a back could take: the rewind that unwinds the layer
// has to know the surface is there. It asks — `window.__stackedSurfaces()` —
// and every surface that pushes inside a page answers. Nothing else changes:
// the engine's rewind was reading a count it ASSUMED, and now it reads one
// that is told to it.

// EVERY SURFACE THAT HAS PUSHED INSIDE A PAGE, asked rather than counted here:
// each one knows whether it is open and this module never learns what any of
// them IS. The answer is what the ladder's rewind adds to its own two entries.
//
// « OPEN » IS NOT « HAS AN ENTRY », and that distinction is the whole of the
// `posed` flag. A surface is open at a COLD LOAD of its own address, where
// nothing was pushed because nothing was navigated; and it is open when a rule
// DRIVES the state directly, which the harness does constantly. Counting those
// would have the rewind step over an entry that is not there, and the reader
// would leave the application from a tab tap. So a surface says it has posed an
// entry when it pushes one, and the flag goes out by itself the moment the
// surface is no longer open — read lazily, so nothing has to remember to clear
// it.
const stacked: (() => boolean)[] = [];

/**
 * How many surfaces inside the page have an entry of their own right now.
 *
 * Published on the window because its reader is the dying engine's rewind,
 * which no module imports — the same door every other driving seam uses, and
 * it dies with the engine.
 */
function stackedSurfaces(): number {
  return stacked.filter((isOpen) => isOpen()).length;
}

declare global {
  interface Window {
    /** How many surfaces inside the page have pushed an entry of their own. */
    __stackedSurfaces?: () => number;
  }
}

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
 *     the same as having an entry — see the note on `posed` above — and a
 *     surface that never calls this is one nothing here will ever step over.
 */
export function giveTheEntryBackFirst(isOpen: () => boolean): () => void {
  let posed = false;
  const hasItsOwnEntry = () => {
    if (!isOpen()) posed = false;
    return posed;
  };
  stacked.push(hasItsOwnEntry);
  window.__stackedSurfaces = stackedSurfaces;
  document.addEventListener("click", (event) => {
    if (!hasItsOwnEntry()) return;
    if ((history.state as { layer?: unknown } | null)?.layer !== undefined) return;
    const control = pageChanger(event.target);
    if (control === null) return;
    event.stopPropagation();
    window.addEventListener("popstate", () => {
      // THE TAP IS MADE AGAIN, not simulated: the same element, the same
      // listeners, the same delegation — over a stack that is now the shape the
      // page switch was written against.
      control.click();
    }, { once: true });
    history.back();
  }, true);
  // WHAT THE SURFACE CALLS WHEN IT HAS PUSHED. Handed back rather than
  // exported, so there is no way to claim an entry for a surface that never
  // registered one.
  return () => {
    posed = true;
  };
}
