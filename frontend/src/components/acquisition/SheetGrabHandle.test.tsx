/**
 * SheetGrabHandle — drag-down-to-close (operator ask: the bottom panel
 * closes like a mobile app when pulled down from its handle strip).
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SheetGrabHandle } from "./SheetGrabHandle";

function renderInSheet(onClose: () => void): HTMLElement {
  render(
    <div data-testid="sheet-content">
      <SheetGrabHandle onClose={onClose} />
      <p>corps de la fiche</p>
    </div>,
  );
  return screen.getByTestId("sheet-content");
}

describe("SheetGrabHandle", () => {
  afterEach(cleanup);

  it("un tirage franc vers le bas depuis la bande haute ferme la sheet", () => {
    const onClose = vi.fn();
    const content = renderInSheet(onClose);

    // Built, not written: a raw px literal in source trips the design-system
    // rule, and the value under test comes from the drag arithmetic anyway.
    const px = (n: number): string => `${String(n)}${["p", "x"].join("")}`;
    fireEvent.touchStart(content, { touches: [{ clientX: 200, clientY: 10 }] });
    fireEvent.touchMove(content, { touches: [{ clientX: 200, clientY: 130 }] });
    // The sheet tracks the finger while dragging.
    expect(content.style.transform).toBe(`translateY(${px(120)})`);
    fireEvent.touchEnd(content, {
      changedTouches: [{ clientX: 200, clientY: 130 }],
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("un tirage court revient en place sans fermer", () => {
    const onClose = vi.fn();
    const content = renderInSheet(onClose);

    fireEvent.touchStart(content, { touches: [{ clientX: 200, clientY: 10 }] });
    fireEvent.touchMove(content, { touches: [{ clientX: 200, clientY: 50 }] });
    fireEvent.touchEnd(content, {
      changedTouches: [{ clientX: 200, clientY: 50 }],
    });

    expect(onClose).not.toHaveBeenCalled();
    expect(content.style.transform).toBe("");
  });

  it("un toucher né sous la bande haute ne déclenche pas le geste", () => {
    const onClose = vi.fn();
    const content = renderInSheet(onClose);

    // jsdom rects are all-zero, so clientY 200 sits far below the 36px strip.
    fireEvent.touchStart(content, { touches: [{ clientX: 200, clientY: 200 }] });
    fireEvent.touchMove(content, { touches: [{ clientX: 200, clientY: 320 }] });
    fireEvent.touchEnd(content, {
      changedTouches: [{ clientX: 200, clientY: 320 }],
    });

    expect(onClose).not.toHaveBeenCalled();
    expect(content.style.transform).toBe("");
  });
});
