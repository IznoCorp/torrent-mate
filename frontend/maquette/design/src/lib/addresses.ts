// The address model: which page sits at which path, and which dials a page
// carries in its query.
//
// D1 — the path carries the IDENTITY (which thing is being looked at), the
// query carries the STATE (how it is being looked at). This table is the whole
// of that decision, in one place, and it is the piece that LEFT the engine:
// composing and parsing an address is not navigation logic, it is a naming
// convention, and a naming convention nobody can find is one every reader
// re-invents.
//
// It knows no domain and renders nothing, so it lives here rather than in a
// feature or in the shell.
//
// THE VOCABULARY IS PRODUCTION'S. `/acquisition`, `/media`, `/system` are the
// addresses the shipped app already serves; this prototype replaces that app,
// so adopting a second vocabulary would mean renaming everything twice. A route
// path is a NAME, which is why it is written in English like any other.

/** The store field a page id maps to, and the path that names it. */
export const PAGE_PATHS: Readonly<Record<string, string>> = {
  acq: "/acquisition",
  lib: "/media",
  arr: "/arrivals",
  sys: "/system",
  maint: "/maintenance",
  cfg: "/settings",
  profile: "/account",
};

/** The page an address names, for every path the table above declares. */
export const PAGE_OF_PATH: Readonly<Record<string, string>> = Object.fromEntries(
  Object.entries(PAGE_PATHS).map(([page, path]) => [path, page]),
);

/** The page the bare root stands for — `/` redirects onto its path. */
export const HOME_PAGE = "acq";

/** The page an address nobody serves lands on. */
export const NOT_FOUND_PAGE = "404";

// Every dial: the query parameter that carries it, the store field it writes,
// and the value at which it is ABSENT from the address.
//
// « Only what DIFFERS from the opening state is written » is R69's first hold
// and it is kept exactly: the common case has a clean address, and a link
// carries only what it means to carry.
//
// A parameter name is a NAME — `topic` rather than the `rub` it replaced.
// A dial belongs to ONE page. That is D1 read literally — the query says how
// THIS surface is being looked at — and it is what keeps `/media?tab=follows`
// from existing: a library address carrying an acquisition dial describes a
// state no screen is in.
const DIALS = [
  { parameter: "tab", field: "acqTab", default: "now", of: "acq" },
  { parameter: "lens", field: "libLens", default: "cat", of: "lib" },
  { parameter: "mode", field: "libMode", default: "grid", of: "lib" },
  { parameter: "cat", field: "libCat", default: "all", of: "lib" },
  { parameter: "topic", field: "maintTopic", default: "", of: "maint" },
] as const;

/** The query parameters any page may carry — read by the addressing guard. */
export const DIAL_PARAMETERS: readonly string[] = DIALS.map((d) => d.parameter);

/** The dials one page carries, by the parameter name each appears under. */
export function dialsOfPage(page: string): readonly string[] {
  return DIALS.filter((dial) => dial.of === page).map((dial) => dial.parameter);
}

/** What an address resolves to: a page, the dials it sets, and, when the page
 * is nobody's, the address exactly as it was asked for. */
export type Destination = {
  page: string;
  dials: Record<string, string>;
  notFound?: string;
};

/**
 * Composes the address a state should be seen at.
 *
 * Args:
 *     page: The page id the interface is showing.
 *     values: The current value of every dial, keyed by its STORE FIELD —
 *         the engine's own vocabulary, so a caller reads its state and hands
 *         it over without translating.
 *
 * Returns:
 *     The path, plus the query for whatever differs from the opening state.
 *     A page the table does not carry keeps the root: an id nobody serves is
 *     rendered as the not-found surface, and giving it an address of its own
 *     would rewrite a mistyped link into a different one.
 */
export function addressOf(page: string, values: Record<string, unknown>): string {
  const path = PAGE_PATHS[page] ?? "/";
  const query = new URLSearchParams();
  for (const dial of DIALS) {
    if (dial.of !== page) continue;
    const value = values[dial.field];
    if (value && String(value) !== dial.default) query.set(dial.parameter, String(value));
  }
  const written = query.toString();
  return path + (written ? "?" + written : "");
}

/**
 * Reads back what an address carries.
 *
 * An absent parameter is not « empty », it is « unchanged »: nothing is
 * written for it and the opening state stands.
 *
 * Args:
 *     pathname: The address's path.
 *     search: Its query string, leading `?` included or not.
 *
 * Returns:
 *     The page the path names and the dials the query sets. A path no page
 *     claims resolves to the not-found page, carrying the address AS ASKED —
 *     deriving a corrected address from it is the interface rewriting the
 *     operator's link behind their back, which a browser answering 404 never
 *     does.
 */
export function destinationOf(pathname: string, search: string): Destination {
  const page =
    PAGE_OF_PATH[pathname] ?? (pathname === "/" ? HOME_PAGE : NOT_FOUND_PAGE);
  const dials: Record<string, string> = {};
  const query = new URLSearchParams(search);
  for (const dial of DIALS) {
    if (dial.of !== page) continue;
    const value = query.get(dial.parameter);
    if (value) dials[dial.field] = value;
  }
  if (page === NOT_FOUND_PAGE) return { page, dials, notFound: pathname };
  return { page, dials };
}
