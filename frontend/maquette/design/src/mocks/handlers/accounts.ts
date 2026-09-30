// The accounts and their roles — the roster « Comptes » manages and the
// reassign chooser reads (§ 17; demands F, G, H).
//
// INVENTED beside the owner (`../identity`): read only while a named state
// dials a manager or turns the invented accounts on.
import { GET, route } from "./shared";
import type { MockRoute } from "../router";
import { heldAccounts, roles } from "../identity";

/** The roster, as `readAccounts` answers it. */
function roster() {
  const every = roles();
  return {
    accounts: heldAccounts().map((one) => ({
      id: one.id,
      name: one.name,
      email: one.email,
      role: every.find((role) => role.id === one.role)!,
      plexLinked: one.plexLinked,
    })),
    roles: every,
  };
}

/** Every route this subject answers. */
export function accountRoutes(): MockRoute[] {
  return [route("readAccounts", GET, "/api/accounts", roster)];
}
