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

**Landed** over two commits — the move, and one hold a mutation proved was missing.

### What moved beyond the two producers

**The settings CATALOGUE is the feature's**, and the engine imports it back:
`settingIdentifier`, `flattenSettings`, `valueShown` in `features/settings/catalog.ts`.
`app/icons.ts`'s arrangement and its reasoning word for word. Leaving them in the engine was the
alternative and §13 refuses it: the producer reads the LAYER's answer while the engine's field
verbs read the FIXTURE, so « what is this setting's identity » would have carried two derivations
that agree today.

`valueShown` takes the pending edits as an ARGUMENT, so nothing in the catalogue depends on where
`SETTINGS_STATE` lives — and it does not move (design § 2; it goes with the last verb that writes
it, L13's).

**`REOPEN`'s `setting` entry reads the feature both ways**, so the addressed-panel table stops
asking the fixture whether a subject exists. `openSetting` leaves the reference slice.

### The fan-in ceiling, hit in one phase

`app/icons.ts` is outside `ui/` and `lib/`, so invariant 8's ceiling of **four features** applies
to it. A producer per feature importing it directly walked it from 3 to **5** in this one phase —
« no god module » arriving exactly where the guard was aimed. The producers read icons through
`lib/engine-drawing.ts`, the door every other drawing helper already uses; same object, and it
dies with the engine. `panel-account.ts` was rewired with them. Back to **3**.

### The mutations

| # | Mutation | Rule | Outcome |
| --- | --- | --- | --- |
| 1 | `settingIdentifier` drops the file half | `producers.py`, `settings.py` | fell 3 + 4 — « drawn 'Nettoyer les disques' · expected 'Espace libre minimal avant une ingestion' »: the panel opened about **another setting entirely** |
| 2 | `valueShown` ignores the pending edit | `settings.py` | **fell NOTHING.** See below |
| 2-bis | the same, after the repair | `settings.py` | fell — « 'Valeur actuelleoui' · pending ['40', 'false'] » |

**Mutation 2 is the phase's finding.** A panel that ignores the pending edit tells the operator
their edit did not take — « Valeur actuelle » showing the file's value while the save bar below
says that file is about to change. `settings.py` walks that very panel and R120 drives the kind,
and neither read the value. The hold reads the two rows TOGETHER, because either alone passes
over a panel showing the same value twice.

### Readings

| Gate | Reading |
| --- | --- |
| **oracle** | 2 958 measurements, **NO DIVERGENCE** |
| `run.sh --contracts` | 14 rules, 26 guards, no violation |
| `producers.py` | 22 holds | 
| `settings.py` | 46 → **48** holds |
| `engine/legacy.js` | 32 376 → **32 287**, re-recorded |
| `engine/states.js` | 790 → **789**, re-recorded |
| `check-frontend-boundaries --arm fan-in` | highest 3, ceiling 4 |

### Deviation

**A fourth shell-list rule appeared and is written into `panel-contributions.ts`**: a feature with
more than one panel gathers its own siblings (`features/settings/panels.ts`) so the boot list
stays one line per FEATURE. The design said « one module per feature is named in the shell »; this
is that sentence made true rather than assumed.
