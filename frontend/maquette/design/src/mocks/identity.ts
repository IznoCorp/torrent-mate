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
  /** What Plex answers once the PIN is asked about (`signInWithPlex`). */
  plexClaim: PlexClaim;
  /** Whether a current password given to `changeOwnPassword` matches. */
  passwordAccepted: boolean;
  inventedRequests: boolean;
  /** Whether the test roles and their accounts join the seeded five (harness states only). */
  testRoster: boolean;
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
  /** Roles « Comptes » deleted, by id — seeded or created. */
  deletedRoles: string[];
  /** Accounts « Comptes » created. */
  createdAccounts: HeldAccount[];
  /** Accounts assigned another role since the seed, by account id. */
  assigned: Record<string, string>;
  /** Accounts an Admin cut: their sign-ins are refused until the switch is back on. */
  accessCut: string[];
  /** Accounts whose sessions were ended by a cut, until their next sign-in opens one. */
  sessionsEnded: string[];
};

/**
 * What a Plex PIN comes to: claimed by the identity dialled, still unclaimed,
 * claimed by an identity with no access to the managed server, or expired.
 */
export type PlexClaim = "claimed" | "pending" | "no-access" | "expired";

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
      plexClaim: "claimed",
      passwordAccepted: true,
      inventedRequests: false,
      testRoster: false,
      moved: {},
      preferences: structuredClone(ACCOUNTS.preferences) as Record<string, Record<string, Preference>>,
      roleRights: {},
      roleNames: {},
      createdRoles: [],
      deletedRoles: [],
      createdAccounts: [],
      assigned: {},
      accessCut: [],
      sessionsEnded: [],
    };
    dialled.set(held, found);
  }
  return found;
}

/** Every role the layer holds. */
export function roles(): Role[] {
  const { roleRights, roleNames, createdRoles, deletedRoles, testRoster } = dials();
  const seeded = ACCOUNTS.roles as Role[];
  const tested = testRoster ? (ACCOUNTS.testRoles as Role[]) : [];
  return [...seeded, ...tested, ...createdRoles].filter((role) => !deletedRoles.includes(role.id)).map((role) => {
    const name = roleNames[role.id] ?? role.name;
    // A role never renamed keeps no name at all: the key stays absent.
    return { ...role, ...(name === undefined ? {} : { name }), rights: [...(roleRights[role.id] ?? role.rights)] };
  });
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
  signInKind: Schemas["SignInKind"];
  /** The role it held before its link dropped it to its Plex kind's starting role, by id. */
  demotedFrom?: string;
};

/** Every account: the owner first, then the invented ones. */
export function heldAccounts(): HeldAccount[] {
  const { assigned, createdAccounts, testRoster } = dials();
  return [
    { id: ACCOUNT.id, name: accountName(), email: ACCOUNT.email, role: ACCOUNT.role,
      signInKind: ACCOUNT.signInKind as Schemas["SignInKind"] },
    ...(ACCOUNTS.accounts as HeldAccount[]),
    ...(testRoster ? (ACCOUNTS.testAccounts as HeldAccount[]) : []),
    ...createdAccounts,
  ].map((one) => {
    // A ROLE GIVEN AGAIN ENDS THE DEMOTION a link made: the fact is gone.
    if (assigned[one.id] === undefined) return one;
    const { demotedFrom: _ended, ...promoted } = one;
    return { ...promoted, role: assigned[one.id] };
  });
}

/** What « Comptes » writes, over the layer's own state (demands G, H). */
export const roster = {
  addRole: (role: Role) => { dials().createdRoles.push(role); },
  removeRole: (id: string) => { dials().deletedRoles.push(id); },
  renameRole: (id: string, name: string) => { dials().roleNames[id] = name; },
  setRoleRights: (id: string, rights: Right[]) => { dials().roleRights[id] = [...rights]; },
  addAccount: (account: HeldAccount) => { dials().createdAccounts.push(account); },
  assign: (id: string, role: string) => { dials().assigned[id] = role; },
  /**
   * Cuts one account's access or gives it back (the operator, 2026-10-04). A
   * CUT ENDS EVERY SESSION OF THE ACCOUNT AT ONCE (Q4 = A); giving it back opens
   * none — only a sign-in does.
   */
  setAccess: (id: string, allowed: boolean) => {
    const state = dials();
    state.accessCut = state.accessCut.filter((one) => one !== id);
    if (allowed) return;
    state.accessCut.push(id);
    if (!state.sessionsEnded.includes(id)) state.sessionsEnded.push(id);
  },
};

/**
 * Whether one account may sign in.
 *
 * @param id The account.
 * @returns False once an Admin cut it, until the switch is back on.
 */
export function signInAllowed(id: string): boolean {
  return !dials().accessCut.includes(id);
}

/**
 * Whether the session in force is one a cut ended — the maquette holds ONE
 * session, the identity dialled, so its next request answers 401.
 *
 * @returns True while the account dialled has not signed in again since its cut.
 */
export function sessionEnded(): boolean {
  const state = dials();
  return state.sessionsEnded.includes(signedInId());
}

/**
 * Opens a session for one account whose credentials were proven — refused
 * while its access is cut.
 *
 * @param id The account.
 * @returns True once signed in; false when its access is cut.
 */
export function openSession(id: string): boolean {
  if (!signInAllowed(id)) return false;
  const state = dials();
  state.sessionsEnded = state.sessionsEnded.filter((one) => one !== id);
  state.identity = id;
  return true;
}

// THE REAL ACCOUNT, ON THE DESIGN HOST (the operator, 2026-10-04; Q5 = A).
// There a sign-in reaches the real server (`passthrough.ts`), and the account
// it answers is who the operations still mocked are asked by: the rights guard
// judges it, `readAccount`'s shape is its own. A fact of the real session, not
// a dial — so the layer's reset leaves it, and only a sign-out or a 401 ends it.
let adopted: Schemas["Account"] | null = null;

/**
 * Makes the mocks answer as the real signed-in account, or as the seed again.
 *
 * @param account The account the real server answered; null to release it.
 */
export function adoptAccount(account: Schemas["Account"] | null): void {
  adopted = account;
}

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
  if (adopted !== null) return adopted;
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
    signInKind: held.signInKind,
    forbiddenWrites: [...dials().forbiddenWrites],
  };
}

/** What the signed-in account may do — the model's own derivation. */
export function signedInRights(): Rights {
  return rightsOf(signedIn());
}

/** The id of the account signed in. */
export function signedInId(): string {
  return adopted?.id ?? dials().identity;
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
    .map((id): Schemas["AccountRef"] | undefined => {
      const one = heldAccounts().find((held) => held.id === id) ?? (adopted?.id === id ? adopted : undefined);
      return one === undefined ? undefined : { id: one.id, name: one.name };
    })
    .filter((one): one is Schemas["AccountRef"] => one !== undefined);
  if (state.moved[title]) return named(state.moved[title]);
  if (!state.inventedRequests && signedInId() === ACCOUNT.id) return named([ACCOUNT.id]);
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
  if (!ids.includes(signedInId())) ids.push(signedInId());
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
  dials().moved[title] = requestersOf(title).map((one) => one.id).filter((id) => id !== signedInId());
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

/** What Plex answers once a PIN is asked about. */
export function plexClaim(): PlexClaim {
  return dials().plexClaim;
}

/** Whether the current password given to `changeOwnPassword` matches. */
export function passwordAccepted(): boolean {
  return dials().passwordAccepted;
}

/** The dials a named state turns to sign someone else in. */
export type IdentityDials = {
  /** Signs in one account of the roster, by id, until the layer is next reset. */
  setIdentity: (id: string) => void;
  /** Sets the instance's forbidden writes (ruling 23) — a named list, never a boolean. */
  setForbiddenWrites: (rights: Right[]) => void;
  /** Whether the Plex server answers a sign-in. */
  setPlexReachable: (reachable: boolean) => void;
  /** What Plex answers once a PIN is asked about. */
  setPlexClaim: (claim: PlexClaim) => void;
  /** Whether the current password given to `changeOwnPassword` matches. */
  setPasswordAccepted: (accepted: boolean) => void;
  /** Whether the invented accounts' requests join the owner's on the lists. */
  setInventedRequests: (on: boolean) => void;
  /**
   * Whether the test roles and their accounts join the five seeded roles — roles
   * a manager might have created, which a harness state needs as its subject and
   * a tester's default world never shows (O-K1-4).
   */
  setTestRoster: (on: boolean) => void;
  /** Sets one role's rights, as « Comptes » would, until the layer is next reset. */
  setRoleRights: (roleId: string, rights: Right[]) => void;
  /** Gives one account a role, as « Comptes » would — a second Admin, for a state that needs one. */
  setAccountRole: (id: string, roleId: string) => void;
  /** Cuts one account's access or gives it back, as « Comptes »' switch would. */
  setAccountAccess: (id: string, allowed: boolean) => void;
  /** Adds one ordinary role, as « Comptes »' creation page would — a role no account holds yet. */
  addRole: (role: Role) => void;
};

/** Those dials, over the layer's own state. */
export const identityDials: IdentityDials = {
  setIdentity: (id) => {
    if (adopted !== null) throw new Error("identity follows the signed-in account");
    // A TEST ACCOUNT BRINGS THE TEST ROSTER WITH IT: a state that signs one in
    // is a state that needs it, and a tester's default world never does.
    if ((ACCOUNTS.testAccounts as HeldAccount[]).some((one) => one.id === id)) dials().testRoster = true;
    if (!heldAccounts().some((one) => one.id === id)) throw new Error(`no account is seeded under ${id}`);
    dials().identity = id;
  },
  setForbiddenWrites: (rights) => { dials().forbiddenWrites = [...rights]; },
  setPlexReachable: (reachable) => { dials().plexReachable = reachable; },
  setPlexClaim: (claim) => { dials().plexClaim = claim; },
  setPasswordAccepted: (accepted) => { dials().passwordAccepted = accepted; },
  // THE INVENTED REQUESTS ARE THE TEST ACCOUNTS' too: they come with them.
  setInventedRequests: (on) => {
    dials().inventedRequests = on;
    if (on) dials().testRoster = true;
  },
  setTestRoster: (on) => { dials().testRoster = on; },
  setRoleRights: (roleId, rights) => {
    if ((ACCOUNTS.testRoles as Role[]).some((one) => one.id === roleId)) dials().testRoster = true;
    roleFor(roleId);
    roster.setRoleRights(roleId, rights);
  },
  setAccountRole: (id, roleId) => {
    roleFor(roleId);
    roster.assign(id, roleId);
  },
  setAccountAccess: (id, allowed) => roster.setAccess(id, allowed),
  addRole: (role) => roster.addRole(role),
};
