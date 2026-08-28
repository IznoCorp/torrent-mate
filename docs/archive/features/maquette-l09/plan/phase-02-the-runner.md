# Phase 2 — The unit-test runner, and the pure functions

**The debt is L04's, handed here deliberately.** The maquette has no runner: every proof is a
browser rule, so a pure function is proved through a browser. L04 measured **11** pure functions
worth testing; the meatiest is `epState` — **8 branches**, touched today by **3 assertions in one
browser rule**.

## What lands

- **Vitest**, reading the maquette's own Vite configuration — so the aliases, the TypeScript
  setup and the `__MOCKS_BUILT_IN__` replacement are the real ones and not a second declaration.
- `npm test` in `design/package.json`, wired into `make check` and into the CI job that already
  runs the maquette's gates.
- Tests where L04's target tree reserved them: `features/<domain>/*.test.ts`, `lib/*.test.ts`.

## Which functions, and why those

The pure, browser-free ones — `lib/addresses.ts` (`screenParentOf`, `isScreenPath`,
`withoutPanel`, `withPanel`, `dialsOfPage`, `addressOf`, `destinationOf`),
`lib/served-identity.ts` (`servedIdentityLines`), `mocks/router.ts` (`match`, `resolve`), and
`epState` once it leaves the engine at phase 9.

`mocks/router.ts` is the highest-value of them and it is not on L04's list, because it did not
exist then: `resolve` throws on an ambiguous table, and `match` decodes a malformed segment
without throwing. Both are branches no browser rule reaches.

## What makes these tests NON-vacuous

**They assert against a committed artefact, never against the code under test.** The seeds are
extracted from `legacy.js` and held byte for byte by `check-mock-seeds.py --arm correspondence`.
A test that imported the projection and asserted what it returns is B-075's shape said for tests,
and it is exactly why this debt waited for L08.

## It is collectable without a browser

B-077 cost a wave: a test of the browser-free half of a rule could not be collected without one,
CI caught it, no local gate did. **Verified by running the suite with no browser binary
reachable**, not by reading the imports.

## The rule that bites

The mutation is on the runner's wiring, not on a test: remove a test file's registration from the
glob and confirm `make check` reports a smaller count rather than staying green — a runner that
silently collects nothing is the vacuity this phase exists to end.

## Done when

- `cd frontend/maquette/design && npm test -- --run` passes, and prints its test count.
- The same command runs with no browser available.
- `make check` runs it, and its count is asserted rather than merely printed.
- `python3 frontend/maquette/oracle.py --check` → `no divergence`. Nothing rendered changed.
