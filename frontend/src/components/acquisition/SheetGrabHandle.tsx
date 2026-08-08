/**
 * SheetGrabHandle — the bottom-sheet handle bar, draggable to close.
 *
 * Renders the maquette ``.sheetgrab`` bar unchanged and wires the mobile-app
 * gesture the operator asked for: dragging DOWN from the top strip of the
 * sheet follows the finger and, released past a threshold, closes the sheet.
 *
 * The touch listeners sit on the sheet CONTENT (the handle's parent), gated
 * to gestures that START in the top strip: the visual bar is only 36×4 px,
 * far too small a target for a thumb, while the strip is easy to hit and is
 * exactly where the maquette draws the handle.
 */

import { useEffect, useRef, type ReactElement } from "react";

/** Height of the grab strip at the top of the sheet, in CSS pixels. */
const GRAB_STRIP_PX = 36;

/** Downward travel past which a release closes the sheet, in CSS pixels. */
const CLOSE_THRESHOLD_PX = 80;

/** Props for {@link SheetGrabHandle}. */
export interface SheetGrabHandleProps {
  /** Closes the hosting sheet. */
  readonly onClose: () => void;
}

/**
 * The grab bar of a bottom sheet, with drag-down-to-close.
 *
 * Args:
 *   props: See {@link SheetGrabHandleProps}.
 *
 * Returns:
 *   The ``.sheetgrab`` bar element.
 */
export function SheetGrabHandle({
  onClose,
}: SheetGrabHandleProps): ReactElement {
  const barRef = useRef<HTMLDivElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const content = barRef.current?.parentElement;
    if (content == null) return undefined;

    let startY = 0;
    let dy = 0;
    let dragging = false;

    const onTouchStart = (e: TouchEvent): void => {
      if (e.touches.length !== 1) return;
      const t = e.touches[0];
      if (t == null) return;
      const top = content.getBoundingClientRect().top;
      if (t.clientY - top > GRAB_STRIP_PX) return;
      dragging = true;
      startY = t.clientY;
      dy = 0;
      // The sheet must TRACK the finger — an eased transition would lag it.
      content.style.transition = "none";
    };

    const onTouchMove = (e: TouchEvent): void => {
      if (!dragging) return;
      const t = e.touches[0];
      if (t == null) return;
      dy = Math.max(0, t.clientY - startY);
      // Claim the pan: without this the browser scrolls the sheet body and
      // cancels the touch stream mid-drag.
      e.preventDefault();
      content.style.transform = `translateY(${String(dy)}px)`;
    };

    const onTouchEnd = (): void => {
      if (!dragging) return;
      dragging = false;
      content.style.transition = "";
      if (dy > CLOSE_THRESHOLD_PX) {
        // Radix's exit animation owns the transform from here.
        onCloseRef.current();
        return;
      }
      content.style.transform = "";
    };

    content.addEventListener("touchstart", onTouchStart, { passive: true });
    content.addEventListener("touchmove", onTouchMove, { passive: false });
    content.addEventListener("touchend", onTouchEnd);
    content.addEventListener("touchcancel", onTouchEnd);
    return () => {
      content.removeEventListener("touchstart", onTouchStart);
      content.removeEventListener("touchmove", onTouchMove);
      content.removeEventListener("touchend", onTouchEnd);
      content.removeEventListener("touchcancel", onTouchEnd);
    };
  }, []);

  return <div ref={barRef} className="sheetgrab" aria-hidden="true" />;
}
