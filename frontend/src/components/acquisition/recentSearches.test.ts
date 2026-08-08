/**
 * recentSearches — the honest data source behind the `.sugg` chips.
 */

import { afterEach, describe, expect, it } from "vitest";

import {
  RECENT_SEARCHES_KEY,
  RECENT_SEARCHES_MAX,
  pushRecentSearch,
  readRecentSearches,
} from "./recentSearches";

afterEach(() => {
  localStorage.clear();
});

describe("recentSearches", () => {
  it("stocke plus-récent-d'abord et déduplique sans casse", () => {
    pushRecentSearch("silo");
    pushRecentSearch("severance");
    pushRecentSearch("Silo");

    expect(readRecentSearches()).toEqual(["Silo", "severance"]);
  });

  it("plafonne l'historique", () => {
    for (const q of ["a", "b", "c", "d", "e", "f", "g"]) pushRecentSearch(q);

    const stored = readRecentSearches();
    expect(stored).toHaveLength(RECENT_SEARCHES_MAX);
    expect(stored[0]).toBe("g");
  });

  it("ignore le vide et survit à un storage corrompu", () => {
    pushRecentSearch("   ");
    expect(readRecentSearches()).toEqual([]);

    localStorage.setItem(RECENT_SEARCHES_KEY, "{pas du json[");
    expect(readRecentSearches()).toEqual([]);

    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify([1, "ok", null]));
    expect(readRecentSearches()).toEqual(["ok"]);
  });
});
