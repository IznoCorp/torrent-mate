# Phase 2 — The pages take their paths

**This is the lot.** Eight pages leave `?page=` for a real path, the query keeps the dials, and the
address derivation leaves the engine for the shell — the first subtraction of D5.

## What exists today

`legacy.js` owns the whole address. `urlFromState()` (≈ line 11044) reads six dials off
`currentState()`, drops those at their default, and returns `baseAddress + "?" + query`.
`stateFromUrl()` reads them back. `recordPath()` pushes through `__bridge.record(navigationState(),
urlFromState())`. `baseAddress` is handed in at boot from `shell.tsx:561`, computed as
`matchedRoute ? "/" : location.pathname` — a computation whose whole purpose is to let the engine
own any pathname the router does not, and which therefore loses its subject here.

The router already owns five screen addresses and is the single writer of the history. What this
phase does is put the pages through the same door.

## Steps

1. **Declare the page routes** — one address, one file, under `routes/`, as `arm_one_address`
   already requires. Seven pages plus the catch-all; each route's component stays `null` and the
   `PageHost` keeps portalling into `#view` (who DRAWS is L07/L09's subject, not this wave's).
2. **`/` answers a `replace` redirect onto `/acquisition`.** Never a push: the boot is where R69
   paid two defects, and an extra entry there makes the first Back land on nothing the operator
   recognises.
3. **The route match writes `state.page`.** One direction only — the address is the source, the
   store follows.
4. **Add the shell seam that replaces `urlFromState()`.** It takes *(page, dials)* and calls
   `go({ to, search })` — the function R76 holds to exactly one call site. Dials at their default
   stay absent from the address: R69's hold 1 is kept as it is, and it is the reason a shared link
   carries only what it means to carry.
5. **Subtract from the engine**: `urlFromState`, `stateFromUrl`, `URL_DEFAULTS`, and the
   `baseAddress` plumbing with the `base` computation that fed it. `recordPath()` calls the seam.
   `navigationState()` and `onEngineBack()` STAY — unwinding layers is logic, and this wave takes
   navigation, not decision.
6. **The 404 keeps its promise.** An unknown path renders the not-found page and the address stays
   **exactly as typed**. `state.notFound` now carries the pathname rather than the query value.
   Deriving the address from the 404 state is the defect R69 hold 4 exists for, and it survived one
   fix already.

## The rule that bites — R69, renegotiated

Its five holds are kept; its premise is replaced. The docstring and the `regions.json` entry are
rewritten naming D1 as what replaces them, never quietly edited to pretend the rule always said
this. The sixth hold is new.

| # | Hold |
| --- | --- |
| 1 | the opening address is `/acquisition` and carries no query |
| 2 | walking writes the address — the page in the PATH, the dial in the query |
| 3 | reloading that address lands on the same screen, cold |
| 4 | a wrong address renders the 404 and is left exactly as typed |
| 5 | Back walks the addresses in reverse |
| 6 | **no page identity in a query, and no dial in a path** |

Plus one the redirect earns: after a cold boot on `/`, the history depth is what a single entry
gives — the redirect replaced, it did not push.

**Mutations** (three, from the plan's table): re-add `page` to the page route's search params;
make the route loader ignore its match; derive the address from the 404 state. Each must fall AND
name its own defect.

## Done when

- ACC-07 (R69's six holds), ACC-13 (`urlFromState`/`stateFromUrl`/`URL_DEFAULTS` gone), ACC-14
  (no `page=` outside `data-page`).
- ACC-11 (R76 — still exactly one `navigate()` call site) and ACC-12 (R59/R71/R74 green at
  **unchanged rule code**; ACC-21 proves they were not edited).
- ACC-03, ACC-04, ACC-05 green. **A divergence in the oracle is accepted one by one with a written
  reason, never in a block** — this wave moves navigation, and a rectangle that moved is a question,
  not a formality.
- The three mutations have each been seen to fall and been restored.
