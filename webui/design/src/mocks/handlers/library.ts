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
import { refused, type MockRequest, type MockRoute } from "../router";
import { holdersOf, incompleteHolding, type MediaRef } from "./membership";

// How many rows one page carries. A page size belongs to the interface, not to
// a server — the register classifies it `interface` — so the layer states its
// own rather than seeding one.
const PAGE_SIZE = 24;

// The three orders, as the contract's `sort` parameter names them, and the
// token its `reversed` parameter carries for « the other way round ». Named
// rather than written inline: the handler guard reads a schema's enum and not a
// parameter's, so a constant is what stops these being four bare strings that
// nobody can tie back to the contract.
const BY_TITLE = "az";
const BY_WHAT_IS_MISSING = "missing";
const REVERSED = "1";

// The providers an identity is read at, as the contract's `MediaRef` names them.
const PROVIDERS: readonly string[] = ["tvdb", "tmdb", "imdb"];

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
 * READ FROM THE INCOMPLETE REGISTER, the aired catalogue's own answer: a row
 * carries facts, never a line to read a fraction off. A title it does not name
 * answers -1, which sorts it last — « unknown », never « complete ».
 *
 * @param row The library row.
 * @returns How many are missing, or -1 when nothing says.
 */
function missing(row: { title: string }): number {
  const known = INCOMPLETE_SHOWS.find((show) => show.title === row.title);
  return known === undefined ? NOTHING_SAYS : known.aired - known.owned;
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
function ordered<Row extends { title: string }>(
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
  const leaves = request.query.getAll("category");
  let rows = state.library;
  let filtered = false;
  if (wanted !== "") {
    rows = rows.filter((row) => row.title.toLowerCase().includes(wanted));
    filtered = true;
  }
  // THE ENGINE'S LEAVES, repeated: the lens is the interface's, and no leaf
  // asked keeps every category.
  if (leaves.length > 0) {
    rows = rows.filter((row) => leaves.includes(row.category));
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
    route("readLibraryItems", GET, "/library/items", listing),
    route("readLibraryCategories", GET, "/library/categories", () => LIBRARY_CATEGORIES),
    route("readLibraryRecent", GET, "/library/recent", () => RECENT),
    route("readLibraryIncomplete", GET, "/library/incomplete", () => INCOMPLETE_SHOWS),
    route("deleteLibraryItems", DELETE, "/library/items", (request) => {
      const state = mockState();
      const asked = field(request.body, "media");
      const media: MediaRef[] = Array.isArray(asked)
        ? asked.map((one) => ({ provider: String(field(one, "provider")), providerId: String(field(one, "providerId")) }) as MediaRef)
        : [];
      if (media.length === 0 || media.some((one) => !PROVIDERS.includes(one.provider) || one.providerId === ""))
        return refused(400, "media must name each medium by provider and providerId", "request.invalid");
      // NOTHING GOES WHILE A RUN HOLDS THE PIPELINE'S LOCK: the dispatch may be
      // writing the very folder.
      if (state.pipelineSince !== null) return refused(409, "the pipeline holds its lock", "library.locked");
      // EVERY MEDIUM IS JUDGED BEFORE ANY GOES: a refusal deletes nothing.
      for (const one of media) {
        const rows = holdersOf(state.library, one).length;
        if (rows === 0 && incompleteHolding(one) === undefined)
          return refused(404, `no library row holds ${one.provider} ${one.providerId}`, "media.not_found", { ...one });
        // O-5 B: an identity held twice is not deleted until the duplicate is settled.
        if (rows > 1)
          return refused(409, `${rows} library rows hold ${one.provider} ${one.providerId}`, "media.ambiguous", { ...one });
      }
      const doomed = new Set(media.flatMap((one) => holdersOf(state.library, one)));
      const titles = [
        ...[...doomed].map((row) => row.title),
        ...media.map((one) => incompleteHolding(one)?.title).filter((title): title is string => title !== undefined),
      ];
      // An incomplete series the seed holds no row of still counts as one medium gone.
      const withoutRow = media.filter((one) => holdersOf(state.library, one).length === 0).length;
      const before = state.library.length;
      state.library = state.library.filter((row) => !doomed.has(row));
      // AND THE SHEETS ARE TOLD. Ownership on a media sheet comes from a seed
      // keyed by title, so filtering the listing left every sheet answering as
      // before — and a reader who reopened one after confirming was offered
      // « Supprimer » a second time, over a toast saying it was done.
      for (const title of titles) {
        if (!state.deletedTitles.includes(title)) state.deletedTitles.push(title);
      }
      return { deleted: before - state.library.length + withoutRow };
    }),
  ];
}
