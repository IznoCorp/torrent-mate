// THE ENTRY — the splash, the sign-in gate and the install proposal.
//
// `MODEL.md` § 2 Part 9. All three were engine LOGIC over static markup
// (`legacy.js:9678–9915`), and it is the LOGIC that had to move: §17 redraws
// the gate for Plex SSO and cannot do so while the gate is engine code, because
// D5 allows no addition there.
//
// THE MARKUP STAYS IN `index.html`, AND THAT IS A DECISION WITH TWO REASONS,
// one per surface.
//
//   THE SPLASH is on screen from the FIRST PAINTED FRAME. A browser paints what
//   it has parsed so far, and the markup is first in the frame for exactly that
//   reason; drawn by React it would appear only once the bundle it exists to
//   cover has already run, which is the property inverted rather than moved.
//
//   THE SIGN-IN GATE is EXTRACTED by `frontend/maquette/serve.py`
//   (`login:markup:start…end`) and served as the design host's own password
//   page. A component would leave that host with a second copy to keep in step,
//   and the extraction exists precisely so there is not one: the file's own
//   comment records that both halves were retyped once and both times the copy
//   rendered correctly while the reference was broken.
//
// The install proposal's markup could move and does not in this wave: it is the
// one piece of the entry that neither a server nor the first paint pins, so it
// is the one that can move at any time, and moving it is forty lines of copy
// into `fr.json` for no property this lot owes.
import i18next from "../i18n";

/** How long a full load is BUDGETED for — the bar's pace, never a floor. */
const STARTUP_MS = 5000;

let finish: (() => void) | null = null;

function node(selector: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(selector);
}

/**
 * Shows the startup screen, restarting its bar from zero.
 *
 * The restart is the whole of why this is not a `hidden = false`: driving to
 * the named state twice would otherwise measure a bar left where the previous
 * visit stopped it. Reflow between the two writes, or the browser coalesces
 * them and the animation never restarts.
 */
export function showStartup(): void {
  const screen = node("#splash");
  if (!screen) return;
  screen.hidden = false;
  const bar = screen.querySelector<HTMLElement>(".splashbar i");
  if (bar) {
    bar.style.animation = "none";
    void bar.offsetWidth;
    bar.style.animation = "";
  }
}

export function hideStartup(): void {
  const screen = node("#splash");
  if (screen) screen.hidden = true;
}

/**
 * Covers a wait with the startup screen until the wait resolves.
 *
 * WHAT IT COVERS is one gap: between asking for the application and having an
 * interface. What ENDS it is the interface being there — never a timer. Held on
 * a timer once, the bar filled while the document downloaded and then RESTARTED
 * from zero in a document that was already rendered.
 *
 * Args:
 *     duration: Passed only where the wait is PLAYED rather than observed — the
 *         sign-in inside the prototype, which fetches nothing and has to show
 *         what the real one looks like.
 */
export function coverLoading(duration = STARTUP_MS): void {
  showStartup();
  void new Promise<void>((resolve) => {
    finish = resolve;
  }).then(hideStartup);
  window.setTimeout(() => window.__loadingDone?.(), duration);
}

declare global {
  interface Window {
    /** Whatever really knows the interface is ready calls this. */
    __loadingDone?: () => void;
    /** The shape the engine writes on a navigation entry. Dies with it (L13). */
    __navigationState?: () => Record<string, unknown>;
    /** The entry's verbs, as the dying engine and the harness say them. */
    __entry?: {
      showSignIn: (withError: boolean, silent?: boolean) => void;
      hideSignIn: (silent?: boolean) => void;
      signOut: () => Promise<void>;
      coverLoading: (duration?: number) => void;
      showStartup: () => void;
      hideStartup: () => void;
      showInstall: (platform: "ios" | "android") => void;
      hideInstall: () => void;
      alreadyInstalled: () => boolean;
    };
  }
}

/**
 * Shows or hides the unauthenticated entry screen.
 *
 * The prototype holds NO credentials. The screen exists to be judged as a
 * surface; who may see it is decided by the server that serves this file. A
 * password written into a page is readable by everyone the page reaches, which
 * is the opposite of what a password is for.
 *
 * The gate sits on a real path (D1). It is not a page — it is a layer covering
 * everything — but it is what one SEES, and every screen owes an address. The
 * refusal is a STATE of that address, not a second one: it is not a place
 * anyone links to. Written in REPLACE, because signing in is not a step of the
 * walk one goes back through.
 *
 * Args:
 *     withError: True to show the refusal state.
 *     silent: True when the harness is driving. `__go` reaches this state
 *         without touching history (R74 holds that), so the address must not
 *         move. It used to be the engine's own `pilotage` latch, read from
 *         inside this function; it crosses as an ARGUMENT now, because the flag
 *         is the engine's and the function is not.
 */
export function showSignIn(withError: boolean, silent = false): void {
  const gate = node("#login");
  const refusal = node("#loginerr");
  if (gate) gate.hidden = false;
  if (refusal) refusal.hidden = !withError;
  if (withError)
    (document.querySelector("#loginform") as HTMLFormElement | null)?.reset();
  if (silent) return;
  try {
    window.__bridge.replace(
      window.__navigationState?.() ?? null,
      window.__address.signInPath,
    );
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error("sign-in gate: navigation write failed", error);
    window.__navEchec = true;
  }
}

/** Takes the gate off, and the address with it. */
export function hideSignIn(silent = false): void {
  const gate = node("#login");
  const wasShown = gate !== null && !gate.hidden;
  if (gate) gate.hidden = true;
  const refusal = node("#loginerr");
  if (refusal) refusal.hidden = true;
  // The address follows the screen off, so the gate does not stay in the bar
  // over the application it has just let through.
  if (!wasShown || silent) return;
  try {
    window.__bridge.replace(
      window.__navigationState?.() ?? null,
      window.__address.compose(window.__store.read().state),
    );
  } catch (error) {
    console.error("sign-in release: navigation write failed", error);
    window.__navEchec = true;
  }
}

/**
 * Ends the session and lands on the entry screen.
 *
 * The session is the cookie and the cookie is the server's, so the server is
 * asked to drop it FIRST and the screen only reflects what has already
 * happened. Showing the entry form over a session that is still valid would be
 * a lie the next reload exposes. A failure is swallowed on purpose: served from
 * a plain static server there is no such route, and a design reference that
 * dead-ends on a 404 teaches nothing about the design.
 */
export async function signOut(): Promise<void> {
  window.__panel.close();
  try {
    await fetch("/logout", { redirect: "manual" });
  } catch (error) {
    void error;
  }
  // AND THE CACHED SHELL GOES WITH THE SESSION. Before L11 the worker cached
  // one page — the offline notice — and signing out left nothing behind. It now
  // caches the DOCUMENT and every bundle, taken from an AUTHENTICATED context,
  // and a cache outlives a cookie: sign in on a phone, sign out, hand it over,
  // turn the radio off, and the whole password-protected prototype renders from
  // disk with no session at all. Online it still answers 401, so the bypass
  // would cost exactly one toggle of airplane mode.
  //
  // The worker is unregistered as well as emptied. A worker left registered
  // re-caches the shell the moment anyone signs in again, and the point is that
  // what is on this device belongs to the session that put it there.
  await forgetTheCachedShell();
  showSignIn(false);
}

/**
 * Empties the offline shell and unregisters the worker that fills it.
 *
 * Every step is best-effort and independent: a browser that refuses the Cache
 * API must still get the unregister, and a failure here must never stop a
 * sign-out — refusing to sign out because a cache would not clear is the worse
 * of the two failures.
 */
async function forgetTheCachedShell(): Promise<void> {
  try {
    if ("caches" in globalThis) {
      const names = await caches.keys();
      await Promise.allSettled(
        names.filter((name) => name.startsWith("tm-shell-"))
          .map((name) => caches.delete(name)),
      );
    }
  } catch (refused) {
    void refused;
  }
  try {
    const registrations =
      (await globalThis.navigator?.serviceWorker?.getRegistrations()) ?? [];
    await Promise.allSettled(
      registrations.map((registration) => registration.unregister()),
    );
  } catch (refused) {
    void refused;
  }
}

/* ── The install proposal — two platforms, two paths ─────────────────
   Android and desktop fire `beforeinstallprompt`, which a page may capture and
   replay on a gesture. iOS Safari fires NOTHING: there is no event to wait for
   and no API to call, so the only honest thing a page can do is explain the
   manual route. A single banner saying « installez-moi » on both would be a
   dead end on one of them. */

let installEvent: (Event & { prompt: () => void; userChoice: Promise<{ outcome: string }> }) | null =
  null;
let installRefused = false;

export function showInstall(platform: "ios" | "android"): void {
  const bar = node("#installbar");
  const onIOS = platform === "ios";
  if (bar) bar.hidden = false;
  const subtitle = node("#installsub");
  const steps = node("#installsteps");
  const go = node("#installgo");
  if (subtitle) subtitle.hidden = onIOS;
  if (steps) steps.hidden = !onIOS;
  if (go) go.hidden = onIOS;
}

export function hideInstall(): void {
  const bar = node("#installbar");
  if (bar) bar.hidden = true;
}

/**
 * Whether browser chrome exists around this application.
 *
 * THE ONE PLACE THAT KNOWS (Part 9). Nobody is asked to install while already
 * installed: `display-mode: standalone` means the icon is on the home screen,
 * and a banner there is noise about something already done. L11's P27 reads
 * this same question for the surfaces that exist only because a browser is
 * around them.
 */
export function alreadyInstalled(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (window.navigator as { standalone?: boolean }).standalone === true
  );
}

function onIOSSafari(): boolean {
  const userAgent = navigator.userAgent;
  const ios =
    /iPad|iPhone|iPod/.test(userAgent) ||
    // iPadOS 13+ reports itself as a Mac; the touch points give it away.
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  // Every browser on iOS is Safari underneath, but only Safari can install.
  return ios && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(userAgent);
}

function offerInstall(platform: "ios" | "android"): void {
  if (installRefused || alreadyInstalled()) return;
  // Never over the entry screen: there is nothing to install yet, and the
  // banner would cover the only field on it.
  const gate = node("#login");
  if (gate && !gate.hidden) return;
  showInstall(platform);
}

/**
 * Installs the entry: the gate's submit, the install proposal's two paths, and
 * the seam the engine and the harness say all of it through.
 *
 * Called once, from the frame, after the document is parsed.
 */
export function installEntry(): void {
  window.__loadingDone = () => {
    finish?.();
    finish = null;
    hideStartup();
  };

  document
    .querySelector("#loginform")
    ?.addEventListener("submit", (event) => {
      event.preventDefault();
      const fields = new FormData(event.currentTarget as HTMLFormElement);
      const username = String(fields.get("username") ?? "").trim();
      const password = String(fields.get("password") ?? "");
      // An empty field shows the refusal state; anything filled in walks
      // through, because this surface demonstrates the SCREEN and not the
      // check — the check lives where the file is served from.
      if (!username || !password) {
        const refusal = node("#loginerr");
        if (refusal) refusal.hidden = false;
        return;
      }
      hideSignIn();
      // What actually follows a sign-in: the interface is not there yet, and
      // the wait is covered rather than left blank — by the same screen, ended
      // the same way, as the one a cold load puts up.
      coverLoading();
    });

  node("#installclose")?.addEventListener("click", () => {
    hideInstall();
    // Refused: not asked again this session. The next visit may ask again — a
    // banner that never returns after one dismissal is a feature nobody finds
    // twice.
    installRefused = true;
  });

  node("#installgo")?.addEventListener("click", async () => {
    hideInstall();
    if (!installEvent) {
      window.__toast?.show({
        message: i18next.t("message.installRequested"),
      });
      return;
    }
    // The captured event is REPLAYED here, on a gesture, which is the only
    // moment a browser accepts it. It can be used exactly once.
    installEvent.prompt();
    const choice = await installEvent.userChoice.catch(() => null);
    installEvent = null;
    window.__toast?.show({
      message: i18next.t(
        choice && choice.outcome === "accepted"
          ? "message.installing"
          : "message.installRefused",
      ),
    });
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    // Without this the browser posts its own proposal and ours never runs.
    event.preventDefault();
    installEvent = event as typeof installEvent;
    offerInstall("android");
  });

  window.addEventListener("appinstalled", () => {
    installEvent = null;
    hideInstall();
    window.__toast?.show({ message: i18next.t("message.installed") });
  });

  // iOS has no event to wait for, so the offer is made once the interface is
  // there — after the startup screen, not over it.
  if (onIOSSafari()) window.setTimeout(() => offerInstall("ios"), 1200);

  window.__entry = {
    showSignIn,
    hideSignIn,
    signOut,
    coverLoading,
    showStartup,
    hideStartup,
    showInstall,
    hideInstall,
    alreadyInstalled,
  };
}
