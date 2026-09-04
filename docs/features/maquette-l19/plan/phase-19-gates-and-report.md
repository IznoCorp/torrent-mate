# Phase 19 — The gates, the figures, the register, the report

## Objective

Close the wave: the full suite, the figures taken ONCE on the final head, the register written,
the report written, the pull request opened.

## The gates, each run ALONE, wrapped

```bash
TM_HARNESS_JOBS=2 sh scripts/heavy.sh l19 frontend/maquette/harness/run.sh      # the FULL suite
TM_HARNESS_JOBS=2 sh scripts/heavy.sh l19 frontend/maquette/harness/run.sh --a11y
TM_HARNESS_JOBS=2 sh scripts/heavy.sh l19 python3 scripts/harness-hold-counts.py --compare
TM_HARNESS_JOBS=2 sh scripts/heavy.sh l19 make maquette-oracle
PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh l19 make check
```

- The full suite, **not** the `--contracts` tier.
- `--compare`: **read `failed` in the totals before trusting a record** (B-291). Every movement
  is written down.
- `make check` at **zero failures and zero errors** — an ERROR means collection crashed and
  everything after it was skipped.
- The oracle green or its divergences accepted with reasons; for the seventeen conversion phases
  the answer is zero.

**Never a build beside a run.** Kill what is started, delete what is built, verify with `ps`.

## The figures, taken ONCE, on the final head

The fifth review rule. Every command of `DESIGN.md` § 0 is re-run here and the readings go into
`REPORT.md` — never into `DESIGN.md`, which is what was decided.

```bash
grep -c "panel\.open(" frontend/maquette/design/src/engine/legacy.js            # expect 0
grep -nE '\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML\(|\.(appendChild|append|prepend|replaceChildren)\(' \
  frontend/maquette/design/src/engine/legacy.js | grep -v '^\s*//'              # the harness panel only
grep -c "closest\.dataset\." frontend/maquette/design/src/engine/legacy.js
grep -n "setTimeout(.*260" frontend/maquette/design/src/engine/legacy.js
grep -n "install[A-Za-z]*(" frontend/maquette/design/src/app/shell.tsx | grep -vc "^\s*//"
python3 scripts/check-frontend-boundaries.py --arm size
python3 scripts/check-frame-domain.py | tail -1
grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/legacy.js
```

And **D5's bracket-match method re-derived**, not remembered: the declarations over 100 lines and
their total, against the design's 9 / 26 375. The DIFFERENCE is the deliverable.

## The register, written DURING the wave and closed here

B-236, B-247 (producer half), B-249 (the SHAPE, for what this lot owns), B-299, B-300, B-306 —
each with the instrument that RAN, the mutation, and the reading. An entry closed with no
instrument that ran is a claim.

**Recount « guards green over what they do not read »** and add this wave's figure with what
establishes it. **Zero is a real answer and is written down.**

## `IMPLEMENTATION.md`

The « In flight » row is written **when the pull request opens** — the number first, then the
version. `scripts/check-implementation-state.py` holds the row by both.

## The pull request

One pull request, **title and body in English**, the version bumped, the constitution's §§
cited. Then the steward is messaged: the review is independent of this session.

## Verdict

*(the gates' readings are written into `REPORT.md` § 10, taken once on the final head)*

### The full suite found two pointers this wave had invalidated

Neither went quiet; both fell **loudly**, in the tier written to catch exactly that.

- **R56 « there really are callers » read `panel.open(` and found ZERO.** A producer does not
  CALL `open` since this lot: it is registered against a kind and RETURNS a descriptor. The hold
  counts registrations beside calls now, and holds the same discipline on them — a registration is
  a DECLARATION, never a string.
- **R56 « every block module outside `ui/panel` is imported at boot » read `app/shell.tsx`**, and
  the list moved to `app/panel-contributions.ts`. It reads what the boot REACHES now, one level
  down, because a feature with more than one panel gathers its siblings — a reader that stopped at
  the first file called `panel-field` absent while the boot reached it.

Both are the shape this wave met four times: **a pointer that silently misses its target is how a
rule goes quiet.** These did not.
