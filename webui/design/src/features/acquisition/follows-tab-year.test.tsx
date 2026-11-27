// A follow with no year draws no year: never the word « null ».
//
// The server serves `year: null` for a medium nothing dates (the contract's `Follow.year` admits it), and the
// tab wrote the year with `String(follow.year)` in two places — the row's second line and the tile's fallback
// subtitle — so an undated follow read « null · Film ». Rendered, not unit-tested on a helper: only the tab can
// show that BOTH places went through the year's one wording.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import i18next from "../../i18n";
import type { Follow } from "./types";

const screen = vi.hoisted(() => ({ mode: "list" }));
const held = vi.hoisted(() => ({ follows: [] as unknown[] }));

vi.mock("./queries", () => ({
  useFollows: () => ({ data: held.follows, error: null, isError: false }),
  useGrabCadence: () => ({ data: undefined }),
}));
vi.mock("../../lib/store-access", () => ({
  useUiState: () => ({ phase: "ready", scen: "", followMode: screen.mode, pill: "tout", filter: "" }),
  useStoreContent: () => 0,
}));
vi.mock("../../lib/account", () => ({
  useRights: () => ({ known: true, id: "a", forbidden: [], holds: () => true, holdsAny: () => true }),
}));

const follow = (year: Follow["year"], extra: Partial<Follow> = {}): Follow => ({
  title: "Heat",
  kind: "movie",
  year,
  status: "up_to_date",
  showStatus: null,
  addedAt: 1_700_000_000,
  nextAirDate: null,
  searches: 0,
  fresh: false,
  ids: { tmdb: 949 },
  poster: null,
  ...extra,
});

/** The tab's visible text in one display mode, over the follows held. */
async function textOf(mode: string, follows: Follow[]): Promise<string> {
  const { FollowsTab } = await import("./follows-tab");
  screen.mode = mode;
  held.follows = follows;
  void i18next.changeLanguage("fr");
  return renderToStaticMarkup(createElement(FollowsTab)).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
}

describe("a follow with no year", () => {
  it.each(["list", "grid"])("never says « null » in the %s", async (mode) => {
    const text = await textOf(mode, [follow(null)]);
    expect(text).toContain("Heat");
    expect(text).not.toMatch(/\bnull\b/);
  });

  it("keeps the year of a dated follow where it was drawn", async () => {
    expect(await textOf("list", [follow(1995)])).toContain("1995");
    expect(await textOf("grid", [follow(1995)])).toContain("1995");
  });

  it("draws nothing for a year the maquette's own mocks hold as an empty string", async () => {
    const text = await textOf("grid", [follow("")]);
    expect(text).toContain("Heat");
    expect(text).not.toMatch(/\bnull\b/);
  });
});
