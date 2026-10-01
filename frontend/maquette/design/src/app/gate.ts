// THE GATE'S TWO WAYS IN — Plex first, the password behind a disclosure (§ 17;
// round 8 Q10 = B; F47).
//
// OUTSIDE THE HOST'S EXTRACTION, by construction: the design host builds its
// own password page from `index.html`'s `login:markup` region and the
// stylesheet's `login:*` regions, byte for byte (R72's bridge). Nothing here is
// in either: the Plex block is built into the prototype's gate at run time,
// from `fr.json`, and styled by the utilities, so the host's page is unchanged.
//
// THE PASSWORD IS A RIGHT (`auth.password`), not a way in every account has: a
// password given for an account that does not hold it is refused with its
// reason — « ce compte se connecte avec Plex ». When Plex does not answer, the
// disclosure opens by itself: the password is the door of last resort.
//
// THE GATE READS NO RIGHT ITSELF: after a sign-in the frame reads the account,
// and the account's entry page is where it lands (round 10 Q7).
import i18next from "i18next";

import { entryPageFor } from "./navigation";
import { rightsOf } from "../lib/rights";
import { sharedQueryClient } from "../lib/query-client";
import { landSignedIn } from "./frame-verbs";
import type { Schemas } from "../lib/contract-schemas";
import { actionButton, crossReferenceLink } from "../ui/variants";

// The statuses the two doors answer with.
const REFUSED = 403;
const UNREACHABLE = 503;

/** What the gate needs from the entry: how a sign-in ends. */
type Ending = () => void;

let ending: Ending = () => {};

/** An element of the gate, by its selector. */
function node<Element extends HTMLElement>(selector: string): Element | null {
  return document.querySelector<Element>(selector);
}

/**
 * The Plex block, built once into the gate, before the password form.
 *
 * @returns The block.
 */
function plexBlock(): HTMLElement | null {
  const existing = node<HTMLElement>('[data-part="login/plex"]');
  if (existing) return existing;
  const gate = node("#login");
  const form = node("#loginform");
  if (!gate || !form) return null;
  const say = (key: string) => i18next.t(`screens.gate.${key}`);
  const block = document.createElement("div");
  block.className = "logincard";
  block.dataset.part = "login/plex";
  const plex = document.createElement("button");
  plex.type = "button";
  plex.className = "loginsubmit";
  plex.dataset.part = "login/plex-submit";
  plex.textContent = say("plex");
  const unreachable = document.createElement("p");
  unreachable.className = "loginerr";
  unreachable.dataset.part = "login/plex-unreachable";
  unreachable.textContent = say("plexUnreachable");
  unreachable.hidden = true;
  const disclosure = document.createElement("button");
  disclosure.type = "button";
  disclosure.className = `${actionButton({ kind: "cardFoot" })} ${crossReferenceLink()}`;
  disclosure.dataset.part = "login/password-disclosure";
  disclosure.textContent = say("usePassword");
  disclosure.setAttribute("aria-controls", "loginform");
  block.append(plex, unreachable, disclosure);
  gate.insertBefore(block, form);
  plex.addEventListener("click", () => void signInWithPlex());
  disclosure.addEventListener("click", () => setPasswordOpen(form.hidden !== false));
  return block;
}

/**
 * Opens or closes the password form behind its disclosure.
 *
 * @param open True to show the form.
 */
export function setPasswordOpen(open: boolean): void {
  const form = node("#loginform");
  const disclosure = node('[data-part="login/password-disclosure"]');
  if (form) form.hidden = !open;
  disclosure?.setAttribute("aria-expanded", String(open));
}

/**
 * Puts the gate in its resting shape: Plex offered, the password closed —
 * or open, when the gate is shown for a refusal the form carries.
 *
 * @param passwordOpen Whether the form is to be shown.
 */
export function restGate(passwordOpen: boolean): void {
  if (!plexBlock()) return;
  const unreachable = node('[data-part="login/plex-unreachable"]');
  if (unreachable) unreachable.hidden = true;
  const refusal = node("#loginerr");
  if (refusal) refusal.textContent = i18next.t("screens.gate.invalid");
  setPasswordOpen(passwordOpen);
}

/**
 * Lands the signed-in account on its entry page once its rights are read.
 */
async function land(): Promise<void> {
  const client = sharedQueryClient;
  if (client === undefined) return ending();
  await client.resetQueries();
  const account = await client.fetchQuery({
    queryKey: ["/api/auth/me"],
    queryFn: async () => (await fetch("/api/auth/me")).json() as Promise<Schemas["Account"]>,
  });
  landSignedIn(entryPageFor(rightsOf(account)));
  ending();
}

/** Asks Plex to sign in; opens the password when Plex does not answer. */
async function signInWithPlex(): Promise<void> {
  const answer = await fetch("/api/auth/plex", { method: "POST" }).catch(() => null);
  if (answer?.ok) return land();
  if (answer === null || answer.status === UNREACHABLE) {
    const unreachable = node('[data-part="login/plex-unreachable"]');
    if (unreachable) unreachable.hidden = false;
    setPasswordOpen(true);
  }
}

/**
 * Signs in with a password, as the account that holds `auth.password` may.
 *
 * @param username The identifier typed.
 * @param password The password typed.
 */
async function signInWithPassword(username: string, password: string): Promise<void> {
  const refusal = node("#loginerr");
  const answer = await fetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  }).catch(() => null);
  if (answer?.ok) return land();
  if (refusal) {
    refusal.textContent = i18next.t(answer?.status === REFUSED ? "screens.gate.passwordRefused" : "screens.gate.invalid");
    refusal.hidden = false;
  }
}

/**
 * Installs the gate's two doors.
 *
 * @param end What follows a sign-in: the gate lifted and the wait covered.
 */
export function installGate(end: Ending): void {
  ending = end;
  document.querySelector("#loginform")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const fields = new FormData(event.currentTarget as HTMLFormElement);
    const username = String(fields.get("username") ?? "").trim();
    const password = String(fields.get("password") ?? "");
    // An empty field shows the refusal state and asks nobody.
    if (!username || !password) {
      const refusal = node("#loginerr");
      if (refusal) refusal.hidden = false;
      return;
    }
    void signInWithPassword(username, password);
  });
}
