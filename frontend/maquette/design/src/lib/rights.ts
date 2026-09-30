// WHAT THIS ACCOUNT MAY DO — one derivation from the answer, and every surface
// reads it (§ 17; DESIGN maquette-l18 § 1.2). In `lib/`, not in the account
// feature, because every feature reads it and invariant 7 forbids a feature
// importing another.
//
// ITS INPUT IS WHAT THE SERVER ANSWERED: the role the account holds, the rights
// that role carries, and the instance's forbidden writes (ruling 23). Its output
// is a closed set of named rights. NO SURFACE COMPARES A ROLE'S NAME — the name is
// for display, and a role renamed in « Comptes » must move nothing but the words.
//
// ADMIN BYPASSES THE LIST (ruling 22: « il contourne les ACL »): the function
// never enumerates its rights, it short-circuits, so a right declared after the
// account signed in is held too. The forbidden writes subtract BEFORE the role
// adds, for every role, Admin's included — which is how the read-only instance
// stays read-only for its owner.
//
// PURE, AND IMPORTED BY THE MOCK'S GUARD TOO: the offer side (a surface draws
// the act) and the refusal side (the call answers 403) read ONE derivation, so
// they cannot disagree about who may do what.
import type { Schemas } from "./contract-schemas";

/** One right of the ACL, in the contract's own names. */
export type Right = Schemas["Right"];

/** Every right of the ACL, in the order Profil and « Comptes » list them. */
export const RIGHTS: readonly Right[] = [
  "library.read", "library.delete", "library.rescrape",
  "acquisition.request", "acquisition.follow", "acquisition.pilot.own", "acquisition.pilot.any",
  "acquisition.see.others", "acquisition.quality.own", "acquisition.pause.own", "acquisition.reassign",
  "pipeline.control", "trackers.view", "trackers.control", "system.view",
  "configuration.view", "configuration.write", "accounts.manage", "auth.password",
];

/**
 * Every WRITE right of the ACL — what a forbidden-writes list may name (ruling
 * 23). The view rights and the password door are never forbidden writes.
 */
export const WRITE_RIGHTS: readonly Right[] = [
  "library.delete", "library.rescrape", "acquisition.request", "acquisition.follow",
  "acquisition.pilot.own", "acquisition.pilot.any", "acquisition.quality.own", "acquisition.pause.own",
  "acquisition.reassign", "pipeline.control", "trackers.control", "configuration.write", "accounts.manage",
];

/** The account as `readAccount` answers it. */
type Account = Schemas["Account"];

/**
 * What one account may do.
 *
 * `known` is false until the account has been read: nothing is held then, so
 * a surface drawn before the answer offers nothing it might have to withdraw.
 */
export type Rights = {
  /** Whether the account has been read at all. */
  readonly known: boolean;
  /** The account's key — what a requester list names it by. */
  readonly id: string;
  /** The role's name, for display — never compared. */
  readonly roleName: string;
  /** The instance's forbidden writes, for the ceiling's own sentence. */
  readonly forbidden: readonly Right[];
  /**
   * Whether the account holds a right.
   *
   * @param right The right asked about.
   * @returns True when its role carries it (or it is Admin) and the instance
   *     does not forbid it.
   */
  holds: (right: Right) => boolean;
  /**
   * Whether the account holds at least one of several rights.
   *
   * @param rights The rights asked about.
   * @returns True when any one is held.
   */
  holdsAny: (rights: readonly Right[]) => boolean;
};

/** The rights of an account nobody has read yet: none. */
export const NO_RIGHTS: Rights = {
  known: false,
  id: "",
  roleName: "",
  forbidden: [],
  holds: () => false,
  holdsAny: () => false,
};

/**
 * Derives what an account may do from what the server answered.
 *
 * @param account The answer of `readAccount`, or undefined before it lands.
 * @returns The account's rights.
 */
export function rightsOf(account: Account | undefined): Rights {
  if (account === undefined) return NO_RIGHTS;
  const forbidden = account.forbiddenWrites;
  // THE ROLE'S KIND IS THE ONE THING READ OFF THE ROLE, and only here: it is
  // the contract's closed marker of the system role that bypasses the list, not
  // a name a manager can type.
  const bypass = account.role.kind === "admin";
  const carried = new Set<Right>(account.role.rights);
  const holds = (right: Right): boolean =>
    !forbidden.includes(right) && (bypass || carried.has(right));
  return {
    known: true,
    id: account.id,
    roleName: account.role.name,
    forbidden,
    holds,
    holdsAny: (rights) => rights.some(holds),
  };
}

/** What an acquisition says of who asked for it. */
type Requested = { requesters?: readonly { id: string }[] };

/**
 * Whether an acquisition is the account's own to act on (§ 17: « own tunnel »).
 *
 * MEMBERSHIP, NOT SINGLE OWNERSHIP (F27): the account is AMONG its requesters —
 * or holds `acquisition.pilot.any`, which makes every card its own.
 *
 * @param acquisition A follow or a queue card.
 * @param rights What the account may do.
 * @returns True when the account may act on it.
 */
export function isOwn(acquisition: Requested, rights: Rights): boolean {
  if (rights.holds("acquisition.pilot.any")) return true;
  return (acquisition.requesters ?? []).some((one) => one.id === rights.id);
}
