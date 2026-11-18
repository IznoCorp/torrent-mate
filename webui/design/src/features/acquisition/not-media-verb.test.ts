// « Ce n'est pas un média » says held, refused and failed — for the filing and for its undo.
//
// WHAT MAKES THIS NON-VACUOUS. The filing and its « Annuler » each end four ways. A held filing is
// not offered an undo (the folder has not moved); a held, refused or failed undo says so instead of
// reading the lists again as if the folder were back. Each verb is RUN as the tap runs it.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";

interface Shown {
  message: string;
  undo?: () => void;
}

const shown: Shown[] = [];
const verbs = new Map<string, (value: string) => void>();
const invalidated: unknown[] = [];
const HELD_ANSWER = Symbol.for("test-held");
const sends: unknown[] = [];

vi.mock("../../lib/query-client", () => ({
  HELD: Symbol.for("test-held"),
  send: async () => {
    const next = sends.shift();
    if (next instanceof Error || (typeof next === "object" && next !== null && "status" in next)) throw next;
    return next;
  },
  read: async () => [],
  isRequestFailure: (failure: unknown) => typeof failure === "object" && failure !== null && "status" in failure,
  sharedQueryClient: { invalidateQueries: async (filters: unknown) => void invalidated.push(filters) },
}));
vi.mock("../../lib/shell-doors", () => ({
  toast: { show: (toast: Shown) => shown.push(toast) },
  panel: { close: () => undefined, isOpen: () => false, produce: () => undefined },
  bridge: { rewind: () => undefined },
  icons: {},
}));
vi.mock("../../lib/verbs", () => ({
  registerVerb: (name: string, run: (value: string) => void) => void verbs.set(name, run),
}));
vi.mock("../../ui/panel/contract", () => ({ registerProducer: () => undefined }));

await import("./not-media-verb");

const REFUSED = { status: 403, title: "no", code: "auth.forbidden" };

/** Files one folder as the tap does and lets the detached promise settle. */
async function reclassify(): Promise<void> {
  verbs.get("reclassify")?.("Folder|Docs");
  await settle();
}

/** Lets the detached promises settle. */
const settle = () => new Promise((done) => setTimeout(done, 20));

/**
 * Files one folder successfully and runs the undo the toast offers.
 *
 * @param ended How the undo's own write ends.
 */
async function undo(ended: unknown): Promise<void> {
  sends.push({ destination: "Docs" }, ended);
  await reclassify();
  invalidated.length = 0;
  shown.pop()?.undo?.();
  await settle();
}

describe("« ce n'est pas un média »", () => {
  beforeEach(() => {
    shown.length = 0;
    invalidated.length = 0;
    sends.length = 0;
  });

  it("says a held filing is held and offers no undo", async () => {
    sends.push(HELD_ANSWER);
    await reclassify();
    expect(shown.map((toast) => toast.message)).toEqual([i18next.t("verbs.acquisition.held")]);
    expect(shown[0].undo).toBeUndefined();
    expect(invalidated).toEqual([]);
  });

  it("says a refused filing is refused", async () => {
    sends.push(REFUSED);
    await reclassify();
    expect(shown.map((toast) => toast.message)).toEqual([i18next.t("verbs.acquisition.refused")]);
    expect(invalidated).toEqual([]);
  });

  it("words a network error on the filing as failed", async () => {
    sends.push(new TypeError("network down"));
    await reclassify();
    expect(shown.map((toast) => toast.message)).toEqual([i18next.t("verbs.acquisition.failed")]);
  });

  it("reads the lists again once the filing is done, and its undo is offered", async () => {
    sends.push({ destination: "Docs" });
    await reclassify();
    expect(shown[0].undo).toBeTypeOf("function");
    expect(invalidated).toHaveLength(2);
  });

  it("says a held undo is held and reads nothing again", async () => {
    await undo(HELD_ANSWER);
    expect(shown.map((toast) => toast.message)).toEqual([i18next.t("verbs.acquisition.held")]);
    expect(invalidated).toEqual([]);
  });

  it("says a refused undo is refused and reads nothing again", async () => {
    await undo(REFUSED);
    expect(shown.map((toast) => toast.message)).toEqual([i18next.t("verbs.acquisition.refused")]);
    expect(invalidated).toEqual([]);
  });

  it("words a network error on the undo as failed and reads nothing again", async () => {
    await undo(new TypeError("network down"));
    expect(shown.map((toast) => toast.message)).toEqual([i18next.t("verbs.acquisition.failed")]);
    expect(invalidated).toEqual([]);
  });

  it("reads the lists again once the undo is done", async () => {
    await undo({});
    expect(shown).toEqual([]);
    expect(invalidated).toHaveLength(2);
  });
});
