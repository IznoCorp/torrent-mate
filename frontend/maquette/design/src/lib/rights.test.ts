// The model, read on every seeded role: the rights a role carries, Admin's
// bypass, and the instance's forbidden writes subtracted from every role.
import { describe, expect, it } from "vitest";
import ACCOUNTS from "../mocks/seeds/accounts.json";
import contract from "../../../../../contract/openapi.json";
import { NO_RIGHTS, RIGHTS, rightsOf, type Right } from "./rights";
import type { Schemas } from "./contract-schemas";

const EVERY = (contract as unknown as { components: { schemas: { Right: { enum: Right[] } } } })
  .components.schemas.Right.enum;

function accountOn(roleId: string, forbiddenWrites: Right[] = []): Schemas["Account"] {
  const role = ACCOUNTS.roles.find((one) => one.id === roleId) as Schemas["Role"];
  return { id: "a", name: "a", email: "a@example.invalid", avatar: "", role, signInKind: "plex", forbiddenWrites };
}

describe("the rights of an account are its role's", () => {
  it("lists every right the contract declares, and no other", () => {
    expect([...RIGHTS].sort()).toEqual([...EVERY].sort());
  });

  it("holds nothing before the account is read", () => {
    expect(EVERY.filter((right) => NO_RIGHTS.holds(right))).toEqual([]);
  });

  it("lets Admin through every right, without a list", () => {
    expect(accountOn("admin").role.rights).toEqual([]);
    expect(EVERY.filter((right) => !rightsOf(accountOn("admin")).holds(right))).toEqual([]);
  });

  it.each(ACCOUNTS.roles.filter((role) => role.kind !== "admin").map((role) => [role.id, role.rights]))(
    "holds exactly what %s carries",
    (roleId, carried) => {
      const held = EVERY.filter((right) => rightsOf(accountOn(roleId as string)).holds(right));
      expect(held.sort()).toEqual([...(carried as Right[])].sort());
    },
  );

  it("seeds the five roles the operator ruled, and where each newcomer starts (O-K1-4)", () => {
    const seeded = ACCOUNTS.roles.map((role) => [role.id, role.kind, (role as { defaultFor?: string[] }).defaultFor ?? []]);
    expect(seeded).toEqual([
      ["admin", "admin", []],
      ["household", "ordinary", ["plexHome"]],
      ["plex-guest", "ordinary", ["plexGuest"]],
      ["requester", "ordinary", []],
      ["local-guest", "ordinary", ["local"]],
    ]);
    const rightsOfRole = (id: string) => ACCOUNTS.roles.find((role) => role.id === id)!.rights;
    // Demandeur carries Membre du foyer's rights, Invité Invité Plex's: the library alone.
    expect(rightsOfRole("requester")).toEqual(rightsOfRole("household"));
    expect(rightsOfRole("plex-guest")).toEqual(["library.read"]);
    expect(rightsOfRole("local-guest")).toEqual(["library.read"]);
    expect(rightsOfRole("household")).not.toContain("acquisition.quality.own");
  });

  it("subtracts the instance's forbidden writes, Admin's included", () => {
    const preprod = rightsOf(accountOn("admin", ["library.delete"]));
    expect(preprod.holds("library.delete")).toBe(false);
    expect(preprod.holds("library.rescrape")).toBe(true);
    expect(rightsOf(accountOn("household", ["acquisition.request"])).holds("acquisition.request")).toBe(false);
  });
});
