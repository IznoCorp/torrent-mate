// An incomplete show whose year nothing states (N1 of the K2-11 correction round).
//
// WHAT MAKES THIS NON-VACUOUS. The contract serves `IncompleteShow.year` nullable,
// as the backend does: the line used to interpolate it whatever it was, so a
// year-less show read « null · il manque 3 épisodes ».
import { describe, expect, it } from "vitest";
import i18next from "../../lib/unit-words";
import type { IncompleteShow } from "./types";

const { incompleteLine } = await import("./incomplete-lens");

/** An incomplete show, owning one of four aired episodes, in a given year. */
function show(year: number | null): IncompleteShow {
  return { title: "Silo", owned: 1, aired: 4, year, ids: { tvdb: 1 }, poster: null, category: "tv_shows", kind: "show" };
}

describe("an incomplete show's line", () => {
  it("names its year, then what it is missing", () => {
    expect(incompleteLine(show(2023))).toBe(i18next.t("screens.library.incompleteSubMany", { year: 2023, count: 3 }));
  });

  it("says only what is missing when nothing states its year", () => {
    const line = incompleteLine(show(null));
    expect(line).toBe(i18next.t("screens.library.incompleteSubNoYearMany", { count: 3 }));
    expect(line).not.toMatch(/null|·/);
  });
});
