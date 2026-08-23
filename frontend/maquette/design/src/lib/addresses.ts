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

// The sign-in screen's address. It is not a PAGE — it is a layer that covers
// everything, so it names no entry in the page table — but D1 says every screen
// sits on a real path, and this is a screen: it is the whole of what one sees.
// Its address therefore resolves to the home page UNDERNEATH plus the flag that
// raises it, which is what lets a cold `/login` show the sign-in over a frame
// that is already built rather than over nothing.
export const SIGN_IN_PATH = "/login";

// The screen addresses. A screen is not a PAGE either — it is a layer drawn
// OVER the home frame — but D1 gives it a real path, so its address has to
// resolve to the page UNDERNEATH exactly as `SIGN_IN_PATH` does. Resolving it
// to the not-found page instead puts « this address leads nowhere » beneath a
// screen the operator opened from a stable link, and the moment the screen
// closes that is all they are left with.
//
// This list is the SINGLE declaration the routes, the addressing rule and the
// offline guard are all held against: a screen route with no entry here, or an
// entry no route claims, is a violation. A `$segment` stands for any one
// non-empty segment, the way the route files write it.
export const SCREEN_PATHS: readonly string[] = [
  "/add",
  "/quality/$name",
  "/media/$provider/$id",
  "/releases/$title",
  "/resolution/$folder",
];

/**
 * Tells whether a path is one of the screen addresses.
 *
 * Args:
 *     pathname: The address's path.
 *
 * Returns:
 *     True when the path matches a `SCREEN_PATHS` entry, a `$segment`
 *     standing for any one non-empty segment.
 */
export function isScreenPath(pathname: string): boolean {
  const asked = pathname.split("/").filter(Boolean);
  return SCREEN_PATHS.some((declared) => {
    const segments = declared.split("/").filter(Boolean);
    return (
      segments.length === asked.length &&
      segments.every((segment, index) => segment.startsWith("$") || segment === asked[index])
    );
  });
}

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

/** The parameter the addressed panel travels under — D1's second tier. It
 * belongs to no page: a panel opens over whichever one is showing. */
export const PANEL_PARAMETER = "panel";

/**
 * Drops the panel parameter from a query string, keeping the rest verbatim.
 *
 * The panel tier is the one part of an address a reader can ask for and the
 * interface can legitimately decline — the subject may be one nobody holds. The
 * address the arrival is RECORDED at therefore never carries it: either the
 * panel reopened, and it pushes its own entry carrying its own address on top,
 * or it did not, and an address naming a panel nothing opened would be a
 * parameter the interface never honoured.
 *
 * The kept pairs are copied as they were WRITTEN rather than re-serialised: a
 * round trip through `URLSearchParams` rewrites `%20` as `+` and would change
 * an address that was only being passed through.
 *
 * Args:
 *     search: The query string, leading `?` included or not.
 *
 * Returns:
 *     The query string without the panel parameter, leading `?` included when
 *     anything is left, and the empty string when nothing is.
 */
export function withoutPanel(search: string): string {
  const raw = search.startsWith("?") ? search.slice(1) : search;
  const kept = raw
    .split("&")
    .filter((pair) => pair !== "" && pair.split("=")[0] !== PANEL_PARAMETER);
  return kept.length ? "?" + kept.join("&") : "";
}

/** The query parameters any page may carry — read by the addressing guard. */
export const DIAL_PARAMETERS: readonly string[] = [
  ...DIALS.map((d) => d.parameter),
  PANEL_PARAMETER,
];

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
  /** The sign-in screen is asked for, over whatever page the address names. */
  signIn?: boolean;
  /** The addressed panel asked for, as `<kind>:<subject>`. */
  panel?: string;
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
 *     The not-found page composes the address EXACTLY as it was asked for —
 *     `values.notFound`, nothing appended — because a mistyped link that
 *     composes back to some other page's path is the interface rewriting the
 *     operator's address behind their back.
 *
 * Raises:
 *     Error: When the page is one the table does not carry. An id nobody
 *         serves has no address of its own, so composing one is a refusal
 *         rather than a default — a caller that reaches this has a state no
 *         address describes, and inventing one hides that. The not-found page
 *         raises the same way when it is handed no `notFound` to give back.
 */
export function addressOf(
  page: string,
  values: Record<string, unknown>,
  panel?: string,
): string {
  // A not-found address is reproduced verbatim: no dials, and no panel either
  // — a panel over an address that leads nowhere is not a state anyone links
  // to, so a `panel` passed with this page is ignored rather than appended.
  if (page === NOT_FOUND_PAGE) {
    const asked = values.notFound;
    if (typeof asked !== "string" || asked === "") {
      throw new Error(
        `addressOf: page "${NOT_FOUND_PAGE}" needs the address it was asked for, ` +
          "and no notFound was given",
      );
    }
    return asked;
  }
  const path = PAGE_PATHS[page];
  if (path === undefined) {
    throw new Error(`addressOf: no address is declared for page "${page}"`);
  }
  const query = new URLSearchParams();
  if (panel) query.set(PANEL_PARAMETER, panel);
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
 *     The page the path names and the dials the query sets. A screen address
 *     resolves to the page underneath it, the way the sign-in one does. A path
 *     neither a page nor a screen claims resolves to the not-found page,
 *     carrying the address AS ASKED — deriving a corrected address from it is
 *     the interface rewriting the operator's link behind their back, which a
 *     browser answering 404 never does.
 */
export function destinationOf(pathname: string, search: string): Destination {
  if (pathname === SIGN_IN_PATH) return { page: HOME_PAGE, dials: {}, signIn: true };
  const query = new URLSearchParams(search);
  // The panel tier is independent of which page shows — a panel opens over
  // whichever surface is underneath, a screen included.
  const panel = query.get(PANEL_PARAMETER) || undefined;
  if (isScreenPath(pathname)) return { page: HOME_PAGE, dials: {}, panel };
  const page =
    PAGE_OF_PATH[pathname] ?? (pathname === "/" ? HOME_PAGE : NOT_FOUND_PAGE);
  const dials: Record<string, string> = {};
  for (const dial of DIALS) {
    if (dial.of !== page) continue;
    const value = query.get(dial.parameter);
    if (value) dials[dial.field] = value;
  }
  if (page === NOT_FOUND_PAGE) return { page, dials, notFound: pathname, panel };
  return { page, dials, panel };
}
