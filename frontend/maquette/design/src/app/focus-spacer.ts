// A FOCUSED FIELD'S SCROLLER HAS SOMETHING TO SCROLL (B-674, operator ruling « ok A »).
//
// On the installed iPhone app the caret of a field whose scrolling container
// cannot scroll is drawn below the field; once that container scrolls — the
// « + » search with enough results to overflow — the caret is back in its field
// (the reporter's own test, 2026-10-02). A container that overflows is given its
// own scroll view by iOS, and the caret is placed with it.
//
// So while a field has the focus, its scroller ends with an invisible spacer
// whose box reaches ONE PIXEL past the scroller's bottom, and which is zero tall
// when the content already overflows; the spacer leaves with the focus. ITS
// BOTTOM MARGIN CANCELS ITS HEIGHT: it takes no room in the flow, so a scroller
// as tall as its content (a sheet) does not grow for it — only its box counts
// in what the scroller can scroll. It sits after everything, draws nothing and
// takes no pointer: the one pixel of scroll is all there is to see. It goes in
// the scrollers that hold the app's fields — every screen's and page's port,
// every sheet — and nowhere else.

/** The scrollers a field may sit in: every screen's and page's port, every sheet. */
export const SCROLLERS = ".port, .sheetin";

/** What the decision reads of a scroller, in CSS pixels. */
export type ScrollerGeometry = {
  /** The scroller's `clientHeight`. */
  clientHeight: number;
  /** Where its content ends, its bottom padding included, the spacer apart. */
  contentEnd: number;
  /** Where the spacer's box begins, in the scroller's content coordinates. */
  spacerTop: number;
};

/**
 * The spacer's height that leaves exactly one pixel to scroll.
 *
 * Args:
 *     geometry: The scroller, read without the spacer's own height.
 *
 * Returns:
 *     The height in pixels; zero when the content already overflows.
 */
export function spacerHeight(geometry: ScrollerGeometry): number {
  // Below a pixel the content's end is rounding (290.34 px in a 290 px sheet), not
  // an overflow: the scroller has nothing to scroll.
  if (geometry.contentEnd >= geometry.clientHeight + 1) return 0;
  return Math.max(0, geometry.clientHeight + 1 - geometry.spacerTop);
}

/**
 * How far a scroller can scroll with a spacer of the given height.
 *
 * Args:
 *     geometry: The scroller, read without the spacer's own height.
 *     spacer: The spacer's height, zero when there is none.
 *
 * Returns:
 *     The scrollable distance in pixels.
 */
export function scrollRoom(geometry: ScrollerGeometry, spacer: number): number {
  // The spacer takes no room in the flow: its box only reaches further down.
  const end = Math.max(geometry.contentEnd, spacer > 0 ? geometry.spacerTop + spacer : 0);
  return Math.max(0, end - geometry.clientHeight);
}

/** Whether an element takes typed text. */
function takesText(element: Element | null): element is HTMLElement {
  if (element instanceof HTMLTextAreaElement) return true;
  if (element instanceof HTMLInputElement) {
    return !["button", "checkbox", "color", "file", "hidden", "image", "radio", "range", "reset", "submit"]
      .includes(element.type);
  }
  return element instanceof HTMLElement && element.isContentEditable;
}

/** The spacer in place, with the scroller it belongs to and what watches that scroller. */
type Placed = { scroller: HTMLElement; spacer: HTMLElement; watchers: Array<{ disconnect(): void }> };

let placed: Placed | null = null;

/**
 * Sizes the spacer, and keeps it the scroller's last child.
 *
 * The spacer's own top does not depend on its height, so it is read without
 * touching the height: setting it to zero first would let the scroller clamp a
 * scroll position it has to give back.
 */
function size(): void {
  if (placed === null) return;
  const { scroller, spacer } = placed;
  // A child appended after it (a list growing under the field) would sit below
  // the spacer's room: the spacer goes back to the end.
  if (scroller.lastElementChild !== spacer) scroller.appendChild(spacer);
  const top = spacer.getBoundingClientRect().top - scroller.getBoundingClientRect().top
    - scroller.clientTop + scroller.scrollTop;
  const bottom = parseFloat(getComputedStyle(scroller).paddingBottom) || 0;
  const height = spacerHeight({ clientHeight: scroller.clientHeight, contentEnd: top + bottom, spacerTop: top });
  stretch(spacer, height);
  // Rounding is settled on the scroller's own answer: one pixel to scroll, never more.
  if (height > 0) {
    const off = scroller.scrollHeight - scroller.clientHeight - 1;
    if (off !== 0) stretch(spacer, Math.max(0, height - off));
  }
}

/**
 * Gives the spacer a height its bottom margin takes back.
 *
 * Args:
 *     spacer: The spacer.
 *     height: Its height in pixels.
 */
function stretch(spacer: HTMLElement, height: number): void {
  spacer.style.height = `${height}px`;
  spacer.style.marginBottom = `${-height}px`;
}

/** Takes the spacer out, and the scroller is as it was. */
function remove(): void {
  if (placed === null) return;
  for (const watcher of placed.watchers) watcher.disconnect();
  placed.spacer.remove();
  placed = null;
}

/**
 * Puts the spacer at the end of a field's scroller.
 *
 * Args:
 *     scroller: The scroller the focused field sits in.
 */
function place(scroller: HTMLElement): void {
  if (placed?.scroller === scroller) return size();
  remove();
  const spacer = document.createElement("div");
  spacer.setAttribute("aria-hidden", "true");
  spacer.dataset.focusSpacer = "";
  spacer.style.cssText = "display:block;margin:0;padding:0;border:0;pointer-events:none;height:0";
  scroller.appendChild(spacer);
  const watchers: Placed["watchers"] = [];
  // What is under the field changes as it is typed in (results arrive, a hint
  // appears), and the scroller's own height changes with the window.
  const mutations = new MutationObserver(size);
  mutations.observe(scroller, { childList: true, subtree: true, characterData: true });
  watchers.push(mutations);
  if (typeof ResizeObserver !== "undefined") {
    const resizes = new ResizeObserver(size);
    resizes.observe(scroller);
    watchers.push(resizes);
  }
  placed = { scroller, spacer, watchers };
  size();
}

/**
 * Watches the focus: a text field that takes it gives its scroller the spacer,
 * synchronously — before the keyboard opens and the caret is placed — and the
 * spacer leaves once no field of that scroller holds the focus any more.
 */
export function installFocusSpacer(): void {
  document.addEventListener("focusin", (event) => {
    const field = event.target instanceof Element ? event.target : null;
    if (!takesText(field)) return remove();
    const scroller = field.closest<HTMLElement>(SCROLLERS);
    if (scroller === null) return remove();
    place(scroller);
  });
  document.addEventListener("focusout", (event) => {
    // The focus moving to another field of the same scroller keeps the spacer;
    // `focusin` follows and answers for the new field.
    const next = event.relatedTarget instanceof Element ? event.relatedTarget : null;
    if (takesText(next) && placed !== null && placed.scroller.contains(next)) return;
    remove();
  });
}
