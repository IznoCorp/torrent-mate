// WHETHER THE LIBRARY HOLDS ONE MEDIUM, answered from the WHOLE library.
//
// The listing is paged and a page is not the library: asking « is it on the
// pages I hold? » answers « no » for a title on page two. This read asks the
// layer's whole state instead — the rows a deletion has already filtered, and
// the incomplete series a deletion has already told — so a removal is heard by
// every surface that asks afterwards.
//
// KEYED BY TITLE, with the year where the title alone names more than one row.
// Provider ids are not an identity here: two rows can share one. The title is
// compared WITHOUT the year a library folder appends (« Furious (2026) » is the
// row « Furious » is followed as): compared exactly, a followed show whose row
// carries its year was answered « not in the library » (B-688).
import INCOMPLETE_SHOWS from "../seeds/incomplete-shows.json";
import { baseTitle } from "../../lib/titles";
import { GET, route } from "./shared";
import { mockState } from "../state";
import type { MockRequest, MockRoute } from "../router";

/* THE ENGINE'S FILM CATEGORIES — its move rules' own list: a film folder is
   replaced, a series folder is merged. A library row carries its category,
   and the category is what tells a film from a series. */
const FILM_CATEGORIES = new Set(["movies", "movies_animation", "movies_documentary", "standup", "theater"]);

/* The year a library row states, read off its secondary line (« 2026 · Film »). */
const LEADING_YEAR = /^(\d\d\d\d)/;

/**
 * Whether a library row's year is the one asked, when one is asked.
 *
 * @param line The row's secondary line.
 * @param year The year asked, or null.
 * @returns True when no year is asked or the row states that year.
 */
function sameYear(line: string | undefined, year: number | null): boolean {
  if (year === null) return true;
  const found = LEADING_YEAR.exec(line ?? "");
  return found !== null && Number(found[1]) === year;
}

/**
 * Answers what the library holds of one exact title.
 *
 * @param request The request, its `title` and optional `year` in the query.
 * @returns Whether it is held, how many rows name it, whether it is incomplete, its kind and its identity.
 */
function membership(request: MockRequest) {
  const state = mockState();
  const title = baseTitle(request.query.get("title") ?? "");
  const asked = request.query.get("year");
  const year = asked !== null && /^\d+$/.test(asked) ? Number(asked) : null;
  const rows = state.library.filter(
    (one) => baseTitle(one.title) === title && sameYear(one.secondaryLine, year),
  );
  const row = rows[0];
  const show = INCOMPLETE_SHOWS.find(
    (one) =>
      baseTitle(one.title) === title &&
      (year === null || one.year === year) &&
      !state.deletedTitles.includes(one.title),
  );
  return {
    inLibrary: row !== undefined || show !== undefined,
    rows: rows.length,
    incomplete: show !== undefined,
    kind: row !== undefined ? (FILM_CATEGORIES.has(row.category) ? "movie" : "show") : show !== undefined ? "show" : null,
    ids: row?.ids ?? show?.ids ?? null,
  };
}

/** Every route this subject answers. */
export function membershipRoutes(): MockRoute[] {
  return [route("readLibraryMembership", GET, "/api/library/membership", membership)];
}
