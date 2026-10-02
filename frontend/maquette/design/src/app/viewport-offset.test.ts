// A stray visual-viewport offset is undone, and only a stray one (B-674).
//
// WHAT THIS HOLDS, AND WHAT IT CANNOT. The defect is an iPhone's (iOS 26, the
// installed app): its caret drawn 22 px under the field, the status bar's inset —
// the offset iOS leaves on the visual viewport of a document that cannot scroll
// (WebKit bug 297779). No engine this machine runs reproduces it, so no test
// here can be seen red on the defect itself; the reporter confirms it on the
// device. What is held is the decision the repair makes: an offset over a
// document that cannot scroll is undone when the field stays in view without it,
// and is left alone for a pinch-zoom, for a field the keyboard would cover, and
// for a document that scrolls. Seen red against a module that undid nothing.
import { describe, expect, it } from "vitest";
import { strayOffset, type ViewportReading } from "./viewport-offset";

// The phone of the report: 390 × 844, the keyboard closed, the document as tall as the window.
const rest: ViewportReading = {
  offsetTop: 0, scale: 1, height: 844, windowHeight: 844, documentHeight: 844, fieldBottom: null,
};

describe("strayOffset", () => {
  it("undoes the offset left once the keyboard has gone", () => {
    expect(strayOffset({ ...rest, offsetTop: 22 })).toBe(true);
  });

  it("undoes it with the keyboard open when the field stays in view without it", () => {
    // The add screen's field ends at 95 px; the keyboard leaves 500 px.
    expect(strayOffset({ ...rest, offsetTop: 22, height: 500, fieldBottom: 95 })).toBe(true);
  });

  it("leaves the pan iOS made to bring a low field above the keyboard", () => {
    expect(strayOffset({ ...rest, offsetTop: 120, height: 500, fieldBottom: 600 })).toBe(false);
  });

  it("leaves a pinch-zoom alone", () => {
    expect(strayOffset({ ...rest, offsetTop: 22, scale: 2 })).toBe(false);
  });

  it("leaves a document that scrolls alone", () => {
    expect(strayOffset({ ...rest, offsetTop: 22, documentHeight: 1200 })).toBe(false);
  });

  it("does nothing when nothing is offset", () => {
    expect(strayOffset(rest)).toBe(false);
  });
});
