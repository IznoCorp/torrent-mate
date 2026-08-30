// The service worker's registration, and the discipline that keeps a cached
// shell from becoming a stale one (L11, MODEL.md § 2 Part 13).
//
// THE DISCIPLINE IS PRODUCTION'S, AND IT IS PROVED (`web-ui.md` § PWA): a check
// on load, on `visibilitychange` and every 15 minutes; the served build compared
// against the built one; a new worker asked to take over, and ONE reload. Two
// things change here, and the second was got WRONG the first time.
//
//   THE SIGNAL — `/build.json` and not `/api/version`, for the reason written
//       at `SERVED_BUILD` below.
//   THE ORDER — and this is the correction. The first version read
//       `registration.waiting` straight after `await registration.update()` and
//       reloaded. `update()` resolves as soon as the new worker begins
//       INSTALLING — before its `install` handler has fetched the document and
//       every bundle — so `waiting` was null, the optional chain swallowed it,
//       and the page reloaded with no swap. After that reload the served build
//       EQUALS the running build, so the comparison returns early and
//       `skip-waiting` is never sent again for the session: the page runs the
//       new build while the OLD worker still controls it, and the new one is
//       parked until every tab closes.
//
//       Production never had that bug because it does not drive the swap from
//       the poll: `updatefound` → `statechange` → `installed` is when a worker
//       is really waiting, and `controllerchange` is when it has really taken
//       over. The reload follows the swap; it does not race it.
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

// WHETHER THIS DOCUMENT EVER HAD A CONTROLLER, read SYNCHRONOUSLY at module
// evaluation and not after an await. `clients.claim()` gives a first worker
// control of a page that loaded without one, which fires `controllerchange` on
// the very first visit of every visitor — so the reload-on-swap must know
// whether this is a first claim or a real swap. Reading it inside a `.then`
// happens to hold today only because `getRegistration()` resolves long before a
// worker finishes installing, and the correctness of the whole guard would rest
// on that race.
const HAD_CONTROLLER_AT_BOOT =
  Boolean(globalThis.navigator?.serviceWorker?.controller);

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
 * Reads which served build this session has already reloaded for.
 *
 * TWO PLACES, AND THE SECOND IS NOT A NICETY. `sessionStorage` is the right
 * home and it THROWS where a browser has site data blocked for the origin — the
 * exact profile on which the first version fell through to an unguarded reload
 * and produced the unbounded loop it excuses itself for. `window.name` survives
 * a same-origin reload, is not gated by storage permissions, and is the
 * standard fallback for precisely this.
 *
 * @returns The remembered build, or null.
 */
function rememberedReload(): string | null {
  try {
    const stored = globalThis.sessionStorage.getItem(RELOADED_FOR);
    if (stored !== null) return stored;
  } catch (unavailable) {
    void unavailable;
  }
  const named = globalThis.window.name;
  return named.startsWith(`${RELOADED_FOR}:`)
    ? named.slice(RELOADED_FOR.length + 1)
    : null;
}

/**
 * Remembers that this session has reloaded for one served build.
 *
 * @param servedBuildIdentity What the host was serving.
 */
function rememberReload(servedBuildIdentity: string): void {
  try {
    globalThis.sessionStorage.setItem(RELOADED_FOR, servedBuildIdentity);
  } catch (unavailable) {
    void unavailable;
  }
  // WRITTEN IN BOTH PLACES, ALWAYS. `window.name` is the only latch that
  // survives where storage throws, and a browser can start refusing storage
  // mid-session — so the fallback is kept current rather than written only once
  // the first write has been seen to fail.
  globalThis.window.name = `${RELOADED_FOR}:${servedBuildIdentity}`;
}

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
function askTheWaitingWorkerToTakeOver(
  registration: ServiceWorkerRegistration | null,
): boolean {
  const waiting = registration?.waiting;
  if (!waiting) return false;
  // The page asks; the worker never takes it by itself. That is what
  // `registerType: 'prompt'` means, and `sw.js` holds the other half. The
  // reload then arrives on `controllerchange`, once the swap has HAPPENED.
  waiting.postMessage("skip-waiting");
  return true;
}


function reloadOnce(
  registration: ServiceWorkerRegistration | null,
  servedBuildIdentity: string | null,
): void {
  if (reloading) return;
  if (servedBuildIdentity !== null) {
    if (rememberedReload() === servedBuildIdentity) return;
    rememberReload(servedBuildIdentity);
  }
  reloading = true;
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
  // stopped updating is the failure this half exists to prevent. A worker that
  // is ALREADY waiting is asked to take over here — `updatefound` fired while
  // this page was in the background, or before the listener was installed.
  await registration?.update().catch(() => undefined);
  if (askTheWaitingWorkerToTakeOver(registration)) return;
  const served = await servedBuild();
  // Unreachable, or serving what is already running: nothing to do. The first
  // is the ordinary offline case, and treating it as a change would reload the
  // application every fifteen minutes on a phone with no signal.
  if (served === null || served === __BUILD_ID__) return;
  // THE BUILD MOVED AND NO WORKER IS WAITING — which happens when there is no
  // worker at all (a plain preview, a browser without support) or when its
  // install is still running. Reloading is right in the first case and harmless
  // in the second: the reload fetches the new document from the network, and
  // the swap arrives on `controllerchange` when the install finishes.
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

    // A WORKER THAT BECOMES WAITING WHILE THIS PAGE IS OPEN. This is the event
    // production drives the swap from, and the one the first version of this
    // file did without: `update()` resolves when a worker starts INSTALLING,
    // and only `statechange` says when it is really waiting.
    registration?.addEventListener("updatefound", () => {
      const arriving = registration.installing;
      arriving?.addEventListener("statechange", () => {
        if (arriving.state !== "installed") return;
        // No controller means this is the FIRST worker, not a replacement:
        // nothing to swap, and `clients.claim()` will take it from here.
        if (!globalThis.navigator.serviceWorker.controller) return;
        askTheWaitingWorkerToTakeOver(registration);
      });
    });
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
    container?.addEventListener("controllerchange", () => {
      if (!HAD_CONTROLLER_AT_BOOT) {
        // A FIRST CLAIM, NOT AN UPDATE — and the moment the shell can finally
        // be completed. `completeShell` returns silently when there is no
        // controller, so on a load where the worker activates after the boot
        // (a fresh profile, and every harness context) nothing would ever have
        // asked it to cache anything for the whole session.
        completeShell(container);
        return;
      }
      // No served build to latch on: a swap under a live page is a one-off
      // event and not a state that could repeat on the next boot.
      reloadOnce(registration, null);
    });
  });
}
