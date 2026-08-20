# Phase 1 — The recipe and the measuring core

## Goal

`oracle.py` measures a real page: it drives a named state, resolves a region, and reads its
bounding rectangle plus the 17 computed style properties. No region list, no reference file, no
modes — just proof that the measurement itself is sound.

## Why this comes first

If the region list existed already, the core would be written to satisfy it. Written against a
handful of hand-picked regions instead, the core has to be honest about what it cannot resolve.

## Work

1. **Recover the `probe` block into `frontend/maquette/regions.json`.**
   `git show bd31d52b:frontend/maquette/regions.json` → its `probe` key. Six keys, restored with
   a comment naming the commit it came from and why it is recovered rather than rebuilt.
   `allowlist` comes back **empty** — its single entry described a maquette-vs-app divergence,
   and this oracle compares the maquette to itself at two commits.

2. **Create `frontend/maquette/oracle.py`** with the measuring core only:
   - one browser, one context, reused across states (friction 3);
   - `assertBeforeMeasuring` evaluated and **raising** when false — a measurement at the wrong
     width is worse than no measurement;
   - `neutralise`: `.note` REMOVED from the DOM (not merely dismissed — `open_page` clicks
     `#toastx`, which is a different mechanism and leaves the node);
   - per region: `getBoundingClientRect()` rounded to a declared precision, plus
     `getComputedStyle` restricted to the 17 properties;
   - a region resolving to **zero elements is recorded as absent**, never silently skipped.

3. **A temporary region set of five**, hand-picked across different pages, to exercise the core.
   It is deleted in Phase 2 — named `_SMOKE_REGIONS` so it cannot be mistaken for the real list.

## Done when

- `python3 frontend/maquette/oracle.py --smoke` prints a table of *(state × region)* measurements
  for the five regions across three states, and exits 0.
- Running it against a viewport forced to 380 raises rather than measuring.
- A region whose selector matches nothing is reported `absent`, and the exit code is non-zero
  when an absent region is not declared in `knownAbsent`.

## Traps this phase must not fall into

- **`open_page`'s 250 ms sleep** is inherited if the core simply calls it. Phase 1 may use it;
  Phase 4 must replace it. Record the dependency in a comment so it is not forgotten.
- `getComputedStyle` returns shorthand properties (`padding`, `margin`, `border`) as computed
  longhands in some engines and as empty strings in others. Read what Chrome actually returns
  and record it — a property that always reads `""` measures nothing.
