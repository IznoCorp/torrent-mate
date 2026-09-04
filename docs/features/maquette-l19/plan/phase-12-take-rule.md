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

*(filled when the phase lands)*
