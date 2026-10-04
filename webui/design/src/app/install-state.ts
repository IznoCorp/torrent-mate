// WHAT THE APPLICATION OFFERS TO INSTALL, TO WHOM, AND WHEN — and, once it is installed, what it offers
// instead (§ 12 Mobile first; the operator, 2026-10-04).
//
//   THE PROPOSAL comes ONCE, right after the first successful sign-in, on every platform; a person who
//   has been proposed it is never proposed it again. « Offered » is a mark in the browser's own storage,
//   so clearing site data proposes again — and every access to storage is guarded, because a private
//   window or blocked site data makes it THROW, and an install offer is never worth a broken sign-in.
//
//   THE PROFIL BUTTON is the other way in, for whoever dismissed the proposal or never saw it: « Installer
//   l'app » on a browser that fired `beforeinstallprompt`, the way to do it by hand on iOS Safari, and —
//   once the app runs installed — « Mettre à jour » when a newer version waits. One button, three faces,
//   and none at all where there is nothing to do.
//
// IT IS IN `app/` AND NOT UNDER A FEATURE (invariant 10): the entry proposes, the update discipline reports
// a waiting version, and the Profil page offers — three readers of one state, none of them its owner.

/** What Chrome hands a page on `beforeinstallprompt`, reduced to the two members a page may use. */
export type InstallPrompt = Event & {
  prompt: () => void;
  userChoice: Promise<{ outcome: string }>;
};

/** Where the proposal is made: the captured prompt, or the guide a platform without one needs. */
export type InstallPlatform = "ios" | "android";

/** What the Profil button says: install, how to install by hand, update, or nothing. */
export type InstallFace = "none" | "install" | "ios" | "update";

// The marks. Both live in the browser: the first for good (until site data is cleared), the second for
// the one navigation between the sign-in page and the application.
const OFFERED = "tm-install-offered";
const SIGNED_IN = "tm-signed-in";

let captured: InstallPrompt | null = null;
// The face a NAMED STATE dials, so the harness can draw each face without a browser that really is one.
let dialled: InstallFace | null = null;
let applier: (() => void) | null = null;
let pending: ((platform: InstallPlatform) => boolean | void) | null = null;
// Shown during this page's life — the memory of a mark storage refused to keep.
let offeredHere = false;
const listeners = new Set<() => void>();

/** Tells every subscriber the face may have moved. */
function notify(): void {
  listeners.forEach((listener) => listener());
}

/**
 * Subscribes to the install state's moves.
 *
 * @param listener Called after the captured prompt, the waiting update or the installed state moves.
 * @returns The unsubscribe.
 */
export function subscribeInstall(listener: () => void): () => void {
  listeners.add(listener);
  return () => void listeners.delete(listener);
}

/**
 * Whether browser chrome exists around this application.
 *
 * THE ONE PLACE THAT KNOWS. Nobody is asked to install while already installed: `display-mode:
 * standalone` means the icon is on the home screen, and a banner there is noise about something already
 * done. P27 reads this same question for the surfaces that exist only because a browser is around them.
 *
 * @returns True when the application runs as an installed one.
 */
export function alreadyInstalled(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as { standalone?: boolean }).standalone === true
  );
}

/**
 * Whether this is Safari on iOS — the only browser there that can install, and one that fires nothing.
 *
 * @returns True on an iPhone or iPad's Safari.
 */
export function onIOSSafari(): boolean {
  const userAgent = navigator.userAgent;
  const ios =
    /iPad|iPhone|iPod/.test(userAgent) ||
    // iPadOS 13+ reports itself as a Mac; the touch points give it away.
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  // Every browser on iOS is Safari underneath, but only Safari can install.
  return ios && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(userAgent);
}

/**
 * Keeps the prompt a browser fired, and takes the browser's own proposal out of the way.
 *
 * @param event The `beforeinstallprompt` event. Its default is prevented: without that the browser posts
 *     its own proposal in its own place and ours never gets a turn.
 */
export function captureInstallEvent(event: InstallPrompt): void {
  event.preventDefault();
  captured = event;
  notify();
  proposeNow();
}

/** Forgets the prompt: the app was installed, or the one use the browser allows was spent. */
export function forgetInstallEvent(): void {
  captured = null;
  notify();
}

/**
 * Whether a proposal was made on this browser before.
 *
 * @returns True when the mark is there; false when it is not, or when storage refuses to say.
 */
export function wasOffered(): boolean {
  try {
    return localStorage.getItem(OFFERED) !== null;
  } catch (unavailable) {
    void unavailable;
    return false;
  }
}

/** Marks the proposal as made. Storage that refuses is not a failure: the page remembers it itself. */
export function markOffered(): void {
  offeredHere = true;
  try {
    localStorage.setItem(OFFERED, String(Date.now()));
  } catch (unavailable) {
    void unavailable;
  }
}

/**
 * Who would be proposed the install now, and how.
 *
 * @returns `android` with a captured prompt, `ios` on iOS Safari, null where there is nothing to propose,
 *     or the app is installed, or it was proposed before.
 */
export function proposalFor(): InstallPlatform | null {
  if (alreadyInstalled() || offeredHere || wasOffered()) return null;
  if (captured) return "android";
  return onIOSSafari() ? "ios" : null;
}

/** Makes the proposal that waits, if there is one to make now. */
function proposeNow(): void {
  if (!pending) return;
  const platform = proposalFor();
  if (!platform) return;
  // A proposal that DECLINES to be drawn — the gate is up over where it would stand — is not made: it
  // keeps waiting, and nothing is marked, so the person is not refused an offer they never saw.
  if (pending(platform) === false) return;
  pending = null;
  markOffered();
}

/**
 * Proposes the install, once, right after a successful sign-in.
 *
 * A browser may fire its prompt only after the sign-in (Chrome waits for the worker and the manifest), so
 * a proposal with nothing to show yet WAITS for it, and is made then.
 *
 * @param show Draws the proposal for a platform, and answers false when it could not be drawn now.
 */
export function proposeAfterSignIn(show: (platform: InstallPlatform) => boolean | void): void {
  pending = show;
  proposeNow();
}

/**
 * Takes the mark the sign-in page left for the first boot after it.
 *
 * The host's sign-in page is a document of its own, so the application boots from scratch after it: this
 * is how the boot learns that a person has just signed in.
 *
 * @returns True once per mark.
 */
export function takeSignedIn(): boolean {
  try {
    if (sessionStorage.getItem(SIGNED_IN) === null) return false;
    sessionStorage.removeItem(SIGNED_IN);
    return true;
  } catch (unavailable) {
    void unavailable;
    return false;
  }
}

/**
 * What the Profil button offers.
 *
 * @returns Nothing where there is nothing to do; the install, or its manual route on iOS, in a browser;
 *     the update when the app is installed and a newer version waits. A browser tab is not offered the
 *     update: it reloads itself.
 */
export function installFace(): InstallFace {
  if (dialled !== null) return dialled;
  if (alreadyInstalled()) return applier ? "update" : "none";
  if (captured) return "install";
  return onIOSSafari() ? "ios" : "none";
}

/**
 * Dials the face a named state draws, or lets the browser decide again.
 *
 * @param face The face to draw, or null for the one the browser's own answers give.
 */
export function dialInstallFace(face: InstallFace | null): void {
  dialled = face;
  notify();
}

/**
 * Says a newer version waits, and how to apply it.
 *
 * @param apply Activates the waiting version and reloads into it; null when none waits any more.
 */
export function setUpdateWaiting(apply: (() => void) | null): void {
  applier = apply;
  notify();
}

/** Applies the waiting update, on the person's word. */
export function applyUpdate(): void {
  const apply = applier;
  if (!apply) return;
  applier = null;
  notify();
  apply();
}

/**
 * Fires the captured prompt, on a gesture — the only moment a browser accepts it, and once.
 *
 * @returns The person's choice, or `unavailable` when no prompt is held.
 */
export async function promptInstall(): Promise<"accepted" | "dismissed" | "unavailable"> {
  const held = captured;
  if (!held) return "unavailable";
  forgetInstallEvent();
  held.prompt();
  const choice = await held.userChoice.catch(() => null);
  return choice?.outcome === "accepted" ? "accepted" : "dismissed";
}
