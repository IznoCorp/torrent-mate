// The model, read on every seeded role: the rights a role carries, Admin's
// bypass, and the instance's forbidden writes subtracted from every role.
import { describe, expect, it } from "vitest";
import ACCOUNTS from "../mocks/seeds/accounts.json";
import contract from "../../../contract/openapi.json";
import { NO_RIGHTS, rightsOf, type Right } from "./rights";
import type { Schemas } from "./contract-schemas";

const EVERY = (contract as unknown as { components: { schemas: { Right: { enum: Right[] } } } })
  .components.schemas.Right.enum;

function accountOn(roleId: string, forbiddenWrites: Right[] = []): Schemas["Account"] {
  const role = ACCOUNTS.roles.find((one) => one.id === roleId) as Schemas["Role"];
  return { id: "a", name: "a", email: "a@example.invalid", avatar: "", role, plexLinked: true, forbiddenWrites };
}

describe("the rights of an account are its role's", () => {
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

  it("seeds the Default role to the library alone", () => {
    expect(ACCOUNTS.roles.find((role) => role.kind === "default")?.rights).toEqual(["library.read"]);
  });

  it("subtracts the instance's forbidden writes, Admin's included", () => {
    const preprod = rightsOf(accountOn("admin", ["library.delete"]));
    expect(preprod.holds("library.delete")).toBe(false);
    expect(preprod.holds("library.rescrape")).toBe(true);
    expect(rightsOf(accountOn("household", ["acquisition.request"])).holds("acquisition.request")).toBe(false);
  });

  it("reads the role's name for display and nothing else", () => {
    expect(rightsOf(accountOn("guest")).roleName).toBe("Invité Plex"); // french-ok: a seeded role's name, asserted as served
  });
});
