# Phase 31 — « Comptes » — assigning a role, escalation-guarded

**New phase, born of round 9 Q14 and M7.** Phase 30 set a role's OWN rights; this phase assigns ONE role to an
account (ruling 20's precision, verbatim « 1 seul ») and carries the escalation guard the operator asked to be
MEASURED here: « si on peut faire A simplement je préfère, sinon B … condition : le dessin de L18 le mesure à une
phase au plus (≤ 15 points) ; au-delà, B sans nouvelle question. »

**Opening measure — re-take at this phase's own opening. This measure IS the answer to round 9 Q14**: if it
reads ≤ 15, reading A (below) stands as drawn; if it exceeds 15, the phase reports the figure and falls back to
reading B (« managing accounts = Admin only », no escalation logic built) with no new question, per the ruling's
own instruction.

- **Points ≈ 12 (reading A).** the role picker on an account's row, ≈ 15 new lines (2) + the subset-inclusion
  check — a manager's own role's rights must be a SUPERSET of the assigned role's, a pure function with its own
  unit rows (3) + greying the picker's options that fail the check, and the manager's OWN role option, on screen
  (2) + the backend-refusal hold (the guard refuses server-side too, never client-trust-only) (2) + **M7's
  extension**: an Admin-role account is never a valid TARGET for a non-Admin manager, to view or to change (1) +
  R-L18-u's escalation mutation (« a non-Admin manager assigns a role outside their own role's rights → falls »;
  « a non-Admin manager touches an Admin-role account → falls », M7) (2).
- **If this measure exceeds 15 (reading B):** drop the subset-inclusion check, the greying, and M7's target guard;
  keep only `accounts.manage` gating the whole page, Admin-only by default, said plainly on the page itself. The
  phase then costs ≈ 6 (the picker alone, no escalation logic) and the plan's next phase renumbers by however many
  points the drop frees, reported to the steward.

**DESIGN § 3.9 (« Escalation »), § 5 (R-L18-u extended), M7.** **Reading A is chosen at this document's own
writing time** (§ 3.9 records the estimate — 8–10 points there, refined to ≈ 12 here once the greying and the
backend-refusal hold are counted in full); the PHASE'S OWN re-measure at its literal opening is what actually
decides, per the ruling's own words, and this file's clause above is not a suggestion — it is the fallback the
ruling names.

## Red today

No role-assignment operation is refused for any reason; a manager could, if the operation existed unguarded,
assign Admin to any account or touch an Admin account's own role.

## Move

The picker, the subset check, the greying, the backend guard, M7's target check.

## Mutation

A non-Admin manager assigns a role whose rights exceed their own → falls; a non-Admin manager modifies their own
role through this picker → falls; a non-Admin manager opens or changes an Admin-role account's assignment → falls
(M7).

## Register

—

## Oracle: states that diverge, declared by name

**`accounts-escalation-greyed`** is new (reading A only). Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): assigning a role is escalation-guarded — a manager grants no more than their own`
