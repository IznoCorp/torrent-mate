# Phase 4 — The five acts of acquisition leave the engine

Carried here by L19 and ratified by the operator on 2026-09-05. Their EMITTERS are React already;
only the READER is the engine's. **Moving a verb is moving its reader onto the seam's owner and
deleting the engine's branch and body.**

| Act | Emitter | Engine branch | Engine body | Seam |
| --- | --- | --- | --- | --- |
| `follow` | `panel-suggestion.ts` (+`sugidx`), `media-details.tsx` (+`fkind`) | `legacy.js:9138` | `actionFollow` `:5567` | `__followActions.add` |
| `dropsug` | `panel-suggestion.ts` | `:9132` | `dismissSug` | the deck's store |
| `sugmore` | `discover-feed.ts:107` | `:9110` | inline | `__refillSuggestions` |
| `pause` | `follow-actions.ts` | `:9250` | `actionPause` `:5532` | `__followActions.setStatus` |
| `remove` | `follow-actions.ts` | `:9256` | `actionRetirer` `:5556` | `__followActions.remove` |

## The rules FIRST — one per act, each red against the engine's branch under mutation

What R123 reads for the take, transposed. **The STATE moves**, no error is raised, **and the undo
puts it back**:

- **pause** — the follow reads `disabled` in the follows cache AND on the row (the state moved
  against what it was before, never a word the rule chose: `actionPause` toggles).
- **remove** — the follow is absent from the cache and the row is gone.
- **follow** — the follow is at the head of « Suivis », marked new.
- **dropsug** — the suggestion is gone from the deck **AND from the cache the deck reads**. One
  without the other is a card that comes back on the next render.
- **sugmore** — one press adds **thirty** and the reserve is intact (B-315 (b)). The end mark on
  `acq-discover-exhausted` says the reserve is spent, and the rule reads it there too (B-315 (c)).

  ⚠ **« this phase gives it one in `engine/states.js` » IS STRUCK — the subject is gone** (§ 7.1:
  a directive whose subject has gone is removed, not executed). `[data-sugmore]` is indeed
  reachable from no state, and a state CANNOT be added: `states.js` is grandfathered at 786
  non-blank lines and the size arm refuses the growth — « A grandfathered file is one that may not
  be EXTENDED; subtract the addition, or record the growth here with the decision that allows it »
  — and then refuses the record itself — « A grandfathered file's record may only go DOWN: raising
  it legalises the growth in the same commit that commits it, which is the ratchet refusing
  nothing ». Both were measured on this branch and reverted. **So the rule BUILDS the spent pile
  itself** (`window.__store.write({ sugMode: "deck", sugGone: … })`) and holds the button's
  DRAWING by its own geometry — its rectangle inside the viewport, not covered at its centre, its
  label read — because the oracle cannot see a state nobody named. The price is FILED rather than
  absorbed: B-352, owner L13.

**Seen red how**: the branches still exist, so each rule is written against the engine and
mutation-tested there — `scripts/mutate.sh` on the engine's branch, confirm the rule falls and
NAMES THE RIGHT DEFECT, restore. Commit before every mutation (B-303).

## The move

- **New files** `features/acquisition/follow-verbs.ts` (pause, remove, follow) and
  `features/acquisition/deck-verbs.ts` (dropsug, sugmore). The deck's two are the discover
  surface's; pausing a follow is not the deck's business. Neither goes in `lib/queue.ts` —
  invariant 10's one tolerated line holds ONE resource, the queue, and a verb on a follow is not
  the queue's.
- **The 240 ms wait goes with the branch.** `setTimeout(() => actionPause(pause), 240)` and the
  same for `actionRetirer` — two of the six `, 240)` sites, B-249's shape. The panel leaves inside
  the navigation's own commit since L12, so the act happens in the tap's own commit, as
  `features/arrivals/verbs.ts` already does.
- **The UNDO moves with the verb it undoes.** `toastUndo` (`legacy.js:8023`) offers to put the
  follow back and calls the seam again. `queries.ts`'s header says « the undo is the engine's and
  it stays » — true while the verb was the engine's; **that sentence is corrected in the same
  commit**.
- **The seam empties.** When the last engine caller of `__followActions` goes, the `declare global`
  goes with it — product code reads no `window.__` at L13. `all()` is read by `busy.py` and by the
  engine's `follows()`; whichever survives is NAMED in the report, never removed blind.
- **`legacy.js` shrinks**, and `scripts/frontend_size_ledger.py` re-records DOWNWARD from 31 591 in
  the same commit as each subtraction.

## B-316 and B-315 (a) — the operator ruled on 2026-09-06, and both are now IN

**STOP A is lifted.** On Découvrir's poster tile `data-panel="sug:N"` and `data-mediasheet` sit on
the SAME node; on the deck card the media verb is on the tile's child — so the media SCREEN opened
on all ten finger points and the suggestion panel was reachable by no finger at all. The operator
chose **reading (i)**:

- **A TAP opens the media sheet**, on the poster tile and the deck card alike.
- **A LONG PRESS opens the suggestion panel** — « Ajouter / Voir la fiche / Pas intéressé » —
  **reusing the gesture the library's rows have carried since L14, not a second mechanism.**
- **The two attributes stop sharing a node.**

**The rule, seen red first**: a finger path on BOTH card kinds — tap → the sheet, with
`panelOpen: false`; long press → the panel produced, its three actions counted BY LABEL. Red on
`main`, where the long press raises nothing. B-316 reads `fixed` under it. The oracle's divergence
on those states is accepted with B-316 as its reason (D8).

**B-315 (a) is now this wave's too** — « Adapte la taille du bouton » (the operator dictates the
amendment). Découvrir's « charger 30 de plus » button is drawn **at the scale the component
catalogue already gives a secondary action in a feed footer** — its `variants.ts`, never a new
size. The state is named, the oracle divergence is accepted with B-315 (a) as its reason, and the
report says what it read BEFORE and AFTER with the command that read it. The operator judges it on
his phone through the design host; **a divergence on any other state stays a defect.**

## Gate

`run.sh --contracts`; five rules green; `grep -cE "closest\.dataset\.(follow|pause|remove|dropsug|sugmore)\b" …/legacy.js` reads **0**; the ledger re-recorded downward; the oracle diverging only where a panel gained or lost nothing visible — a divergence on an untouched state is a STOP.

## Commit

One per act where the act is separable, so a bisect names the verb. Minimum: one for the deck's
two, one for the follows' three.
