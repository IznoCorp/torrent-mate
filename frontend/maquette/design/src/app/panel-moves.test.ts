// A panel asked for before its read landed opens only if nothing moved since (R513).
//
// WHAT MAKES THIS NON-VACUOUS. Each case asks first and moves second, so a counter that
// never moved, or one that moved on every read, both fail a case: the first that must
// still open, or one of those that must not.
import { describe, expect, it, vi } from "vitest";

const walk = vi.hoisted(() => ({ naming: false }));
vi.mock("./page-switch", () => ({ walk }));

import { askPanel, interfaceMoved, stillAsked, watchLandings } from "./panel-moves";
import { createStore } from "./store";

describe("a deferred panel open", () => {
  it("still opens when nothing moved", () => {
    const asked = askPanel();
    expect(stillAsked(asked)).toBe(true);
  });

  it("is dropped once the interface moved — a close of the sheet", () => {
    const asked = askPanel();
    interfaceMoved();
    expect(stillAsked(asked)).toBe(false);
  });

  it("is dropped once a newer panel was asked for", () => {
    const first = askPanel();
    const second = askPanel();
    expect(stillAsked(first)).toBe(false);
    expect(stillAsked(second)).toBe(true);
  });

  it("is dropped by a change of page, and by nothing else the store says", () => {
    const store = createStore();
    watchLandings(store);
    const asked = askPanel();
    store.write({ panelOpen: false, acqTab: "todo" });
    expect(stillAsked(asked)).toBe(true);
    store.write({ page: "lib" });
    expect(stillAsked(asked)).toBe(false);
  });

  it("is kept through a named state's own closes and pages", () => {
    const store = createStore();
    watchLandings(store);
    const asked = askPanel();
    walk.naming = true;
    try {
      interfaceMoved();
      store.write({ page: "trackers" });
    } finally {
      walk.naming = false;
    }
    expect(stillAsked(asked)).toBe(true);
  });
});
