// WHO IS SIGNED IN, as the layer answers it — the owner at rest, an invented
// account while a named state dials one (DESIGN maquette-l18 § 2.2).
//
// THE IDENTITIES ARE INVENTED and marked so (`seeds/accounts.json`,
// `x-unseeded`): no account but the Plex owner exists. They are readable only
// while a dial turns one on, and every dial lives in the layer's own state, so
// `window.__mocks.reset()` puts the owner back with everything else — the
// resting maquette is his (R-L18-a).
//
// Its own module rather than `state.ts`, which is already past its size ceiling
// (F38).
import ACCOUNT from "./seeds/account.json";
import ACCOUNTS from "./seeds/accounts.json";
import type { components } from "../contract/types";
import { rightsOf, type Right, type Rights } from "../lib/rights";
import { accountName } from "./account";
import { mockState } from "./state";

type Schemas = components["schemas"];
type Role = Schemas["Role"];

/** What the dials hold, per layer state. */
type Dialled = {
  identity: string;
  forbiddenWrites: Right[];
  plexReachable: boolean;
  inventedRequests: boolean;
  /** Requesters a reassignment moved, by title — they replace the seed's. */
  moved: Record<string, string[]>;
  /** Each requester's own quality and pause on an acquisition, by title then account. */
  preferences: Record<string, Record<string, Preference>>;
  /** Roles whose rights were set since the seed, by role id. */
  roleRights: Record<string, Right[]>;
  /** Roles renamed since the seed, by role id. */
  roleNames: Record<string, string>;
  /** Roles « Comptes » created. */
  createdRoles: Role[];
  /** Accounts « Comptes » created. */
  createdAccounts: HeldAccount[];
  /** Accounts assigned another role since the seed, by account id. */
  assigned: Record<string, string>;
};

/** One requester's own settings on one acquisition (round 10 Q6). */
export type Preference = { quality?: string | null; paused?: boolean };

// Keyed by the state object, so a reset of the layer forgets every dial.
const dialled = new WeakMap<object, Dialled>();

/** The dials in force now. */
function dials(): Dialled {
  const held = mockState();
  let found = dialled.get(held);
  if (found === undefined) {
    found = {
      identity: ACCOUNT.id,
      forbiddenWrites: [],
      plexReachable: true,
      inventedRequests: false,
      moved: {},
      preferences: structuredClone(ACCOUNTS.preferences) as Record<string, Record<string, Preference>>,
      roleRights: {},
      roleNames: {},
      createdRoles: [],
      createdAccounts: [],
      assigned: {},
    };
    dialled.set(held, found);
  }
  return found;
}

/** Every role the layer holds. */
export function roles(): Role[] {
  const { roleRights, roleNames, createdRoles } = dials();
  return [...(ACCOUNTS.roles as Role[]), ...createdRoles].map((role) => ({
    ...role,
    name: roleNames[role.id] ?? role.name,
    rights: [...(roleRights[role.id] ?? role.rights)],
  }));
}

/** The role one id names. */
export function roleFor(id: string): Role {
  const role = roles().find((one) => one.id === id);
  if (role === undefined) throw new Error(`no role is seeded under ${id}`);
  return role;
}

/** One account of the roster, as the layer holds it. */
export type HeldAccount = {
  id: string;
  name: string;
  email: string;
  role: string;
  plexLinked: boolean;
};

/** Every account: the owner first, then the invented ones. */
export function heldAccounts(): HeldAccount[] {
  const { assigned, createdAccounts } = dials();
  return [
    { id: ACCOUNT.id, name: accountName(), email: ACCOUNT.email, role: ACCOUNT.role, plexLinked: ACCOUNT.plexLinked },
    ...ACCOUNTS.accounts,
    ...createdAccounts,
  ].map((one) => ({ ...one, role: assigned[one.id] ?? one.role }));
}

/** What « Comptes » writes, over the layer's own state (demands G, H). */
export const roster = {
  addRole: (role: Role) => { dials().createdRoles.push(role); },
  renameRole: (id: string, name: string) => { dials().roleNames[id] = name; },
  setRoleRights: (id: string, rights: Right[]) => { dials().roleRights[id] = [...rights]; },
  addAccount: (account: HeldAccount) => { dials().createdAccounts.push(account); },
  assign: (id: string, role: string) => { dials().assigned[id] = role; },
};

/** The account dialled in, in the roster's shape. */
function dialledAccount(): HeldAccount {
  const id = dials().identity;
  const found = heldAccounts().find((one) => one.id === id);
  if (found === undefined) throw new Error(`no account is seeded under ${id}`);
  return found;
}

/**
 * Who is signed in, as `readAccount` answers it.
 *
 * @returns The account, its role, its Plex link and the instance's forbidden writes.
 */
export function signedIn(): Schemas["Account"] {
  const held = dialledAccount();
  return {
    id: held.id,
    name: held.name,
    email: held.email,
    // THE OWNER'S PICTURE IS HIS: an invented account carries none — the field
    // is absent, as a local account's is — and the header draws its initial
    // (the reader's L18 round, izno's face on Tom).
    ...(held.id === ACCOUNT.id ? { avatar: ACCOUNT.avatar } : {}),
    role: roleFor(held.role),
    plexLinked: held.plexLinked,
    forbiddenWrites: [...dials().forbiddenWrites],
  };
}

/** What the signed-in account may do — the model's own derivation. */
export function signedInRights(): Rights {
  return rightsOf(signedIn());
}

/** The id of the account signed in. */
export function signedInId(): string {
  return dials().identity;
}

/**
 * Who asked for one acquisition.
 *
 * AT REST, THE OWNER ALONE — he is the one account that exists. With the
 * invented requests dialled (and whenever an invented account is signed in,
 * whose lists would be empty otherwise), the seed's accounts join him on the
 * titles it names.
 *
 * @param title The acquisition, by its title.
 * @returns Its requesters, the owner first.
 */
export function requestersOf(title: string): Schemas["AccountRef"][] {
  const state = dials();
  const named = (ids: string[]) => ids
    .map((id) => heldAccounts().find((one) => one.id === id))
    .filter((one): one is HeldAccount => one !== undefined)
    .map((one) => ({ id: one.id, name: one.name }));
  if (state.moved[title]) return named(state.moved[title]);
  if (!state.inventedRequests && state.identity === ACCOUNT.id) return named([ACCOUNT.id]);
  const requests = ACCOUNTS.requests as Record<string, string[]>;
  return named([ACCOUNT.id, ...heldAccounts().filter((one) => requests[one.id]?.includes(title)).map((one) => one.id)]);
}

/**
 * Moves one requester of an acquisition off, and another account on.
 *
 * @param title The acquisition, by its title.
 * @param from The requester moved off.
 * @param to The account moved on.
 * @returns The requesters after the move, or null when `from` was not one.
 */
export function moveRequester(title: string, from: string, to: string): Schemas["AccountRef"][] | null {
  const ids = requestersOf(title).map((one) => one.id);
  if (!ids.includes(from) || !heldAccounts().some((one) => one.id === to)) return null;
  const next = ids.filter((id) => id !== from);
  if (!next.includes(to)) next.push(to);
  dials().moved[title] = next;
  return requestersOf(title);
}

/**
 * Records the signed-in account as a requester of an acquisition — its first,
 * when it creates one; one more, when it asks for one another account already
 * follows (round 9 Q16: a follow keeps a table of requesters).
 *
 * @param title The acquisition, by its title.
 * @param existing Whether the acquisition was already there.
 */
export function claimRequest(title: string, existing: boolean): void {
  const ids = existing ? requestersOf(title).map((one) => one.id) : [];
  if (!ids.includes(dials().identity)) ids.push(dials().identity);
  dials().moved[title] = ids;
}

/**
 * Takes the signed-in account off an acquisition's requesters — what « Retirer
 * de la liste » does to a follow others asked for too (round 9 Q16): the follow
 * stays for them.
 *
 * @param title The acquisition, by its title.
 * @returns The requesters left.
 */
export function releaseRequest(title: string): Schemas["AccountRef"][] {
  dials().moved[title] = requestersOf(title).map((one) => one.id).filter((id) => id !== dials().identity);
  return requestersOf(title);
}

/**
 * What one account may do — its role's rights under the instance's ceiling.
 *
 * @param id The account.
 * @returns Its rights, by the model's own derivation.
 */
export function rightsOfAccount(id: string): Rights {
  const held = heldAccounts().find((one) => one.id === id);
  if (held === undefined) return rightsOf(undefined);
  return rightsOf({ ...signedIn(), id, role: roleFor(held.role) });
}

/**
 * Every requester's own settings on one acquisition.
 *
 * @param title The acquisition, by its title.
 * @returns The settings, by account — a live record the verbs write into.
 */
export function preferencesOf(title: string): Record<string, Preference> {
  const all = dials().preferences;
  all[title] ??= {};
  return all[title];
}

/** Whether the Plex server answers — the gate's own dial. */
export function plexReachable(): boolean {
  return dials().plexReachable;
}

/** The dials a named state turns to sign someone else in. */
export type IdentityDials = {
  /** Signs in one account of the roster, by id, until the layer is next reset. */
  setIdentity: (id: string) => void;
  /** Sets the instance's forbidden writes (ruling 23) — a named list, never a boolean. */
  setForbiddenWrites: (rights: Right[]) => void;
  /** Whether the Plex server answers a sign-in. */
  setPlexReachable: (reachable: boolean) => void;
  /** Whether the invented accounts' requests join the owner's on the lists. */
  setInventedRequests: (on: boolean) => void;
  /** Sets one role's rights, as « Comptes » would, until the layer is next reset. */
  setRoleRights: (roleId: string, rights: Right[]) => void;
};

/** Those dials, over the layer's own state. */
export const identityDials: IdentityDials = {
  setIdentity: (id) => {
    if (!heldAccounts().some((one) => one.id === id)) throw new Error(`no account is seeded under ${id}`);
    dials().identity = id;
  },
  setForbiddenWrites: (rights) => { dials().forbiddenWrites = [...rights]; },
  setPlexReachable: (reachable) => { dials().plexReachable = reachable; },
  setInventedRequests: (on) => { dials().inventedRequests = on; },
  setRoleRights: (roleId, rights) => {
    roleFor(roleId);
    roster.setRoleRights(roleId, rights);
  },
};
