// WHETHER THE LIBRARY HOLDS ONE MEDIUM, answered from the WHOLE library.
//
// The listing is paged and a page is not the library: asking « is it on the
// pages I hold? » answers « no » for a title on page two. This read asks the
// layer's whole state instead — the rows a deletion has already filtered, and
// the incomplete series a deletion has already told — so a removal is heard by
// every surface that asks afterwards.
//
// KEYED BY PROVIDER IDENTITY (operator ruling Q5 A, 2026-10-01: provider ids
// ARE the identity). Two rows holding one id are a DUPLICATE, and `rows` says
// so: the deletion refuses such an id until it is settled (O-5 B).
import INCOMPLETE_SHOWS from "../seeds/incomplete-shows.json";
import { GET, route } from "./shared";
import { mockState } from "../state";
import { refused, type MockRequest, type MockRoute } from "../router";
import type { Schemas } from "../../lib/contract-schemas";

/** A medium named by its provider identity, in the contract's names. */
export type MediaRef = Schemas["MediaRef"];

/** The providers an identity may be read at. */
const PROVIDERS = new Set(["tvdb", "tmdb", "imdb"]);

/**
 * Whether one set of provider identifiers carries the identity asked.
 *
 * A seed spells one identifier as a number and another as a string, so both
 * are compared as strings.
 *
 * @param ids The identifiers a row carries, or null.
 * @param ref The identity asked.
 * @returns True when the row carries it.
 */
function carries(
  ids: Record<string, string | number> | null | undefined,
  ref: MediaRef,
): boolean {
  const held = ids?.[ref.provider];
  return held !== undefined && held !== null && String(held) === ref.providerId;
}

/**
 * The library rows holding one identity — two or more is a duplicate.
 *
 * @param rows The library's rows.
 * @param ref The identity.
 * @returns Every row carrying it.
 */
export function holdersOf<
  Row extends { ids?: Record<string, string | number> | null },
>(rows: readonly Row[], ref: MediaRef): Row[] {
  return rows.filter((row) => carries(row.ids, ref));
}

/**
 * The incomplete series holding one identity, unless a deletion took it.
 *
 * @param ref The identity.
 * @returns The series, or undefined.
 */
export function incompleteHolding(ref: MediaRef) {
  const gone = mockState().deletedTitles;
  return INCOMPLETE_SHOWS.find(
    (show) =>
      carries(show.ids as Record<string, string | number>, ref) &&
      !gone.includes(show.title),
  );
}

/**
 * Answers what the library holds of one medium.
 *
 * @param request The request, its `provider` and `providerId` in the query.
 * @returns Whether it is held, how many rows hold it, whether it is incomplete, its kind and its identifiers.
 */
function membership(request: MockRequest) {
  const provider = request.query.get("provider") ?? "";
  const providerId = request.query.get("providerId") ?? "";
  if (!PROVIDERS.has(provider) || providerId === "")
    return refused(
      400,
      "provider and providerId are required",
      "request.invalid",
    );
  const ref = { provider, providerId } as MediaRef;
  const rows = holdersOf(mockState().library, ref);
  const row = rows[0];
  const show = incompleteHolding(ref);
  return {
    inLibrary: row !== undefined || show !== undefined,
    rows: rows.length,
    incomplete: show !== undefined,
    kind: row?.kind ?? (show !== undefined ? "show" : null),
    ids: row?.ids ?? show?.ids ?? null,
  };
}

/** Every route this subject answers. */
export function membershipRoutes(): MockRoute[] {
  return [
    route("readLibraryMembership", GET, "/library/membership", membership),
  ];
}
