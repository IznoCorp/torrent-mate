// The named states of « Comptes »' two creation pages and of a role's deletion (the
// operator, 2026-10-04: « une nouvelle page avec un formulaire de création avec
// validation », « possibilité de supprimer un rôle mais seulement s'il est attribué
// à aucun compte »; ruling A).
//
// Each page is drawn EMPTY, INVALID and VALID; the account's page also REFUSED at a
// field by the server. A role's panel is drawn with Delete — on a role nobody holds —
// and without it — on a role a newcomer starts on, held by nobody — and the
// confirmation Delete asks first.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes, the label
// says the state in words, and `run` builds the state.
import i18next from "i18next";

import { applyState, onLeave, type NamedState } from "../drive";
import { forgetOwed, owed } from "../owed";
import { as } from "./rights";

// How long a page waits for its roster before a field is typed into.
const TYPE_AFTER = 400;
// How long after the typing the act is pressed — React has drawn what was typed.
const PRESS_AFTER = 150;

// A role nobody holds and nobody starts on, created as « Comptes » would.
export const UNUSED_ROLE = { id: "friends", name: "Amis", kind: "ordinary" as const, rights: ["library.read" as const] };

// A provisional password long enough for the layer's minimum.
export const LONG_PASSWORD = "correct horse battery";

/**
 * Types into one field of the open creation page as a finger would: through the
 * native setter, so the controlled field hears the event as typing.
 *
 * @param name The field's `name`.
 * @param value What is typed — an empty string empties it, and the field is touched.
 */
function typeInto(name: string, value: string): void {
  const field = document.querySelector<HTMLInputElement | HTMLSelectElement>(
    `[data-part="screen"][data-open] [data-part="creation/form"] [name="${name}"]`);
  if (field === null) return;
  const prototype = field instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value);
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
}

/**
 * Opens one creation page over « Comptes » and fills it, field by field in
 * order, then presses Create if asked.
 *
 * @param page Which page: a role's or an account's.
 * @param fields The fields typed, in order — a field typed twice is touched, then emptied.
 * @param extra What else is done on the page once typed, before the act.
 * @param press Whether Create is pressed.
 */
export function fillCreation(
  page: "role" | "account",
  fields: [string, string][],
  extra?: () => void,
  press = false,
): void {
  applyState({ page: "accounts", phase: "ready" });
  if (page === "role") window.__screens.newRole();
  else window.__screens.newAccount();
  if (!fields.length && !extra && !press) return;
  // BOTH DEFERRED ACTS ARE STOPPED WHEN THE NEXT STATE IS DRIVEN: a field typed or a Create pressed
  // after it lands on the next state's own page — a form it never asked to fill, a submit it never
  // asked to press (`cards.py` R44, driven right after; the pattern is `tunnel.ts`'s). The press is
  // armed by the typing, so it is not known yet: it is forgotten through the variable it will fill.
  let pressing: number | undefined;
  const typing = owed(() => {
    for (const [name, value] of fields) typeInto(name, value);
    extra?.();
    if (press)
      pressing = owed(() => {
        document.querySelector<HTMLElement>('[data-part="screen"][data-open] [data-part="creation/submit"]')?.click();
      }, PRESS_AFTER);
  }, TYPE_AFTER);
  onLeave(() => {
    forgetOwed(typing);
    if (pressing !== undefined) forgetOwed(pressing);
  });
}

/** Turns one right of the role's page on, as a finger would. */
function chooseRight(right: string): void {
  document.querySelector<HTMLElement>(`[data-role-create-right="${right}"]`)?.click();
}

/**
 * Adds a role nobody holds, then opens « Comptes » on a role's panel.
 *
 * @param role The role whose panel is opened.
 */
function rolePanel(role: string): void {
  window.__mocks?.addRole(UNUSED_ROLE);
  void window.__queries?.resetQueries();
  applyState({ page: "accounts", phase: "ready" });
  window.__panel.produce("role", role);
}

export function creationStates(): NamedState[] {
  return [
    [
      "accounts-role-create",
      "Comptes — nouveau rôle : sa page, le nom vide et obligatoire, aucun droit choisi, Créer fermé",
      () => fillCreation("role", []),
    ],
    [
      "accounts-role-create-invalid",
      "Comptes — nouveau rôle : le nom vidé, dit sous le champ, Créer fermé",
      () => fillCreation("role", [["name", "A"], ["name", ""]]),
    ],
    [
      "accounts-role-create-taken",
      "Comptes — nouveau rôle : un nom qu'un autre rôle porte déjà, dit sous le champ, Créer fermé",
      () => fillCreation("role", [["name", i18next.t("roles.seed.household")]]),
    ],
    [
      "accounts-role-create-valid",
      "Comptes — nouveau rôle : un nom et un droit choisis, Créer ouvert",
      () => fillCreation("role", [["name", UNUSED_ROLE.name]], () => chooseRight("library.read")),
    ],
    [
      "accounts-account-create",
      "Comptes — nouveau compte : sa page, chaque champ vide, les obligatoires marqués, Créer fermé",
      () => fillCreation("account", []),
    ],
    [
      "accounts-account-create-invalid",
      "Comptes — nouveau compte : une adresse e-mail invalide, dite sous le champ, Créer fermé",
      () => fillCreation("account", [["name", "Nina"], ["email", "nina"]]),
    ],
    [
      "accounts-account-create-valid",
      "Comptes — nouveau compte : nom, adresse, rôle et mot de passe provisoire saisis, Créer ouvert",
      () => fillCreation("account", [
        ["name", "Nina"], ["email", "nina@example.invalid"], ["role", "local-guest"], ["password", LONG_PASSWORD]]),
    ],
    [
      "accounts-create-refused",
      "Comptes — nouveau compte sans adresse e-mail : dit sous le champ, rien n'est demandé",
      () => fillCreation("account", [["name", "Maya"], ["email", "x"], ["email", ""]]),
    ],
    [
      "accounts-role-unused",
      "Comptes — un rôle qu'aucun compte ne tient et où aucun nouveau compte ne démarre : Supprimer offert",
      () => rolePanel(UNUSED_ROLE.id),
    ],
    [
      "accounts-role-default-unheld",
      "Comptes — le rôle de départ des comptes locaux, tenu par personne : Supprimer absent",
      () => {
        window.__mocks?.setAccountRole("local-guest", "requester");
        rolePanel("local-guest");
      },
    ],
    [
      "accounts-role-delete-confirm",
      "Comptes — supprimer un rôle inutilisé : la confirmation, avant toute écriture",
      () => {
        rolePanel(UNUSED_ROLE.id);
        // STOPPED WHEN THE NEXT STATE IS DRIVEN: a press that fires after it opens
        // this role's confirmation over the next state, whose own taps then land on
        // the dialog instead of its page (`cards.py` R44, driven right after).
        const press = owed(() => document.querySelector<HTMLElement>("#sheet [data-role-delete]")?.click(), TYPE_AFTER);
        onLeave(() => forgetOwed(press));
      },
    ],
    [
      "accounts-account-create-manager",
      "Comptes — nouveau compte ouvert par un gestionnaire qui n'est pas Admin : les rôles au-delà de ses droits grisés",
      () => {
        window.__mocks?.setRoleRights("spectator", ["library.read", "acquisition.see.others", "accounts.manage", "acquisition.request"]);
        as("see-only");
        fillCreation("account", []);
      },
    ],
  ];
}
