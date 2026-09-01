# Phase 3 — The arbitration moves

**Kind: CONVERSION.** Nothing a finger does changes. **The oracle is green at zero divergence and
that is this phase's proof** — but the oracle proves only that no pixel moved, so the driven rule
below is what proves the *gesture* survived (§ 6's newest trap).

## What moves, and what does not

`legacy.js:8102`–`8232` holds the press / drag / scroll arbitration. It becomes
`lib/press-arbitration.ts` — **vocabulary** by invariant 10.

**What moves** (the arbitration — how a press, a drag and a scroll are told apart):

- `PRESS_MS = 480` and `PRESS_TOLERANCE = 12`;
- `armPress` / `followPress` / `cancelPress` and the pointer listeners;
- the click swallowed **by its point** — a click arrives 1 ms after the lift, so no timer can tell
  it from a deliberate tap;
- the `contextmenu` refusal, with its text-field exemption.

**What does NOT move**: `panelUnderFinger` and `openPanel` are **producers**. They stay, and their
engine-side callers — the deck, the rows — are **L19's** (D5: you subtract, you do not edit).

## Why this is allowed, and the precedent

Moving code **out** of `legacy.js` is a **subtraction**, which is exactly how D5 says the engine
dies. `app/drawer-gesture.ts` set the posture and wrote down why: it installs from the React side
against the node as it stands, and **zero lines are added to the engine**. The engine consumes the
vocabulary; it does not grow.

## The constraint that decides the implementation

**The tolerance must live on the POINTER stream.** Chrome delivers **no `touchmove` at all** for a
drift of a few pixels — a tolerance written on the touch stream would never run. And the converse
is equally load-bearing: a *drag* must be read from touch events, because the compositor fires
`pointercancel` and stops delivering `pointermove` the moment it decides a drag is a scroll. A
pointer-only drag **passed under a real mouse and did nothing at all under a real thumb**
(`drawer-gesture.ts`'s own record, and the engine's before it). **One implementation serves both,
and it reads each stream for what only that stream can tell it.**

## The rule

One rule driving a **real touch stream** (`Input.dispatchTouchEvent`, R55's and `drag.py`'s
discipline) **and a real mouse** (`mouse.py`'s), asserting all four cases: a long press opens the
panel; a 12 px drift cancels it; the click the lift causes is swallowed **wherever it lands**; a
deliberate tap elsewhere is **not**.

**A synthetic event is not a finger** — it is never cancelled, so a rule passing with
`dispatchEvent` alone has proved nothing about the compositor. Two gestures were lost that way.

## Mutation

Raise the tolerance past the drift the rule drives → the cancel case falls. Swallow by target
instead of by point → the « swallowed wherever it lands » case falls, and it must name *that* case.
Restore.

## Done when

`lib/press-arbitration.ts` holds the arbitration; `legacy.js` is **shorter**; the engine and the
React surfaces both consume it; the oracle is green at zero divergence; the rule bit under touch
**and** under mouse.
