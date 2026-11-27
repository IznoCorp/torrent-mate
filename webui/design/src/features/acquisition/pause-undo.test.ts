// The undo of a pause sends a status `updateFollow` accepts.
//
// WHAT MAKES THIS NON-VACUOUS. The pause read the follow at `acquiring` and its undo replayed that
// word: `updateFollow.status` is the three-value enum `disabled | pending | up_to_date` (K3-G10), so
// the layer answered 400 and the undo did nothing. Each case RUNS the pause as the tap runs it, takes
// the undo off the toast it offers and reads every status that was written.
import { beforeEach, describe, expect, it, vi } from "vitest";

const written: string[] = [];
const verbs = new Map<string, (value: string, element: HTMLElement) => void>();
const toasts: { message: string; undo?: () => void }[] = [];
// A row that sits in no swipe container: `settleSwipeRow` finds no card and leaves it alone.
const ROW = { closest: () => null } as unknown as HTMLElement;
let held: { title: string; kind: string; status: string }[] = [];

vi.mock("../../lib/verbs", () => ({
  registerVerb: (name: string, run: (value: string, element: HTMLElement) => void) => void verbs.set(name, run),
}));
vi.mock("../../lib/shell-doors", () => ({
  toast: { show: (shown: { message: string; undo?: () => void }) => toasts.push(shown) },
  panel: { close: () => undefined, redraw: () => undefined, produce: () => undefined },
  bridge: {},
  icons: {},
  dialog: undefined,
}));
vi.mock("../../lib/store-access", () => ({ store: { touch: () => undefined } }));
vi.mock("./queries", () => ({
  suggestions: undefined,
  followActions: {
    all: () => held,
    setStatus: async (_title: string, status: string) => {
      written.push(status);
      return "done";
    },
  },
}));

await import("./follow-verbs");

/** Runs the pause verb, lets its detached promise settle and returns the undo it offered. */
async function pauseThenUndo(title: string): Promise<void> {
  verbs.get("pause")?.(title, ROW);
  await new Promise((settle) => setTimeout(settle, 20));
  toasts.at(-1)?.undo?.();
  await new Promise((settle) => setTimeout(settle, 20));
}

describe("the undo of a pause", () => {
  beforeEach(() => {
    written.length = 0;
    toasts.length = 0;
  });

  it("resumes a show with the status a lifted pause goes back to, not the one it was read at", async () => {
    held = [{ title: "Silo", kind: "show", status: "acquiring" }];
    await pauseThenUndo("Silo");
    expect(written).toEqual(["disabled", "up_to_date"]);
  });

  it("resumes a film at pending", async () => {
    held = [{ title: "Kyma", kind: "movie", status: "to_grab" }];
    await pauseThenUndo("Kyma");
    expect(written).toEqual(["disabled", "pending"]);
  });

  it("puts a resumed follow back to disabled", async () => {
    held = [{ title: "Silo", kind: "show", status: "disabled" }];
    await pauseThenUndo("Silo");
    expect(written).toEqual(["up_to_date", "disabled"]);
  });
});
