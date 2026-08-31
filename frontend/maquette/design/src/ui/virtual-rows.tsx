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
import type { ReactElement } from "react";

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

  // The virtualiser counts LINES, not rows: with three lanes, 1 861 titles are
  // 621 lines, and it is lines that have a height.
  const lineCount = Math.ceil(count / lanes);
  const lineHeight = rowHeight + gap;
  const virtualizer = useVirtualizer({
    count: lineCount,
    getScrollElement: scrollElement,
    estimateSize: () => lineHeight,
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

  const start = firstLine * lanes;
  const end = Math.min(count, (lastLine + 1) * lanes);

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
      id="libitems"
      className={properties.className}
      data-part={properties.part}
      data-virtualised={String(count)}
      dangerouslySetInnerHTML={{
        __html: spacer(before) + window_ + spacer(after),
      }}
    />
  );
}
