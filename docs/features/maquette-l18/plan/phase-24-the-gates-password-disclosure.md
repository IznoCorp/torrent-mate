# Phase 24 — The gate's password disclosure

**New phase, born of F47**: « the password disclosure (OPEN 2 = B): [the first drawing's] mutation refuses the
ruled layout, and nothing opens it when Plex is unreachable. » Phase 23 drew the collapsed structure; this phase
drives its behaviour and wires `auth.password`.

**Opening measure — re-take at this phase's own opening:**

- **Points ≈ 10.** the disclosure's open/close state and its toggle (≈ 15 new lines, 2) + the auto-open on Plex
  unreachable (reads the same answer S1 point 3 already reads, ≈ 10 lines, 1) + `auth.password`'s refusal wired
  to the password form's submit (2) + R-L18-r EXTENDED with the auto-open hold and its mutation (« disclosure
  stays closed when Plex is unreachable → falls ») (3) + two named states, `signin-password-open` and
  `signin-plex-unreachable-open` (2).
- **What to cut if the opening measure exceeds 15.** Not expected at this size; if the auto-open logic collides
  with S1's existing unreachable-line code, fold rather than duplicate (−2).

**DESIGN § 3.1, § 5 (R-L18-r), F47.** The toggle and its collapsed/open states live OUTSIDE `login:markup:start/end`
(in the Plex marker pair and `entry.ts`), so R-L18-q's byte-identity hold on the design host's password page
still passes.

## Red today

No disclosure exists; the password form, once drawn in phase 23, is either always shown or always hidden — never
collapsed-by-default-with-a-toggle, and never auto-opening on an unreachable answer.

## Move

The disclosure's own open/close local state; the auto-open effect; `auth.password`'s gate on submit.

## Mutation

Hide the password form entirely when Plex is offered → the door-of-last-resort hold falls (this is the mutation
F47 asks the first drawing's own phase to stop making); leave the disclosure closed when Plex answers unreachable
→ the new auto-open hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**`signin`, `signin-error`** gain the collapsed disclosure — named, per DESIGN § 4.1. Any other divergence is
STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the password disclosure — collapsed by default, opens when Plex cannot be reached`
