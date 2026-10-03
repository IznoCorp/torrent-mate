// THE GATE'S TWO WAYS IN — Plex first, the password behind a disclosure (§ 17;
// round 8 Q10 = B; F47).
//
// OUTSIDE THE HOST'S EXTRACTION, by construction: the design host builds its
// own password page from `index.html`'s `login:markup` region and the
// stylesheet's `login:*` regions, byte for byte (R72's bridge). Nothing here is
// in either: the Plex block is built into the prototype's gate at run time,
// from `fr.json`, and styled by the utilities, so the host's page is unchanged.
//
// EVERY LOGIN IS AN E-MAIL (the operator, 2026-10-03). A Plex identity with
// access to the managed server signs in by Plex only; the server's owner keeps
// a fallback password, and a local account has nothing but its password. When
// Plex does not answer, the disclosure opens by itself: the password is the
// door of last resort.
//
// NO REFUSAL TELLS WHICH E-MAILS THE SERVER KNOWS (O-K1-4): an unknown e-mail,
// a wrong password, a Plex-linked account's password, a Plex identity without
// access to the server — one refusal, one sentence. Which door is whose is
// said BEFORE anything is tried, as neutral guidance under the two doors.
//
// THE PLEX PIN RUNS ON THE SERVER (round 4 P-2 = B): `startPlexSignIn` answers
// a PIN and Plex's page, the gate opens the page and asks `signInWithPlex`
// once a second while the PIN is unclaimed (202), its wait drawn with a way
// back to the page and a way out.
//
// EVERY REFUSAL IS SAID FROM `fr.json` BY ITS CODE (gap G-1), never from the
// wire's English.
//
// THE GATE READS NO RIGHT ITSELF: after a sign-in the frame reads the account,
// and the account's entry page is where it lands (round 10 Q7).
import { CancelledError } from "@tanstack/react-query";
import i18next from "i18next";

import { entryPageFor } from "./navigation";
import { rightsOf } from "../lib/rights";
import { sharedQueryClient } from "../lib/query-client";
import { landSignedIn } from "./frame-verbs";
import type { Schemas } from "../lib/contract-schemas";
import { refusalWords } from "../lib/refusal";
import { actionButton, crossReferenceLink } from "../ui/variants";

// The statuses the two doors answer with.
const PENDING = 202;
const UNREACHABLE = 503;
// How often an unclaimed PIN is asked about: at most once a second (NE-DOIT-PAS-8).
const POLL_EVERY = 1000;

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
  const refusal = document.createElement("p");
  refusal.className = "loginerr";
  refusal.dataset.part = "login/plex-refusal";
  refusal.setAttribute("role", "status");
  refusal.hidden = true;
  block.append(plex, unreachable, refusal, pendingBlock(say));
  const disclosure = document.createElement("button");
  disclosure.type = "button";
  disclosure.className = `${actionButton({ kind: "cardFoot" })} ${crossReferenceLink()}`;
  disclosure.dataset.part = "login/password-disclosure";
  disclosure.textContent = say("usePassword");
  disclosure.setAttribute("aria-controls", "loginform");
  const doors = document.createElement("p");
  doors.className = "loginsub";
  doors.dataset.part = "login/doors";
  doors.textContent = say("doors");
  block.append(disclosure, doors);
  gate.insertBefore(block, form);
  plex.addEventListener("click", () => void signInWithPlex());
  disclosure.addEventListener("click", () => setPasswordOpen(form.hidden !== false));
  loginByEmail(form);
  return block;
}

/**
 * The Plex wait: what is awaited, the way back to Plex's page, and the way out.
 *
 * @param say The gate's words, by key.
 * @returns The block, hidden until a PIN is unclaimed.
 */
function pendingBlock(say: (key: string) => string): HTMLElement {
  const pending = document.createElement("div");
  pending.dataset.part = "login/plex-pending";
  pending.setAttribute("role", "status");
  pending.hidden = true;
  const words = document.createElement("p");
  words.className = "loginsub";
  words.textContent = say("plexPending");
  const reopen = document.createElement("a");
  reopen.className = `${actionButton({ kind: "cardFoot" })} ${crossReferenceLink()}`;
  reopen.dataset.part = "login/plex-reopen";
  reopen.target = "_blank";
  reopen.rel = "noopener";
  reopen.textContent = say("plexReopen");
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = actionButton({ kind: "cardFoot" });
  cancel.dataset.part = "login/plex-cancel";
  cancel.textContent = say("plexCancel");
  cancel.addEventListener("click", () => stopPlex());
  pending.append(words, reopen, cancel);
  return pending;
}

/**
 * Says the password form's identifier is the account's e-mail.
 *
 * AT RUN TIME, NOT IN THE MARKUP: the form is the region the design host
 * extracts byte for byte (R427), so its words are set here, from `fr.json`.
 *
 * @param form The password form.
 */
function loginByEmail(form: HTMLElement): void {
  const field = form.querySelector<HTMLInputElement>('input[name="username"]');
  if (!field) return;
  field.type = "email";
  // THE GATE SAYS ITS OWN REFUSALS: the browser's bubble would stop the submit
  // before the gate's words could be said.
  (form as HTMLFormElement).noValidate = true;
  const label = field.closest("label")?.querySelector("span");
  if (label) label.textContent = i18next.t("screens.gate.email");
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
  stopPlex();
  const unreachable = node('[data-part="login/plex-unreachable"]');
  if (unreachable) unreachable.hidden = true;
  const refusal = node("#loginerr");
  if (refusal) refusal.textContent = i18next.t("screens.gate.invalid");
  setPasswordOpen(passwordOpen);
}

// THE PLEX SIGN-IN IN FLIGHT: its generation, so a wait cancelled or
// superseded stops asking, and the page opened for it, closed once it ends.
let plexGeneration = 0;
let plexPage: Window | null = null;

/** Shows or hides one part of the Plex block. */
function showPart(part: string, shown: boolean): void {
  const found = node(`[data-part="login/${part}"]`);
  if (found) found.hidden = !shown;
}

/** Ends the Plex sign-in in flight: no more asking, no wait, no page left open. */
function stopPlex(): void {
  plexGeneration += 1;
  showPart("plex-pending", false);
  plexPage?.close();
  plexPage = null;
}

/**
 * Lands the signed-in account on its entry page once its rights are read.
 *
 * A read CANCELLED — the cache cleared under it, by a sign-out or a driven
 * state — lands nowhere and says nothing: whatever cleared it has moved the
 * interface on. Any other failure is left to surface.
 */
async function land(): Promise<void> {
  const client = sharedQueryClient;
  if (client === undefined) return ending();
  await client.resetQueries();
  let account: Schemas["Account"];
  try {
    account = await client.fetchQuery({
      queryKey: ["/api/v1/auth/me"],
      queryFn: async () => (await fetch("/api/v1/auth/me")).json() as Promise<Schemas["Account"]>,
    });
  } catch (failure) {
    if (failure instanceof CancelledError) return;
    throw failure;
  }
  landSignedIn(entryPageFor(rightsOf(account)));
  ending();
}

/** Says Plex does not answer, and opens the password: the door of last resort. */
function plexDown(): void {
  showPart("plex-unreachable", true);
  setPasswordOpen(true);
}

/**
 * Says why Plex's door refused, in `fr.json`'s words for its code.
 *
 * @param body The problem the server answered.
 */
function plexRefused(body: unknown): void {
  const refusal = node('[data-part="login/plex-refusal"]');
  if (!refusal) return;
  refusal.textContent = refusalWords(body, "screens.gate.invalid");
  refusal.hidden = false;
}

/** The answer's body, or nothing when it carries none. */
async function bodyOf(answer: Response): Promise<unknown> {
  return answer.json().catch(() => undefined);
}

/**
 * Starts a Plex sign-in: a PIN from the server, Plex's page opened, then the
 * PIN asked about until it is claimed, refused or expired.
 *
 * THE PAGE IS OPENED IN THE TAP, before the server answers: a window opened
 * after an `await` is a popup the browser blocks. Its address follows.
 */
async function signInWithPlex(): Promise<void> {
  stopPlex();
  const generation = plexGeneration;
  showPart("plex-unreachable", false);
  showPart("plex-refusal", false);
  plexPage = window.open("", "_blank");
  const started = await fetch("/api/v1/auth/plex/start", { method: "POST" }).catch(() => null);
  if (generation !== plexGeneration) return;
  if (started === null || started.status === UNREACHABLE) return (stopPlex(), plexDown());
  const body = await bodyOf(started);
  if (!started.ok) return (stopPlex(), plexRefused(body));
  const { pinId, signInUrl } = body as Schemas["StartedPlexSignIn"];
  if (plexPage) plexPage.location.href = signInUrl;
  node<HTMLAnchorElement>('[data-part="login/plex-reopen"]')?.setAttribute("href", signInUrl);
  await awaitPlex(pinId, generation);
}

/**
 * Asks about one PIN once a second while it is unclaimed, its wait drawn.
 *
 * @param pinId The PIN `startPlexSignIn` answered.
 * @param generation The sign-in this wait belongs to.
 */
async function awaitPlex(pinId: number, generation: number): Promise<void> {
  while (generation === plexGeneration) {
    const answer = await fetch("/api/v1/auth/plex", {
      method: "POST",
      body: JSON.stringify({ pinId }),
    }).catch(() => null);
    if (generation !== plexGeneration) return;
    if (answer?.status === PENDING) {
      showPart("plex-pending", true);
      await new Promise((done) => setTimeout(done, POLL_EVERY));
      // A GATE NO LONGER SHOWN ASKS NOTHING MORE: whatever lifted it has moved
      // the interface on, and a claim landing now would sign in under it.
      if (node<HTMLElement>("#login")?.hidden !== false) return stopPlex();
      continue;
    }
    stopPlex();
    if (answer?.ok) return land();
    if (answer === null || answer.status === UNREACHABLE) return plexDown();
    return plexRefused(await bodyOf(answer));
  }
}

/**
 * Signs in with a password — the owner's fallback, or a local account's door.
 *
 * @param email The account's e-mail, as typed.
 * @param password The password typed.
 */
async function signInWithPassword(email: string, password: string): Promise<void> {
  const refusal = node("#loginerr");
  const answer = await fetch("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  }).catch(() => null);
  if (answer?.ok) return land();
  if (refusal) {
    refusal.textContent = refusalWords(answer ? await bodyOf(answer) : undefined, "screens.gate.invalid");
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
    // THE FIELD KEEPS ITS NAME `username`: it is the host's region (R427), and
    // the name is what a password manager files the e-mail under.
    const email = String(fields.get("username") ?? "").trim();
    const password = String(fields.get("password") ?? "");
    // An empty field shows the refusal state and asks nobody.
    if (!email || !password) {
      const refusal = node("#loginerr");
      if (refusal) refusal.hidden = false;
      return;
    }
    void signInWithPassword(email, password);
  });
}
