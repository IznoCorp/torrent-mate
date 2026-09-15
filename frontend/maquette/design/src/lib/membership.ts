// WHETHER ONE MEDIUM IS HELD, asked by its exact title — the one read every
// surface that states the fact shares.
//
// A listing is paged, so « is it on a page I hold? » is a narrower question
// than « is it held? », and it answers « no » for a title on page two. This read
// is exact and answered from everything the layer holds. It is written here,
// once, because the follow panel and the removal dialog ask it from two features
// that never import each other.
import { read } from "./query-client";
import type { components } from "../contract/types";

/** What the layer answers about one title. */
export type Membership = components["schemas"]["LibraryMembership"];

/**
 * The membership read for one exact title, as a query the cache and a producer share.
 *
 * @param title The medium's exact title.
 * @returns The query's key and function.
 */
export function membershipQuery(title: string) {
  return {
    queryKey: ["/api/library/membership", title] as const,
    queryFn: () =>
      read<Membership>(`/api/library/membership?title=${encodeURIComponent(title)}`),
  };
}
