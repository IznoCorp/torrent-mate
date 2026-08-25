// What the library holds.
//
// The whole of this subject is a DEMAND on the backend: there is no library
// endpoint of any kind in `frontend/openapi.json` — no listing, no categories,
// no recents, no incompletes. The register computed by
// `scripts/compare-contracts.py` says so, operation by operation.
import CATS from "../seeds/CATS.json";
import INCOMPLETE from "../seeds/INCOMPLETE.json";
import LIB_TOTAL from "../seeds/LIB_TOTAL.json";
import RECENT from "../seeds/RECENT.json";
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
  if (wanted !== "") {
    rows = rows.filter((row) => row.title.toLowerCase().includes(wanted));
  }
  if (category !== "" && category !== CATS[0].id) {
    const known = CATS.find((entry) => entry.id === category);
    const included = known?.includes ?? [category];
    rows = rows.filter((row) => included.includes(row.category));
  }
  const page = Number(request.query.get("page") ?? 0);
  return {
    total: LIB_TOTAL,
    items: rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
  };
}

/** Every route this subject answers. */
export function libraryRoutes(): MockRoute[] {
  return [
    route("readLibraryItems", GET, "/api/library/items", listing),
    route("readLibraryCategories", GET, "/api/library/categories", () => CATS),
    route("readLibraryRecent", GET, "/api/library/recent", () => RECENT),
    route("readLibraryIncomplete", GET, "/api/library/incomplete", () => INCOMPLETE),
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
