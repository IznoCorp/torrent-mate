// THE POSTER THAT TRAVELS FROM A TILE INTO THE PANEL (P6).
//
// A long press on a medium opens the panel, and the panel shows the same
// poster. Without a shared element the poster is drawn twice — it vanishes on
// the card and reappears, a different size, in a layer sliding up. With one it
// is the SAME picture moving, which is the whole difference between a document
// swapping content and an application answering a gesture.
//
// ─────────────────────────────────────────────────────────────────────────────
// WHY THIS LIVES IN `app/` AND MARKS THE NODE ITSELF.
//
// `view-transition-name` must be UNIQUE in the document, so it cannot be put on
// `.tile .p` by a class rule — every tile would carry the same name and the
// browser would ignore all of them. Exactly one tile has to be marked, at the
// moment the gesture picks it.
//
// The tile is drawn by the dying engine, so its markup cannot be given the
// attribute; and `lib/press-arbitration.ts` is vocabulary, which may not learn
// what a poster is. So this installs from the React side against the nodes as
// they stand — the posture `app/drawer-gesture.ts` established and wrote down:
// it watches what both worlds already emit and ZERO LINES ARE ADDED TO THE
// ENGINE.
//
// ─────────────────────────────────────────────────────────────────────────────
// THE NAME LIVES IN THE STYLESHEET, NOT HERE (D9 rule 1). This module writes an
// ATTRIBUTE; `styles/base.css` decides that `[data-carrying]` is a transition
// name and what the transition looks like. A name assigned in JavaScript would
// move a drawing decision out of the design reference.
//
// AND THE MARK MUST LEAVE THE TILE AS THE PANEL ARRIVES. A shared element is one
// name on the OLD state and the same name on the NEW one; if the tile still
// carried it once the panel is up, two elements would answer to it in the same
// frame and the browser would skip the transition entirely. `releaseCarried()`
// is what the panel's own commit calls, inside the transition, so the name is on
// the tile when the snapshot is taken and on `.sheetposter` afterwards.

/** The attribute the stylesheet reads. Written here, drawn there. */
const CARRYING = "data-carrying";

/** The poster a press is currently addressing, or `null` between gestures. */
let carried: Element | null = null;

/**
 * Finds the poster inside whatever a press has landed on.
 *
 * Args:
 *     target: Where the finger went down.
 *
 * Returns:
 *     The poster element to carry, or `null` when this surface has none.
 */
function posterWithin(target: Element): Element | null {
  const medium = target.closest("[data-panel]") ?? target.closest(".card, .tile");
  if (!medium) return null;
  // A tile IS its poster; a card holds one beside its text.
  return medium.matches(".tile") ? medium : medium.querySelector(".poster, .p");
}

/**
 * Releases the mark, so the name is free for the surface receiving it.
 *
 * Called by the panel's own commit, INSIDE the view transition: the snapshot of
 * the old state has already been taken by then, and the new state must not
 * carry the same name twice.
 */
export function releaseCarriedPoster(): void {
  if (!carried) return;
  carried.removeAttribute(CARRYING);
  carried = null;
}

/**
 * Watches for a press and marks the poster it addresses.
 *
 * Installed once at boot. It marks on `pointerdown` rather than when the press
 * fires, because the mark has to be in place before the transition takes its
 * snapshot — and a mark on a press that never completes costs nothing: a
 * `view-transition-name` on an element no transition involves is inert.
 */
export function installSharedPoster(): void {
  document.addEventListener(
    "pointerdown",
    (event) => {
      releaseCarriedPoster();
      if (!event.isPrimary || !(event.target instanceof Element)) return;
      const poster = posterWithin(event.target);
      if (!poster) return;
      carried = poster;
      poster.setAttribute(CARRYING, "");
    },
    { passive: true },
  );
  // A gesture that ends without opening a panel leaves nothing behind. Deferred
  // by a frame: the press fires while the finger is still down, but a TAP lifts
  // first and its own layer may open on the click that follows.
  const clear = () => requestAnimationFrame(() => releaseCarriedPoster());
  window.addEventListener("pointerup", clear);
  window.addEventListener("pointercancel", clear);
}
