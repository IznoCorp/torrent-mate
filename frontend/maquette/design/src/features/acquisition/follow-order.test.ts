// « Suivis »'s filter and five sorts (maquette-blocked § 1.9, his round 3 q1 = C).
//
// WHAT MAKES THIS NON-VACUOUS. The follows are given in an order that is none
// of the expected ones, and the title, the urgency, the creation and the next
// release disagree on purpose, so a sort reading the wrong field fails.
import { describe, expect, it } from "vitest";
import { FOLLOW_SORTS, followCounts, orderFollows } from "./follow-order";
import type { Follow } from "./types";

/**
 * A follow with what the order reads.
 *
 * @param title Its title.
 * @param fields What else it carries.
 * @returns The follow.
 */
function follow(title: string, fields: Partial<Follow>): Follow {
  return {
    title, kind: "show", year: 2026, status: "up_to_date", showStatus: null, since: "", searches: 0,
    ids: { tmdb: "1" }, poster: null, addedAt: 0, nextAirDate: null, ...fields,
  } as Follow;
}

const FOLLOWS = [
  follow("Bravo", { status: "pending", addedAt: 300, nextAirDate: null }),
  follow("Alpha", { status: "up_to_date", addedAt: 100, nextAirDate: "2026-12-01" }),
  follow("Delta", { kind: "movie", status: "to_grab", addedAt: 400, nextAirDate: "2026-10-05" }),
  follow("Charlie", { status: "up_to_date", fresh: true, addedAt: 200, nextAirDate: "2027-01-01" }),
  follow("Écho", { kind: "movie", status: "pending", addedAt: 50, nextAirDate: null }),
];

/**
 * The titles of an ordering.
 *
 * @param follows The follows.
 * @returns Their titles.
 */
function titles(follows: Follow[]): string[] {
  return follows.map((entry) => entry.title);
}

describe("the follows' sorts", () => {
  it("offers his five, « Urgence » first", () => {
    expect(FOLLOW_SORTS).toEqual(["urgency", "az", "za", "added", "nextRelease"]);
  });

  it("« Urgence » is today's fixed order: fresh, then the status's urgency, then the title", () => {
    expect(titles(orderFollows(FOLLOWS, "tout", "urgency"))).toEqual(["Charlie", "Delta", "Bravo", "Écho", "Alpha"]);
  });

  it("« A → Z » and « Z → A » are French collation, both ways", () => {
    expect(titles(orderFollows(FOLLOWS, "tout", "az"))).toEqual(["Alpha", "Bravo", "Charlie", "Delta", "Écho"]);
    expect(titles(orderFollows(FOLLOWS, "tout", "za"))).toEqual(["Écho", "Delta", "Charlie", "Bravo", "Alpha"]);
  });

  it("« Suivi récemment » is the newest follow first", () => {
    expect(titles(orderFollows(FOLLOWS, "tout", "added"))).toEqual(["Delta", "Bravo", "Charlie", "Alpha", "Écho"]);
  });

  it("« Prochaine sortie » is the soonest release first, a follow with none last", () => {
    expect(titles(orderFollows(FOLLOWS, "tout", "nextRelease"))).toEqual(["Delta", "Alpha", "Charlie", "Bravo", "Écho"]);
  });
});

describe("the follows' filter", () => {
  it("keeps the series or the films, in the sort asked", () => {
    expect(titles(orderFollows(FOLLOWS, "movies", "az"))).toEqual(["Delta", "Écho"]);
    expect(titles(orderFollows(FOLLOWS, "series", "added"))).toEqual(["Bravo", "Charlie", "Alpha"]);
  });

  it("counts what each filter keeps", () => {
    expect(followCounts(FOLLOWS)).toEqual({ tout: 5, series: 3, movies: 2 });
  });
});
