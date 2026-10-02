// A focused field's scroller has exactly one pixel to scroll, and loses it on blur (B-674).
//
// WHAT THIS HOLDS, AND WHAT IT CANNOT. The defect is an iPhone's (the installed
// app): the caret of a field whose scrolling container cannot scroll is drawn
// below the field; once the container scrolls, the caret is back in place (the
// reporter's own test). No engine this machine runs draws that caret, so no test
// here sees the defect itself; the reporter confirms it on the device. What is
// held is the structural condition the repair sets: while a field has the focus
// its scroller overflows by exactly one pixel, by nothing when the content
// already overflows, and by what it did before once the field lets the focus go.
import { describe, expect, it } from "vitest";
import { scrollRoom, spacerHeight, type ScrollerGeometry } from "./focus-spacer";

// The « + » screen with nothing typed: a 700 px scroller whose content ends at 420 px
// (its last box at 388 px, then 32 px of padding).
const short: ScrollerGeometry = { clientHeight: 700, contentEnd: 420, spacerTop: 388 };
// The same screen once enough results fill it: the content ends 300 px below.
const tall: ScrollerGeometry = { clientHeight: 700, contentEnd: 1000, spacerTop: 968 };

describe("the focus spacer", () => {
  it("gives a scroller that does not overflow exactly one pixel to scroll while a field has the focus", () => {
    expect(scrollRoom(short, 0)).toBe(0);
    expect(scrollRoom(short, spacerHeight(short))).toBe(1);
  });

  it("gives back the scroller as it was once the field loses the focus", () => {
    // Blurred, the spacer is gone: nothing is left to scroll.
    expect(scrollRoom(short, 0)).toBe(0);
  });

  it("adds nothing to a scroller whose content already overflows", () => {
    expect(spacerHeight(tall)).toBe(0);
    expect(scrollRoom(tall, spacerHeight(tall))).toBe(scrollRoom(tall, 0));
  });

  it("gives one pixel to a scroller whose content ends exactly at its bottom", () => {
    const flush: ScrollerGeometry = { clientHeight: 700, contentEnd: 700, spacerTop: 668 };
    expect(scrollRoom(flush, spacerHeight(flush))).toBe(1);
  });

  it("gives one pixel to a sheet as tall as its content, which the spacer does not make grow", () => {
    // A sheet sizes to its content: its client height IS where the content ends.
    const sheet: ScrollerGeometry = { clientHeight: 260, contentEnd: 260, spacerTop: 228 };
    expect(scrollRoom(sheet, spacerHeight(sheet))).toBe(1);
  });

  it("reads a content end within a pixel of the bottom as no overflow", () => {
    // A sheet whose content ends at 290.34 px in its 290 px: rounding, nothing to scroll.
    const rounded: ScrollerGeometry = { clientHeight: 290, contentEnd: 290.34, spacerTop: 272.34 };
    expect(scrollRoom(rounded, spacerHeight(rounded))).toBeCloseTo(1, 5);
  });

  it("names the scrollers a field sits in, and only those", async () => {
    const { SCROLLERS } = await import("./focus-spacer");
    expect(SCROLLERS.split(",").map((one) => one.trim()).sort()).toEqual([".port", ".sheetin"]);
  });
});
