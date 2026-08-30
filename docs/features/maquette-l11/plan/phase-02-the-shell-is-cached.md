# Phase 2 — The worker precaches the shell (P7)

## What lands

- `frontend/maquette/design/sw.js` — the worker, a source the build substitutes into.
- `frontend/maquette/design/vite.config.mjs` — one build identity, three consumers: the bundle
  (`__BUILD_ID__`), the worker's cache name, and `dist/build.json`.
- `frontend/maquette/design/src/lib/platform-network.ts` — `askTheHost()`, the named seam past the
  mock layer.
- `frontend/maquette/design/src/app/worker-registration.ts` — the update discipline, and the
  shell's completion.
- `frontend/maquette/installable.py`, `serve.py` — the worker is read from `dist/`, and
  `/build.json` exists.
- `frontend/maquette/harness/run.sh` — the served copy gets `sw.js` and `build.json`.
- `frontend/maquette/harness/pwa.py` — R52 re-aimed, **R105** written.
- `README.md` — the amended decision.

## What the host taught, measured rather than reasoned

The design is not the one this phase started with, and every change came from a reading:

1. **`set_offline` does not reach a service worker's own requests in Chromium.** P7 measured that
   way is green because the *network* answered. R105 raises a scratch server on a kernel-chosen
   port and **stops** it — never the shared host on 8899, which seven other rules are reading.
2. **The mocked `fetch` answers every same-origin path**, 404 « no mock route » for one it does not
   know. An in-page probe for « is the host gone? » therefore comes back with a *Response*. The
   probe goes through Playwright's own request context; the freshness poll goes through
   `askTheHost`.
3. **`/` answers 401 on the gate** — the login page is served *with* that status — and so does
   `/vite/*`. So nothing is required-cacheable at install, and the shell is completed by the
   running application. The obvious design produces one symptom: « the service worker never became
   ready ».
4. **`clients.claim()` fires `controllerchange` on the first visit**, so an unguarded
   reload-on-swap reloads the application in the middle of every measurement in the suite.

## Done when

ACC-05 (P7), ACC-06 (`/api/*` never cached), and `pwa.py` green — **38 holds, 0 failures**.
