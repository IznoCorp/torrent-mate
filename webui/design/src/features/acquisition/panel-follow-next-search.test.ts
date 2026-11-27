// The follow sheet names the next search the server states, the way the follows line does.
//
// A release found and not taken is taken at the scheduler's next pass. The hour comes from the server's
// `nextSearch`; on dev the server answers `nextSearch: null` beside a cadence, and a sheet that derived the hour
// from the cadence named a search that never runs. The clock is pinned so that the cadence's next slot (15 h 20
// from 12:00) differs from the instant the server states (9 h 45): a develop sheet that reads the cadence fails.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";
import { producerFor, type PanelCache } from "../../ui/panel/contract";
import type { FollowFacts } from "./follow-facts";
import type { AcquisitionStatus } from "./queries";
import { acquisitionStatusQuery } from "./queries";
import "./panel-follow";

const facts = vi.hoisted(() => ({ value: null as unknown }));

vi.mock("./follow-facts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./follow-facts")>()),
  followFacts: () => facts.value,
}));

/** A found-not-taken follow's facts: the sheet has its identity and its seasons, and the release is takeable. */
function foundNotTaken(): FollowFacts {
  return {
    follow: { title: "Kyma", kind: "movie", status: "pending", year: 2026, requesters: undefined, ids: { tmdb: 1 }, poster: null } as never,
    seasons: [],
    seasonsPending: false,
    isFilm: true,
    incomplete: false,
    isFollowed: true,
    inLibrary: false,
    stage: null,
    toTake: true,
    toResolve: false,
    plexMatch: false,
    tunnelError: false,
    closure: null,
    setAside: false,
    hasSheet: true,
  } as unknown as FollowFacts;
}

/** A cache that holds the schedule and nothing else the sheet reads. */
function cacheWith(status: AcquisitionStatus): PanelCache {
  return {
    held: <Result,>(key: readonly unknown[]) =>
      JSON.stringify(key) === JSON.stringify(acquisitionStatusQuery.queryKey) ? (status as unknown as Result) : undefined,
  };
}

/** Every word the sheet draws, as one string. */
function sheetWords(status: AcquisitionStatus): string {
  const descriptor = producerFor("follow")?.("follow:kyma", cacheWith(status));
  if (!descriptor) throw new Error("the follow sheet has no descriptor");
  return JSON.stringify(descriptor);
}

describe("the follow sheet's next search", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 7, 10, 12, 0));
    facts.value = foundNotTaken();
    void i18next.changeLanguage("fr");
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("names no search when the server schedules none, even though the cadence is set", () => {
    const words = sheetWords({ cadence: "20 3,15 * * *", nextSearch: null, runState: null });
    expect(words).toContain(i18next.t("panels.follow.foundNoNextPass"));
    expect(words).not.toContain(i18next.t("panels.follow.foundNextPassAt", { at: "15 h 20" }));
  });

  it("names the hour the server states, not the cadence's next slot", () => {
    const at = new Date(2026, 7, 10, 9, 45).toISOString();
    const words = sheetWords({ cadence: "20 3,15 * * *", nextSearch: at, runState: null });
    expect(words).toContain(i18next.t("panels.follow.foundNextPassAt", { at: "9 h 45" }));
    expect(words).not.toContain("15 h 20");
  });
});
