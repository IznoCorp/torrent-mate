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
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";

import { accountQuery, accountsQuery } from "../../lib/account";
import { RIGHTS, bypassesRights, isDefaultRole, rightsOf, sameRole, type Right } from "../../lib/rights";
import { send } from "../../lib/query-client";
import { panel, toast } from "../../lib/shell-doors";
import { registerVerb } from "../../lib/verbs";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import type { Schemas } from "../../lib/contract-schemas";
import { typedRoleName } from "./panel-role-name";

type Roster = Schemas["Roster"];
type Role = Schemas["Role"];

// What separates the parts a verb carries: an id never carries it.
const PART = "|";

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
  return {
    address: "roster:" + id,
    title: account.name,
    meta: [{ m: account.email }],
    puce: ["info", account.role.name],
    blocs: [
      { type: "note", text: translate(account.plexLinked ? "screens.accounts.plexLinked" : "screens.accounts.plexNotLinked") },
      { type: "note", text: translate("screens.accounts.oneRole") },
      own ? { type: "note", text: translate("screens.accounts.notOwnRole") } : null,
      {
        type: "actions",
        actions: roster.roles.map((role) => ({
          text: role.name,
          mention: sameRole(role, account.role) ? translate("screens.accounts.current") : said(role),
          // GREYED, NEVER HIDDEN, where the manager may not give it: the
          // escalation is drawn so it is not a surprise (round 9 Q14 = A).
          desactive: own || sameRole(role, account.role)
            || (bypassesRights(role) && !(manager !== undefined && bypassesRights(manager.role)))
            || !withinReach(role.rights, manager),
          target: { "account-role": [account.id, role.id].join(PART) },
        })),
      },
    ],
  };
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
      title: role.name,
      blocs: [{ type: "note", text: translate("screens.accounts.adminRole") }],
    };
  const own = manager !== undefined && sameRole(manager.role, role) && !bypassesRights(manager.role);
  // ITS NAME IS OFFERED where the manager may change the role: an ordinary one
  // (Default keeps its name, ruling 22), not its own, within its reach (round 9
  // Q14 = A: a manager renames only a role whose rights it holds).
  const nameOffered = !isDefaultRole(role) && !own && withinReach(role.rights, manager);
  return {
    address: "role:" + id,
    title: role.name,
    blocs: [
      isDefaultRole(role) ? { type: "note", text: translate("screens.accounts.defaultRole") } : null,
      own ? { type: "note", text: translate("screens.accounts.notOwnRole") } : null,
      nameOffered ? { type: "roleName", role: role.id, name: role.name } : null,
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
    ],
  };
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
 * Declares « Comptes »' acts to the tap registry.
 *
 * @param client The cache the roster and the account are read from again.
 */
export function installRosterVerbs(client: QueryClient): void {
  registerVerb("account-role", (value) => {
    const [id, role] = value.split(PART);
    void change(client, () => send("PATCH", `/api/v1/accounts/${encodeURIComponent(id)}`, { role }));
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
  registerVerb("role-create", () => {
    // A NEW ROLE STARTS WITH THE DEFAULT ROLE'S RIGHTS, as every new account
    // does — nothing handed out that the manager did not choose.
    const roster = client.getQueryData<Roster>(accountsQuery.queryKey);
    const rights = roster?.roles.find(isDefaultRole)?.rights ?? [];
    const name = i18next.t("screens.accounts.newRoleName", { count: (roster?.roles.length ?? 0) + 1 });
    void change(client, () => send("POST", "/api/v1/roles", { name, rights }));
  });
}
