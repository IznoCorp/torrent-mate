// A creation state's deferred acts are forgotten when the next state is driven.
//
// WHAT MAKES THIS NON-VACUOUS. `fillCreation` arms two timers — the typing, and, once typed, a press on
// Create — and a state driven in the meantime must not have either land on ITS page: a field typed into
// the next state's form, or a Create pressed over it, is an act nobody asked for (the same class as the
// role-delete state's, 125378eb4; `cards.py` R44 found both). The driver is stood in for by the one thing
// it contributes here, the leave callback it runs before the next state, and the page by a form that
// records what it was typed and what pressed it. Each leg leaves at a different moment — before the
// typing, and between the typing and the press — and reads that nothing lands after.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let leave: (() => void) | null;
let typed: string[];
let pressed: number;

vi.mock("../drive", () => ({
  applyState: () => {},
  onLeave: (stop: () => void) => {
    leave = stop;
  },
}));
vi.mock("./rights", () => ({ as: () => {} }));

beforeEach(() => {
  vi.useFakeTimers();
  leave = null;
  typed = [];
  pressed = 0;
  vi.stubGlobal("window", {
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
    __screens: { newAccount: () => {}, newRole: () => {} },
  });
  vi.stubGlobal("HTMLSelectElement", class {});
  vi.stubGlobal("HTMLInputElement", class {});
  vi.stubGlobal("Event", class {});
  const field = Object.create(globalThis.HTMLInputElement.prototype, {});
  Object.defineProperty(globalThis.HTMLInputElement.prototype, "value", {
    configurable: true,
    set(value: string) {
      typed.push(value);
    },
  });
  field.dispatchEvent = () => {};
  vi.stubGlobal("document", {
    querySelector: (selector: string) =>
      selector.includes("creation/submit") ? { click: () => void (pressed += 1) } : selector.includes("creation/form") ? field : null,
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("fillCreation", () => {
  it("lands its typing and its press when nothing is driven in between — the control", async () => {
    const { fillCreation } = await import("./creation");
    fillCreation("account", [["name", "Nina"]], undefined, true);
    vi.advanceTimersByTime(400 + 150);
    expect(typed).toEqual(["Nina"]);
    expect(pressed).toBe(1);
  });

  it("types nothing into the next state when it is left before the typing", async () => {
    const { fillCreation } = await import("./creation");
    fillCreation("account", [["name", "Nina"]], undefined, true);
    expect(leave).not.toBeNull();
    leave?.();
    vi.advanceTimersByTime(2000);
    expect(typed).toEqual([]);
    expect(pressed).toBe(0);
  });

  it("presses nothing over the next state when it is left between the typing and the press", async () => {
    const { fillCreation } = await import("./creation");
    fillCreation("account", [["name", "Nina"]], undefined, true);
    vi.advanceTimersByTime(400);
    expect(typed).toEqual(["Nina"]);
    leave?.();
    vi.advanceTimersByTime(2000);
    expect(pressed).toBe(0);
  });
});
