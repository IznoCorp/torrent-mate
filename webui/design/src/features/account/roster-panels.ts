// « Comptes »' two panels and their acts — an account and its ONE role, a role
// and its rights (§ 17; ruling 20; round 9 Q14 = A).
//
// ESCALATION IS DRAWN AS WELL AS REFUSED: a manager who is not Admin sees the
// roles and rights its own role does not include GREYED, never offered as an
// act the server would refuse (round 9 Q14: « greyed on screen, refused by the
// guard if forced »). What is within reach is the model's answer on the
// manager's own role — never a role compared by name.
//
// A CHANGE REACHES THE ACCOUNT IT CONCERNS through the answer (demand M, F37):
// the roster and the signed-in account are read again, and every surface that
// draws by rights recomposes from what comes back — no poll.
//
// ONLY THE SERVER'S OWNER GIVES THE ADMIN ROLE (the operator, 2026-10-04: « seul
// le compte propriétaire peut promouvoir Admin ; un autre Admin ne le peut pas »):
// to another Admin the Admin choice is GREYED WITH ITS REASON, as an escalation is
// — never an act the server would refuse. AN ADMIN NEVER RESETS ITS OWN PASSWORD
// here (the operator, 2026-10-04): its panel says it changes in Profil.
//
// A ROLE IS DELETED ONLY WHEN NOTHING DEPENDS ON IT (the operator, 2026-10-04:
// « seulement s'il est attribué à aucun compte »; ruling A: nor when a newcomer
// starts on it), and Delete is OFFERED only there — never an act the server
// would refuse. It asks first (NE-DOIT-PAS-6).
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";

import { accountQuery, accountsQuery, roleLabel } from "../../lib/account";
import { RIGHTS, bypassesRights, rightsOf, sameRole, type Right } from "../../lib/rights";
import { HELD, send } from "../../lib/query-client";
import { refusalWords } from "../../lib/refusal";
import { dialog, panel, screens, toast } from "../../lib/shell-doors";
import { registerVerb } from "../../lib/verbs";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import type { Schemas } from "../../lib/contract-schemas";
import { typedRoleName } from "./panel-role-name";

type Roster = Schemas["Roster"];
type Role = Schemas["Role"];

// What separates the parts a verb carries: an id never carries it.
export const PART = "|";

/**
 * Whether the signed-in manager may hand out a set of rights: Admin any, any
 * other manager only rights its own role holds (round 9 Q14 = A).
 *
 * @param rights The rights handed out.
 * @param account The manager, as `readAccount` answered it.
 * @returns True when every right is within the manager's reach.
 */
export function withinReach(rights: readonly Right[], account: Schemas["Account"] | undefined): boolean {
  if (account === undefined) return false;
  const own = rightsOf({ ...account, forbiddenWrites: [] });
  return rights.every((right) => own.holds(right));
}

/**
 * How many rights a role carries, in words — Admin's holds no list, it
 * bypasses every right (ruling 22), and « 0 droit » would say the opposite.
 */
function said(role: Role): string {
  if (bypassesRights(role)) return i18next.t("screens.accounts.bypass");
  return i18next.t("screens.accounts.roleCount", { count: role.rights.length });
}

/**
 * One account's panel: its role, and the roles it may be given.
 *
 * @param id The account.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while the roster has not landed.
 */
function accountPanel(id: string, cache: PanelCache): PanelDescriptor | null {
  const roster = cache.held<Roster>(accountsQuery.queryKey);
  const manager = cache.held<Schemas["Account"]>(accountQuery.queryKey);
  const account = roster?.accounts.find((one) => one.id === id);
  if (roster === undefined || account === undefined) return null;
  const translate = i18next.t.bind(i18next);
  const own = manager !== undefined && manager.id === account.id && !bypassesRights(manager.role);
  const demotedFrom = roster.roles.find((one) => one.id === account.demotedFrom);
  const admin = manager !== undefined && bypassesRights(manager.role);
  const self = manager !== undefined && manager.id === account.id;
  // AN ADMIN WHO IS NOT THE OWNER may keep an Admin on Admin, never put one there.
  const ownerOnly = admin && manager.signInKind !== "owner" && !bypassesRights(account.role);
  return {
    address: "roster:" + id,
    title: account.name,
    meta: [{ m: account.email }],
    puce: ["info", roleLabel(account.role)],
    blocs: [
      { type: "note", text: translate(`screens.accounts.signInKind.${account.signInKind}`) },
      demotedFrom ? { type: "note", text: translate("screens.accounts.demoted", { role: roleLabel(demotedFrom) }) } : null,
      // ITS PASSWORD, by its kind (the operator, 2026-10-03): a local account's
      // provisional one is set again here; the owner's fallback one only on the
      // server — said in the words its refusal already has.
      // ADMIN ONLY (the operator, 2026-10-03): another manager is told so.
      account.signInKind === "local" && admin && !self
        ? { type: "accountPassword", account: account.id, name: account.name } : null,
      account.signInKind === "local" && admin && self ? { type: "note", text: translate("screens.accounts.reset.own") } : null,
      account.signInKind === "local" && !admin ? { type: "note", text: translate("screens.accounts.reset.adminOnly") } : null,
      account.signInKind === "owner" ? { type: "note", text: translate("refusals.password.held_by_cli") } : null,
      { type: "note", text: translate("screens.accounts.oneRole") },
      own ? { type: "note", text: translate("screens.accounts.notOwnRole") } : null,
      ownerOnly ? { type: "note", text: translate("screens.accounts.adminOwnerOnly") } : null,
      {
        type: "actions",
        actions: roster.roles.map((role) => ({
          text: roleLabel(role),
          mention: sameRole(role, account.role) ? translate("screens.accounts.current")
            : ownerOnly && bypassesRights(role) ? translate("screens.accounts.ownerOnly") : said(role),
          // GREYED, NEVER HIDDEN, where the manager may not give it: the
          // escalation is drawn so it is not a surprise (round 9 Q14 = A).
          desactive: own || sameRole(role, account.role)
            || (bypassesRights(role) && !(manager !== undefined && bypassesRights(manager.role)))
            || (bypassesRights(role) && ownerOnly)
            || !withinReach(role.rights, manager),
          target: { "account-role": [account.id, role.id].join(PART) },
        })),
      },
    ],
  };
}

/**
 * Whether a role may be deleted by this manager: no account holds it, no
 * newcomer starts on it (ruling A), it is not Admin's, and its rights are
 * within the manager's reach (round 9 Q14 = A).
 *
 * @param role The role.
 * @param roster The roster, its accounts each on its role.
 * @param manager The signed-in manager.
 * @returns True when Delete is offered.
 */
export function deletable(role: Role, roster: Roster, manager: Schemas["Account"] | undefined): boolean {
  if (bypassesRights(role) || (role.defaultFor ?? []).length > 0) return false;
  if (roster.accounts.some((account) => sameRole(account.role, role))) return false;
  return withinReach(role.rights, manager);
}

/**
 * One role's panel: what it is, and each right of § 1.2 it holds or does not.
 *
 * @param id The role.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while the roster has not landed.
 */
function rolePanel(id: string, cache: PanelCache): PanelDescriptor | null {
  const roster = cache.held<Roster>(accountsQuery.queryKey);
  const manager = cache.held<Schemas["Account"]>(accountQuery.queryKey);
  const role = roster?.roles.find((one) => one.id === id);
  if (roster === undefined || role === undefined) return null;
  const translate = i18next.t.bind(i18next);
  const say = (right: Right) => translate(`access.rights.${right}`);
  // THE ADMIN ROLE HOLDS NO LIST (ruling 22): it says so and offers nothing.
  if (bypassesRights(role))
    return {
      address: "role:" + id,
      title: roleLabel(role),
      blocs: [{ type: "note", text: translate("screens.accounts.adminRole") }],
    };
  const own = manager !== undefined && sameRole(manager.role, role) && !bypassesRights(manager.role);
  // ITS NAME IS OFFERED where the manager may change the role: not its own,
  // within its reach (round 9 Q14 = A: a manager renames only a role whose
  // rights it holds).
  const nameOffered = !own && withinReach(role.rights, manager);
  return {
    address: "role:" + id,
    title: roleLabel(role),
    blocs: [
      // WHO STARTS ON IT (O-K1-4): its rights are every such newcomer's.
      ...(role.defaultFor ?? []).map((kind) => ({ type: "note" as const, text: translate(`screens.accounts.defaultFor.${kind}`) })),
      own ? { type: "note", text: translate("screens.accounts.notOwnRole") } : null,
      nameOffered ? { type: "roleName", role: role.id, name: roleLabel(role) } : null,
      nameOffered
        ? { type: "actions", actions: [{ text: translate("screens.accounts.rename"), target: { "role-rename": role.id } }] }
        : null,
      {
        type: "actions",
        actions: RIGHTS.map((right) => {
          const held = role.rights.includes(right);
          return {
            text: translate(held ? "screens.accounts.withdraw" : "screens.accounts.grant", { right: say(right) }),
            mention: translate(`access.holders.${right}`),
            desactive: own || !withinReach([right], manager),
            target: { "role-right": [role.id, right, String(!held)].join(PART) },
          };
        }),
      },
      deletable(role, roster, manager)
        ? { type: "actions", actions: [{ text: translate("screens.accounts.roleDelete.act"), ton: "danger",
          target: { "role-delete": role.id } }] }
        : null,
    ],
  };
}

/**
 * Asks before a role is deleted, naming it (NE-DOIT-PAS-6).
 *
 * @param id The role.
 * @param name Its name, as the interface says it.
 */
function askToDelete(id: string, name: string): void {
  const translate = i18next.t.bind(i18next);
  dialog?.open({
    heading: translate("screens.accounts.roleDelete.heading", { name }),
    body: [{ type: "paragraph", runs: [{ text: translate("screens.accounts.roleDelete.body") }] }],
    actions: [
      { text: translate("screens.accounts.roleDelete.confirm"), tone: "danger", target: { "data-confirm-role-delete": id } },
      { text: translate("screens.accounts.roleDelete.cancel"), tone: "ghost", dismiss: true },
    ],
  });
}

/**
 * Deletes one role, then reads the roster again; a refusal is said in its code's words.
 *
 * @param client The cache.
 * @param id The role.
 */
async function deleteRole(client: QueryClient, id: string): Promise<void> {
  try {
    const answer = await send("DELETE", `/api/v1/roles/${encodeURIComponent(id)}`);
    panel?.close();
    if (answer === HELD) return;
    await client.refetchQueries({ queryKey: accountsQuery.queryKey });
    toast?.show({ message: i18next.t("screens.accounts.roleDelete.done") });
  } catch (failure) {
    toast?.show({ message: refusalWords(failure, "screens.accounts.roleDelete.refused") });
  }
}

registerProducer("roster", { produce: accountPanel, needs: [accountsQuery, accountQuery] });
registerProducer("role", { produce: rolePanel, needs: [accountsQuery, accountQuery] });

/**
 * Asks for one change, then reads the roster and the signed-in account again.
 *
 * @param client The cache.
 * @param ask The change.
 */
async function change(client: QueryClient, ask: () => Promise<unknown>): Promise<void> {
  try {
    await ask();
    await client.refetchQueries({ queryKey: accountsQuery.queryKey });
    await client.refetchQueries({ queryKey: accountQuery.queryKey });
    panel?.redraw();
    toast?.show({ message: i18next.t("screens.accounts.saved") });
  } catch {
    toast?.show({ message: i18next.t("screens.accounts.refused") });
  }
}

/**
 * Cuts one account's access or gives it back, then reads the roster again
 * (the operator, 2026-10-04). A refusal is said in its code's words.
 *
 * @param client The cache.
 * @param id The account.
 * @param allowed Whether it may sign in from now on.
 */
async function setAccess(client: QueryClient, id: string, allowed: boolean): Promise<void> {
  const name = client.getQueryData<Roster>(accountsQuery.queryKey)?.accounts.find((one) => one.id === id)?.name ?? id;
  try {
    const answer = await send("PUT", `/api/v1/accounts/${encodeURIComponent(id)}/access`, { signInAllowed: allowed });
    // HELD offline: nothing new to show until it departs.
    if (answer === HELD) return;
    await client.refetchQueries({ queryKey: accountsQuery.queryKey });
    toast?.show({ message: i18next.t(allowed ? "screens.accounts.access.restored" : "screens.accounts.access.cutDone", { name }) });
  } catch (failure) {
    toast?.show({ message: refusalWords(failure, "screens.accounts.access.refused") });
  }
}

/**
 * Declares « Comptes »' acts to the tap registry.
 *
 * @param client The cache the roster and the account are read from again.
 */
export function installRosterVerbs(client: QueryClient): void {
  registerVerb("account-role", (value) => {
    const [id, role] = value.split(PART);
    void change(client, () => send("PATCH", `/api/v1/accounts/${encodeURIComponent(id)}`, { role }));
  });
  registerVerb("account-access", (value) => {
    const [id, allowed] = value.split(PART);
    void setAccess(client, id, allowed === "true");
  });
  registerVerb("role-right", (value) => {
    const [id, right, on] = value.split(PART);
    const roster = client.getQueryData<Roster>(accountsQuery.queryKey);
    const current = roster?.roles.find((one) => one.id === id)?.rights ?? [];
    const rights = on === "true" ? [...current, right as Right] : current.filter((one) => one !== right);
    void change(client, () => send("PATCH", `/api/v1/roles/${encodeURIComponent(id)}`, { rights }));
  });
  registerVerb("role-rename", (id) => {
    const name = typedRoleName(id);
    // A ROLE IS NEVER NAMELESS: said before anything is asked.
    if (!name) {
      toast?.show({ message: i18next.t("screens.accounts.nameRequired") });
      return;
    }
    void change(client, () => send("PATCH", `/api/v1/roles/${encodeURIComponent(id)}`, { name }));
  });
  // A CREATION OPENS ITS OWN PAGE (the operator, 2026-10-04): the tap creates
  // nothing, and nothing is made up for it.
  registerVerb("role-create", () => screens?.newRole());
  registerVerb("account-create", () => screens?.newAccount());
  registerVerb("role-delete", (id) => {
    const role = client.getQueryData<Roster>(accountsQuery.queryKey)?.roles.find((one) => one.id === id);
    askToDelete(id, role === undefined ? id : roleLabel(role));
  });
  registerVerb("confirm-role-delete", (id) => {
    dialog?.close();
    void deleteRole(client, id);
  });
}
