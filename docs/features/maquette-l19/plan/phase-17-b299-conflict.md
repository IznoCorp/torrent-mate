# Phase 17 — B-299: the version conflict draws

## **This is a BEHAVIOUR phase. It is alone in its commit, and its rule is seen RED first.**

## Objective

`SettingsState.conflict` (`features/settings/reference.ts:55`) and `mocks/state.ts:135,187`
declare it and set it `false`. **Nothing raises it, nothing draws it, no `fr.json` key names
it** — `grep -c "conflit" frontend/maquette/design/src/i18n/fr.json` → 0. The copy names « three
banners » and draws two.

Production answers **412** on `PUT /api/config/files/{name}` when the file changed under the
editor.

## What changes

- **The mock answers that shape, seeded from the CONTRACT** (`contract/types.d.ts`), D7 — no
  backend work: a 412 the backend already answers is mocked from its shape.
  **In a NEW file under `mocks/`, never in `mocks/stream.ts`**, which stands at 399 of 400. A
  single added line there is a red gate in this phase.
- The banner draws **from the query's error**, not from a flag someone remembers to set — a flag
  set beside the failure is a second source for one fact, and `conflict` being declared-and-never-
  raised is what that costs. Whether `SettingsState.conflict` survives as a derived read or is
  deleted is decided here and recorded, not left declared and dead a second time.
- It offers **reload**, which is the only honest verb: the editor's copy is stale and there is
  nothing local to keep.
- The copy lands in `fr.json`.

## The rule that bites — RED FIRST

Written and run **before** the banner exists, against the tree as it stands: it drives a save
over a mocked 412 and reads the banner. **It must fall, and name the absence.** That reading is
written into this file before the repair.

Then the repair, the rule green, and the mutation:

```bash
sh scripts/mutate.sh frontend/maquette/design/src/features/settings/<the banner's reader> \
  '<the error branch removed>' frontend/maquette/harness/settings.py
```

Red again, naming the same absence. Restored.

## Gates

The oracle — **a new banner is a new drawing, so a divergence HERE is expected and is described
state by state**, unlike every conversion phase in this plan · `--a11y` on the states that gain
the banner · `--contracts`.

## Verdict

*(filled when the phase lands)*
