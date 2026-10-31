// A library row carries the identity of ITS medium, not its title's.
//
// WHAT MAKES THIS NON-VACUOUS. « RoboCop » 1987 and 2014 are two films under
// two TMDB ids and one title: a removal or a tick keyed by the title names the
// same medium from both rows, and the one resolved first was deleted from the
// other's swipe. The rows are drawn from the seed itself, and the identity each
// carries is read off the markup the tap registry answers on.
import { describe, expect, it, vi } from "vitest";
import LIBRARY from "../../mocks/seeds/library-items.json";
import type { LibraryRow } from "./types";

let selected = new Map<string, unknown>();
let selectionMode = false;

vi.mock("../../lib/store-access", () => ({
  store: { read: () => ({ state: { selMode: selectionMode, selected } }) },
}));
vi.mock("../../lib/account", () => ({ heldRights: () => ({ holds: () => true }) }));

const { libraryRowMarkup, libraryTileMarkup } = await import("./library-rows");
const REFERENCE = { icons: { trash: "", check: "" } };

/** The seed's rows under one title. */
function rowsNamed(title: string): LibraryRow[] {
  return (LIBRARY as LibraryRow[]).filter((row) => row.title === title);
}

/** The value of one attribute in a markup string. */
function attribute(markup: string, name: string): string | null {
  return new RegExp(`${name}="([^"]*)"`).exec(markup)?.[1] ?? null;
}

describe("a library row's identity", () => {
  it("names each of two media sharing a title by its own id, on the swipe", () => {
    selectionMode = false;
    const refs = rowsNamed("RoboCop").map((row) => attribute(libraryRowMarkup(REFERENCE, row, 0, ""), "data-del-ref"));
    expect(refs.sort()).toEqual(["tmdb:5548", "tmdb:97020"]);
  });

  it("names a film TMDB-first, whatever other provider it carries", () => {
    selectionMode = false;
    const [film] = rowsNamed("Die Hart Die Harter");
    expect(film.ids).toHaveProperty("tvdb");
    expect(attribute(libraryRowMarkup(REFERENCE, film, 0, ""), "data-del-ref")).toBe(`tmdb:${film.ids?.tmdb}`);
  });

  it("ticks one of two media sharing a title, and presses that row alone", () => {
    selectionMode = true;
    selected = new Map([["tmdb:97020", null]]);
    for (const draw of [
      (row: LibraryRow) => libraryRowMarkup(REFERENCE, row, 0, ""),
      (row: LibraryRow) => libraryTileMarkup(REFERENCE, row, 0),
    ]) {
      const drawn = rowsNamed("RoboCop").map((row) => ({
        ref: attribute(draw(row), "data-selected-ref"),
        pressed: attribute(draw(row), "aria-pressed"),
      }));
      expect(drawn.sort((a, b) => String(a.ref).localeCompare(String(b.ref)))).toEqual([
        { ref: "tmdb:5548", pressed: "false" },
        { ref: "tmdb:97020", pressed: "true" },
      ]);
    }
  });
});
