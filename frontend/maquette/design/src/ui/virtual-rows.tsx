// WINDOWING A LONG LIST — P24, and it knows nothing of what it draws.
//
// VOCABULARY (invariant 10): it takes a count, a size and a function that turns
// an index into markup, and it never learns what a row IS. What stays with the
// surface is which rows exist and how one is drawn.
//
// THE LIBRARY HOLDS 1 861 TITLES. Without this, scrolling to the end leaves
// 1 861 nodes in the document — and a poster that grows after paint then moves
// the scroll position under the reader's thumb, which is why P29 is this
// property's PRECONDITION and lands before it (D-L12-2).
//
// ─────────────────────────────────────────────────────────────────────────────
// WHY A LIBRARY AND NOT TEN LINES OF ARITHMETIC. The operator reversed D9's
// rule 2 on 2026-08-31: hand-written code is for maths NOBODY has written, and a
// reliable, maintained, proven, widely used library that solves EXACTLY the
// problem is PREFERRED to re-coding it. Three candidates were surveyed with
// their registry facts and put to the operator, who named this one.
//
// `@tanstack/react-virtual` is the one rule 1 admits: it is HEADLESS — the
// registry's own description is « Headless UI for virtualizing scrollable
// elements in React » — so it returns measurements and renders nothing, and
// every drawing decision stays in the stylesheet where the oracle can read it.
// The two alternatives render their own scroller and write inline styles onto
// each child, which moves drawing out of the design reference and is refused
// whatever rule 2 says.
//
// ─────────────────────────────────────────────────────────────────────────────
// SPACERS, NOT ABSOLUTE POSITIONING, and this is the decision that keeps the
// rendering still.
//
// The usual shape for a virtualiser is `position: absolute` on every item inside
// a relative container. That would replace `.gallery`'s CSS grid and `.sec`'s
// flex column with hand-computed coordinates — re-deriving, in JavaScript, a
// layout the stylesheet already expresses, and moving it out of the oracle's
// field in the process.
//
// Instead the window is rendered in place and two SPACERS stand in for what is
// not: one before, one after, each sized to the rows it replaces. The grid and
// the flex column lay the visible rows out exactly as they always did, so the
// end state is the one the oracle recorded, and the node count is constant.
import { useVirtualizer } from "@tanstack/react-virtual";
import { useLayoutEffect, useRef, useState, type ReactElement } from "react";

/** What the surface tells the window, and none of it names a domain. */
export type VirtualRowsProperties = {
  /** How many rows exist in total. */
  readonly count: number;
  /**
   * One row's height in pixels, gap excluded.
   *
   * MEASURED, never guessed. Both of this application's list modes are
   * fixed-height — tiles at 203.34px, cards at 126px — which is what the survey
   * established before anything was adopted, and it is why this takes a number
   * rather than a measuring callback.
   */
  readonly rowHeight: number;
  /** The gap between rows, so a spacer stands in for the space too. */
  readonly gap: number;
  /** How many rows share a line. 1 for a list, 3 or 4 for a gallery. */
  readonly lanes: number;
  /** The scrolling ancestor. Windowing needs to know what is scrolling. */
  readonly scrollElement: () => HTMLElement | null;
  /**
   * Turns ONE index into markup. The surface's own, and only that.
   *
   * A range renderer was tried first and made every caller write the same
   * slice-map-join — which is this module's job, not the surface's, and it cost
   * the calling file eight lines it did not have to spend.
   */
  readonly renderRow: (index: number) => string;
  /** The container's class and naming attribute — the surface's, unchanged. */
  readonly className: string;
  readonly part: string;
  /** Remounts the container when the surface says the draw is a new one. */
  readonly drawKey: number | string;
};

/**
 * Renders only the rows near the viewport, with spacers standing in for the rest.
 *
 * Args:
 *     properties: The count, the geometry, the scroller and the row renderer.
 *
 * Returns:
 *     The container the surface would have rendered, holding a window.
 */
export function VirtualRows(properties: VirtualRowsProperties): ReactElement {
  const { count, rowHeight, gap, lanes, scrollElement, renderRow } = properties;
  const containerRef = useRef<HTMLDivElement | null>(null);

  // THE GEOMETRY IS MEASURED FROM THE RENDERED GRID, and the props are only the
  // estimate the first frame needs before anything exists to measure.
  //
  // The lane count was a PROP, typed 3. `.gallery` is a CONTAINER QUERY:
  // `repeat(3)` below 460px of port, then 4, then 5 at 620 and 6 at 820 — and
  // nothing caps the port to a phone's width in production. The only 390px
  // frame is `styles/harness.css`, which ships nowhere. At five columns the
  // virtualiser believed in 621 lines where the grid draws 373, sized its
  // spacers for three per line, and put the wrong rows under the finger.
  //
  // The row height moves with it for the same reason: a narrower column makes a
  // shorter 2:3 poster, so 203.34375 is the height at THREE columns and at no
  // other width.
  //
  // A container query is a DESIGNED state. The window reads it rather than being
  // told about it — which is also the only form that survives the next
  // breakpoint somebody adds to the stylesheet.
  const [measured, setMeasured] = useState<{ lanes: number; lineHeight: number } | null>(null);
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const read = () => {
      const style = getComputedStyle(container);
      // One track per column, as the grid resolves it. A flex column (the list
      // mode) resolves to `none`, which is one lane.
      const tracks = style.gridTemplateColumns;
      const columns = tracks && tracks !== "none" ? tracks.split(/\s+/).length : 1;
      const item = container.querySelector(":scope > *:not([data-part='window/spacer'])");
      const height = item ? (item as HTMLElement).getBoundingClientRect().height : 0;
      const rowGap = parseFloat(style.rowGap || style.gap) || 0;
      if (!height) return;
      setMeasured((held) =>
        held && held.lanes === columns && Math.abs(held.lineHeight - (height + rowGap)) < 0.5
          ? held
          : { lanes: columns, lineHeight: height + rowGap });
    };
    read();
    // AND AGAIN ON THE NEXT FRAME. The container is keyed by the draw, so React
    // replaces the node on every redraw; an effect that measured only at commit
    // read a computed style of empty strings — measured, `gridTemplateColumns`
    // came back '' and the window silently kept the props' estimate of three
    // lanes at every width.
    const retry = requestAnimationFrame(read);
    const watcher = new ResizeObserver(read);
    watcher.observe(container);
    return () => {
      cancelAnimationFrame(retry);
      watcher.disconnect();
    };
  }, [count, properties.drawKey]);

  const activeLanes = measured ? measured.lanes : lanes;
  const lineHeight = measured ? measured.lineHeight : rowHeight + gap;

  // The virtualiser counts LINES, not rows: at three lanes 1 861 titles are 621
  // lines, and it is lines that have a height.
  const lineCount = Math.ceil(count / activeLanes);

  // THE LIST DOES NOT START AT THE SCROLLER'S ORIGIN, and a virtualiser that
  // assumes it does renders the wrong window.
  //
  // `#libitems` sits 179px below the top of `#port` — the filters and the tabs
  // are above it, inside the same scrollport. Without telling the virtualiser
  // so, every offset it computes is short by that distance: measured at
  // scrollTop 1200, the rendered window ran from -485px to +1517px around a
  // 775px viewport, which is 485 of margin above and 742 below where the
  // overscan asks for the same on each side. The visible rows were still
  // covered HERE — but the safety margin at the top was two thirds of what it
  // was meant to be, and it is the top that a scroll-up eats first.
  //
  // Measured rather than passed in: a caller told to hand over a distance would
  // be told to hand over a number that changes with the surface above it.
  const [scrollMargin, setScrollMargin] = useState(0);
  // MEASURED ONCE PER DRAW, not on every render. Without a dependency list this
  // forced a `getBoundingClientRect` and a `setState` on every render the
  // virtualiser causes while scrolling — a layout read per frame, in the lot
  // whose subject is the performance floor.
  useLayoutEffect(() => {
    const container = containerRef.current;
    const scroller = scrollElement();
    if (!container || !scroller) return;
    const distance = container.getBoundingClientRect().top
      - scroller.getBoundingClientRect().top
      + scroller.scrollTop;
    setScrollMargin((held) => (Math.abs(held - distance) < 0.5 ? held : distance));
  }, [count, properties.drawKey]);

  const virtualizer = useVirtualizer({
    count: lineCount,
    getScrollElement: scrollElement,
    estimateSize: () => lineHeight,
    scrollMargin,
    // Enough rendered beyond the viewport that a fast flick never shows a gap,
    // and few enough that the node count stays a small constant.
    overscan: 4,
  });

  const lines = virtualizer.getVirtualItems();
  const firstLine = lines.length ? lines[0].index : 0;
  const lastLine = lines.length ? lines[lines.length - 1].index : -1;

  // THE SPACERS ARE THEMSELVES ITEMS, AND THE CONTAINER PUTS A GAP BESIDE EACH.
  //
  // Measured, and it cost 33 oracle divergences of exactly +16px — two gaps of
  // 8. The container is a flex column or a grid with its own `gap`, and the
  // spacers sit in it as ordinary children, so one gap appears between the
  // leading spacer and the first visible row and another between the last and
  // the trailing spacer. The un-windowed list has N rows and N-1 gaps; three
  // children make it N+1.
  //
  // So each spacer gives ONE gap back, and a spacer with nothing to displace is
  // not rendered at all rather than rendered at zero height — a zero-height
  // child still brings its gap with it, which is the whole of the +16.
  const linesBefore = firstLine;
  const linesAfter = Math.max(0, lineCount - 1 - lastLine);
  const before = linesBefore ? linesBefore * lineHeight - gap : 0;
  const after = linesAfter ? linesAfter * lineHeight - gap : 0;

  const start = firstLine * activeLanes;
  const end = Math.min(count, (lastLine + 1) * activeLanes);

  // THE SPACERS ARE PART OF THE SAME MARKUP STRING, and that is not a
  // shortcut — it is what keeps the DOM the shape the rest of the interface
  // expects.
  //
  // A React wrapper holding the rows (`display: contents`) was tried first and
  // the layout was correct — the oracle stayed green, because `contents` makes
  // the tiles participate in the grid exactly as before. But a tile's
  // `parentElement` was then the WRAPPER rather than `.gallery`, and
  // `harness/cards.py`'s R50 reads a tile's parent to compare one gallery
  // against another: three states failed with « columns (1, 3) » on a layout
  // that was pixel-perfect. React refuses `dangerouslySetInnerHTML` beside
  // children, so the way to have no wrapper is to have no children.
  const spacer = (height: number) =>
    height > 0
      ? `<div aria-hidden="true" data-part="window/spacer" `
        + `style="grid-column:1/-1;height:${height}px"></div>`
      : "";
  const window_ = Array.from(
    { length: Math.max(0, end - start) },
    (_unused, offset) => renderRow(start + offset),
  ).join("");

  return (
    <div
      key={properties.drawKey}
      ref={containerRef}
      id="libitems"
      className={properties.className}
      data-part={properties.part}
      data-virtualised={String(count)}
      data-lanes={String(activeLanes)}
      dangerouslySetInnerHTML={{
        __html: spacer(before) + window_ + spacer(after),
      }}
    />
  );
}
