// The service worker's registration, and the discipline that keeps a cached
// shell from becoming a stale one (L11, MODEL.md § 2 Part 13).
//
// THE DISCIPLINE IS PRODUCTION'S, AND IT IS PROVED (`web-ui.md` § PWA): a check
// on load, on `visibilitychange` and every 15 minutes; the served build compared
// against the built one; a new worker asked to take over, and ONE reload. What
// changes here is the signal, and only the signal — see `SERVED_BUILD` below.
//
// WHY THIS FILE EXISTS AT ALL, GIVEN `index.html` ALREADY REGISTERS. The
// envelope's inline script registers the worker and does nothing else, and it
// has to stay there: the sign-in gate borrows that whole block and is the only
// document a phone reaches before signing in, so registration must work with no
// bundle at all. What the gate cannot do is DISCIPLINE — it has no build
// identity to compare and nothing to reload into. So registration is the
// envelope's and the update is the application's, and neither duplicates the
// other.
//
// IT IS IN `app/` AND NOT UNDER A FEATURE (invariant 10). A worker, an update
// policy and a reload are the frame's; the page one happens to have open when
// the new build lands is not what any of it is about — MODEL Part 13 names this
// the single most likely misplacement of the whole plan.
import { askTheHost } from "../lib/platform-network";

/** What the running bundle was built from. The build injects it. */
declare const __BUILD_ID__: string;

// WHERE THE HOST PUBLISHES WHAT IT IS SERVING, and why it is not `/api/version`
// as production has it. The mock layer replaces the page's `fetch` and answers
// only the maquette's contract, so a poll under `/api/` would be answered by a
// fixture and could never fail — a check that cannot fail is not a check. The
// address is outside the contract for that reason, and it is asked for through
// `askTheHost` for the same one.
const SERVED_BUILD = "/build.json";

// Production polls every 15 minutes and so does this. It is not a number
// somebody liked: it is the interval an installed application can be left
// running on a phone without the operator ever reloading it by hand.
const EVERY = 15 * 60 * 1000;

let reloading = false;

// WHICH SERVED BUILD THIS SESSION HAS ALREADY RELOADED FOR.
//
// `reloading` alone is not a latch and cannot be one: a reload REPLACES the
// document, so the module is evaluated again and the flag is false again. The
// page then boots, checks, still sees a served build different from its own,
// and reloads — forever. Measured, not imagined: R106 read FIFTEEN loads where
// it expected two, which is why that hold is « and it does not reload again »
// rather than « it reloads ».
//
// A reload loop is the one failure this discipline can produce that is worse
// than staleness: on a design host it is indistinguishable from a host that is
// down. So the latch outlives the document. One reload per served build — if
// the page comes back still not matching, the convergence has failed and that
// needs a person, not another reload.
const RELOADED_FOR = "tm-reloaded-for";

/**
 * Asks the worker to finish caching the shell.
 *
 * WHY THE APPLICATION HAS TO ASK. The worker installs from whichever document a
 * browser had in front of it, and on the design host that is the SIGN-IN GATE —
 * a browser reads the manifest of the page it is on, never one waiting behind a
 * cookie. From the gate the bundles answer 401, because the bundles are the
 * prototype and the prototype is what the password protects. So the install
 * caches the document and tries the rest; this is the moment the rest becomes
 * reachable, because the page making the request is running from it.
 *
 * It is best-effort by design and loud by measurement: nothing here can repair
 * a shell the host will not serve, and what guarantees the shell is whole is
 * R105 reading the cache after boot, not a promise made here.
 *
 * @param container The worker container, or null where there is none.
 */
function completeShell(container: ServiceWorkerContainer | null): void {
  const worker = container?.controller;
  if (!worker) return;
  worker.postMessage("cache-shell");
}

/**
 * Asks the host which build it is serving.
 *
 * @returns The served build's identity, or null when the host cannot be
 *     reached — which offline is the NORMAL case and must never be read as
 *     « the build changed ».
 */
async function servedBuild(): Promise<string | null> {
  try {
    // `cache: "no-store"` and not a cache-busting query parameter: the worker
    // does not precache this address, but an HTTP cache upstream would happily
    // answer the poll with the answer it gave fifteen minutes ago, and the
    // discipline would then be measuring its own cache.
    const answer = await askTheHost(SERVED_BUILD, { cache: "no-store" });
    if (!answer.ok) return null;
    const body = (await answer.json()) as { build?: unknown };
    return typeof body.build === "string" ? body.build : null;
  } catch (unreachable) {
    return null;
  }
}

/**
 * Reloads once, into the build the host is serving.
 *
 * ONCE is the whole contract. The check fires on load, on every return to the
 * foreground and on a timer, so a reload that did not latch would fire again
 * from the handler that is still queued behind it — and a reload loop on a
 * design host is indistinguishable from a host that is down.
 *
 * @param registration The worker's registration, whose waiting worker is asked
 *     to take over. Absent when no worker ever installed, in which case the
 *     reload alone is the whole of it.
 */
function reloadOnce(
  registration: ServiceWorkerRegistration | null,
  servedBuildIdentity: string | null,
): void {
  if (reloading) return;
  try {
    // Session storage and not local: the latch is about THIS run of the
    // application. A new tab, or the same one opened tomorrow, is entitled to
    // try converging again.
    if (servedBuildIdentity !== null) {
      if (globalThis.sessionStorage.getItem(RELOADED_FOR) === servedBuildIdentity) {
        return;
      }
      globalThis.sessionStorage.setItem(RELOADED_FOR, servedBuildIdentity);
    }
  } catch (unavailable) {
    // Private browsing, or storage refused. Fall through: one reload that may
    // repeat is a worse outcome than staleness, but refusing to update at all
    // because a storage call threw is worse than both.
  }
  reloading = true;
  // The page asks; the worker never takes it by itself. That is what
  // `registerType: 'prompt'` means, and `sw.js` holds the other half.
  registration?.waiting?.postMessage("skip-waiting");
  globalThis.location.reload();
}

/**
 * Compares what is running against what is served, and acts once.
 *
 * @param registration The worker's registration, or null.
 */
async function checkForUpdate(
  registration: ServiceWorkerRegistration | null,
): Promise<void> {
  if (reloading) return;
  // Ask the worker to look for a new script REGARDLESS of the comparison
  // below: the two are different questions, and a worker that has quietly
  // stopped updating is the failure this half exists to prevent.
  await registration?.update().catch(() => undefined);
  const served = await servedBuild();
  // Unreachable, or serving what is already running: nothing to do. The first
  // is the ordinary offline case, and treating it as a change would reload the
  // application every fifteen minutes on a phone with no signal.
  if (served === null || served === __BUILD_ID__) return;
  reloadOnce(registration, served);
}

/**
 * Installs the update discipline. Called once, from the boot.
 *
 * REGISTRATION IS NOT DONE HERE — the envelope's inline script owns it, so that
 * the sign-in gate, which has no bundle, is installable too. This waits for
 * whatever that script produced and then disciplines it. When there is no
 * worker at all (a plain static preview, a browser without support) the
 * comparison still runs and still reloads into a new build: the discipline is
 * about the BUILD, and the worker is only what makes the old one persist.
 */
export function installUpdateDiscipline(): void {
  const container = globalThis.navigator?.serviceWorker ?? null;
  const ready: Promise<ServiceWorkerRegistration | null> = container
    ? container.getRegistration().then((found) => found ?? null, () => null)
    : Promise.resolve(null);

  void ready.then((registration) => {
    const check = () => void checkForUpdate(registration);
    check();
    // The bundles, which the install could not reach. A worker that is not yet
    // controlling this page will control the next load, and the shell is
    // completed then — there is nothing to retry here.
    completeShell(container);
    // On every return to the foreground. `visibilitychange` and not `focus`:
    // an installed application on a phone is switched away from and back to,
    // and it is never focused in between.
    globalThis.document.addEventListener("visibilitychange", () => {
      if (globalThis.document.visibilityState === "visible") check();
    });
    globalThis.setInterval(check, EVERY);
    // A worker that took over while the page was open — another client asked
    // for the swap — means the shell under this page has changed.
    //
    // THE GUARD IS NOT OPTIONAL AND IT IS EASY TO MISS. `clients.claim()` in
    // the worker's `activate` makes the FIRST worker take over pages that were
    // loaded without one, which fires `controllerchange` on the very first
    // visit of every visitor. Unguarded, this listener would reload the
    // application once on first load, every time — and in the harness, where a
    // rule opens a fresh context per run, that is a reload in the middle of
    // every measurement in the suite. A first claim is not an update; only a
    // swap under a page that already HAD a controller is.
    const hadController = Boolean(container?.controller);
    container?.addEventListener("controllerchange", () => {
      if (!hadController) return;
      // No served build to latch on: a swap under a live page is a one-off
      // event and not a state that could repeat on the next boot.
      reloadOnce(registration, null);
    });
  });
}
