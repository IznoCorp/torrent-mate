// « Chercher maintenant » says queued, held, refused and failed in its own words, and lets nothing escape.
//
// WHAT MAKES THIS NON-VACUOUS. The verb is RUN as the tap runs it (`sheetprim` with a status that is
// not « to_grab »), as a detached promise: a refusal that escaped `searchNow` would be an unhandled
// rejection, a held search worded as queued would announce a search nothing sent.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";

const said: string[] = [];
const stale: unknown[] = [];
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
  read: async () => ({ cadence: "20 3,15 * * *", nextSearch: null, runState: "settled" }),
  isRequestFailure: (failure: unknown) => typeof failure === "object" && failure !== null && "status" in failure,
  sharedQueryClient: {
    invalidateQueries: async ({ queryKey }: { queryKey: unknown }) => void stale.push(queryKey),
  },
}));
// THE KEY CROSSING is the module `lib/follow-key.test.ts` proves; here it answers a key, so the verb's own words are what is read.
vi.mock("../../lib/follow-key", () => ({
  followKeyOfTitle: async () => "tvdb:1",
  followSegment: encodeURIComponent,
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
  await vi.advanceTimersByTimeAsync(20);
}

describe("« chercher maintenant »", () => {
  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  beforeEach(() => {
    vi.useFakeTimers();
    said.length = 0;
    stale.length = 0;
    refusal = null;
    answer = undefined;
  });

  it("says the search is queued, « en file », for that title", async () => {
    answer = { queued: true, runUid: "run-1" };
    await search();
    expect(said).toEqual([i18next.t("verbs.acquisition.searchQueued", { title: "Lucky" })]);
  });

  it("leaves the result to be read later, from the follow and its releases", async () => {
    answer = { queued: true, runUid: "run-1" };
    await search();
    // Nothing is stale at the answer: the search has not run yet.
    expect(stale).toEqual([]);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(stale).toEqual([["/api/v1/acquisition/followed"], ["/api/v1/acquisition/releases"]]);
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
