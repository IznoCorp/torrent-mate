# Phase 04 — Settings: a secret and a setting

## Objective

`openSecret` (`legacy.js:7520–7564`) and `openSetting` (`:7569–7619`, four callers) move to
`features/settings/panel-secret.ts` and `features/settings/panel-setting.ts`, kinds `secret` and
`setting`, the second addressed `setting:<id>`.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- The settings block is ALREADY React: `features/settings/panel-field.tsx` registers the field
  block. What `openSetting` still does is build the descriptor that names it — the same shape as
  the seasons block, and the precedent the plan calls « a feature ADDS a block kind ».
- **The shell's existing line `import "../features/settings/panel-field"` changes TARGET, not
  count**: a `features/settings/panels.ts` imports the field block and both producers.
- `SETTINGS` and `SECRETS` are cached by `features/settings/queries.ts` already
  (`["/api/config/schema"]`, `["/api/config/secrets"]`). `SETTINGS_STATE` is the engine's own
  MUTABLE object, written by the delegation and read on every store bump — **it is not server
  state and it does not move here.** It moves with the last delegation verb that writes it,
  which is L13's. Said so rather than half-moved.
- A secret's VALUE is never read back and never drawn. The panel says which keys exist and
  whether each is defined — unchanged, and the rule below reads it.
- R100 hold (f) gains `settings-field-text` and `settings-secrets`.

## The rules that bite

`harness/settings.py` gains a hold that the secret panel names no value; `producers.py` gains the
two kinds. The mutation makes the secret producer put `secret.v` in the descriptor and the hold
must fall naming the key it leaked.

## Verdict

*(filled when the phase lands)*
