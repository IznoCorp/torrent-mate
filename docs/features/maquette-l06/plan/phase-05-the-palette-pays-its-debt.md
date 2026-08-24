# Phase 5 — The palette pays its debt

L03 measured colour contrast, recorded it and deliberately did not enforce it (D-L03-4), because a
contrast repair is a palette decision and the palette is this lot's subject. This phase spends that
handover and then arms it: an empty debt left unenforced is how it comes back.

**Why here and not earlier.** axe applies 3:1 rather than 4.5:1 to large text, and « large » is
read from the RENDERED font size. Repairing a badge at 12.5 px and then folding that text to 11 px
in phase 3 re-opens a finding that was reported closed. The type scale settles first.

## The handover, re-measured — and one figure in the design does not reproduce

```bash
python3 -c "import json,collections;d=json.load(open('frontend/maquette/a11y-contrast.json'));\
t=collections.Counter(x for f in d['states'].values() for i in f for x in i['targets']);\
print(sum(t.values()),'targets over',len([s for s,f in d['states'].items() if f]),'states,',len(t),'selectors');\
[print(f'  {c:2d}  {s}') for s,c in t.most_common()]"
```

| selector                             | targets |
| ------------------------------------ | ------- |
| `button[data-cat="all"] > .c`        | 7       |
| `button[data-cat="anim"] > .c`       | 7       |
| `button[data-cat="movies"] > .c`     | 7       |
| `button[data-cat="tv"] > .c`         | 7       |
| `button[data-pill="tout"] > .c`      | 6       |
| `.danger.dlgbtn[data-tone="danger"]` | 2       |
| `.surferr > b`                       | 2       |
| `.loaderr > b`                       | 2       |
| `b`                                  | 1       |
| `button[data-delsel="1"]`            | 1       |

**42 targets over 18 states on 10 distinct selectors — those three figures reproduce.** The split
does not: the design and the lot's contract both say « 27 of the 42 are the count badge », and the
file recorded today says **34**, leaving 8 elsewhere rather than 15. `a11y-contrast.json` is a LIVE
handover, refreshed by every `--record`, so the 27 was true when it was written and is not now.
Nothing about the work changes — the badge is still where the debt is concentrated, and it is still
the place to start — but the phase report states 34, because a figure copied forward without being
re-measured is how a stale number gets read as current.

## 5.1 — The count badge, which carries 34 of the 42

**Files touched**: `frontend/maquette/design/refonte.html` (the `.c` badge inside
`button[data-cat="…"]` and `button[data-pill="…"]`, and the palette tokens it reads).

1. Read what the badge actually resolves to in each of its states — resting, selected, inside a
   selected chip — rather than what the rule declares. One tone under-serves several states, which
   is why one selector produces seven findings.
2. Raise it to **≥ 4.5:1**, 3:1 only where axe's own large-text rule applies, and take the decision
   in the PALETTE: a token whose contrast is wrong is wrong everywhere it is used, and repairing it
   at the call site leaves the next use broken.
3. **The tone must survive both themes.** The palette declares light overrides under a conditional
   scope; a repair verified on the dark theme alone repairs one of the two.

**The hold**: `python3 frontend/maquette/a11y.py --check --rules color-contrast` drops by the
badge's share. Record the before and after counts in the sub-phase report — the count is the only
thing that says the repair reached every state rather than the one that was looked at.

## 5.2 — The remaining eight

**Files touched**: `refonte.html`.

1. `.danger.dlgbtn[data-tone="danger"]` (2) — the destructive dialog button's tone, and
   `button[data-delsel="1"]` (1), the delete-selection control. Same family, same decision: a
   danger tone that is legible on its own fill.
2. `.surferr > b` (2), `.loaderr > b` (2) and the bare `b` (1) — the bold lead of the two error
   surfaces. An error message is the one text in the interface that must be readable on the first
   attempt.

**Out of scope, named so nobody reads it as missed**: `data-pill="tout"` is a French `data-*`
value on a filter pill. It is a name and it will have to be renamed, but a rename is a different
kind of change from a palette repair, and one wave carries one kind. It is not touched here.

**The hold**: the contrast run reads **0**.

## 5.3 — `color-contrast` joins the enforced floor

**Files touched**: `frontend/maquette/a11y.py`, `frontend/maquette/a11y-contrast.json`.

1. `check()` stops splitting `color-contrast` out of the enforced set — the carve-out at
   `a11y.py:336` and the « recorded for L06, not part of this floor » line at `a11y.py:360-362` go
   with it, while `record()`'s split at `a11y.py:286-287` stays. The floor
   stays what it is: a hard zero, no threshold, no tolerated list, no baseline file consulted.
2. **`record()` keeps writing `a11y-contrast.json`**, and it now reads empty. The file stops being
   a debt and becomes the record that the debt was paid — which is worth more than deleting it,
   because ACC-09 can then prove the emptiness rather than the absence.
3. The module docstring's « COLOUR CONTRAST IS MEASURED AND IS NOT THE FLOOR » section is rewritten
   to say what is now true, naming D-L06-5 as what replaced D-L03-4. **A sentence that outlives its
   subject is read as current by the next reader**; this repository has paid for that literally.
4. `python3 frontend/maquette/a11y.py --record` refreshes the contrast file. `a11y-debt.json` is
   left alone — `record()` refuses to overwrite it, deliberately, and that refusal is correct.

**The mutation**, run after the phase is committed: restore the count badge's pre-repair
foreground. `python3 frontend/maquette/a11y.py --check` must **exit 1** and name `color-contrast`
in the enforced total — not merely report it in a line below the floor. Restore.

**This mutation is the one that matters in this phase.** Before the change,
`--check --rules color-contrast` returned zero whatever the palette did, because the split removed
the findings before they were counted: a green that proves nothing. The mutation is what separates
the two.

## The divergences

A colour change moves no rectangle, so this phase's oracle divergences should be limited to the
computed properties `regions.json` probes — `color`, `background-color` and their neighbours in
`probe.computedStyleSubset`. **A geometric divergence in this phase is a defect**: it means a
repair changed a border or a font weight along with the tone. Accept the colour rows with their
reason in `ACCEPTED-DIVERGENCES.md`, investigate anything else.

## Gates before each commit in this phase

```bash
cd frontend/maquette/design && npm run build \
  && cp dist/index.html /tmp/tm-refonte/wrapped.html \
  && rm -rf /tmp/tm-refonte/vite \
  && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
python3 scripts/check-css-tokens.py
python3 scripts/check-no-french.py
python3 frontend/maquette/a11y.py --check
frontend/maquette/harness/run.sh
```

No TypeScript moves in this phase.

## Done when

- ACC-09: the contrast record's `byRule` is `{}`.
- ACC-10 and ACC-23: `a11y.py --check` is a hard zero **including** `color-contrast`, and the
  « not part of this floor » line is gone.
- The mutation has been seen to fail the gate and has been restored.
- The phase report states the re-measured split (34/8), not the design's 27/15.
- Every divergence is accepted with a reason and the reference re-recorded.
