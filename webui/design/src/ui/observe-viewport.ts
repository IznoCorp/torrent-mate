// WHAT SIZE THE WINDOW'S SCROLLER IS, WATCHED THROUGH ITS BORDER BOX.
//
// `@tanstack/virtual-core` 3.19 moved its own scroller observer from the border
// box to the CONTENT box (`observeElementRect`, `observe(element, { box:
// 'content-box' })`), and the move is what made WebKit at 390 px report
// « ResizeObserver loop completed with undelivered notifications » on the
// library (`lib-selection`, `signin-plex-bare`; `responsive.py`).
//
// THE CAUSE IS IN HOW THE PAGE USES THE SCROLLER, not in the library. `#port`
// reserves the bars' heights as padding-bottom (`index.html`), and those heights
// are measurements published by ResizeObservers of their own (`app/bar-height.ts`
// writes `--tm-bottom-bar-h` from inside its callback). A bar coming or going
// therefore changes `#port`'s PADDING, which is part of its content box and not
// of its border box: the new observer saw a resize, delivered after the bar's
// callback had written the property, at a depth the delivery had already passed
// — and the browser's answer to a change it cannot deliver in the same frame is
// that error.
//
// A padding change moves nothing the window reads. What the window needs is the
// viewport's size (`clientWidth`/`clientHeight`), and the padding is inside it;
// a change of the border box is what moves that size, which is the box the
// observer watched before 3.19. So this watches the border box, and reads the
// same measurement the library does, from the same properties.
//
// WHAT IT DOES NOT SEE, and 3.17 did not either: a classic scrollbar appearing
// narrows `clientWidth` with the border box unchanged. The window windows a
// vertical list by HEIGHT, `#port` clips its horizontal overflow
// (`overflow-x-clip`) so no scrollbar can shorten it, and the columns of a gallery
// are read from the rendered grid (`ui/window-geometry.ts`), never from this width.
import type { Rect, Virtualizer } from "@tanstack/react-virtual";

/**
 * Reports the scroller's viewport size now and whenever its border box changes.
 *
 * Meant for the virtualizer's `observeElementRect` option, whose contract it keeps:
 * a first report before returning, a callback per change, and a disposer.
 *
 * Args:
 *     instance: The virtualizer that asks, which knows its scroller and its window.
 *     report: Receives the viewport's size, rounded as the library rounds it.
 *
 * Returns:
 *     The disposer that stops watching, or undefined when there is no scroller or window.
 */
export function observeViewport(
  instance: Virtualizer<HTMLElement, Element>,
  report: (rect: Rect) => void,
): (() => void) | undefined {
  const scroller = instance.scrollElement;
  const targetWindow = instance.targetWindow;
  if (!scroller || !targetWindow) return undefined;

  const read = () =>
    report({ width: Math.round(scroller.clientWidth), height: Math.round(scroller.clientHeight) });
  read();

  if (!targetWindow.ResizeObserver) return () => {};
  const observer = new targetWindow.ResizeObserver(read);
  observer.observe(scroller, { box: "border-box" });
  return () => observer.unobserve(scroller);
}
