# Phase 4 — The seam

## Scope

- `frontend/maquette/design/src/mocks/index.ts` — installs the mock `fetch` and publishes the
  driving surface.
- `frontend/maquette/design/src/mocks/router.ts` — matches method plus path template to a handler.
- The boot branch in `app/` that installs it, behind a build-time flag.

## The shape

One module replaces `globalThis.fetch` with a function that resolves the request against a handler
table and returns a real `Response`. No service worker (D-L08-2). A request no handler claims is a
**failure that names itself** — never a pass-through to the network, and never a silent empty
object: a mock that answers something to everything is a mock that hides a missing handler.

## The build flag

The mocks must not ship at switchover. They sit behind a Vite `define` constant and a dynamic
`import()`, so a false flag removes them from the bundle rather than merely skipping them. The
flag is true today; the point is that turning it off is one edit and provably removes the code.

## The boundary

`mocks/` is imported by `app/` alone and imports no feature (D-L08-10). The arm that holds it
lands in phase 8, with the rest of the guards — but the tree is built to satisfy it here, so the
arm is written against a tree that is already right rather than against one it has to correct.

## Done when

- The seam installs, and an unclaimed request fails naming its method and path.
- The build with the flag off contains no seed byte: a `grep` over `dist/` for a value only a seed
  holds finds nothing.
- ACC-01, ACC-02, ACC-03 green. The oracle must still read 0 divergence: nothing fetches yet.
