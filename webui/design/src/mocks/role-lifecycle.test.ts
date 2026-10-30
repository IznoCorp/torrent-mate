// A role's creation and deletion, as the layer judges them (the operator,
// 2026-10-04: « Pas de nom par défaut, saisie avec champs obligatoires, et aussi
// possibilité de supprimer un rôle mais seulement s'il est attribué à aucun
// compte »; ruling A: a role a newcomer starts on is not deletable either).
//
// WHAT MAKES THIS NON-VACUOUS. Each leg asks the route the interface asks and
// reads the status and the code the layer answers: a nameless role and a name
// another role carries are refused at creation; a role an account holds, a role
// a newcomer starts on, the Admin role and an unknown one are refused at
// deletion; a role nobody holds and nobody starts on goes, and the roster no
// longer carries it.
import { beforeEach, describe, expect, it } from "vitest";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { identityDials } from "./identity";

type Answer = {
  status?: number;
  coded?: { code: string };
  ok?: boolean;
  id?: string;
  name?: string;
  roles?: { id: string }[];
};

/**
 * Asks one route the way the interface does.
 *
 * @param method The method.
 * @param path The address, under the contract's base.
 * @param body What is sent.
 * @returns What the layer answered: the result, or its refusal.
 */
function ask(method: string, path: string, body?: Record<string, unknown>): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route answers ${method} ${path}`);
  return found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(), body }) as Answer;
}

/** The ids of the roles the roster carries. */
function roleIds(): string[] {
  return (ask("GET", "/accounts").roles ?? []).map((one) => one.id);
}

describe("createRole", () => {
  beforeEach(() => resetMockState());

  it("creates a role under the name typed, with the rights chosen", () => {
    const created = ask("POST", "/roles", { name: "Amis", rights: ["library.read"] });
    expect(created.name).toBe("Amis");
    expect(roleIds()).toContain(created.id);
  });

  it("refuses a nameless role: no name is ever made up for it", () => {
    for (const name of ["", "   "]) {
      const answer = ask("POST", "/roles", { name, rights: [] });
      expect([answer.status, answer.coded?.code]).toEqual([400, "role.name_required"]);
    }
  });

  it("refuses a name another role already carries, whatever its case", () => {
    ask("POST", "/roles", { name: "Amis", rights: [] });
    const answer = ask("POST", "/roles", { name: " amis ", rights: [] });
    expect([answer.status, answer.coded?.code]).toEqual([409, "role.name_taken"]);
  });
});

describe("updateRole", () => {
  beforeEach(() => resetMockState());

  it("refuses a rename onto a name another role carries, whatever its case and spaces", () => {
    ask("POST", "/roles", { name: "Amis", rights: [] });
    const other = ask("POST", "/roles", { name: "Voisins", rights: [] });
    const answer = ask("PATCH", `/roles/${other.id}`, { name: "  AMIS " });
    expect([answer.status, answer.coded?.code]).toEqual([409, "role.name_taken"]);
    expect(ask("GET", "/accounts").roles?.find((one) => one.id === other.id)).toMatchObject({ name: "Voisins" });
  });

  it("lets a role keep its own name, in another case", () => {
    const created = ask("POST", "/roles", { name: "Amis", rights: [] });
    expect(ask("PATCH", `/roles/${created.id}`, { name: "AMIS" }).name).toBe("AMIS");
  });
});

describe("deleteRole", () => {
  beforeEach(() => resetMockState());

  it("deletes a role no account holds and no newcomer starts on", () => {
    const created = ask("POST", "/roles", { name: "Amis", rights: [] });
    const answer = ask("DELETE", `/roles/${created.id}`);
    expect(answer.ok).toBe(true);
    expect(roleIds()).not.toContain(created.id);
  });

  it("refuses a role an account holds", () => {
    const answer = ask("DELETE", "/roles/requester");
    expect([answer.status, answer.coded?.code]).toEqual([409, "role.in_use"]);
  });

  it("refuses a role a newcomer starts on, even when no account holds it (ruling A)", () => {
    identityDials.setAccountRole("plex-without-rights", "requester");
    const answer = ask("DELETE", "/roles/plex-guest");
    expect([answer.status, answer.coded?.code]).toEqual([409, "role.default"]);
    expect(roleIds()).toContain("plex-guest");
  });

  it("deletes « local-guest » once nobody holds it: no newcomer starts on it any more", () => {
    identityDials.setAccountRole("local-guest", "requester");
    expect(ask("DELETE", "/roles/local-guest").ok).toBe(true);
    expect(roleIds()).not.toContain("local-guest");
  });

  it("never deletes the Admin role", () => {
    const answer = ask("DELETE", "/roles/admin");
    expect([answer.status, answer.coded?.code]).toEqual([409, "role.system_immutable"]);
  });

  it("answers an unknown role 404", () => {
    const answer = ask("DELETE", "/roles/nobody");
    expect([answer.status, answer.coded?.code]).toEqual([404, "role.unknown"]);
  });

  it("refuses a manager who is not Admin a role beyond its own rights", () => {
    const created = ask("POST", "/roles", { name: "Large", rights: ["library.read", "library.delete"] });
    identityDials.setRoleRights("spectator", ["library.read", "acquisition.see.others", "accounts.manage"]);
    identityDials.setIdentity("see-only");
    const answer = ask("DELETE", `/roles/${created.id}`);
    expect([answer.status, answer.coded?.code]).toEqual([403, "role.escalation"]);
  });
});
