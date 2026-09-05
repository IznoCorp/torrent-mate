# Phase 06 — `data-cancelsetting`: the move

## Objective

The reader moves from the engine's delegation into `features/settings/`. The verb's NAME does
not change, the markup that emits it does not change, and phase 05's rule reads it green with
**the same assertion count**.

## What changes

- The branch at `legacy.js:9578` calls the feature's verb through a seam the settings feature
  publishes, and the logic — which edit is dropped, and the redraw — lives in the feature.
- `SETTINGS_STATE.modifs` is still the engine's object (phase 04 said why); what moves is the
  DECISION about it, which is the feature's.

## The proof

Phase 05's hold, unchanged, green — and its assertion count compared to the number phase 05
recorded. **A count that moved means the rule was edited to agree with the move**, which is the
defect the two-phase shape exists to prevent.

The mutation is re-run against the NEW reader:

```bash
sh scripts/mutate.sh frontend/maquette/design/src/features/settings/<the new reader> \
  '<the branch disabled>' frontend/maquette/harness/settings.py
```

Red, naming the same defect as phase 05's mutation did. Restored.

## Gates

The oracle at zero divergence · `settings.py` · `--contracts` · the size arm re-recorded.

## Verdict

**Landed.** The reader is `features/settings/panel-setting.ts`'s, beside the panel that offers
the verb. The delegation branch keeps the verb and is one line.

### The count

| | Holds | Result |
| --- | ---: | --- |
| phase 05, engine's branch, unmutated | 53 | green |
| phase 05, engine's branch mutated | 53 | **3 fell** |
| phase 06, moved reader | **53** | green |
| phase 06, moved reader mutated (`window.__settingsVerbs` publication removed) | 53 | **the same 3 fell, naming the same defect** |

**Unchanged in count, both ways.** That is what the two-phase shape exists to establish.

### What did NOT move, said rather than inferred

`SETTINGS_STATE` is still the engine's map; what moved is the DECISION about it. The redraw and
the message go through seams that die with the engine. The 200 ms wait is the panel's exit and is
unchanged — shortening it is a behaviour change and this is a conversion.

### One word entered the vocabulary

`cancelsetting`. The arm caught it in this phase's own PROSE and is right to: a name written
anywhere must be a name this codebase uses. It had never been read before, because the engine
only ever spells it `dataset.cancelsetting` and the arm looks for the literal `data-…` — a scope
that had a hole exactly where the verb lived.
