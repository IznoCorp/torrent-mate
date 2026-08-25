// What the library holds.
//
// The whole of this subject is a DEMAND on the backend: there is no library
// endpoint of any kind in `frontend/openapi.json` — no listing, no categories,
// no recents, no incompletes. The register computed by
// `scripts/compare-contracts.py` says so, operation by operation.
import LIBRARY_CATEGORIES from "../seeds/library-categories.json";
import INCOMPLETE_SHOWS from "../seeds/incomplete-shows.json";
import LIBRARY_TOTAL from "../seeds/library-total.json";
import SYNOPSES from "../seeds/synopses.json";
import RECENT from "../seeds/recent.json";
import { DELETE, GET, field, route } from "./shared";
import { mockState } from "../state";
import type { MockRequest, MockRoute } from "../router";

// How many rows one page carries. The engine's own page size is `LIB_PAGE`,
// classified `interface` in the register — it belongs to the interface, not to
// a server — so the layer states its own rather than seeding one.
const PAGE_SIZE = 24;

/**
 * Answers one page of the listing, filtered and sorted as the query asks.
 *
 * @param request The request.
 * @returns The page, and how many titles there are in all.
 */
function listing(request: MockRequest): unknown {
  const state = mockState();
  const wanted = (request.query.get("query") ?? "").toLowerCase();
  const category = request.query.get("category") ?? "";
  let rows = state.library;
  let filtered = false;
  if (wanted !== "") {
    rows = rows.filter((row) => row.title.toLowerCase().includes(wanted));
    filtered = true;
  }
  const known = LIBRARY_CATEGORIES.find((entry) => entry.id === category);
  // A category whose `includes` is null filters NOTHING — it is the one that
  // aggregates everything. Reading it by identifier rather than by position
  // stops the answer depending on the order the seed happens to be written in.
  if (known !== undefined && known.includes !== null) {
    const included = known.includes;
    rows = rows.filter((row) => included.includes(row.category));
    filtered = true;
  }
  // An UNREADABLE page is not the end of the list. `Number("abc")` is NaN and
  // `slice(NaN, NaN)` answers an empty array, which reads exactly like having
  // scrolled past the last row.
  const asked = Number(request.query.get("page") ?? 0);
  const page = Number.isInteger(asked) && asked >= 0 ? asked : 0;
  return {
    // The library's own total when nothing filters, and the size of the result
    // set when something does. Answering 1 861 over a search for two rows made
    // the count describe the library rather than the answer.
    total: filtered ? rows.length : LIBRARY_TOTAL,
    items: rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((row) => ({
      ...row,
      // Where the ENGINE attaches it: a library row carries its synopsis on the
      // card, and the media sheet carries its own. Substituting one for the
      // other made 213 of 259 sheets answer a different text, some of them in
      // English.
      overview: (SYNOPSES as Record<string, string>)[row.title],
    })),
  };
}

/** Every route this subject answers. */
export function libraryRoutes(): MockRoute[] {
  return [
    route("readLibraryItems", GET, "/api/library/items", listing),
    route("readLibraryCategories", GET, "/api/library/categories", () => LIBRARY_CATEGORIES),
    route("readLibraryRecent", GET, "/api/library/recent", () => RECENT),
    route("readLibraryIncomplete", GET, "/api/library/incomplete", () => INCOMPLETE_SHOWS),
    route("deleteLibraryItems", DELETE, "/api/library/items", (request) => {
      const state = mockState();
      const asked = field(request.body, "titles");
      const titles = Array.isArray(asked) ? asked.map(String) : [];
      const before = state.library.length;
      state.library = state.library.filter((row) => !titles.includes(row.title));
      return { deleted: before - state.library.length };
    }),
  ];
}
