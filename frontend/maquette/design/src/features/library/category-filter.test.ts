// « Incomplets » draws what the search asks for, like the listing (B-688).
//
// WHAT MAKES THIS NON-VACUOUS. The lens drew the field and never read it: typing
// « Friends » left all twelve incomplete series on screen, and the filter pill
// went on counting them. The rows the lens shows and the figure its pill prints
// are one derivation; it is asked here with a query, a category and both.
import { describe, expect, it } from "vitest";
import { incompleteShown } from "./category-filter";
import type { LibraryCategory } from "./types";

const ROWS = [
  { title: "Friends", category: "tv_shows" },
  { title: "Les Animaniacs", category: "tv_shows_animation" },
  { title: "Regular Show", category: "tv_shows_animation" },
];
const CATEGORY_PILL = { id: "anim", label: "Animation", count: 2, includes: ["tv_shows_animation"] } as unknown as LibraryCategory;

describe("the rows « Incomplets » shows", () => {
  it("keeps the titles the search names, the listing's way: anywhere in the title, whatever the case", () => {
    expect(incompleteShown(ROWS, undefined, "FRI").map((row) => row.title)).toEqual(["Friends"]);
    expect(incompleteShown(ROWS, undefined, "show").map((row) => row.title)).toEqual(["Regular Show"]);
  });

  it("keeps every row when nothing is searched", () => {
    expect(incompleteShown(ROWS, undefined, "")).toHaveLength(3);
  });

  it("combines the search with the category", () => {
    expect(incompleteShown(ROWS, CATEGORY_PILL, "a").map((row) => row.title)).toEqual(["Les Animaniacs", "Regular Show"]);
    expect(incompleteShown(ROWS, CATEGORY_PILL, "friends")).toEqual([]);
  });
});
