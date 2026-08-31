# Phase 3 — `/build.json` and the update discipline

## What lands

- `frontend/maquette/harness/freshness.py` — **R106**, four holds.
- `frontend/maquette/design/src/app/worker-registration.ts` — the latch that outlives the reload.

## The defect the rule found, in the code the rule was written for

R106's third hold read **fifteen loads** where it expected two. `reloading` is module state and a
reload *replaces the document*, so the flag was false again on the way back in: the page booted,
compared, still saw a different served build, and reloaded — forever. A reload loop on a design
host is indistinguishable from a host that is down, and it is the only failure this discipline can
produce that is worse than the staleness it exists to prevent.

The latch is `sessionStorage` now: **one reload per served build**. If the page comes back still
not matching, convergence has failed and that needs a person, not another reload. Session and not
local storage — a new tab, or the same one tomorrow, is entitled to try again.

## Why the rule serves its own copy

It has to make the served build MOVE, and the honest way is to change what a server answers with.
Doing that to `/tmp/tm-refonte` would rewrite the copy every other rule is reading — **B-256
exactly, committed by the rule meant to catch it.** It duplicates the copy onto a scratch port.

## Done when

ACC-08 (one reload), ACC-09 (the signal survives a dirty tree). R106 — 5 holds, no violation.
