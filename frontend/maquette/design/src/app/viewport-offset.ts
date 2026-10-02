// A STRAY VISUAL-VIEWPORT OFFSET IS UNDONE (B-674).
//
// The document never scrolls: `html` and `body` are `100dvh` and every page
// scrolls inside the frame. iOS 26 still leaves an offset on the visual viewport
// of such a document once the keyboard has opened (WebKit bug 297779), and the
// installed app's caret is then drawn that far from its field — 22 px under the
// search field on an iPhone SE, the status bar's inset (the TM Bugs report of
// 2026-10-02). The page is drawn where it belongs and the caret is not, so
// every text field shares the defect.
//
// NOTHING IS DRAWN DIFFERENTLY: the offset is scrolled back to zero, and only
// when it is stray — never a pinch-zoom, never the pan iOS makes to lift a low
// field above the keyboard, never a document that scrolls.

/** What the decision reads of the window, the visual viewport and the focused field. */
export type ViewportReading = {
  /** `visualViewport.offsetTop`, in CSS pixels. */
  offsetTop: number;
  /** `visualViewport.scale`: 1 unless the reader has zoomed. */
  scale: number;
  /** `visualViewport.height`: the window minus the keyboard. */
  height: number;
  /** `innerHeight`. */
  windowHeight: number;
  /** The document's scroll height. */
  documentHeight: number;
  /** The focused text field's bottom edge in the layout viewport, or null when none has the focus. */
  fieldBottom: number | null;
};

// Below a pixel an offset is rounding, not a defect.
const SLACK = 1;

/**
 * Whether the visual viewport carries an offset nothing asked for.
 *
 * @param reading What the window says now.
 * @returns True when scrolling back to zero is the repair and hides nothing.
 */
export function strayOffset(reading: ViewportReading): boolean {
  if (Math.abs(reading.offsetTop) < SLACK) return false;
  if (Math.abs(reading.scale - 1) > 0.01) return false;
  if (reading.documentHeight > reading.windowHeight + SLACK) return false;
  // A field the keyboard would cover once the offset is gone keeps the pan.
  return reading.fieldBottom === null || reading.fieldBottom <= reading.height;
}

/** The focused element when it takes text, else null. */
function focusedField(): HTMLElement | null {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement)) return null;
  const typed = active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement
    || active.isContentEditable;
  return typed ? active : null;
}

/** Reads the window and undoes a stray offset. */
function settle(): void {
  const viewport = window.visualViewport;
  if (!viewport) return;
  const field = focusedField();
  const reading: ViewportReading = {
    offsetTop: viewport.offsetTop,
    scale: viewport.scale,
    height: viewport.height,
    windowHeight: window.innerHeight,
    documentHeight: document.documentElement.scrollHeight,
    fieldBottom: field ? field.getBoundingClientRect().bottom : null,
  };
  if (strayOffset(reading)) window.scrollTo(0, 0);
}

/**
 * Watches the visual viewport and undoes a stray offset whenever it moves, and
 * whenever a field takes or leaves the focus — the keyboard's two moments.
 */
export function installViewportOffset(): void {
  const viewport = window.visualViewport;
  if (!viewport) return;
  // A frame later: iOS moves the viewport after the focus event, not during it.
  const soon = () => requestAnimationFrame(settle);
  viewport.addEventListener("resize", soon);
  viewport.addEventListener("scroll", soon);
  document.addEventListener("focusin", soon);
  document.addEventListener("focusout", soon);
}
