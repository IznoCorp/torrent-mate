// A queued search's result reaches an open follow sheet and release picker once its run has settled (O-6 B).
//
// WHAT MAKES THIS NON-VACUOUS. The releases are held by a REAL query with an active observer, which is
// what an open picker is: `staleTime: Infinity` and no event refresh them. The fake server stores the
// new release only at the read that answers `settled`, so a list read again at the 202 still holds the
// old answer, and nothing but a re-read AFTER the settlement can draw the new one.
import { QueryObserver } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../lib/unit-words";

const RELEASES = ["/api/v1/acquisition/releases", "Lucky"];
const verbs = new Map<string, (value: string) => void>();

/** What the fake server holds and was asked. */
const server = {
  /** The states the status read answers, one per read; the last is repeated. `null` makes a read fail. */
  states: [] as (string | null | Error)[],
  releases: [] as string[],
  statusReads: [] as string[],
};

vi.mock("../../lib/query-client", async (importActual) => {
  const actual = await importActual<typeof import("../../lib/query-client")>();
  const client = actual.createQueryClient();
  return {
    ...actual,
    sharedQueryClient: client,
    send: async () => ({ queued: true, runUid: "run-1" }),
    read: async (path: string, query?: URLSearchParams) => {
      if (path !== "/api/v1/acquisition/status") return [];
      server.statusReads.push(String(query));
      const state = server.states.length > 1 ? server.states.shift() : server.states[0];
      if (state instanceof Error) throw state;
      if (state === "settled") server.releases = ["Lucky S01E01 1080p"];
      return { cadence: "20 3,15 * * *", nextSearch: null, runState: state };
    },
  };
});
vi.mock("../../lib/follow-key", () => ({
  followKeyOfTitle: async () => "tvdb:1",
  followSegment: encodeURIComponent,
}));
vi.mock("../../lib/shell-doors", () => ({
  toast: { show: () => undefined },
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
const { sharedQueryClient } = await import("../../lib/query-client");
const client = sharedQueryClient!;

/** The list the open picker draws. */
let drawn: string[] | undefined;
let close: () => void = () => {};

/** Opens the picker, taps « chercher maintenant » and lets the 202 land. */
async function searchWithThePickerOpen(): Promise<void> {
  const observer = new QueryObserver<string[]>(client, { queryKey: RELEASES, queryFn: async () => [...server.releases] });
  close = observer.subscribe((answer) => void (drawn = answer.data));
  await vi.advanceTimersByTimeAsync(0);
  verbs.get("sheetprim")?.("Lucky|followed");
  await vi.advanceTimersByTimeAsync(0);
}

describe("the result of a queued search", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    server.states = [];
    server.releases = [];
    server.statusReads = [];
    drawn = undefined;
  });

  afterEach(() => {
    close();
    client.clear();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("is drawn by the open picker once the run has settled, and not before", async () => {
    server.states = ["queued", "running", "settled"];
    await searchWithThePickerOpen();
    expect(drawn).toEqual([]);

    // Queued, then running: the run is followed, and the list is left as it was.
    await vi.advanceTimersByTimeAsync(3_000);
    expect(server.statusReads).toEqual(["runUid=run-1", "runUid=run-1"]);
    expect(drawn).toEqual([]);

    await vi.advanceTimersByTimeAsync(4_000);
    expect(drawn).toEqual(["Lucky S01E01 1080p"]);
    // A settled run is followed no further.
    await vi.advanceTimersByTimeAsync(600_000);
    expect(server.statusReads).toHaveLength(3);
  });

  it("survives a status read that fails, and still lands", async () => {
    server.states = [new TypeError("network down"), "settled"];
    await searchWithThePickerOpen();

    await vi.advanceTimersByTimeAsync(3_000);

    expect(drawn).toEqual(["Lucky S01E01 1080p"]);
  });

  it("gives up after about five minutes, reading both lists once more", async () => {
    server.states = ["queued"];
    await searchWithThePickerOpen();
    server.releases = ["read at the bound"];

    await vi.advanceTimersByTimeAsync(290_000);
    expect(drawn).toEqual([]);
    await vi.advanceTimersByTimeAsync(30_000);

    expect(drawn).toEqual(["read at the bound"]);
    const asked = server.statusReads.length;
    await vi.advanceTimersByTimeAsync(600_000);
    expect(server.statusReads).toHaveLength(asked);
    expect(asked).toBeLessThan(40);
  });

  it("stops once the session is gone, rather than knock at the sign-in gate again", async () => {
    server.states = [Object.assign(new Error("no session"), { status: 401, title: "no session", detail: "no session" })];
    await searchWithThePickerOpen();

    await vi.advanceTimersByTimeAsync(600_000);

    expect(server.statusReads).toHaveLength(1);
  });

  it("stops at once when no run answers to the uid", async () => {
    server.states = [null];
    await searchWithThePickerOpen();

    await vi.advanceTimersByTimeAsync(600_000);

    expect(server.statusReads).toHaveLength(1);
  });
});
