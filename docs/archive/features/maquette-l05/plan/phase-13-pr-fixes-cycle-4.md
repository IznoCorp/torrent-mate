# Phase 13 — PR #484 fixes, review cycle 4

One blocking finding, isolated to a single flag; two sentences that claim more than the code
does. Phase 8's « How this phase runs » applies unchanged.

## 13.1 — `homeFloorExists` is written once and goes stale the moment a floor is laid · CRITICAL

Cold `/nimportequoi` → the escape tap lays the floor (12.1's own fix) — and the flag stays
false, so every later switch takes the no-floor branch: five Médiathèque↔Acquisition round
trips read `history.length 4 → 14` and TWELVE Backs before the guard arms (an ordinary boot:
3 → 4 and one). With the drawer it re-opens 12.2's replace-in-place. Reload restores it —
the stack is right, only the flag lies.

Fix: the flag becomes true at every point a home entry is laid — `switchPage`'s no-floor
branch (the destination IS home there), and `switchPageFromLayer`'s no-floor branch when the
destination is home. Hold in R82: after the 404 escape, two tab round trips — the depth does
not grow, and one Back from `/acquisition` arms the guard. Mutation: the flag never revised →
the hold falls on the depth.

## 13.2 — Two sentences, corrected to what runs · MINOR

- The boot comment says the flag is « read off what the loop above actually did » — it is
  derived from the arrival, before any write, and a refused floor push leaves it true over a
  missing floor (latent: only a broken bridge reaches it). Either read it off the writes'
  outcome (preferred, one line: set it where the floor's `record` succeeds), or say what it is.
  Prefer the code fix — it also closes 13.1's shape at the root: the flag then follows the
  WRITES, wherever they happen.
- R82's docstring and the README row say « every hold reads history.length and armedExit » —
  parsed, 12 of 34 read `armedExit` and one group reads neither. Say what is true per group.
