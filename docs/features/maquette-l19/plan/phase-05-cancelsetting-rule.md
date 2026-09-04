# Phase 05 — `data-cancelsetting`: the rule, on the engine's side

## Objective

**No rule reads this verb today** — `grep -ln 'cancelsetting' frontend/maquette/harness/*.py`
returns nothing. So the rule is written FIRST, against the engine as it stands, and seen RED
under a mutation of the engine's own branch. **A rule written after the move proves only that it
agrees with the move.**

## What the verb does today

Emitted at `legacy.js:7607` (the setting panel's « Annuler » action) and read at `:9578`: it
drops the pending edit for that setting id out of `SETTINGS_STATE.modifs` and redraws.

## The rule

`harness/settings.py` gains a hold that walks the operator's own path:

1. `__go("settings-field-text")`, read the field's value;
2. edit it, read the « modifié » mark and the pending edit's presence;
3. tap « Annuler » — a real tap, not `__go`;
4. read the value back at its FILE value and the mark gone.

It asserts the pending edit is dropped **for that setting only**, which is the half a cheaper
hold would miss.

## The mutation, seen red BEFORE anything moves

```bash
sh scripts/mutate.sh frontend/maquette/design/src/engine/legacy.js \
  't.replace("if (closest.dataset.cancelsetting)", "if (false && closest.dataset.cancelsetting)")' \
  frontend/maquette/harness/settings.py
```

The hold must fall and NAME the setting whose edit survived. The assertion count is written into
this file: phase 06 must read the same count, green.

## Gates

`--contracts` · the hold alone, on a quiet machine.

## Verdict

*(filled when the phase lands)*
