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

*(filled when the phase lands)*
