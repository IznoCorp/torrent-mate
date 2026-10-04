// WHERE THE READER WAS, ACROSS A REDRAW THAT MOVES THE GEOMETRY UNDER THEM.
//
// The window re-measures itself when the row pitch changes — a selection row is
// about 60 px against a card's 126, a tile is 213 — and re-measuring at a deep
// scroll leaves the offset meaning a different row, or past the new end, where
// the browser clamps it to zero and the list jumps to the top. Keeping the
// reader in front of the same row across that is its own question, with its own
// state, and it is not the window's drawing.
//
// WHAT A PLACE IS, and every one of these was learnt from a reading:
//
//   - a ROW, never a pixel: the same offset names a different row at the other
//     pitch;
//   - an ITEM, never a line: a line is one row in a list and three in a
//     gallery, so a line index restored across a mode switch sent a reader at
//     row 21 to row 3;
//   - the FIRST VISIBLE row, never the first drawn one: the window keeps four
//     lines of overscan beyond each edge, and restoring the top of the overscan
//     walked the reader four rows up on every switch;
//   - and it EXPIRES. A place is kept for the frame between a new draw key and
//     the pitch that key brings, and no longer. Browsing to selection in a
//     gallery changes the key and not the pitch (a tile is a tile), so a place
//     taken at row 39 sat waiting while the reader went back to the top — and
//     the next pitch change of any kind, a rotation or a window widening
//     minutes later, fired it and threw them 2 940 px down the list.
import { useRef } from "react";

/** Where a reader is: the row, and whether they had scrolled into the list. */
export type Place = {
  /** The row's own index, lanes multiplied in — never a line. */
  readonly item: number;
  /**
   * Whether the port was past the container's own start. Item 0 is a place: a
   * reader three hundred pixels down, with the first row a sliver at the top,
   * is looking at row 0, and refusing to restore it because the index is zero
   * moved them two rows down on every round trip. What is NOT restored is a
   * port ABOVE the container's start, where the head is on screen and scrolling
   * to row 0 would hide it.
   */
  readonly scrolled: boolean;
};

/** What the window asks of a place across one render. */
export type ReaderPlace = {
  /** Records where the reader is, after the range for this render is known. */
  remember: (place: Place) => void;
  /** The place to restore in this commit, consumed by the asking. */
  take: () => Place | null;
};

/**
 * Keeps a reader's place across the redraws that move the geometry under them.
 *
 * Called DURING the render, after the virtualiser exists and before its range is
 * read: a pitch change has to re-measure before the range is computed, or the
 * range is the previous pitch's.
 *
 * Args:
 *     drawKey: What makes this a different DRAWING — the mode, the selection.
 *     lineHeight: The pitch the geometry measured for the drawing on screen.
 *     measuredFor: The draw key that measurement belongs to, null until one
 *         exists. A place expires when the NEW drawing has been measured
 *         without the pitch moving.
 *     remeasure: Invalidates the virtualiser's memoised measurements. It
 *         memoises them on options that do not include the estimated size, so
 *         a new pitch is read by the caller and ignored by the virtualiser
 *         until this is called.
 *
 * Returns:
 *     What to remember after the range, and what to restore after the draw.
 */
export function useReaderPlace(
  drawKey: number | string,
  lineHeight: number,
  measuredFor: number | string | null,
  remeasure: () => void,
): ReaderPlace {
  const lastPitch = useRef(lineHeight);
  const lastKey = useRef(drawKey);
  const lastPlace = useRef<Place>({ item: 0, scrolled: false });
  const kept = useRef<(Place & { forKey: number | string }) | null>(null);
  const toRestore = useRef<Place | null>(null);

  // THE PLACE IS TAKEN BEFORE THE RESET. A new draw key empties the container,
  // which collapses the scroller's height and makes the browser clamp the offset
  // to zero — so by the time the new pitch is known the position is already
  // lost.
  if (lastKey.current !== drawKey) {
    lastKey.current = drawKey;
    kept.current = { ...lastPlace.current, forKey: drawKey };
  }
  // AND IT EXPIRES HERE, one measurement later, if the new drawing turned out to
  // have the same pitch. See the head of this file for what that cost.
  if (kept.current && measuredFor === drawKey && lastPitch.current === lineHeight) {
    kept.current = null;
  }
  if (lastPitch.current !== lineHeight) {
    lastPitch.current = lineHeight;
    remeasure();
    // A PLACE BELONGS TO THE DRAWING IT WAS TAKEN FOR. Kept past that, it is a
    // row number from another listing waiting for the next pitch change.
    const held = kept.current;
    toRestore.current = held && held.forKey === drawKey
      ? { item: held.item, scrolled: held.scrolled }
      : lastPlace.current;
    kept.current = null;
  }

  return {
    remember: (place) => {
      lastPlace.current = place;
    },
    take: () => {
      const place = toRestore.current;
      toRestore.current = null;
      return place;
    },
  };
}
