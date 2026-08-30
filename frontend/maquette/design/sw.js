// The offline shell (L11, MODEL.md § 2 Part 13).
//
// WHAT IT CACHES: the shell — the document, the bundles, the icons — and
// NOTHING under `/api/` or the event stream. Server state belongs in the query
// cache and in the relay, and a worker that answered `/api/` from disk would
// make an interface say things the operator's machine had stopped saying, which
// is §8 of the constitution read from the wrong end.
//
// WHAT REPLACED « THE WORKER CACHES NOTHING ». That was a real decision with a
// real reason — a caching worker would serve yesterday's prototype to someone
// judging today's design, the one failure a design reference cannot afford. It
// is not overturned by ignoring it. It is overturned by removing the failure it
// names: a navigation goes to the NETWORK first and falls back to the cache, so
// a reachable host always serves what it has now; and the update discipline
// (`app/worker-registration.ts`) compares the served build against the built
// one and reloads once when they differ.
//
// THE PRECACHE HAPPENS IN TWO MOMENTS, AND THAT IS FORCED BY THE HOST.
//
// `cache.addAll` is ATOMIC: one refusal and nothing is cached at all. And the
// only document a phone can reach on the design host before signing in is the
// LOGIN GATE — which is exactly where a worker has to install, since a browser
// reads the manifest of the page in front of it and never one waiting behind a
// cookie. From there `/vite/*` answers 401: the bundles are the prototype, and
// the prototype is what the password protects.
//
// So an install that REQUIRED anything would fail on the gate, every time, and
// no worker would ever exist. Measured, not reasoned, and the measurement is
// worth writing down because it defeats the obvious design: on the design host
// `/` itself answers **401** before sign-in — the login page is served WITH that
// status — so even the document cannot be required. Making the document the one
// required entry was tried and produced exactly one symptom: « the service
// worker never became ready », with a 401 in the console and no registration
// left behind.
//
//   AT INSTALL — everything is ATTEMPTED and nothing is required. On the gate
//       that caches the manifest, the icons and the offline notice, and no more.
//   ONCE THE APPLICATION IS RUNNING — it asks for the shell to be completed
//       (`cache-shell`). That is the first moment the document and the bundles
//       are reachable, by definition: the page is running FROM them.
//
// What guarantees the shell is whole is therefore a RULE and not an install:
// R105 reads the cache after boot and refuses a shell with no bundle in it. And
// the application asks on EVERY boot, so a completion that failed once repairs
// itself the next time the operator opens the application.
//
// THIS FILE IS A SOURCE, NOT THE SERVED FILE. The build writes `dist/sw.js`,
// substituting the three placeholders below with what it actually emitted —
// the bundle names carry content hashes and cannot be written here by hand.

const BUILD = "__BUILD__";
const SHELL = __SHELL__;
const EXTRAS = __EXTRAS__;

// The cache's name carries the build, so a new build is a NEW cache and the old
// one is deleted on activation rather than merged into. A single cache reused
// across builds is how a shell ends up half one version and half another.
const CACHE = `tm-shell-${BUILD}`;

// The last resort, and it is not the shell: it says the prototype lives on a
// server and is not reachable. It is what a visitor who has never loaded the
// application sees offline — there is nothing cached for them yet, and a blank
// page would say nothing at all.
const OFFLINE = "/offline.html";

// Never cached, in any mode. The stream is a connection, not a document.
const NEVER = (url) => url.pathname.startsWith("/api/") || url.pathname === "/ws";

// The document is `SHELL[0]` by the build's own contract, and it is the entry a
// navigation falls back to. The rest of the shell is the bundles.
const DOCUMENT = SHELL[0];
const BUNDLES = SHELL.slice(1);

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // ATTEMPTED, ALL OF IT. `allSettled` and not `all`, and not `addAll`: both
    // of those fail the install as a whole, and on the sign-in gate — the only
    // document a phone reaches before signing in, and therefore the only one a
    // worker can install from — the document and the bundles both answer 401.
    await Promise.allSettled(
      [DOCUMENT, ...BUNDLES, ...EXTRAS].map((asset) => cache.add(asset)),
    );
  })());
});

/**
 * Completes the shell, and says how it went.
 *
 * Called by the running application, which is the first moment the bundles are
 * certainly reachable. It REPORTS rather than throwing into nothing: a shell
 * that silently failed to complete is a shell that works until the network goes.
 */
async function completeShell() {
  const cache = await caches.open(CACHE);
  const missing = [];
  for (const asset of [DOCUMENT, ...BUNDLES]) {
    try {
      await cache.add(asset);
    } catch (refused) {
      missing.push(asset);
    }
  }
  return { build: BUILD, missing };
}

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      // Only this application's caches, and only the builds that are not this
      // one: `caches` is shared per origin, and deleting by prefix rather than
      // by « everything but mine » is what keeps a neighbour's cache alive.
      if (name.startsWith("tm-shell-") && name !== CACHE) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

// The page asks for the swap; the worker never takes it. That is what
// `registerType: 'prompt'` means, and it is the half a worker owns.
self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") {
    self.skipWaiting();
    return;
  }
  if (event.data === "cache-shell") {
    // The reply goes back down the port the caller opened, so a caller that
    // wants to know can wait and one that does not can ignore it.
    event.waitUntil(
      completeShell().then((report) => event.ports[0]?.postMessage(report)),
    );
  }
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (NEVER(url) || url.origin !== self.location.origin) return;

  // A NAVIGATION GOES TO THE NETWORK FIRST. This is the line that keeps a
  // design host honest: whoever can reach the server sees today's prototype,
  // and the cache answers only when the network does not.
  if (event.request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        return await fetch(event.request);
      } catch (unreachable) {
        const cache = await caches.open(CACHE);
        return (await cache.match(DOCUMENT))
          || (await cache.match(OFFLINE))
          || Response.error();
      }
    })());
    return;
  }

  // EVERYTHING ELSE IS CACHE-FIRST, and it is safe precisely because the
  // bundles carry content hashes: a name that is in the cache is the same bytes
  // it has always been, so there is nothing to revalidate. A build that changes
  // them changes their names, and the new names miss and go to the network.
  event.respondWith((async () => {
    const hit = await caches.match(event.request);
    if (hit) return hit;
    try {
      return await fetch(event.request);
    } catch (unreachable) {
      return Response.error();
    }
  })());
});
