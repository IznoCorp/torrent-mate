# Phase 20 — The per-instance seeds, and the ceiling's reason

**New phase, born of ruling 23** (« le plafond d'instance de L18 devient une liste d'écritures interdites par
instance »). Phase 19 built the mechanism (a served list, subtracted from every role); this phase supplies the
two lists the mock will dial between, and the banner/Profil text that names a PARTIAL list specifically rather
than a generic « lecture seule ».

**Opening measure — re-take at this phase's own opening:**

- **Points ≈ 8.** two named seeds — `forbidden-writes: "all"` (a sentinel meaning every write right, computed
  dynamically rather than enumerated — the current `:8711` instance's own case) and `forbidden-writes:
  ["library.delete"]` (preprod's, ruling 23 precised: preprod writes INTO the prod library — replace, merge, NFO
  rewrite — only explicit deletion is forbidden) (2) + the banner's reason text, naming the forbidden right(s) by
  name rather than a blanket phrase, with a branch for the partial case (2) + Profil's own reason line reusing the
  same text (S8, phase 22 — declared here, read there) (1) + two named states, `ceiling-preprod` (new seed) and
  `settings-read-only` re-driven onto the list dial (3).
- **What to cut if the opening measure exceeds 15.** Not expected — this phase adds seeds and text, no new
  mechanism.

**DESIGN § 3.7, § 3.8's forbidden-writes reason, ruling 23.** This lot draws the MECHANISM and these two
illustrative lists; which served instance answers which list is the backend's, not drawn here (§ 7.1).

## Red today

No forbidden-writes list is served anywhere; the mock's dial (phase 19's `setForbiddenWrites`) exists but has no
named seed to turn it to beyond an empty list.

## Move

The two seed lists; the banner and Profil's reason text, branching on whether the list is total or partial.

## Mutation

Serve a partial list and let the banner still say « lecture seule » unqualified → falls (the reason must name
`library.delete` specifically when that is all that is forbidden).

## Register

—

## Oracle: states that diverge, declared by name

**None** — `ceiling-preprod` is a new state. Any divergence elsewhere is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the two instance seeds and the ceiling's specific reason`
