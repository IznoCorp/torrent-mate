// What « Comptes »' creation pages and a role's panel judge before anything is
// asked (the operator, 2026-10-04; ruling A): a name another role carries, an
// e-mail that does not read as one, and the role Delete is offered on.
//
// WHAT MAKES THIS NON-VACUOUS. Each judgement is read on the seeded roster's own
// roles and accounts: Delete is refused on a role an account holds, on a role a
// newcomer starts on even held by nobody, on Admin's, and on a role beyond a
// manager's reach — and offered on the one role left.
import { describe, expect, it } from "vitest";
import ACCOUNTS from "../../mocks/seeds/accounts.json";
import ACCOUNT from "../../mocks/seeds/account.json";
import type { Schemas } from "../../lib/contract-schemas";
import { deletable } from "./roster-panels";
import { nameTaken } from "./role-create-screen";
import { readsAsEmail } from "./account-create-screen";
import FRENCH from "../../i18n/fr.json";

type Role = Schemas["Role"];
type Roster = Schemas["Roster"];

const ROLES = ACCOUNTS.roles as Role[];
const role = (id: string): Role => ROLES.find((one) => one.id === id)!;
const UNUSED: Role = { id: "friends", name: "Amis", kind: "ordinary", rights: ["library.read"] };

/** The roster with every seeded account on its role, the owner on Admin's. */
function roster(roles: Role[] = [...ROLES, UNUSED], holders: [string, string][] = []): Roster {
  const held: [string, string][] = holders.length ? holders
    : [[ACCOUNT.id, "admin"], ...ACCOUNTS.accounts.map((one): [string, string] => [one.id, one.role])];
  return {
    roles,
    accounts: held.map(([id, on]) => ({
      id, name: id, email: `${id}@example.invalid`, role: roles.find((one) => one.id === on)!,
      signInKind: "local", signInAllowed: true,
    })),
  } as Roster;
}

const ADMIN = { id: ACCOUNT.id, role: role("admin"), forbiddenWrites: [] } as unknown as Schemas["Account"];

describe("deletable", () => {
  it("offers Delete on a role nobody holds and nobody starts on", () => {
    expect(deletable(UNUSED, roster(), ADMIN)).toBe(true);
  });

  it("never on a role an account holds", () => {
    expect(deletable(role("requester"), roster(), ADMIN)).toBe(false);
  });

  it("never on a role a newcomer starts on, even held by nobody (ruling A)", () => {
    const nobodyOnLocal = roster(undefined, [[ACCOUNT.id, "admin"]]);
    expect(deletable(role("local-guest"), nobodyOnLocal, ADMIN)).toBe(false);
  });

  it("never on the Admin role", () => {
    expect(deletable(role("admin"), roster(undefined, [[ACCOUNT.id, "household"]]), ADMIN)).toBe(false);
  });

  it("never on a role beyond a manager's own rights (round 9 Q14 = A)", () => {
    const manager = { id: "see-only", forbiddenWrites: [],
      role: { id: "spectator", kind: "ordinary", rights: ["accounts.manage"] } } as unknown as Schemas["Account"];
    expect(deletable(UNUSED, roster(), manager)).toBe(false);
  });
});

describe("nameTaken", () => {
  it("finds a name another role carries, regardless of case and spaces", () => {
    expect(nameTaken("  amis ", [UNUSED])).toBe(true);
    expect(nameTaken("Crew", [UNUSED])).toBe(false);
  });

  it("judges the name a role carries, never a seeded role's translated words — the server cannot know them", () => {
    const household = role("household");
    expect(household.name ?? null).toBeNull();
    expect(nameTaken(FRENCH.roles.seed.household, ROLES)).toBe(false);
    expect(nameTaken(household.id, ROLES)).toBe(false);
  });

  it("finds an existing name typed in another case between spaces, as the contract's rule", () => {
    expect(nameTaken("\t AMIS  ", [...ROLES, UNUSED])).toBe(true);
  });

  it("never calls an empty name taken — that is the required field's to say", () => {
    expect(nameTaken("  ", [UNUSED])).toBe(false);
  });
});

describe("readsAsEmail", () => {
  it("reads something, an at sign and something, without a space", () => {
    expect(readsAsEmail("nina@example.invalid")).toBe(true);
    for (const typed of ["nina", "nina@", "@example.invalid", "ni na@example.invalid"]) expect(readsAsEmail(typed)).toBe(false);
  });
});
