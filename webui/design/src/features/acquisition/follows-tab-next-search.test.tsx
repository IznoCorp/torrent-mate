// The next search a follow's line names is the server's `nextSearch`, never a time derived from `cadence`.
//
// The contract says `nextSearch` is « when the next search runs », null when none is scheduled. In dev the
// server answers prod's cadence with `nextSearch: null` (no scheduler runs there), so a tab that derived the
// slot from `cadence` drew a search that never runs. The line must follow `nextSearch` alone.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import i18next from "../../i18n";
import type { Follow } from "./types";

const schedule = vi.hoisted(() => ({ cadence: "20 3,15 * * *", nextSearch: null as string | null }));
const held = vi.hoisted(() => ({ follows: [] as unknown[] }));

vi.mock("./queries", () => ({
  useFollows: () => ({ data: held.follows, error: null, isError: false }),
  useGrabCadence: () => ({ data: schedule.cadence }),
  useGrabNextSearch: () => ({ data: schedule.nextSearch }),
}));
vi.mock("../../lib/store-access", () => ({
  useUiState: () => ({ phase: "ready", scen: "", followMode: "list", pill: "tout", filter: "" }),
  useStoreContent: () => 0,
}));
vi.mock("../../lib/account", () => ({
  useRights: () => ({ known: true, id: "a", forbidden: [], holds: () => true, holdsAny: () => true }),
}));

const pending: Follow = {
  title: "Heat",
  kind: "movie",
  year: 1995,
  status: "pending",
  showStatus: null,
  addedAt: 1_700_000_000,
  nextAirDate: null,
  searches: 0,
  fresh: false,
  ids: { tmdb: 949 },
  poster: null,
};

/** The tab's visible text, with one pending follow held and the schedule set. */
async function textWithSchedule(nextSearch: string | null): Promise<string> {
  const { FollowsTab } = await import("./follows-tab");
  schedule.nextSearch = nextSearch;
  held.follows = [pending];
  void i18next.changeLanguage("fr");
  return renderToStaticMarkup(createElement(FollowsTab)).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
}

describe("the next search a follow names", () => {
  it("names no search when the server schedules none, even though the cadence is set", async () => {
    const text = await textWithSchedule(null);
    expect(text).toContain(i18next.t("screens.acquisition.noConformRelease"));
    expect(text).toContain(i18next.t("screens.acquisition.nextSearchNone"));
    expect(text).not.toContain(i18next.t("screens.acquisition.nextSearch", { at: "15 h 20" }));
    expect(text).not.toContain(i18next.t("screens.acquisition.nextSearch", { at: "3 h 20" }));
  });

  it("names the slot the server answers, as its clock time", async () => {
    const text = await textWithSchedule(new Date(2026, 7, 10, 15, 20).toISOString());
    expect(text).toContain(i18next.t("screens.acquisition.nextSearch", { at: "15 h 20" }));
    expect(text).not.toContain(i18next.t("screens.acquisition.nextSearchNone"));
  });
});
