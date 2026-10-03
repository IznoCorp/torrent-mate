// The accounts and their roles — the roster « Comptes » manages and the
// reassign chooser reads (§ 17; demands F, G, H).
//
// INVENTED beside the owner (`../identity`): read only while a named state
// dials a manager or turns the invented accounts on.
//
// THE GUARDS ARE THE SERVER'S, and each answers with its code (gap G-1):
//   · 409 — no account left on the Admin role, the Admin role modified
//     (F2; ruling 22), an e-mail already taken;
//   · 403 — escalation (round 9 Q14 = A, M7): a manager who is not Admin sets
//     only rights its own role holds, never its own role, never an account on
//     the Admin role;
//   · 400 — a new account without an e-mail.
// No guard keeps a password holder: the owner's fallback password is his
// account's, replaced on the server only (the operator, 2026-10-03).
import ACCOUNTS from "../seeds/accounts.json";
import { GET, PATCH, POST, field, route, text } from "./shared";
import { refused, type MockRoute } from "../router";
import { heldAccounts, roleFor, roles, roster, signedInId, type HeldAccount } from "../identity";
import type { components } from "../../contract/types";
import type { Right } from "../../lib/rights";

type Role = components["schemas"]["Role"];

const INVALID = 400;
const FORBIDDEN = 403;
const MISSING = 404;
const CONFLICT = 409;
const ADMIN = "admin";

/** The roster, as `readAccounts` answers it. */
function answered() {
  const every = roles();
  // A MANAGER WHO IS NOT ADMIN NEVER TOUCHES AN ADMIN ACCOUNT, TO VIEW OR TO
  // CHANGE (M7): the roster it reads holds none.
  const admin = callerRole().kind === ADMIN;
  return {
    accounts: heldAccounts()
      .filter((one) => admin || roleFor(one.role).kind !== ADMIN)
      .map((one) => summary(one, every)),
    roles: every,
  };
}

/** One account in the answer's shape. */
function summary(one: HeldAccount, every: Role[] = roles()) {
  return {
    id: one.id,
    name: one.name,
    email: one.email,
    role: every.find((role) => role.id === one.role)!,
    signInKind: one.signInKind,
    ...(one.demotedFrom ? { demotedFrom: one.demotedFrom } : {}),
  };
}

/** The caller's role — what escalation is measured against. */
function callerRole(): Role {
  const caller = heldAccounts().find((one) => one.id === signedInId())!;
  return roleFor(caller.role);
}

/** Whether rights are included in the caller's own role's (Admin includes every right). */
function within(rights: readonly string[]): boolean {
  const own = callerRole();
  return own.kind === ADMIN || rights.every((right) => own.rights.includes(right as Right));
}

/**
 * Whether the roster, as it would stand, keeps an account on the Admin role.
 *
 * @param accounts The accounts, each on the role it would hold.
 * @returns True when one is left on it.
 */
function keepsAnAdmin(accounts: HeldAccount[]): boolean {
  return accounts.some((one) => roleFor(one.role).kind === ADMIN);
}

/**
 * The role a newcomer of one kind starts on (O-K1-4).
 *
 * @param kind Who starts: a Plex Home user, another user of the server, a local account.
 * @returns The role, or undefined when none is marked for it.
 */
function startingRole(kind: "plexHome" | "plexGuest" | "local"): Role | undefined {
  return roles().find((one) => one.defaultFor?.includes(kind));
}

/** Every route this subject answers. */
export function accountRoutes(): MockRoute[] {
  return [
    route("readAccounts", GET, "/accounts", answered),
    route("createAccount", POST, "/accounts", (request) => {
      const name = text(request.body, "name").trim();
      const email = text(request.body, "email").trim();
      if (!email.includes("@") || !name) return refused(INVALID, "a local account carries a name and an e-mail", "account.email_invalid");
      // AN E-MAIL THAT IS A USER OF THE MANAGED SERVER IS LINKED from the start,
      // signs in by Plex only, and starts on its Plex kind's role; any other is a
      // local account, on the role asked, else the one local accounts start on
      // (O-K1-4).
      const linked = ACCOUNTS.plexUsers.includes(email.toLowerCase());
      const asked = text(request.body, "role");
      const target = linked ? startingRole("plexGuest") : asked ? roles().find((one) => one.id === asked) : startingRole("local");
      if (target === undefined) return refused(MISSING, "no role carries that id", "role.unknown");
      if (target.kind === ADMIN && callerRole().kind !== ADMIN)
        return refused(FORBIDDEN, "only Admin gives Admin", "role.escalation");
      if (!within(target.rights))
        return refused(FORBIDDEN, "the role holds rights the caller's does not", "role.escalation");
      if (heldAccounts().some((one) => one.email.toLowerCase() === email.toLowerCase()))
        return refused(CONFLICT, "an account already carries that e-mail", "account.email_taken");
      const created: HeldAccount = {
        id: `account-${heldAccounts().length + 1}`,
        name,
        email,
        role: target.id,
        signInKind: linked ? "plex" : "local",
      };
      roster.addAccount(created);
      return summary(created);
    }),
    route("updateAccount", PATCH, "/accounts/{accountId}", (request) => {
      const account = heldAccounts().find((one) => one.id === request.parameters.accountId);
      const target = roles().find((one) => one.id === text(request.body, "role"));
      if (account === undefined) return refused(MISSING, "no account carries that id", "account.unknown");
      if (target === undefined) return refused(MISSING, "no role carries that id", "role.unknown");
      const caller = callerRole();
      if (caller.kind !== ADMIN) {
        if (account.id === signedInId()) return refused(FORBIDDEN, "a manager never touches its own role", "role.own_role");
        if (roleFor(account.role).kind === ADMIN || target.kind === ADMIN)
          return refused(FORBIDDEN, "a manager who is not Admin never touches Admin", "account.admin_untouchable");
        if (!within(target.rights))
          return refused(FORBIDDEN, "the role holds rights the caller's does not", "role.escalation");
      }
      const after = heldAccounts().map((one) => (one.id === account.id ? { ...one, role: target.id } : one));
      if (!keepsAnAdmin(after))
        return refused(CONFLICT, "no account would be left on the Admin role", "account.last_admin");
      roster.assign(account.id, target.id);
      return summary(heldAccounts().find((one) => one.id === account.id)!);
    }),
    route("createRole", POST, "/roles", (request) => {
      const rights = (field(request.body, "rights") as Right[] | undefined) ?? [];
      if (!within(rights))
        return refused(FORBIDDEN, "the role would hold rights the caller's does not", "role.escalation");
      const created: Role = {
        id: `role-${roles().length + 1}`,
        name: text(request.body, "name") || `role-${roles().length + 1}`,
        kind: "ordinary",
        rights: [...rights],
      };
      roster.addRole(created);
      return created;
    }),
    route("updateRole", PATCH, "/roles/{roleId}", (request) => {
      const role = roles().find((one) => one.id === request.parameters.roleId);
      if (role === undefined) return refused(MISSING, "no role carries that id", "role.unknown");
      if (role.kind === ADMIN)
        return refused(CONFLICT, "the Admin role holds no list and is not modified", "role.system_immutable");
      const name = field(request.body, "name");
      const rights = field(request.body, "rights") as Right[] | undefined;
      if (callerRole().kind !== ADMIN) {
        if (callerRole().id === role.id) return refused(FORBIDDEN, "a manager never touches its own role", "role.own_role");
        if (rights && !within(rights))
          return refused(FORBIDDEN, "the role would hold rights the caller's does not", "role.escalation");
        if (typeof name === "string" && !within(role.rights))
          return refused(FORBIDDEN, "a manager renames only a role within its own rights", "role.escalation");
      }
      if (rights) roster.setRoleRights(role.id, rights);
      if (typeof name === "string" && name.trim()) roster.renameRole(role.id, name.trim());
      return roleFor(role.id);
    }),
  ];
}
