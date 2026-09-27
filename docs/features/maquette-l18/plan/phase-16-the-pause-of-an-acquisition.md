# Phase 16 — The pause preference of an acquisition

**New phase, born of round 10 Q6's precision** (the operator, verbatim: « l'accès aux réglages de qualité est un
droit tout de même […] Même lecture pour la pause : c'est un droit, et « tous » s'entend de tous les demandeurs
qui l'ont »). Same shape as phase 15's quality override, kept as its own phase rather than folded in, to hold each
at or under the 15-point ceiling.

**Opening measure — re-take at this phase's own opening:**

- **Commands.** `python3 -c "import re;print(len(re.findall('pause',open('frontend/maquette/contract/openapi.json').read(),re.I)))"` — expected 0 before this phase's own contract edit (phase 1) lands, confirming no prior `pause` operation exists to collide with.
- **Points ≈ 10.** the quality screen's own write pattern, reused for pause — a toggle rather than a profile
  picker, so less markup (≈ 20 new lines, 2) + `setAcquisitionPause`'s call wired (1) + the « all holders paused »
  computation, a small pure function with its own unit rows (2) + R-L18-l-bis with its mutation (3) + one named
  state re-using a seed (`pause-own-offered`) and one needing a new seed row (`pause-own-absent`) (2).
- **What to cut if the opening measure exceeds 15.** Drop the unit rows to a table already covered by phase 15's
  own quality unit table, reusing its harness rather than writing a second one (−2).

**DESIGN § 1.2 (`acquisition.pause.own`), § 3.4 point 5, § 5 (R-L18-l-bis).** Offered on one's own requested
acquisition, under the right; « paused » holds only when EVERY requester who holds `acquisition.pause.own` has
asked for it — a requester without the right is simply not counted, in either direction.

## Red today

No pause preference exists on any acquisition; the acquisition's own paused/not-paused state, if any, is read
from nowhere a requester can set per-account.

## Move

The screen's toggle, `setAcquisitionPause`'s call, the all-holders computation.

## Mutation

Count a right-less requester's absence as a "no" that blocks the pause → falls (the requester was never asked, so
their silence must not count against those who were); drop the right check and let anyone set the pause → falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** — no existing state reads a pause preference. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): a per-acquisition pause preference, role-gated, effective only when every holder asks`
