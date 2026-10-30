// A POPOVER — a transient layer anchored to what was tapped.
//
// It is `{ anchor, content }`: the frame decides WHERE, the feature decides
// WHAT. The engine built both in one function — the node, its placement, its
// dismissal AND the sentence it shows. Only the first three are the frame's;
// the sentence is a producer and moves to its feature at L19 (Part 12), so it
// crosses here as facts and is drawn from them.
//
// THE CLAMP IS THE WHOLE OF WHAT THIS LAYER DOES THAT A TOOLTIP DOES NOT: it
// stays inside the phone frame, on both sides, and flips above its anchor when
// there is room. Eight pixels of margin, measured against `#device` and not
// against the window — a 390px frame on a desktop is centred, so a clamp
// against the viewport would let it leave the device on the left.
import { useLayoutEffect, useRef, useState } from "react";
import type { ReactElement } from "react";

import { popover, popoverTitle } from "./variants";

export type PopoverContent = {
  /** What it is — « S01E02 · Le titre ». */
  title: string;
  /** What is true of it — a date, or that the date is unknown. */
  text: string;
  /** Where it stands, in the vocabulary the matrix uses. */
  note: string;
};

const WIDTH = 220;
const MARGIN = 8;
/** Above the anchor rather than below, once there is this much room over it. */
const ROOM_ABOVE = 120;

export function Popover({
  anchor,
  content,
}: {
  anchor: HTMLElement | null;
  content: PopoverContent | null;
}): ReactElement | null {
  const node = useRef<HTMLDivElement | null>(null);
  const [placement, setPlacement] = useState<{ left: number; top: number } | null>(
    null,
  );

  // MEASURED AFTER THE CONTENT IS IN THE TREE AND BEFORE THE PAINT: the flip
  // depends on the popover's own height, which is not known until it is drawn.
  // The engine read `offsetHeight` for the same reason, at the same moment.
  useLayoutEffect(() => {
    if (!anchor || !content || !node.current) {
      setPlacement(null);
      return;
    }
    const box = anchor.getBoundingClientRect();
    const device = document
      .querySelector("#device")
      ?.getBoundingClientRect() ?? { left: 0, right: window.innerWidth, top: 0 };
    let left = box.left + box.width / 2 - WIDTH / 2;
    left = Math.max(
      device.left + MARGIN,
      Math.min(left, device.right - WIDTH - MARGIN),
    );
    const above = box.top - device.top > ROOM_ABOVE;
    const top = above
      ? box.top - node.current.offsetHeight - MARGIN
      : box.bottom + MARGIN;
    setPlacement({ left, top });
  }, [anchor, content]);

  if (!anchor || !content) return null;
  return (
    <div
      ref={node}
      className={popover()}
      data-part="episode/popover"
      style={{
        left: `${placement?.left ?? 0}px`,
        top: `${placement?.top ?? 0}px`,
        // Hidden until it has been placed, so it is never painted at 0,0 for a
        // frame. THE ENGINE DID NOT DO THIS — it appended the node and THEN
        // read `offsetHeight` to place it, so it painted once unplaced. This is
        // a rendering change inside a conversion, small and deliberate, and it
        // is written down rather than left resting on a false sentence about
        // the code it replaced.
        visibility: placement ? undefined : "hidden",
      }}
    >
      <b className={popoverTitle()}>{content.title}</b>
      {content.text}
      <br />
      <span className="text-muted-foreground">{content.note}</span>
    </div>
  );
}
