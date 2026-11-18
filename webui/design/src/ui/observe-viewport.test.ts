// The window's scroller is watched through its BORDER box (virtual-core 3.19 watches the content box).
//
// WHAT MAKES THIS NON-VACUOUS. `#port` takes the bars' heights as padding-bottom, and the bars publish
// them from ResizeObserver callbacks of their own (`app/bar-height.ts`). Watched through the content
// box, a bar coming or going changed what the observer saw after the delivery that wrote it, and WebKit
// at 390 px answered « ResizeObserver loop completed with undelivered notifications » on the library.
// The first case below is the library's own observer, kept to show it is the one that watches the
// content box: it fails the day the library changes that, and this module can then go.
import { observeElementRect } from "@tanstack/react-virtual";
import type { Rect } from "@tanstack/react-virtual";
import { describe, expect, it } from "vitest";
import { observeViewport } from "./observe-viewport";
import { SCROLLER_OBSERVERS } from "./virtual-rows";

type Watch = { target: unknown; options: ResizeObserverOptions | undefined };

/** A window whose ResizeObserver records what it is asked to watch, and lets a test deliver a resize. */
function fakeWindow() {
  const watches: Watch[] = [];
  const unwatched: unknown[] = [];
  const callbacks: Array<() => void> = [];
  class FakeResizeObserver {
    constructor(callback: () => void) {
      callbacks.push(callback);
    }
    observe(target: unknown, options?: ResizeObserverOptions) {
      watches.push({ target, options });
    }
    unobserve(target: unknown) {
      unwatched.push(target);
    }
  }
  return { targetWindow: { ResizeObserver: FakeResizeObserver }, watches, unwatched, callbacks };
}

/** The part of a virtualizer the observers read: its scroller and its window. */
function fakeVirtualizer(scroller: object | null, targetWindow: object | null) {
  return { scrollElement: scroller, targetWindow, options: {} } as never;
}

describe("the scroller observer", () => {
  it("is the one the window's virtualizer is given", () => {
    expect(SCROLLER_OBSERVERS.observeElementRect).toBe(observeViewport);
  });

  it("is not the library's, which watches the content box", () => {
    const { targetWindow, watches } = fakeWindow();
    const scroller = { clientWidth: 390, clientHeight: 775 };
    observeElementRect(fakeVirtualizer(scroller, targetWindow), () => {});
    expect(watches.map((watch) => watch.options?.box)).toEqual(["content-box"]);
  });

  it("watches the border box", () => {
    const { targetWindow, watches } = fakeWindow();
    const scroller = { clientWidth: 390, clientHeight: 775 };
    observeViewport(fakeVirtualizer(scroller, targetWindow), () => {});
    expect(watches).toEqual([{ target: scroller, options: { box: "border-box" } }]);
  });

  it("reports the viewport's size at once, rounded, and again on each resize", () => {
    const { targetWindow, callbacks } = fakeWindow();
    const scroller = { clientWidth: 390.4, clientHeight: 774.6 };
    const reports: Rect[] = [];
    observeViewport(fakeVirtualizer(scroller, targetWindow), (rect) => reports.push(rect));
    expect(reports).toEqual([{ width: 390, height: 775 }]);

    scroller.clientHeight = 702;
    callbacks[0]();
    expect(reports).toEqual([{ width: 390, height: 775 }, { width: 390, height: 702 }]);
  });

  it("stops watching its scroller when disposed", () => {
    const { targetWindow, unwatched } = fakeWindow();
    const scroller = { clientWidth: 390, clientHeight: 775 };
    const dispose = observeViewport(fakeVirtualizer(scroller, targetWindow), () => {});
    dispose?.();
    expect(unwatched).toEqual([scroller]);
  });

  it("watches nothing when there is no scroller or no window", () => {
    const { targetWindow } = fakeWindow();
    const reports: Rect[] = [];
    expect(observeViewport(fakeVirtualizer(null, targetWindow), (rect) => reports.push(rect))).toBeUndefined();
    expect(observeViewport(fakeVirtualizer({ clientWidth: 1, clientHeight: 1 }, null), (rect) => reports.push(rect))).toBeUndefined();
    expect(reports).toEqual([]);
  });

  it("reports once and watches nothing in a window with no ResizeObserver", () => {
    const reports: Rect[] = [];
    const dispose = observeViewport(
      fakeVirtualizer({ clientWidth: 390, clientHeight: 775 }, {}), (rect) => reports.push(rect));
    expect(reports).toEqual([{ width: 390, height: 775 }]);
    expect(dispose).toBeTypeOf("function");
  });
});
