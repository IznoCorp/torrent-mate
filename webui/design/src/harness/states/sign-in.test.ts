// A sign-in state's deferred submit is forgotten when the next state is driven.
//
// WHAT MAKES THIS NON-VACUOUS. The password change in Profil and the provisional-password reset in
// « Comptes » arm a timer that fills a form and submits it, and a state driven in the meantime must not
// have that submit land on ITS page — the same class `fillCreation` was repaired for (`creation.test.ts`).
// The driver is stood in for by the one thing it contributes here, the leave callback it runs before the
// next state, and the page by a form that counts its submits. Each state is run once left before its
// timer (nothing may land) and once not left (the control: it lands).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let leave: (() => void) | null;
let submitted: number;

vi.mock("../drive", () => ({
  applyState: () => {},
  onLeave: (stop: () => void) => {
    leave = stop;
  },
}));
vi.mock("./rights", () => ({ as: () => {} }));
vi.mock("./creation", () => ({ fillCreation: () => {} }));

beforeEach(() => {
  vi.useFakeTimers();
  leave = null;
  submitted = 0;
  vi.stubGlobal("window", {
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
    __panel: { produce: () => {} },
  });
  const form = {
    elements: { namedItem: () => ({ value: "" }) },
    requestSubmit: () => void (submitted += 1),
  };
  vi.stubGlobal("document", { querySelector: () => form });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/**
 * Runs one named state of the sign-in family.
 *
 * @param id The state's id.
 */
async function run(id: string): Promise<void> {
  const { signInStates } = await import("./sign-in");
  const found = signInStates().find(([name]) => name === id);
  expect(found).toBeDefined();
  found?.[2]();
}

describe.each(["profile-password-changed", "accounts-reset-done"])("%s", (id) => {
  it("submits its form when nothing is driven in between — the control", async () => {
    await run(id);
    vi.advanceTimersByTime(2000);
    expect(submitted).toBe(1);
  });

  it("submits nothing over the next state when it is left before its timer", async () => {
    await run(id);
    expect(leave).not.toBeNull();
    leave?.();
    vi.advanceTimersByTime(2000);
    expect(submitted).toBe(0);
  });
});
