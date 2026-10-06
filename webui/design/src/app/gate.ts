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
// IN THE READER'S LANGUAGE: before sign-in, the browser's (OPEN-2 B). Every
// element built here carries the key of its words (`data-words`), as the
// markup's own do, so a change of language words the whole gate again.
//
// THE GATE READS NO RIGHT ITSELF: after a sign-in the frame reads the account,
// and the account's entry page is where it lands (round 10 Q7) — unless the
// gate came up over a place the account opens, which is where it returns (the
// operator, 2026-10-04: the deep link is kept after sign-in).
import { CancelledError } from "@tanstack/react-query";
import i18next from "i18next";

import { entryPageFor, opensFor, rowFor } from "./navigation";
import { addressSeam, NOT_FOUND_PAGE } from "../lib/addresses";
import type { Rights } from "../lib/rights";
import { rightsOf } from "../lib/rights";
import { postJson, sharedQueryClient } from "../lib/query-client";
import { landSignedIn } from "./frame-verbs";
import type { Schemas } from "../lib/contract-schemas";
import { refusalWords } from "../lib/refusal";
import { followTheSignedIn } from "../lib/account";
import {
  actionButton,
  crossReferenceLink,
  passwordReveal,
  passwordRevealField,
  passwordRevealHost,
} from "../ui/variants";
import { icons } from "./icons";
import { svgIcon } from "../lib/markup-text";

// The statuses the two doors answer with.
const PENDING = 202;
const UNREACHABLE = 503;
// How often an unclaimed PIN is asked about: at most once a second (NE-DOIT-PAS-8).
const POLL_EVERY = 1000;

/** What the gate needs from the entry: how a sign-in ends. */
type Ending = () => void;

let ending: Ending = () => {};

// THE PLACE THE GATE CAME UP OVER, kept until the next sign-in takes it.
let keptPlace: string | null = null;

/**
 * Keeps the address the gate is about to replace, so a sign-in returns there.
 *
 * @param address The same-origin path and query the person was at.
 */
export function keepPlace(address: string): void {
  keptPlace = address;
}

/** Forgets the place kept: a sign-out is a leave, and the next person starts at their own entry. */
export function forgetPlace(): void {
  keptPlace = null;
}

/**
 * Takes the place kept, if a signed-in account may return to it.
 *
 * ONLY A SAME-ORIGIN PATH, though the entry keeps nothing else: a scheme, a
 * `//host` or a backslash would make the landing a redirect somewhere else.
 * The sign-in screen, an address nobody serves and a page the account does not
 * open are no place to return to.
 *
 * @param rights What the account just signed in may do.
 * @returns The page and its dials, or null to land on the entry page.
 */
function takePlace(rights: Rights): { page: string; dials: Record<string, string> } | null {
  const place = keptPlace;
  keptPlace = null;
  if (place === null || !/^\/(?![/\\])[^\\\u0000-\u001f]*$/.test(place)) return null;
  const queryAt = place.indexOf("?");
  const destination =
    queryAt < 0
      ? addressSeam.parse(place, "")
      : addressSeam.parse(place.slice(0, queryAt), place.slice(queryAt));
  if (destination.signIn || destination.notFound !== undefined) return null;
  if (destination.page === NOT_FOUND_PAGE) return null;
  const row = rowFor(destination.page);
  if (row === undefined || !opensFor(row, rights)) return null;
  return { page: destination.page, dials: destination.dials };
}

/**
 * Words one element of the gate, and keeps its key beside it so a change of
 * language words it again (`i18n/index.ts`'s `wordMarkup`).
 *
 * @param element The element.
 * @param key Its words' key under `screens.gate`.
 */
function worded(element: HTMLElement, key: string): void {
  element.dataset.words = `screens.gate.${key}`;
  element.textContent = i18next.t(element.dataset.words);
}

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
  const say = worded;
  const block = document.createElement("div");
  block.className = "logincard";
  block.dataset.part = "login/plex";
  const plex = document.createElement("button");
  plex.type = "button";
  plex.className = "loginsubmit";
  plex.dataset.part = "login/plex-submit";
  say(plex, "plex");
  const unreachable = document.createElement("p");
  unreachable.className = "loginerr";
  unreachable.dataset.part = "login/plex-unreachable";
  say(unreachable, "plexUnreachable");
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
  say(disclosure, "usePassword");
  disclosure.setAttribute("aria-controls", "loginform");
  const doors = document.createElement("p");
  doors.className = "loginsub";
  doors.dataset.part = "login/doors";
  say(doors, "doors");
  block.append(disclosure, doors);
  gate.insertBefore(block, form);
  plex.addEventListener("click", () => void signInWithPlex());
  disclosure.addEventListener("click", () =>
    setPasswordOpen(form.hidden !== false),
  );
  loginByEmail(form);
  passwordRevealButton(form);
  return block;
}

/**
 * The Plex wait: what is awaited, the way back to Plex's page, and the way out.
 *
 * @param say Words one element of the gate, by key.
 * @returns The block, hidden until a PIN is unclaimed.
 */
function pendingBlock(say: (element: HTMLElement, key: string) => void): HTMLElement {
  const pending = document.createElement("div");
  pending.dataset.part = "login/plex-pending";
  pending.setAttribute("role", "status");
  pending.hidden = true;
  const words = document.createElement("p");
  words.className = "loginsub";
  say(words, "plexPending");
  const reopen = document.createElement("a");
  reopen.className = `${actionButton({ kind: "cardFoot" })} ${crossReferenceLink()}`;
  reopen.dataset.part = "login/plex-reopen";
  reopen.target = "_blank";
  reopen.rel = "noopener";
  say(reopen, "plexReopen");
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = actionButton({ kind: "cardFoot" });
  cancel.dataset.part = "login/plex-cancel";
  say(cancel, "plexCancel");
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
  if (label) worded(label, "email");
}

/**
 * Puts the show/hide button on the password field.
 *
 * AT RUN TIME, NOT IN THE MARKUP, for the reason `loginByEmail` gives: the form is the region the design
 * host extracts byte for byte (R427). The field is wrapped where it stands, never rebuilt — its value, its
 * focus and its caret are the same node's throughout — and its label is pointed at by `aria-labelledby`,
 * so the button inside the label does not become part of the field's name.
 *
 * @param form The password form.
 */
function passwordRevealButton(form: HTMLElement): void {
  const field = form.querySelector<HTMLInputElement>('input[name="password"]');
  if (!field || form.querySelector('[data-part="login/password-reveal"]')) return;
  const label = field.closest("label")?.querySelector("span");
  if (label) {
    label.id = "loginpasswordlabel";
    field.setAttribute("aria-labelledby", label.id);
  }
  const host = document.createElement("div");
  host.className = passwordRevealHost();
  field.classList.add(...passwordRevealField().split(" "));
  field.replaceWith(host);
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = passwordReveal();
  toggle.dataset.part = "login/password-reveal";
  toggle.dataset.wordsLabel = "screens.gate.showPassword";
  toggle.setAttribute("aria-label", i18next.t("screens.gate.showPassword"));
  host.append(field, toggle);
  showPassword(false);
  // THE FIELD KEEPS THE FOCUS when a pointer presses the button: the press must not take it.
  toggle.addEventListener("mousedown", (event) => event.preventDefault());
  toggle.addEventListener("click", () => {
    const kept = document.activeElement === field;
    const { selectionStart, selectionEnd } = field;
    showPassword(field.type === "password");
    if (!kept) return;
    field.focus();
    field.setSelectionRange(selectionStart, selectionEnd);
    // A CHANGE OF TYPE REBUILDS THE FIELD'S BOX, and the browser resets the caret when it does, after
    // this handler returns: the caret is put back once more, on the frame that follows.
    requestAnimationFrame(() => field.setSelectionRange(selectionStart, selectionEnd));
  });
}

/**
 * Shows or hides what the password field holds, its button drawn to match.
 *
 * @param shown True to show the value as text.
 */
function showPassword(shown: boolean): void {
  const field = node<HTMLInputElement>('#loginform input[name="password"]');
  const toggle = node<HTMLElement>('[data-part="login/password-reveal"]');
  if (field) field.type = shown ? "text" : "password";
  if (!toggle) return;
  toggle.setAttribute("aria-pressed", String(shown));
  toggle.innerHTML = svgIcon(shown ? icons.eyeOff : icons.eye);
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
  // A FORM CLOSED HIDES WHAT WAS TYPED: it never comes back showing it.
  if (!open) showPassword(false);
  disclosure?.setAttribute("aria-expanded", String(open));
}

// WHY THE SESSION ENDED, said under the form's subtitle: the closed codes v1 answers a refused session or
// sign-in with, and where each one's words live in `fr.json` (`screens.gate.<key>`). Any other code — an
// unknown e-mail, a wrong password — says nothing here: it must tell nothing (O-K1-4).
const REASONS: Readonly<Record<string, string>> = {
  "auth.required": "reasonExpired",
  "auth.access_disabled": "reasonDisabled",
};

/**
 * Says why the session ended, or takes the line down.
 *
 * AT RUN TIME, NOT IN THE MARKUP, for the reason `loginByEmail` gives: the gate is the region the design
 * host extracts byte for byte, and the host's own page says its reason server-side.
 *
 * @param code The refusal code the server gave, if any. A plain visit, or a code that is no reason,
 *     shows no line.
 */
export function sayReason(code: string | undefined): void {
  const key = code === undefined ? undefined : REASONS[code];
  let line = node<HTMLElement>('[data-part="login/reason"]');
  if (key === undefined) {
    if (line) line.hidden = true;
    return;
  }
  if (!line) {
    // IN THE GATE, BEFORE ITS FIRST DOOR — and not in the password form, which rests CLOSED behind its
    // disclosure while Plex is the way in: a reason said inside it would be said to no one.
    const gate = node("#login");
    const anchor = node('[data-part="login/plex"]') ?? node("#loginform");
    if (!gate || !anchor) return;
    line = document.createElement("p");
    line.className = "loginerr";
    line.dataset.part = "login/reason";
    line.setAttribute("role", "status");
    gate.insertBefore(line, anchor);
  }
  worded(line, key);
  line.hidden = false;
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
  // A GATE PUT BACK NEVER SHOWS WHAT WAS TYPED, even when the form comes back open: `setPasswordOpen` hides
  // only on close, and a Plex sign-in can end with the field still revealed.
  showPassword(false);
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
 * Lands the signed-in account where the gate came up, or on its entry page,
 * once its rights are read.
 *
 * A read CANCELLED — the cache cleared under it, by a sign-out or a driven
 * state — lands nowhere and says nothing: whatever cleared it has moved the
 * interface on. Any other failure is left to surface.
 */
async function land(): Promise<void> {
  const client = sharedQueryClient;
  if (client === undefined) return ending();
  // SOMEBODY IS SIGNED IN AGAIN: the interface follows the account this landing reads.
  followTheSignedIn();
  await client.resetQueries();
  let account: Schemas["Account"];
  try {
    account = await client.fetchQuery({
      queryKey: ["/api/v1/auth/me"],
      queryFn: async () =>
        (await fetch("/api/v1/auth/me")).json() as Promise<Schemas["Account"]>,
    });
  } catch (failure) {
    if (failure instanceof CancelledError) return;
    throw failure;
  }
  const rights = rightsOf(account);
  const place = takePlace(rights);
  if (place) landSignedIn(place.page, place.dials);
  else landSignedIn(entryPageFor(rights));
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
  const started = await fetch("/api/v1/auth/plex/start", {
    method: "POST",
  }).catch(() => null);
  if (generation !== plexGeneration) return;
  if (started === null || started.status === UNREACHABLE)
    return (stopPlex(), plexDown());
  const body = await bodyOf(started);
  if (!started.ok) return (stopPlex(), plexRefused(body));
  const { pinId, signInUrl } = body as Schemas["StartedPlexSignIn"];
  if (plexPage) plexPage.location.href = signInUrl;
  node<HTMLAnchorElement>('[data-part="login/plex-reopen"]')?.setAttribute(
    "href",
    signInUrl,
  );
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
    const answer = await postJson("/api/v1/auth/plex", { pinId }).catch(() => null);
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
async function signInWithPassword(
  email: string,
  password: string,
): Promise<void> {
  const refusal = node("#loginerr");
  const answer = await postJson("/api/v1/auth/login", { email, password }).catch(() => null);
  if (answer?.ok) return land();
  if (refusal) {
    refusal.textContent = refusalWords(
      answer ? await bodyOf(answer) : undefined,
      "screens.gate.invalid",
    );
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
    // WHATEVER BECOMES OF THE SUBMIT, the secret is hidden again.
    showPassword(false);
    // An empty field shows the refusal state and asks nobody.
    if (!email || !password) {
      const refusal = node("#loginerr");
      if (refusal) refusal.hidden = false;
      return;
    }
    void signInWithPassword(email, password);
  });
}
