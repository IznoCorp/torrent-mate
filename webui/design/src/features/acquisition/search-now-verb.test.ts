// « Chercher maintenant » says held, refused and failed in its own words, and lets nothing escape.
//
// WHAT MAKES THIS NON-VACUOUS. The verb is RUN as the tap runs it (`sheetprim` with a status that is
// not « to_grab »), as a detached promise: a refusal that escaped `searchNow` would be an unhandled
// rejection, a held search worded as found would announce a search nothing sent.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";

const said: string[] = [];
const verbs = new Map<string, (value: string, element?: unknown) => void>();
const HELD_ANSWER = Symbol.for("test-held");
let refusal: unknown = null;
let answer: unknown;

vi.mock("../../lib/query-client", () => ({
  HELD: Symbol.for("test-held"),
  send: async () => {
    if (refusal !== null) throw refusal;
    return answer;
  },
  read: async () => [],
  isRequestFailure: (failure: unknown) => typeof failure === "object" && failure !== null && "status" in failure,
  sharedQueryClient: null,
}));
vi.mock("../../lib/shell-doors", () => ({
  toast: { show: ({ message }: { message: string }) => said.push(message) },
  panel: { close: () => undefined, redraw: () => undefined, produce: () => undefined },
  fillLandingDoor: () => undefined,
  followLink: undefined,
  replaceAddress: undefined,
  redraw: () => undefined,
  bridge: {},
  icons: {},
  dialog: undefined,
}));
vi.mock("../../lib/verbs", () => ({
  registerVerb: (name: string, run: (value: string) => void) => void verbs.set(name, run),
}));

await import("./verbs");

/** Runs the primary act of a follow that is not waiting to be taken, and lets its promise settle. */
async function search(): Promise<void> {
  verbs.get("sheetprim")?.("Lucky|followed");
  await new Promise((settle) => setTimeout(settle, 20));
}

describe("« chercher maintenant »", () => {
  beforeEach(() => {
    said.length = 0;
    refusal = null;
    answer = undefined;
  });

  it("says what the search found", async () => {
    answer = { found: 2 };
    await search();
    expect(said).toEqual([i18next.t("verbs.acquisition.searchFound", { title: "Lucky", count: 2 })]);
  });

  it("says nothing was found", async () => {
    answer = { found: 0 };
    await search();
    expect(said).toEqual([i18next.t("verbs.acquisition.searchFoundNone", { title: "Lucky" })]);
  });

  it("says a held search is held, not found", async () => {
    answer = HELD_ANSWER;
    await search();
    expect(said).toEqual([i18next.t("verbs.acquisition.held")]);
  });

  it("says a refused search is refused and lets nothing escape", async () => {
    refusal = { status: 403, title: "no", code: "auth.forbidden" };
    await search();
    expect(said).toEqual([i18next.t("verbs.acquisition.refused")]);
  });

  it("words a network error as failed, not refused", async () => {
    refusal = new TypeError("network down");
    await search();
    expect(said).toEqual([i18next.t("verbs.acquisition.failed")]);
  });
});
