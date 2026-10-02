// A follow is the same follow whichever surface created it (B-673).
//
// WHAT MAKES THIS NON-VACUOUS. Each leg posts the create body the interface
// sends from one surface — Médiathèque › Incomplets, a library sheet, the search
// results, the discover deck — and reads the follow the layer recorded. Before
// B-673 only the search results and the suggestions were joined, by TITLE, so a
// series followed from « Incomplets » came back with no poster and the year 0
// (« 0 · série »), and a library film whose sheet spells its identifiers as
// strings was refused outright.
import { beforeEach, describe, expect, it } from "vitest";
import INCOMPLETE_SHOWS from "./seeds/incomplete-shows.json";
import MEDIA_SHEETS from "./seeds/media-sheets.json";
import POSTERS from "./seeds/posters.json";
import SEARCH_RESULTS from "./seeds/search-results.json";
import SUGGESTIONS from "./seeds/suggestions.json";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { sentIdentity } from "../features/acquisition/sent-identity";

type Follow = { title: string; year: number | string; poster: string | null; ids: Record<string, unknown> };
type Sheet = { kind: string; year: string; ids: Record<string, string | number> };

/**
 * Posts one create the way the interface does, and answers what the layer recorded.
 *
 * @param title The medium's title.
 * @param kind « movie » or « show ».
 * @param ids The identity the emitter carries.
 * @returns The recorded follow.
 */
function create(title: string, kind: string, ids: Record<string, unknown> | null): Follow {
  const found = resolve(routes(), "POST", "/api/acquisition/followed");
  if (found === null) throw new Error("no createFollow route");
  const body = { title, kind, ...sentIdentity(ids) };
  return found.route.handle({ path: "/api/acquisition/followed", parameters: {},
                              query: new URLSearchParams(), body }) as Follow;
}

describe("a follow created from any surface", () => {
  beforeEach(() => resetMockState());

  it("carries the poster, the year and the identity of a series followed from « Incomplets »", () => {
    for (const show of INCOMPLETE_SHOWS) {
      const follow = create(show.title, "show", show.ids);
      expect(follow.poster, show.title).toBe(show.poster);
      expect(String(follow.year), show.title).toBe(String(show.year));
      // The identity read whole, TVDB included, whether a seed spells it as digits or a number.
      expect(String(follow.ids.tvdb), show.title).toBe(String(show.ids.tvdb));
    }
  });

  it("carries the poster and the year of a library medium followed from its sheet", () => {
    const sheets = MEDIA_SHEETS as Record<string, Sheet>;
    const posters = POSTERS as Record<string, string>;
    // A sheet whose identifiers are all strings: the interface sent none of them.
    const title = "Ninja Turtles";
    const sheet = sheets[title];
    expect(Object.values(sheet.ids).every((value) => typeof value === "string")).toBe(true);
    const follow = create(title, sheet.kind, sheet.ids);
    expect(follow.poster).toBe(posters[title]);
    expect(String(follow.year)).toBe(sheet.year);
  });

  it("carries the year of a search result and of a suggestion, never 0", () => {
    const result = SEARCH_RESULTS.results.find((one) => !one.followed && one.ids !== null)!;
    const suggestion = SUGGESTIONS[0];
    for (const entry of [result, suggestion]) {
      const follow = create(entry.title, entry.kind === "Film" ? "movie" : "show", entry.ids);
      expect(follow.poster, entry.title).toBe(entry.poster);
      expect(String(follow.year), entry.title).toBe(entry.year);
    }
  });

  it("says an unknown year as nothing, never 0", () => {
    const follow = create("Un titre que nul ne connaît", "show", { tvdb: 999999999 }); // french-ok: a media title
    expect(follow.year).not.toBe(0);
    expect(follow.poster).toBeNull();
  });
});
