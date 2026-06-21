// Minimal service worker — its sole purpose is to make KanbanMateUI installable as a PWA.
// It deliberately does NOT cache anything: the SPA shell is served no-cache (to kill stale bundles
// after a redeploy) and the /api responses must never be cached. The empty fetch handler is enough
// for the browser to treat the app as installable; every request still hits the network.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {
  // Pass-through: no respondWith() → the browser performs its normal network fetch.
});
