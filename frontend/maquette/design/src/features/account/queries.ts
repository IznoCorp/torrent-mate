// What Compte asks the server for.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";

/** Who is signed in, as this feature draws it. `avatar` is served with the rest. */
export type Account = { name: string; mail: string; avatar?: string };

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
    toEngineShape<Account>("ACCOUNT", await read("/api/auth/me")),
};

/** Who is signed in. */
export function useAccount() {
  return useQuery(accountQuery);
}
