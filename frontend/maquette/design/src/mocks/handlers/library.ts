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

// The three orders, as the contract's `sort` parameter names them, and the
// token its `reversed` parameter carries for « the other way round ». Named
// rather than written inline: the handler guard reads a schema's enum and not a
// parameter's, so a constant is what stops these being four bare strings that
// nobody can tie back to the contract.
const BY_TITLE = "az";
const BY_WHAT_IS_MISSING = "manque";
const REVERSED = "1";

// The collation the alphabetical order is read in. It is the engine's own, and
// it is not cosmetic: « Écran » sorts before « Emma » in French and after it
// under the default.
const COLLATION = "fr";

// What a title neither source knows about answers. It sorts last, and it is the
// engine's own answer rather than a default chosen here.
const NOTHING_SAYS = -1;

/**
 * How many episodes a title is still missing, for the « ce qu'il manque » order.
 *
 * TWO SOURCES, IN THE ENGINE'S OWN ORDER OF PREFERENCE: the incomplete register
 * when it names the title, and otherwise the `n/m` the second line opens with.
 * A title neither knows answers -1, which sorts it last — that is the engine's
 * own answer and not a default chosen here.
 *
 * @param row The library row.
 * @returns How many are missing, or -1 when nothing says.
 */
function missing(row: { title: string; secondaryLine?: string }): number {
  const known = INCOMPLETE_SHOWS.find((show) => show.title === row.title);
  if (known !== undefined) return known.aired - known.owned;
  // « n/m » — owned over announced — read off the head of the second line.
  const counted = /^(?<owned>\d+)\/(?<aired>\d+)/.exec(row.secondaryLine ?? "");
  if (counted?.groups === undefined) return NOTHING_SAYS;
  return Number(counted.groups.aired) - Number(counted.groups.owned);
}

/**
 * Orders the rows the way the interface asks for them.
 *
 * THE ORDERING MOVED HERE FROM THE INTERFACE, and that is what makes paging
 * mean anything: a page of an unsorted set, sorted afterwards, is a page of the
 * wrong rows. It is the engine's own `sortLibrary`, term for term — the French
 * collation for the alphabetical order, the two-source derivation above for
 * what is missing, and the SOURCE's own order for « ajout récent », which has no
 * comparator at all.
 *
 * REVERSING IS A SECOND PASS, never a second comparator. « Récent » is never
 * compared, so a direction has to be expressible on a list nothing ordered.
 *
 * @param rows The rows to order.
 * @param key Which order, as the interface names it.
 * @param reversed Whether to read it the other way round.
 * @returns The rows, ordered.
 */
function ordered<Row extends { title: string; secondaryLine?: string }>(
  rows: Row[], key: string, reversed: boolean,
): Row[] {
  const held = rows.slice();
  if (key === BY_TITLE) {
    held.sort((left, right) => left.title.localeCompare(right.title, COLLATION));
  }
  else if (key === BY_WHAT_IS_MISSING) {
    held.sort((left, right) => missing(right) - missing(left));
  }
  return reversed ? held.reverse() : held;
}

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
  // ORDERED BEFORE IT IS PAGED. The interface used to hold the whole filtered
  // set and sort it itself, which is the only arrangement under which a page
  // index means nothing; now the order is asked for and the page is a page of
  // that order.
  rows = ordered(rows, request.query.get("sort") ?? "", request.query.get("reversed") === REVERSED);
  // An UNREADABLE page is not the end of the list. `Number("abc")` is NaN and
  // `slice(NaN, NaN)` answers an empty array, which reads exactly like having
  // scrolled past the last row.
  const asked = Number(request.query.get("page") ?? 0);
  const page = Number.isInteger(asked) && asked >= 0 ? asked : 0;
  return {
    // HOW MANY ROWS THIS QUESTION MATCHES, which is what a page is a page of.
    // It is neither of the two below, and conflating it with `total` is what
    // made the end of the list unreachable: paging stopped when the rows so far
    // reached 1 861, a number the source never had, so `hasNextPage` stayed
    // true over an empty page for ever and the end mark was never drawn.
    matching: rows.length,
    // HOW MANY THE LAYER REALLY HOLDS, whatever is being filtered for. It is
    // NOT `total`: the library claims 1 861 titles and the prototype carries
    // 345 of them, and the end mark says the second — « you have reached the
    // end of what there is », which a filtered count would make a lie under
    // every search. The engine answered it from `world.lib.length`; the
    // interface cannot derive it from a page, so the layer states it.
    loaded: state.library.length,
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
