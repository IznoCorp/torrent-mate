// WHO IS SIGNED IN, and what the account may do — read by every surface that
// draws by rights (§ 17). In `lib/` because every feature and the frame read it,
// and invariant 7 forbids a feature importing another.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import i18next from "i18next";
import { browserLanguage, speak } from "../i18n";
import { read, sharedQueryClient, useServerStateVersion } from "./query-client";
import type { Schemas } from "./contract-schemas";
import { bypassesRights, rightsOf, type Rights } from "./rights";

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
  queryKey: ["/api/v1/auth/me"],
  queryFn: async () =>
    read<Account>("/api/v1/auth/me"),
};

/**
 * Makes the interface speak the signed-in account's language (FG-1 B), and the
 * browser's once nobody is signed in (OPEN-2 B).
 *
 * FROM THE CACHE, ON EVERY MOVE OF THE ACCOUNT'S ENTRY, rather than from a
 * component: the account is read by the sign-in, by the frame and by Profil's
 * own write, and the language must follow whichever answered last — at once,
 * with no reload, and before the next paint. An entry emptied (a lost session,
 * the harness's reset) gives the sign-in page back its browser's language; a
 * sign-out says so itself, the entry left in place.
 *
 * @param client The boot's cache.
 */
export function followAccountLanguage(client: QueryClient): void {
  const [key] = accountQuery.queryKey;
  let followed: Account | undefined;
  client.getQueryCache().subscribe((event) => {
    if (event.query.queryKey[0] !== key) return;
    // ONLY WHEN THE ANSWER MOVES, not on every event of its entry: a surface
    // mounting over the same answer is no reason to speak again, and would undo
    // the browser's language a sign-out gave the gate (`app/entry.ts`).
    const account = client.getQueryData<Account>(accountQuery.queryKey);
    if (account === followed) return;
    followed = account;
    // AN ACCOUNT READ WITHOUT ONE — the design host's real server, until it
    // serves the field — speaks as nobody does: the browser's language.
    speak(account?.language ?? browserLanguage());
  });
}

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

/** Every account and every role (demand F) — « Comptes » reads it, and the reassign chooser narrowly (F46). */
export const accountsQuery = {
  queryKey: ["/api/v1/accounts"],
  queryFn: async () => read<Schemas["Roster"]>("/api/v1/accounts"),
};

/**
 * A role's name, as the interface says it (gap G-10).
 *
 * A SEEDED ROLE NEVER RENAMED HAS NO NAME: the words are the interface's, the
 * translation of its id in `fr.json` (`roles.seed.<id>`). A role an Admin named
 * or renamed shows his text. An unknown id with no name shows the id itself —
 * defined and visible, so a gap in the translations is seen rather than blank.
 *
 * @param role The role.
 * @returns Its name, for display — never compared.
 */
export function roleLabel(role: Schemas["Role"]): string {
  return role.name ?? i18next.t(`roles.seed.${role.id}`, { defaultValue: role.id });
}
