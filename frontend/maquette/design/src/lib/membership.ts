// WHETHER ONE MEDIUM IS HELD, asked by its provider identity — the one read
// every surface that states the fact shares.
//
// A listing is paged, so « is it on a page I hold? » is a narrower question
// than « is it held? », and it answers « no » for a title on page two. This read
// is exact and answered from everything the library holds. It is written here,
// once, because the follow panel and the removal dialog ask it from two features
// that never import each other.
//
// THE WIRE KNOWS ONE IDENTITY, THE PROVIDER'S (operator ruling Q5 A). A surface
// that holds only the title it drew — a panel's subject — first finds the
// identity that title was drawn with: in the cache, which holds the read the
// title came from, and otherwise in the library's own search. That resolution
// answers a QUESTION (is it held?) and never reaches a removal: two media may
// share a title, so a removal is handed the identity its row was drawn with.
import { read, sharedQueryClient } from "./query-client";
import { heldIdentity } from "./held-identity";
import { baseTitle } from "./titles";
import type { components } from "../contract/types";

/** What the layer answers about one medium. */
export type Membership = components["schemas"]["LibraryMembership"];

/** A medium named by its provider identity. */
export type MediaRef = components["schemas"]["MediaRef"];

/** The providers an identity is read at, in the order a series names them. */
const SHOW_ORDER = ["tvdb", "tmdb", "imdb"] as const;
/** And a film: TMDB first. */
const MOVIE_ORDER = ["tmdb", "tvdb", "imdb"] as const;

/** What a medium nobody identified answers: the library cannot hold what it cannot name. */
const NOT_HELD: Membership = {
  inLibrary: false,
  rows: 0,
  incomplete: false,
  ids: null,
  kind: null,
};

/**
 * The identity one set of provider identifiers names — TVDB first for a series,
 * TMDB first for a film.
 *
 * @param ids The identifiers, when there are any.
 * @param kind The medium's kind, when known; a series' order otherwise.
 * @returns The identity, or null when no provider is named.
 */
export function mediaRefOf(
  ids: Record<string, number | string> | null | undefined,
  kind?: string | null,
): MediaRef | null {
  if (!ids) return null;
  for (const provider of kind === "movie" ? MOVIE_ORDER : SHOW_ORDER) {
    const held = ids[provider];
    if (held !== undefined && held !== null && String(held) !== "")
      return { provider, providerId: String(held) };
  }
  return null;
}

/**
 * The key one identity is written under — a selection's, a row's attribute.
 *
 * @param ref The identity.
 * @returns `provider:providerId`.
 */
export function refKey(ref: MediaRef): string {
  return `${ref.provider}:${ref.providerId}`;
}

/**
 * The identity one key names — the inverse of `refKey`.
 *
 * @param key The key a row's attribute carries, when it carries one.
 * @returns The identity, or null when the key names none.
 */
export function refOfKey(key: string | null | undefined): MediaRef | null {
  const cut = key?.indexOf(":") ?? -1;
  if (key == null || cut <= 0 || cut === key.length - 1) return null;
  const provider = key.slice(0, cut);
  if (!(SHOW_ORDER as readonly string[]).includes(provider)) return null;
  return { provider: provider as MediaRef["provider"], providerId: key.slice(cut + 1) };
}

/**
 * The membership read for one identity, as a query the cache and a producer share.
 *
 * @param ref The medium's provider identity.
 * @returns The query's key and function.
 */
export function membershipByRefQuery(ref: MediaRef) {
  return {
    queryKey: [
      "/api/v1/library/membership",
      ref.provider,
      ref.providerId,
    ] as const,
    queryFn: () =>
      read<Membership>(
        `/api/v1/library/membership?provider=${encodeURIComponent(ref.provider)}&providerId=${encodeURIComponent(ref.providerId)}`,
      ),
  };
}

/**
 * The identity a title was drawn with: the cache's first, the library's search
 * otherwise — exact on the title once the year a folder appends is set aside.
 *
 * @param title The title a surface drew.
 * @returns The identity, or null when nothing identifies that title.
 */
export async function identityOfTitle(title: string): Promise<MediaRef | null> {
  const held = heldIdentity(title);
  const cached = mediaRefOf(held?.ids, held?.kind);
  if (cached !== null) return cached;
  const base = baseTitle(title);
  const page = await read<{
    items: {
      title: string;
      kind: string;
      ids: Record<string, string | number> | null;
    }[];
  }>("/api/v1/library/items", new URLSearchParams({ query: base }));
  const row = page.items.find(
    (one) => baseTitle(one.title) === base && one.ids !== null,
  );
  return row === undefined ? null : mediaRefOf(row.ids, row.kind);
}

/**
 * The membership read for the medium one title names, as a query the cache and
 * a producer share — the identity found first, then asked by it.
 *
 * @param title The title a surface drew the medium under.
 * @returns The query's key and function.
 */
export function membershipQuery(title: string) {
  return {
    queryKey: ["/api/v1/library/membership", title] as const,
    queryFn: async (): Promise<Membership> => {
      const ref = await identityOfTitle(title);
      if (ref === null) return NOT_HELD;
      const byRef = membershipByRefQuery(ref);
      return sharedQueryClient?.fetchQuery(byRef) ?? byRef.queryFn();
    },
  };
}
