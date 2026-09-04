# Phase 12 — `data-take`: the rule, on the engine's side

## Objective

**No rule reads this verb today** — `grep -ln 'data-take' frontend/maquette/harness/*.py`
returns nothing. The rule is written FIRST, against the engine as it stands, and seen RED under a
mutation of the engine's own branch.

## What the verb does today

EMITTED by React (`features/releases/releases-screen.tsx:113`) and READ by the engine
(`legacy.js:9889`, through the 260 ms site at `:10255`): it closes the panel, waits, and runs
`actionTake(title)` — the arrivals' « Récupérer maintenant ».

**The two ends are in two worlds**, which is why it is one of the two verbs this lot moves: a
contract with an emitter in React and a reader in the engine is a contract nothing holds.

## The rule

`harness/actions.py` gains a hold that walks it: a real tap on the take control, the item leaving
the takeable set, and the interface saying so. It reads the ITEM, not the toast alone — a toast
is a message and a message can be right about nothing.

## The mutation, seen red BEFORE anything moves

```bash
sh scripts/mutate.sh frontend/maquette/design/src/engine/legacy.js \
  't.replace("if (closest.dataset.take)", "if (false && closest.dataset.take)")' \
  frontend/maquette/harness/actions.py
```

Red, naming the item that stayed. The assertion count is written into this file; phase 13 reads
the same count, green.

## Verdict

**Landed.** R123 — `harness/take.py`, 8 holds — written against the engine before anything moved.

### It did not need a mutation: it was RED on the code as it stands

That is the strongest form of « seen red first » this repository asks for, and what it found is
**B-309, a live defect nobody had ever measured**:

```
window.__panel.produce("follow", "The Hawk")   → « Récupérer maintenant » is offered
click on it                                    → "Cannot read properties of undefined (reading 'res')"
takeable ['The Hawk','Backrooms'] → ['The Hawk','Backrooms']    — nothing moved
```

The document has TWO branches for `data-take`. The release screen's is checked first and carries
no guard, so it swallows the one a medium's panel emits — where the value is a TITLE.
`Number("The Hawk")` is NaN, the lookup answers undefined, reading `res` throws. The panel's own
branch, further down, was unreachable dead code.

**Why nothing caught it**: `grep -ln 'data-take' harness/*.py` returned nothing. Emitted by React,
read by the engine — a contract with two ends in two worlds and no reader at all. That is what
the brief meant, and this is what it cost.

### What the rule reads

The STATE, not the message: the medium leaves what is waiting and joins what is in flight. A
toast can be right about nothing. **And the release screen's own take**, because the two share an
attribute and a repair that fixed one by breaking the other would leave a one-sided rule green.

The assertion count is **8**. Phase 13 reads the same number.
