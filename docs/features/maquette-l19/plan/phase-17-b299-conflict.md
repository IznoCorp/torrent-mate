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

**Landed**, alone in its commit, its rule seen RED first (three holds, before the banner existed).

### The brief said 412; the maquette's contract says otherwise

`updateConfigurationFile` answers `{ restartRequired, conflict }` on **200** and declares **409**
for a refusal. « The file moved under the editor » is something the write SUCCEEDS in telling, so
drawing it from an error branch would be drawing it from a case the contract does not describe.
**The contract is the maquette's own artefact (D7)** and it is followed — recorded here rather
than reconciled silently.

### The save had to start asking

`data-save` cleared the pending edits, raised the restart flag and said « Enregistré » **without
writing anything**. A field the contract has always answered had no reader BY CONSTRUCTION. It
writes each changed file now and reads what comes back; a held write (offline) and an empty answer
are passed through rather than flattened — **neither is a conflict, and neither is a promise that
there is none.**

### A conflict does not throw the edits away

The file moved under the editor, so what is on screen no longer describes what is stored. Losing
the operator's work on top of that would be the second loss. Reloading is OFFERED.

### The banners moved to where the operator is

All three were inline in the RUBRIC LIST alone — so a read-only instance said so on the list and
said nothing once a rubric was open, while the save bar that raises the third exists on every
branch. **B-299's banner would have been invisible exactly where « Enregistrer » is tapped.**

### Readings

oracle **2 958, no divergence** (the banner draws on a state no named state reaches, so nothing at
rest moved) · contracts 18 rules + 26 guards, no violation · `settings.py` 53 → **57** holds ·
mutation: the banner's condition forced false fells two holds
