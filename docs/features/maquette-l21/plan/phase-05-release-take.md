# Phase 5 — The release screen's take (B-323, B-322)

`legacy.js:9295` asks the arrivals door — `window.__arrivalsVerbs?.take(…)`, which answers the
panel's TITLE take since B-309. `:9296-9308` is the engine's own INDEX branch behind it:
`releases()[Number(…)]`, `bridge.back()`, a **260 ms** wait, `actionTake`, and a toast.

## Two defects, and they are not one

- **B-323** — the branch is still the engine's, with its own `setTimeout(…, 260)`.
- **B-322** — **the take says TWO sentences.** `actionTake` toasts « … récupéré — suivez-le dans
  « En vol ». » and the delegation toasts « « res src lang » retenue — récupération lancée. » Two
  writes into one `#toast` element: the second overwrites the first, and which one the operator
  reads is a race.

## The rules FIRST

- **B-322's hold is new and it SAMPLES THE TOAST ELEMENT ACROSS THE GESTURE.** A hold reading it
  only at the end sees one sentence whether one or two were written — that is the whole defect,
  and a rule that cannot see it measures nothing. Red against `main` with no mutation: two writes
  are observable there today.
- **R123 (`take.py`) stays green with its count unchanged.** It holds both takes and walks the
  release screen. The two branches share an attribute, so a repair that fixed one by breaking the
  other would leave a rule reading only one side green — R123 reads both, which is why its count
  must not move.

## The move

The releases feature gets its own door — **`features/releases/verbs.ts`** — deciding the same way
the arrivals door does: **by asking whether the value is its own**, never « is it a number? ».
That was refused once already as a rule about spelling, and it is refused again here: `2012`,
`1917`, `300` are titles. The release screen's door asks its OWN offered list.

- The 260 ms wait is gone; the act happens in the tap's own commit.
- The take says **ONE** sentence. Which one it says is drawn from what the operator needs to know
  after taking a release, and it is one write into `#toast`.
- `grep -c "closest\.dataset\.take" …/legacy.js` reads **0**.
- The ledger re-records DOWNWARD in the same commit.

## B-323's instrument half — taken here, because this phase touches the inventory

`harness/exits.py` names the engine's `setTimeout(…, 260)` sites in its own comment and counts
them with `grep -n "setTimeout(.*260)"` — **a command that sees a site only when its call and its
delay share a line**, which is how two went uncounted. This phase removes one of the seven, so it
takes the debt § 5 assigns:

1. **Re-take the inventory with `grep -n ', 260)'`.**
2. **Name all six that remain by the call they wrap** — including the `add:` identify branch
   (`actionResolve` after `bridge.rewind`), the one nobody had named.
3. **Say in the comment WHICH COMMAND counts them**, so the next reader can re-take it.

**R103 is NOT widened into a blanket refusal.** Five of the six remaining are L13's, and the rule
against the wrong subject was refused once already.

## Gate

`run.sh --contracts`; B-322's hold green; R123 green with its count unchanged; `exits.py` green
with its inventory re-taken; the ledger down.

## Commit

`fix(maquette-l21): the release screen's take leaves the engine, and says one sentence`
