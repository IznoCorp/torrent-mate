// A role's label: the Admin's text when he renamed it, else the translation of
// its id — a seeded role never renamed has no name in the contract.
import { describe, expect, it } from "vitest";
import "../i18n";
import ACCOUNTS from "../mocks/seeds/accounts.json";
import fr from "../i18n/fr.json";
import { roleLabel } from "./account";
import type { Schemas } from "./contract-schemas";

const SEEDED = ["admin", "household", "plex-guest", "requester", "local-guest"] as const;

function role(id: string, name?: string): Schemas["Role"] {
  return { id, kind: id === "admin" ? "admin" : "ordinary", rights: [], ...(name === undefined ? {} : { name }) };
}

describe("a role's label", () => {
  it.each(SEEDED)("shows the translation of the seeded id %s when it has no name", (id) => {
    expect(roleLabel(role(id))).toBe(fr.roles.seed[id]);
  });

  it("shows the text an Admin gave a seeded role", () => {
    expect(roleLabel(role("household", "Famille"))).toBe("Famille"); // french-ok: a renamed role's text, as typed
  });

  it("shows the id itself for an unknown role that has no name", () => {
    expect(roleLabel(role("auditor"))).toBe("auditor");
  });
});

describe("the mock seed", () => {
  it("carries no name on a seeded role, so the translation speaks", () => {
    expect(ACCOUNTS.roles.map((one) => [one.id, "name" in one])).toEqual(SEEDED.map((id) => [id, false]));
  });
});
