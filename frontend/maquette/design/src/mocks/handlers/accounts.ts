// The accounts and their roles — the roster « Comptes » manages and the
// reassign chooser reads (§ 17; demands F, G, H).
//
// INVENTED beside the owner (`../identity`): read only while a named state
// dials a manager or turns the invented accounts on.
//
// THE GUARDS ARE THE SERVER'S, and each answers with its reason:
//   · 409 — no account left on the Admin role, none left holding
//     `auth.password` (the door of last resort), a system role renamed, the
//     Admin role given a list (F2; ruling 22);
//   · 403 — escalation (round 9 Q14 = A, M7): a manager who is not Admin sets
//     only rights its own role holds, never its own role, never an account on
//     the Admin role;
//   · 400 — a new account without an e-mail.
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
const DEFAULT = "default";

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
    plexLinked: one.plexLinked,
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

/** Whether a role opens a right, Admin's bypass included. */
function opens(role: Role, right: Right): boolean {
  return role.kind === ADMIN || role.rights.includes(right);
}

/**
 * Whether the roster, as it would stand, keeps an Admin and a password holder.
 *
 * @param accounts The accounts, each on the role it would hold.
 * @param every The roles as they would stand.
 * @returns The reason it would not, or null.
 */
function lastResort(accounts: HeldAccount[], every: Role[]): string | null {
  const role = (one: HeldAccount) => every.find((candidate) => candidate.id === one.role)!;
  if (!accounts.some((one) => role(one).kind === ADMIN)) return "no account would be left on the Admin role";
  if (!accounts.some((one) => opens(role(one), "auth.password")))
    return "no account would be left holding auth.password";
  return null;
}

/** Every route this subject answers. */
export function accountRoutes(): MockRoute[] {
  return [
    route("readAccounts", GET, "/api/accounts", answered),
    route("createAccount", POST, "/api/accounts", (request) => {
      const name = text(request.body, "name").trim();
      const email = text(request.body, "email").trim();
      const role = text(request.body, "role");
      if (!email.includes("@") || !name) return refused(INVALID, "a local account carries a name and an e-mail");
      const target = roles().find((one) => one.id === role);
      if (target === undefined) return refused(MISSING, "no role carries that id");
      if (target.kind === ADMIN && callerRole().kind !== ADMIN) return refused(FORBIDDEN, "only Admin gives Admin");
      if (!within(target.rights)) return refused(FORBIDDEN, "the role holds rights the caller's does not");
      const created: HeldAccount = {
        id: `account-${heldAccounts().length + 1}`,
        name,
        email,
        role,
        plexLinked: ACCOUNTS.plexUsers.includes(email.toLowerCase()),
      };
      roster.addAccount(created);
      return summary(created);
    }),
    route("updateAccount", PATCH, "/api/accounts/{accountId}", (request) => {
      const account = heldAccounts().find((one) => one.id === request.parameters.accountId);
      const target = roles().find((one) => one.id === text(request.body, "role"));
      if (account === undefined || target === undefined) return refused(MISSING, "no such account or role");
      const caller = callerRole();
      if (caller.kind !== ADMIN) {
        if (account.id === signedInId()) return refused(FORBIDDEN, "a manager never touches its own role");
        if (roleFor(account.role).kind === ADMIN || target.kind === ADMIN)
          return refused(FORBIDDEN, "a manager who is not Admin never touches Admin");
        if (!within(target.rights)) return refused(FORBIDDEN, "the role holds rights the caller's does not");
      }
      const after = heldAccounts().map((one) => (one.id === account.id ? { ...one, role: target.id } : one));
      const reason = lastResort(after, roles());
      if (reason) return refused(CONFLICT, reason);
      roster.assign(account.id, target.id);
      return summary({ ...account, role: target.id });
    }),
    route("createRole", POST, "/api/roles", (request) => {
      const rights = (field(request.body, "rights") as Right[] | undefined) ?? [];
      if (!within(rights)) return refused(FORBIDDEN, "the role would hold rights the caller's does not");
      const created: Role = {
        id: `role-${roles().length + 1}`,
        name: text(request.body, "name") || `role-${roles().length + 1}`,
        kind: "ordinary",
        rights: [...rights],
      };
      roster.addRole(created);
      return created;
    }),
    route("updateRole", PATCH, "/api/roles/{roleId}", (request) => {
      const role = roles().find((one) => one.id === request.parameters.roleId);
      if (role === undefined) return refused(MISSING, "no role carries that id");
      if (role.kind === ADMIN) return refused(CONFLICT, "the Admin role holds no list and is not modified");
      const name = field(request.body, "name");
      const rights = field(request.body, "rights") as Right[] | undefined;
      if (typeof name === "string" && role.kind === DEFAULT) return refused(CONFLICT, "a system role keeps its name");
      if (callerRole().kind !== ADMIN) {
        if (callerRole().id === role.id) return refused(FORBIDDEN, "a manager never touches its own role");
        if (rights && !within(rights)) return refused(FORBIDDEN, "the role would hold rights the caller's does not");
      }
      if (rights) {
        const every = roles().map((one) => (one.id === role.id ? { ...one, rights } : one));
        const reason = lastResort(heldAccounts(), every);
        if (reason) return refused(CONFLICT, reason);
        roster.setRoleRights(role.id, rights);
      }
      if (typeof name === "string" && name.trim()) roster.renameRole(role.id, name.trim());
      return roleFor(role.id);
    }),
  ];
}
