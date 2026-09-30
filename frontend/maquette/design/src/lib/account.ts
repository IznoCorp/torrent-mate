// WHO IS SIGNED IN, and what the account may do — read by every surface that
// draws by rights (§ 17). In `lib/` because every feature and the frame read it,
// and invariant 7 forbids a feature importing another.
import { useQuery } from "@tanstack/react-query";
import { read, sharedQueryClient, useServerStateVersion } from "./query-client";
import type { Schemas } from "./contract-schemas";
import { rightsOf, type Rights } from "./rights";

/** Who is signed in, as `readAccount` answers it. */
export type Account = Schemas["Account"];

/**
 * The signed-in account, as a query DEFINITION.
 *
 * IT IS A DEFINITION AND NOT ONLY A HOOK because two readers want it and only
 * one of them renders: the account PAGE subscribes through `useAccount()`, and
 * the account MENU is produced from a click on the header — on every page,
 * including the ones that never mount the page. A producer cannot await, so
 * what it reads has to have been asked for; asking through the same definition
 * is what stops the two from drifting into two shapes of one answer (§13).
 */
export const accountQuery = {
  queryKey: ["/api/auth/me"],
  queryFn: async () =>
    read<Account>("/api/auth/me"),
};

/** Who is signed in. */
export function useAccount() {
  return useQuery(accountQuery);
}

/**
 * What the signed-in account may do, observed: a surface that draws by rights
 * redraws when the account's answer moves.
 *
 * @returns The rights, or none while the account has not been read.
 */
export function useRights(): Rights {
  // SUBSCRIBED TO THE CACHE AS A WHOLE, as the frame's badges are: an observer
  // keeps the query it was given, so after the cache is emptied it would go on
  // reading an entry the cache no longer holds. Redrawing on every move hands
  // the hook the cache's current entry.
  useServerStateVersion();
  return rightsOf(useAccount().data);
}

/**
 * What the signed-in account may do, read synchronously from the cache — for a
 * producer or a badge, which run in a task that cannot await.
 *
 * @returns The rights, or none while the account has not been read.
 */
export function heldRights(): Rights {
  return rightsOf(sharedQueryClient?.getQueryData<Account>(accountQuery.queryKey));
}
