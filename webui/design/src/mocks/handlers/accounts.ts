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
//     the Admin role; and ONLY THE SERVER'S OWNER GIVES THE ADMIN ROLE (the
//     operator, 2026-10-04: « seul le compte propriétaire peut promouvoir
//     Admin ; un autre Admin ne le peut pas »), and THE OWNER'S ACCOUNT NEVER
//     LEAVES IT, whoever asks;
//   · 400 — a new account without an e-mail or without its role — none is
//     chosen for the manager (the operator, 2026-10-04); a local account
//     without its provisional password, or with one breaking the password
//     policy (`lib/password-policy.ts`); a new role without a name — none is
//     ever made up for it (the operator, 2026-10-04);
//   · 409 — a new role under a name another role carries; deleting a role an
//     account holds, a role a newcomer starts on (ruling A) or the Admin role.
// AN ACCOUNT'S ACCESS IS AN ADMIN'S TO CUT (the operator, 2026-10-04; Q4 = A,
// Q5 = A): any account but the owner and the Admin's own, every session of it
// ended at once (`../identity`), its sign-ins refused until it is given back.
// A PROVISIONAL PASSWORD IS A LOCAL ACCOUNT'S ONLY (the operator, 2026-10-03:
// « A »): the Admin gives it at creation and may reset it; the owner's fallback
// password is replaced on the server only, and a Plex-linked account holds none.
// AN ADMIN NEVER RESETS ITS OWN (the operator, 2026-10-04): it changes it in
// Profil, the current one required. The layer judges the kind and the policy,
// and stores no password.
import ACCOUNTS from "../seeds/accounts.json";
import { DELETE, GET, PATCH, POST, PUT, field, route, text } from "./shared";
import { refused, type MockRoute, type Refusal } from "../router";
import { heldAccounts, roleFor, roles, roster, signInAllowed, signedInId, type HeldAccount } from "../identity";
import type { components } from "../../contract/types";
import type { Right } from "../../lib/rights";
import { PASSWORD_MINIMUM, passwordShortfall } from "../../lib/password-policy";

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
    signInAllowed: signInAllowed(one.id),
    ...(one.demotedFrom ? { demotedFrom: one.demotedFrom } : {}),
  };
}

/** The caller's role — what escalation is measured against. */
function callerRole(): Role {
  const caller = heldAccounts().find((one) => one.id === signedInId())!;
  return roleFor(caller.role);
}

/** Whether the caller is the managed Plex server's owner — the one who gives the Admin role. */
function callerIsOwner(): boolean {
  return heldAccounts().find((one) => one.id === signedInId())?.signInKind === "owner";
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

/**
 * Why a password breaks the policy every local door applies, if it does.
 *
 * @param password The password typed.
 * @returns The refusal, naming the minimum, or undefined when it meets the policy.
 */
export function policyRefusal(password: string): Refusal | undefined {
  const shortfall = passwordShortfall(password);
  if (shortfall === undefined) return undefined;
  return refused(INVALID, "the password breaks the password policy", shortfall, { minimum: PASSWORD_MINIMUM });
}

/**
 * Why a provisional password is refused, if it is (the operator, 2026-10-03: « A »).
 *
 * @param password The password the Admin typed.
 * @returns The refusal, or undefined when it meets the policy.
 */
function provisionalRefusal(password: string): Refusal | undefined {
  if (!password) return refused(INVALID, "a local account starts with a provisional password", "password.required");
  return policyRefusal(password);
}

/**
 * An id no role carries, deleted ones included — a count alone would hand a
 * deleted role's id to the next one created.
 *
 * @returns The id.
 */
function nextRoleId(): string {
  const taken = new Set(roles().map((one) => one.id));
  let index = roles().length + 1;
  while (taken.has(`role-${index}`)) index += 1;
  return `role-${index}`;
}

/**
 * Whether another role already carries a name — the contract's rule: the
 * `name` a role carries, trimmed, regardless of case (a seeded role carries
 * none; its words are the interface's). Case is folded by `toLowerCase`,
 * Unicode's default lowercase mapping — the server's `str.lower`, never a
 * `casefold` the layer could only approximate.
 *
 * @param name The name asked for, trimmed.
 * @param except The role being renamed, which may keep its own name.
 * @returns True when another role carries it.
 */
function nameCarried(name: string, except?: string): boolean {
  const wanted = name.toLowerCase();
  return roles().some((one) => one.id !== except && one.name?.trim().toLowerCase() === wanted);
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
      // THE ROLE IS REQUIRED (the operator, 2026-10-04): nothing is chosen for
      // the manager — absent, the body is not the contract's.
      const asked = field(request.body, "role");
      if (typeof asked !== "string") return refused(INVALID, "a new account names its role", "request.invalid");
      const linked = ACCOUNTS.plexUsers.includes(email.toLowerCase());
      const target = linked ? startingRole("plexGuest") : roles().find((one) => one.id === asked);
      if (target === undefined) return refused(MISSING, "no role carries that id", "role.unknown");
      if (target.kind === ADMIN && callerRole().kind !== ADMIN)
        return refused(FORBIDDEN, "only Admin gives Admin", "role.escalation");
      if (target.kind === ADMIN && !callerIsOwner())
        return refused(FORBIDDEN, "only the server's owner gives the Admin role", "account.admin_owner_only");
      if (!within(target.rights))
        return refused(FORBIDDEN, "the role holds rights the caller's does not", "role.escalation");
      if (heldAccounts().some((one) => one.email.toLowerCase() === email.toLowerCase()))
        return refused(CONFLICT, "an account already carries that e-mail", "account.email_taken");
      // A LINKED E-MAIL'S PASSWORD IS IGNORED, never kept: it signs in by Plex only.
      const refusal = linked ? undefined : provisionalRefusal(text(request.body, "password"));
      if (refusal) return refusal;
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
      // ONLY THE OWNER PUTS AN ACCOUNT ON ADMIN; one already there, kept there, is given nothing.
      if (target.kind === ADMIN && roleFor(account.role).kind !== ADMIN && !callerIsOwner())
        return refused(FORBIDDEN, "only the server's owner gives the Admin role", "account.admin_owner_only");
      // THE OWNER'S ACCOUNT NEVER LEAVES ADMIN, whoever asks — the owner too:
      // demoted, nobody would be left to give Admin back. Before the last Admin.
      if (target.kind !== ADMIN && account.signInKind === "owner")
        return refused(FORBIDDEN, "the server owner's account never leaves the Admin role", "account.owner_admin");
      const after = heldAccounts().map((one) => (one.id === account.id ? { ...one, role: target.id } : one));
      if (!keepsAnAdmin(after))
        return refused(CONFLICT, "no account would be left on the Admin role", "account.last_admin");
      roster.assign(account.id, target.id);
      return summary(heldAccounts().find((one) => one.id === account.id)!);
    }),
    route("resetAccountPassword", POST, "/accounts/{accountId}/password", (request) => {
      // ADMIN ONLY (the operator, 2026-10-03): any password account, from
      // « Comptes »; everyone changes their own in Profil. CHECKED FIRST (the
      // operator, 2026-10-04, OPEN-3 B): a manager never learns which ids exist.
      if (callerRole().kind !== ADMIN)
        return refused(FORBIDDEN, "only an Admin resets a password", "password.reset_admin_only");
      // NEVER ITS OWN (the operator, 2026-10-04): an Admin changes its own in Profil, the current one required.
      if (request.parameters.accountId === signedInId())
        return refused(FORBIDDEN, "an Admin changes its own password with its current one", "password.reset_own");
      const account = heldAccounts().find((one) => one.id === request.parameters.accountId);
      if (account === undefined) return refused(MISSING, "no account carries that id", "account.unknown");
      if (account.signInKind === "owner")
        return refused(FORBIDDEN, "the owner's fallback password is replaced on the server only", "password.held_by_cli");
      if (account.signInKind === "plex")
        return refused(FORBIDDEN, "this account signs in with Plex", "auth.plex_only");
      return provisionalRefusal(text(request.body, "password")) ?? { ok: true };
    }),
    route("setAccountAccess", PUT, "/accounts/{accountId}/access", (request) => {
      // ADMIN ONLY, CHECKED FIRST, as the reset: a manager never learns which ids exist.
      if (callerRole().kind !== ADMIN)
        return refused(FORBIDDEN, "only an Admin cuts or gives back an account's access", "account.access_admin_only");
      const account = heldAccounts().find((one) => one.id === request.parameters.accountId);
      if (account === undefined) return refused(MISSING, "no account carries that id", "account.unknown");
      const allowed = field(request.body, "signInAllowed");
      if (typeof allowed !== "boolean")
        return refused(INVALID, "the body says whether the account may sign in", "request.invalid");
      // THE OWNER IS THE FALLBACK DOOR, and an Admin never locks itself out (Q5 = A).
      if (account.signInKind === "owner")
        return refused(FORBIDDEN, "the owner's access is never cut", "account.owner_access");
      if (account.id === signedInId())
        return refused(FORBIDDEN, "an Admin never cuts its own access", "account.own_access");
      roster.setAccess(account.id, allowed);
      return summary(account);
    }),
    route("createRole", POST, "/roles", (request) => {
      const rights = (field(request.body, "rights") as Right[] | undefined) ?? [];
      // THE NAME IS TYPED, NEVER MADE UP (the operator, 2026-10-04), and no two
      // roles carry the same one.
      const name = text(request.body, "name").trim();
      if (!name) return refused(INVALID, "a role carries the name the manager typed", "role.name_required");
      if (nameCarried(name))
        return refused(CONFLICT, "another role already carries that name", "role.name_taken");
      if (!within(rights))
        return refused(FORBIDDEN, "the role would hold rights the caller's does not", "role.escalation");
      const created: Role = { id: nextRoleId(), name, kind: "ordinary", rights: [...rights] };
      roster.addRole(created);
      return created;
    }),
    route("deleteRole", DELETE, "/roles/{roleId}", (request) => {
      // ONLY A ROLE NOTHING DEPENDS ON GOES (the operator, 2026-10-04): no
      // account holds it, and no newcomer starts on it — even held by nobody
      // (ruling A).
      const role = roles().find((one) => one.id === request.parameters.roleId);
      if (role === undefined) return refused(MISSING, "no role carries that id", "role.unknown");
      if (role.kind === ADMIN) return refused(CONFLICT, "the Admin role is never deleted", "role.system_immutable");
      if (role.defaultFor?.length) return refused(CONFLICT, "a newcomer starts on this role", "role.default");
      if (heldAccounts().some((one) => one.role === role.id))
        return refused(CONFLICT, "an account holds this role", "role.in_use");
      if (!within(role.rights))
        return refused(FORBIDDEN, "the role holds rights the caller's does not", "role.escalation");
      roster.removeRole(role.id);
      return { ok: true };
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
      // A RENAME KEEPS NAMES UNIQUE, by the same rule as a creation; a role may
      // keep its own name, in another case.
      if (typeof name === "string" && name.trim() && nameCarried(name.trim(), role.id))
        return refused(CONFLICT, "another role already carries that name", "role.name_taken");
      if (rights) roster.setRoleRights(role.id, rights);
      if (typeof name === "string" && name.trim()) roster.renameRole(role.id, name.trim());
      return roleFor(role.id);
    }),
  ];
}
