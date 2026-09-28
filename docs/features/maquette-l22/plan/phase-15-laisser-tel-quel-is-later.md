# Phase 15 — « Laisser tel quel » means later

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `lib/queue.ts:359` `leave` → `settle(title, "left")` (`:312-316`), whose first act is `takeOutOfQueue` —
  the folder is removed from BOTH lists (staging and the acquisition queue) — then `deliver(…)` sends
  `dismissDecision` (`mocks/handlers/decisions.ts:100`). The `leave` verb (moved to Acquisition by phase 2) calls
  `queueActions.leave` and toasts « verbs.arrivals.left ». `now-tab.tsx` after phase 9 has the sections
  `takeable`, `inflight`, `notfound`, `doneToday`. Rules reading the leave path: `decision.py:197-215`, `ident.py`,
  `two_picks.py`, `actions.py:62` (`git grep -n -E 'data-leave|leave' -- 'frontend/maquette/harness/*.py'` at the opening).
- **Found (2026-09-26) — a reader of the behaviour this phase reverses.** **R57** (`decision.py:197-215`) asserts
  « answering empties the queue, on BOTH lists » and includes `arr-idle` / `stuck` / `[data-leave]` in that: the leave half
  is re-aimed (DESIGN § 5.1) — the card leaves « À traiter » and STAYS in acquisition; the pick half is unchanged.
- **Points ≈ 14.** `lib/queue.ts` `leave` / `settle` ≈ 15 lines edited 3; the « Mis de côté » section in `now-tab.tsx`
  ≈ 15 lines written 2; the `leave` verb ≈ 8 lines 2; the mock keeps the card (a held `aside` state with its date, the
  layer's own, not the screen's) 1; two `fr.json` keys 1; R-L22-i with its mutation 3; R57's leave half re-aimed 1; one
  state (`acq-card-set-aside`, re-using a real stuck row — no new seed) 1.

- **Re-measured 2026-09-27 at its opening, on `0d86834fe` (ruling 16, DESIGN § 7.3 item 4):** « Mis de côté » is a folded section at the END of « À traiter », outside its count and the bar's badge, with four acts (see, delete with a confirmation like the library's, gone from disk → gone from the section, handle); `leave` still sends `continueStagedMedia` outcome `left` (`lib/queue.ts:346`, mock `staging.ts:195`), the rung state `aside` is already declared, no staging delete operation exists (`discardStagedMedia` quarantines) and no folded section exists in Acquisition (`ui/disclosure.tsx` is the primitive) → ≈ 29 points; CUT at its opening into **15a** (the card kept aside, the folded section, « Résoudre → », R-L22-i, R57 re-aimed, ≈ 14) and **15b** (« Supprimer » with its confirmation, the card leaving the section, its rule, ≈ 13–15).

Ruling 6: « Laisser tel quel » means LATER. The card stays in acquisition, `aside`, « identifié » pending, reason
« mis de côté par vous, le … », out of « À traiter » and visible in « En cours »; the file stays in transit. It
disappears only by his own reclassification (phase 16). **The operation does not change (`dismissDecision`); what the
interface does with the answer does.**

## Red today

**R-L22-i — « Laisser tel quel » is later**, walked by finger on a real stuck folder: the card is absent from « À traiter »,
present in « Mis de côté » with « mis de côté par vous, le … », and STILL present after a re-read (the mock's state, not the
screen's); its panel offers « Résoudre → » (One card, one behaviour: the panel carries every action).

**Red against `main`**: the card leaves both lists and nothing draws it.

## Move

> **Amended 2026-09-27 (triage F4, F51):** « Laisser tel quel » sends `continueStagedMedia` with outcome `left`
> (`lib/queue.ts`, mock `handlers/staging.ts`) — built so at 15a; `dismissDecision` below is the first drawing's
> reading, kept for the record. 15b's delete is a SEPARATE operation, and 15b is now **phase 23**.

`leave` keeps the card and marks it `aside` with its date; `now-tab.tsx` draws the section « Mis de côté » (a pip of the
« waiting » tone; its name and place adjust to the drawing); the reason is composed from the date, never a constant (§13).
Named state `acq-card-set-aside`.

## Mutation

With the commit made first: restore the old behaviour (the card leaves both lists) → R-L22-i falls.

## Register

—

## Oracle: states that diverge, declared by name

Only the state this phase adds. Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `decision.py`, `ident.py`, `two_picks.py`, `actions.py` re-run by name.

## Commit

`feat(maquette-l22): « Laisser tel quel » sets the card aside instead of removing it`
