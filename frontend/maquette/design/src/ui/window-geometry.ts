// WHAT THE GRID ACTUALLY DRAWS — the lanes, the line's height, and where the
// container starts inside its scroller.
//
// IT IS MEASURED, NEVER TYPED. Every number here was a prop once, and each was
// wrong in its own way: the lane count was a literal 3 while `.gallery` is a
// container query (four columns at 460 px of port, five at 620, six at 820, and
// nothing caps the port to a phone in production — at five the virtualiser
// believed in 621 lines where the grid drew 373); the row height moves with the
// lane count, since a narrower column makes a shorter 2:3 poster; and the
// container does not start at the scroller's origin, which shifted every offset
// by the height of the filters above it.
import { useLayoutEffect, useState, type RefObject } from "react";

/** What the window needs to know about the grid it is drawn in. */
export type WindowGeometry = {
  /** How many rows share a line, as the grid lays them out. */
  readonly lanes: number;
  /** One line's height, gap included. */
  readonly lineHeight: number;
  /** How far the container starts below its scroller's origin. */
  readonly scrollMargin: number;
};

/**
 * Reads the geometry from the rendered container, with the caller's estimates
 * standing in until there is something to measure.
 *
 * @param container The container the rows are drawn in.
 * @param scrollElement The scrolling ancestor.
 * @param estimates The first frame's guesses: a row's height, the gap, the lanes.
 * @param redrawnOn What makes the container a new drawing — a count, a draw key.
 * @returns The measured geometry, or the estimates until a measurement exists.
 */
export function useWindowGeometry(
  container: RefObject<HTMLDivElement | null>,
  scrollElement: () => HTMLElement | null,
  estimates: { rowHeight: number; gap: number; lanes: number },
  redrawnOn: readonly unknown[],
): WindowGeometry {
  // THE GEOMETRY IS MEASURED FROM THE RENDERED GRID, and the props are only the
  // estimate the first frame needs before anything exists to measure.
  //
  // The lane count was a PROP, typed 3. `.gallery` is a CONTAINER QUERY:
  // `repeat(3)` below 460px of port, then 4, then 5 at 620 and 6 at 820 — and
  // nothing caps the port to a phone's width in production. At five columns the
  // virtualiser believed in 621 lines where the grid draws 373. The row height
  // moves with it: a narrower column makes a shorter 2:3 poster.
  const [measured, setMeasured] =
    useState<{ lanes: number; lineHeight: number } | null>(null);
  useLayoutEffect(() => {
    const node = container.current;
    if (!node) return undefined;
    const read = () => {
      const style = getComputedStyle(node);
      const tracks = style.gridTemplateColumns;
      const columns = tracks && tracks !== "none" ? tracks.split(/\s+/).length : 1;
      // AN ITEM THAT IS NOT UNDER A FINGER: a tile wears `scale: 0.97` while a
      // press arms, so measuring that one sizes every line 3% short.
      const item =
        node.querySelector(
          ":scope > *:not([data-part='window/spacer']):not([data-pressing])")
        || node.querySelector(
          ":scope > *:not([data-part='window/spacer'])");
      // THE RECTANGLE, and not `offsetHeight`, which ROUNDS to an integer. The
      // line height here is 203.34375; rounding it shortened every windowed page
      // by four tenths of a pixel — twelve oracle divergences across the four
      // library states, from a change made to exclude that 3% scale. The scale
      // is excluded by choosing the element instead.
      const height = item ? item.getBoundingClientRect().height : 0;
      const rowGap = parseFloat(style.rowGap || style.gap) || 0;
      if (!height) return;
      setMeasured((held) =>
        held && held.lanes === columns
        && Math.abs(held.lineHeight - (height + rowGap)) < 0.5
          ? held
          : { lanes: columns, lineHeight: height + rowGap });
    };
    read();
    // AND AGAIN ON THE NEXT FRAME. The DRAW changes under the same container, so React
    // replaces the node on every redraw; an effect that measured only at commit
    // read a computed style of empty strings — measured — and the window
    // silently kept the props' estimate of three lanes at every width.
    const retry = requestAnimationFrame(read);
    const watcher = new ResizeObserver(read);
    watcher.observe(node);
    return () => {
      cancelAnimationFrame(retry);
      watcher.disconnect();
    };
  }, redrawnOn);


  // THE LIST DOES NOT START AT THE SCROLLER'S ORIGIN. `#libitems` sits below the
  // filters and the tabs inside the same scrollport; without telling the
  // virtualiser, every offset is short by that distance and the window sits
  // shifted down the list — measured at 485px of margin above against 742 below
  // where the overscan asks for the same on each side.
  const [scrollMargin, setScrollMargin] = useState(0);
  // MEASURED ONCE PER DRAW, not on every render: without a dependency list this
  // forced a layout read and a setState on every render the virtualiser causes
  // while scrolling.
  useLayoutEffect(() => {
    const node = container.current;
    const scroller = scrollElement();
    if (!node || !scroller) return;
    const distance = node.getBoundingClientRect().top
      - scroller.getBoundingClientRect().top
      + scroller.scrollTop;
    setScrollMargin((held) => (Math.abs(held - distance) < 0.5 ? held : distance));
  }, redrawnOn);

  return {
    lanes: measured ? measured.lanes : estimates.lanes,
    lineHeight: measured ? measured.lineHeight : estimates.rowHeight + estimates.gap,
    scrollMargin,
  };
}
