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
//
// ─────────────────────────────────────────────────────────────────────────────
// SPACERS, NOT ABSOLUTE POSITIONING, and this is the decision that keeps the
// rendering still. The usual shape puts every item at computed coordinates
// inside a relative container, which would re-derive `.gallery`'s CSS grid and
// `.sec`'s flex column in JavaScript and take that layout out of the oracle's
// field. Instead the window is rendered in place and two spacers stand in for
// what is not, so the grid lays the visible rows out exactly as it always did.
//
// ─────────────────────────────────────────────────────────────────────────────
// AND THE WINDOW MOVES BY ADDING AND REMOVING ROWS, NEVER BY REWRITING ITSELF.
//
// A first version set the whole window as one `dangerouslySetInnerHTML` string
// and re-applied it whenever the range moved — every row crossing, so about
// every 213px of gallery or 134px of list. That destroyed and recreated every
// visible node, and three things went with them:
//
//   * a row opened by a swipe was replaced by a closed one mid-gesture, and the
//     dying engine kept the detached node as its `openCard`;
//   * `:active` and `data-pressing` vanished from a tile under the finger;
//   * every `<img>` in the window was re-created and re-decoded — about forty
//     per crossing, in the lot whose subject is the PERFORMANCE FLOOR. Before
//     this lot, scrolling re-rendered nothing at all.
//
// So the rows are kept in a map by index and the DOM is updated at the EDGES:
// what left is removed, what arrived is inserted, and what stayed is the same
// node it was. The container therefore has no React children — it is written
// imperatively, which is what preserving identity across a scroll requires when
// the rows are strings somebody else composed.
import { useVirtualizer } from "@tanstack/react-virtual";
import { useLayoutEffect, useRef, useState, type ReactElement } from "react";

/** What the surface tells the window, and none of it names a domain. */
export type VirtualRowsProperties = {
  /** How many rows exist in total. */
  readonly count: number;
  /**
   * One row's height in pixels, gap excluded — the ESTIMATE for the first
   * frame only. The real height is measured from the rendered grid, because it
   * moves with the column count.
   */
  readonly rowHeight: number;
  /** The gap between rows, so a spacer stands in for the space too. */
  readonly gap: number;
  /** How many rows share a line, as an estimate. Measured once drawn. */
  readonly lanes: number;
  /** The scrolling ancestor. Windowing needs to know what is scrolling. */
  readonly scrollElement: () => HTMLElement | null;
  /** Turns ONE index into markup. The surface's own, and only that. */
  readonly renderRow: (index: number) => string;
  /** The container's class and naming attribute — the surface's, unchanged. */
  readonly className: string;
  readonly part: string;
  /** Remounts the container when the surface says the draw is a new one. */
  readonly drawKey: number | string;
};

/** Builds one row's element from the markup the surface composed. */
function elementFor(markup: string): Element | null {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

/**
 * A spacer that displaces whole lines rather than taking a cell of its own.
 *
 * ONLY THE HEIGHT IS WRITTEN HERE, and it has to be: it is the measurement the
 * window computes on every range change, and no stylesheet can hold a number
 * that changes as the reader scrolls. `grid-column: 1 / -1` is not a
 * measurement — it is a DRAWING decision, that a spacer spans the whole row
 * rather than taking a cell — so it lives in `styles/base.css`, keyed on the
 * part this emits. Written inline it was a rule the stylesheet did not have.
 */
function spacerElement(height: number): HTMLElement {
  const node = document.createElement("div");
  node.setAttribute("aria-hidden", "true");
  node.setAttribute("data-part", "window/spacer");
  node.style.height = `${height}px`;
  return node;
}

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
  // THE NODE AND THE STRING IT WAS BUILT FROM, per live index. The string is
  // what says whether a row that is still in range has to be redrawn — see
  // the effect below.
  const liveRows = useRef(new Map<number, { node: Element; markup: string }>());
  const spacers = useRef<{ before: HTMLElement | null; after: HTMLElement | null }>(
    { before: null, after: null });
  const lastDraw = useRef<number | string | null>(null);

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
    const container = containerRef.current;
    if (!container) return undefined;
    const read = () => {
      const style = getComputedStyle(container);
      const tracks = style.gridTemplateColumns;
      const columns = tracks && tracks !== "none" ? tracks.split(/\s+/).length : 1;
      // AN ITEM THAT IS NOT UNDER A FINGER: a tile wears `scale: 0.97` while a
      // press arms, so measuring that one sizes every line 3% short.
      const item =
        container.querySelector(
          ":scope > *:not([data-part='window/spacer']):not([data-pressing])")
        || container.querySelector(
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
    watcher.observe(container);
    return () => {
      cancelAnimationFrame(retry);
      watcher.disconnect();
    };
  }, [count, properties.drawKey]);

  const activeLanes = measured ? measured.lanes : lanes;
  const lineHeight = measured ? measured.lineHeight : rowHeight + gap;
  const lineCount = Math.ceil(count / activeLanes);

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

  // THE MEASUREMENTS ARE RE-TAKEN WHEN THE PITCH MOVES, and nothing else does
  // it. `@tanstack/virtual-core` memoises `getMeasurements()` on the options it
  // considers geometry — count, padding, scroll margin, key, lanes, gap — and
  // `estimateSize` is NOT among them, so a new pitch is read by this component
  // and ignored by the virtualiser until one of those others moves.
  //
  // WHAT THAT COST, measured through the real controls: a selection row is
  // about 60 px against a card's 126. Enter « Sélectionner » on a list scrolled
  // past a page and leave it again, and the browse window is placed with the
  // SELECTION pitch — the spacer reads 5 620 px, the first row sits 2 807 px
  // below the port, and the library is blank. It stays blank through a scroll
  // in either direction, because scrolling changes no memoised option either.
  // Entering the mode looked healthy only because the shorter rows brought the
  // paging sentinel into view and a page landing moved `count`.
  // AND THE READER KEEPS THEIR PLACE ACROSS IT, which is a row and not a pixel.
  // Shorter rows make the same row sit at a smaller offset, so re-measuring at a
  // deep scroll leaves the offset past the new end and the browser clamps it to
  // zero — the list jumps to the top, which is the same loss wearing the
  // opposite symptom. The first drawn line is remembered and restored.
  // THE PLACE IS TAKEN BEFORE THE RESET, and restored after the new pitch is
  // measured. A new draw key empties the container, which collapses the
  // scroller's height and makes the browser clamp the offset to zero — so by
  // the time the pitch is known the position is already lost. The first drawn
  // line under the OLD key is what a reader's place is; the new offset for it
  // is a row's index times the new pitch, and only the virtualiser can say
  // that, once it has re-measured.
  const lastPitch = useRef(lineHeight);
  const lastKey = useRef(properties.drawKey);
  const lastFirstLine = useRef(0);
  const placeToKeep = useRef<number | null>(null);
  const restoreTo = useRef<number | null>(null);
  if (lastKey.current !== properties.drawKey) {
    lastKey.current = properties.drawKey;
    placeToKeep.current = lastFirstLine.current;
  }
  if (lastPitch.current !== lineHeight) {
    lastPitch.current = lineHeight;
    virtualizer.measure();
    restoreTo.current = placeToKeep.current ?? lastFirstLine.current;
    placeToKeep.current = null;
  }

  const lines = virtualizer.getVirtualItems();
  const firstLine = lines.length ? lines[0].index : 0;
  const lastLine = lines.length ? lines[lines.length - 1].index : -1;
  lastFirstLine.current = firstLine;

  useLayoutEffect(() => {
    const index = restoreTo.current;
    restoreTo.current = null;
    if (index != null && index > 0) {
      virtualizer.scrollToIndex(index, { align: "start" });
    }
  });

  // THE SPACERS ARE THEMSELVES ITEMS, AND THE CONTAINER PUTS A GAP BESIDE EACH.
  // Measured, at 33 oracle divergences of exactly +16px: the un-windowed list
  // has N rows and N-1 gaps, three children make it N+1. Each spacer gives one
  // gap back, and a spacer with nothing to displace is not rendered at all —
  // a zero-height child still brings its gap with it.
  const linesBefore = firstLine;
  const linesAfter = Math.max(0, lineCount - 1 - lastLine);
  const before = linesBefore ? linesBefore * lineHeight - gap : 0;
  const after = linesAfter ? linesAfter * lineHeight - gap : 0;

  const start = firstLine * activeLanes;
  const end = Math.min(count, (lastLine + 1) * activeLanes);

  // THE WINDOW MOVES AT ITS EDGES. Rows that stay in range keep the very nodes
  // they had, so an open swipe, a pressed state and a decoded image survive a
  // scroll.
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // THE RESET LIVES HERE, NOT IN AN EFFECT OF ITS OWN, and that is not
    // tidiness. It WAS its own effect, declared after this one — so on mount
    // React ran them in order, this one filled the container and the reset then
    // emptied it. Measured: 17 oracle divergences and a page 310px tall where it
    // is 3 557. Two effects that must happen in an order are one effect.
    if (lastDraw.current !== properties.drawKey) {
      lastDraw.current = properties.drawKey;
      liveRows.current = new Map();
      spacers.current = { before: null, after: null };
      container.replaceChildren();
    }
    const live = liveRows.current;

    for (const [index, held] of [...live]) {
      if (index < start || index >= end) {
        held.node.remove();
        live.delete(index);
      }
    }

    if (!spacers.current.before || !spacers.current.before.isConnected) {
      spacers.current.before = spacerElement(0);
      container.prepend(spacers.current.before);
    }
    if (!spacers.current.after || !spacers.current.after.isConnected) {
      spacers.current.after = spacerElement(0);
      container.append(spacers.current.after);
    }

    // INSERTED FROM THE BOTTOM OF THE RANGE UPWARDS, and the direction is the
    // whole correctness of this loop.
    //
    // Each new row is placed before the row that FOLLOWS it, so that the DOM
    // order is the data order — which the grid's auto-placement then follows.
    // Walking the range upwards, the follower of a new row is itself new and
    // not yet in the tree, so those rows fell through to « append before the
    // tail spacer » and landed at the END of the window. Scrolling UP by one
    // line in a three-lane gallery moved two rows to the bottom of the window;
    // a flick moved all but one. The list mode was immune by arithmetic — one
    // lane means the last new index always has a live follower — which is why
    // a rule driving only the list saw nothing.
    //
    // Descending, the follower is ALWAYS resolved: either it was already live,
    // or this loop inserted it one step earlier.
    //
    // AND A ROW STILL IN RANGE IS REDRAWN WHEN ITS MARKUP CHANGED, which is the
    // only thing that says a kept node has stopped telling the truth. « Keep
    // every index already live » was the first form and it is wrong in one
    // direction: a delete rewrites the rows under the window — the source's own
    // optimistic write — and the row the reader just deleted stayed on screen,
    // because nothing here asked whether its string had moved. Making the whole
    // window depend on a KEY instead was wrong in the other direction: a key
    // coarse enough to catch that empties the window on writes that changed
    // nothing, which is what destroys a tap. The string is the exact question,
    // asked per row, and it costs one comparison against markup already
    // composed.
    for (let index = end - 1; index >= start; index -= 1) {
      const markup = renderRow(index);
      const held = live.get(index);
      if (held && held.markup === markup) continue;
      const node = elementFor(markup);
      if (!node) continue;
      if (held) {
        // REPLACED IN PLACE, so the row keeps its position without the tail of
        // the window being rebuilt around it — AND THE READER'S PLACE IN IT
        // SURVIVES. A row whose markup changes under a finger is a row somebody
        // is using: toggling a checkbox in selection mode rewrites its
        // `aria-pressed` and therefore its string, and the replacement threw
        // keyboard focus to the document root on every toggle of the mode built
        // for going through a library. Focus is restored onto the node that
        // takes the old one's place, which is where the reader left it.
        // WHERE THE READER'S FOCUS IS INSIDE THE ROW, not merely that it is.
        // Restoring onto the row's ROOT loses a focused child — and in browse
        // mode the root is a `<div>` with no tabindex, so `focus()` on it is a
        // no-op and the place goes to the document root. The child is found
        // again by its position among the row's focusable elements.
        const active = document.activeElement;
        const focusable = 'button, [tabindex], a[href], input';
        const focusedAt = held.node.contains(active) && active !== held.node
          ? [...held.node.querySelectorAll(focusable)].indexOf(active as Element)
          : -1;
        const focused = held.node.contains(active);
        if (!held.node.isConnected) {
          // A node the document no longer holds cannot be replaced — the call
          // is a silent no-op and the map would keep a dead node until its
          // index left the window. Insert it as a new row instead.
          live.delete(index);
        } else {
          held.node.replaceWith(node);
          live.set(index, { node, markup });
          if (focused) {
            // PREVENT SCROLL, and it is not a detail. A live row is not
            // necessarily visible — the window keeps four lines beyond each
            // edge — and a row's markup moves for reasons that have nothing to
            // do with the reader: a delete above it shifts every row. Without
            // this the port scrolled back to the row being replaced, 593 px
            // measured, landing the reader somewhere they never asked to be.
            const heir = focusedAt >= 0
              ? node.querySelectorAll(focusable)[focusedAt]
              : node;
            if (heir instanceof HTMLElement) heir.focus({ preventScroll: true });
          }
          continue;
        }
      }
      live.set(index, { node, markup });
      const following = live.get(index + 1);
      if (following && following.node.isConnected) {
        container.insertBefore(node, following.node);
      } else {
        container.insertBefore(node, spacers.current.after);
      }
    }

    spacers.current.before.style.height = `${before}px`;
    spacers.current.before.style.display = before > 0 ? "" : "none";
    spacers.current.after.style.height = `${after}px`;
    spacers.current.after.style.display = after > 0 ? "" : "none";
  });



  // NO `key` ON THE CONTAINER, and removing it is what put the scroll position
  // back. The key existed so a new draw got a NEW node, discarding the inline
  // transforms the engine writes onto rows — and that job belongs to the reset
  // above now, which empties the same node instead of replacing it.
  //
  // Keyed, React swapped in an EMPTY div at commit and filled it in the layout
  // effect afterwards: `#port`'s scrollHeight collapsed for that moment, the
  // browser clamped scrollTop to 0, and R94 fell — « scrolled to 300 with a
  // layer open and came back to 0 ». The old whole-innerHTML form never showed
  // it because React created the node WITH its content in one commit.
  return (
    <div
      ref={containerRef}
      id="libitems"
      className={properties.className}
      data-part={properties.part}
      data-virtualised={String(count)}
      data-lanes={String(activeLanes)}
    />
  );
}
