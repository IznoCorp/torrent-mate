# Phase 2 — `.screen` / `.sheet` / `.scrim`, and the static-`open` correction

## Gate

Phase 1 must have produced, all committed:

- `frontend/maquette/anchor-baseline.json` holding **342 entries** (281 selections + 61 assertions),
  with the four refusals live in `scripts/check-markup-contracts.py`, exiting 0 against it;
- `scripts/classify-rule-anchors.py --summary` reporting `687 selection calls`, `class 281`;
- `harness/attrs.py` green (ACC-06) — **the `|| undefined` arm rests on it, so it must have been
  executed before this phase writes the first `data-open`**;
- `make check` running `oracle.py --contracts` (ACC-09);
- `check_data_attributes` reading `data-part`/`data-region` VALUES, mutation-proved (sub-phase 1.6)
  — without it every name this phase coins enters unread;
- `scripts/harness-hold-counts.py` with its baseline committed (sub-phase 1.7) — **ACC-08 is
  claimed by this phase and cannot be run without it**, because `run.sh` prints a passing rule's
  hold count nowhere.

## Emission sites touched

| DOM concept    | `design/index.html`                                 | `engine/legacy.js` | the 23 components                          |
| -------------- | --------------------------------------------------- | ------------------ | ------------------------------------------ |
| `screen`       | **yes** — DESIGN row _the shell and the components_ | no                 | **yes** — 5 screens                        |
| `sheet`        | no                                                  | no                 | **yes** — `sheet.tsx`                      |
| `scrim`        | no                                                  | no                 | **yes** — `sheet.tsx`                      |
| `open` (state) | no                                                  | no                 | **yes** — DESIGN row _the components only_ |

Two of the three sites. **The engine is not touched here** — `legacy.js` emits none of the four,
verified by counting `class=`/`className=` emissions across the three sites. Phase 3 is where the
engine boundary first matters.

## Baseline entries removed

**84, in the same commits as the migrations they correspond to**: 30 class-anchored selections
headed by `.screen`, and all 54 `classList.contains('open')` assertions. The baseline goes
342 → 258. No sub-phase may remove an entry whose markup end it did not also move.

## What the migration changes, and why it is not a rename

`open` in `.screen.open` is **static**. Five screens write it into a literal, because a mounted
screen _is_ open — `add.tsx:155`, `media.tsx:385`, `profile.tsx:85`, `releases.tsx:48`,
`resolution.tsx:316`, each `<section className="screen open" …>`. Only `sheet.tsx` makes it
conditional: `:84` for the scrim, `:95` for the sheet, both `className={"…" + (open ? " open" :
"")}`. So one class name carried two meanings, and 30 calls carried a redundant state token. After
migration the selectors are shorter **and** more honest:

| Before         | After                            | What it means                |
| -------------- | -------------------------------- | ---------------------------- |
| `.screen.open` | `[data-part="screen"]`           | a screen is mounted          |
| `.sheet.open`  | `[data-part="sheet"][data-open]` | the sheet is currently shown |

**This is where a hold count can drift in silence**, and why ACC-08 is claimed here: dropping
`.open` from 30 selectors widens what they match if a screen is ever mounted closed, and the
per-rule hold counts are the only thing that would say so.

---

## Sub-phase 2.1 — the `screen` contract, all three ends in one commit

One commit: `refactor(maquette-l02): anchor the screen contract on data-part`

- [ ] **Step 1.** Emit the anchor at both sites. In the five screens,
      `className="screen open" data-part="screen"` — **the class stays beside it**; L07 removes it,
      and keeping both is the separation this lot exists to create. Same at the shell's `screen`
      emission in `frontend/maquette/design/index.html`.
- [ ] **Step 2.** Re-anchor the 30 harness selections headed by `.screen`, through
      `python3 scripts/rename-identifiers.py` — never by hand, never with an ad-hoc regex.
      `.screen.open` becomes `[data-part="screen"]`; `.screen.open .fback` becomes
      `[data-part="screen"] .fback` — **only the head moves here**, the descendant leaf belongs to
      the phase that owns its concept.
- [ ] **Step 3.** The tool is not the proof. Re-read the diff itself — not its _N file(s) touched_
      line — and confirm no compound selector lost its leaf. Two corruptions in this repository were
      found this way, after the tool reported success.
- [ ] **Step 4.** Remove the 30 selection entries from the baseline **in this same commit**.
- [ ] **Step 5.** `python3 scripts/check-markup-contracts.py; echo "exit=$?"` → `exit=0`. The
      selection ⇒ emission arm proves the ends met: if the harness selects `[data-part="screen"]` and
      no source emits it, this exits 1 and names it.
- [ ] **Step 6.** `run.sh` — no violation, and **compare the per-rule hold counts against phase 1's
      run**, rule by rule. Equal, or stop. Commit.

## Sub-phase 2.2 — the `sheet` and `scrim` contracts, and the first `|| undefined`

One commit: `refactor(maquette-l02): anchor the sheet and scrim contracts, with data-open`

Measured before planning: the harness carries **no class-anchored selection on `.sheet` or
`.scrim`** — it reaches them by their structural ids `#sheet` and `#scrim`, which D4 permits. So
this sub-phase's work is the **state**, not the selection.

- [ ] **Step 1.** In `sheet.tsx`, emit the part anchors beside the existing classes and ids, and the
      state in the imposed idiom:

```tsx
<div id="scrim" data-part="scrim" data-open={open || undefined}
     className={"scrim" + (open ? " open" : "")} … />
<div id="sheet" data-part="sheet" data-open={open || undefined}
     className={"sheet" + (open ? " open" : "")} … />
```

- [ ] **Step 2.** **ACC-05** — the guard falls on `data-open={x}` written without `|| undefined`:

```bash
F=frontend/maquette/design/src/components/sheet.tsx; cp "$F" /tmp/l02-acc05.bak
python3 -c "
import pathlib
p = pathlib.Path('$F'); t = p.read_text()
old = 'data-open={open || undefined}'
assert t.count(old) == 1, f'{t.count(old)} occurrences — mutation ABANDONED'
p.write_text(t.replace(old, 'data-open={open}'))"
python3 scripts/check-markup-contracts.py; echo "exit=$?"
cp /tmp/l02-acc05.bak "$F"
```

Expected: `exit=1`, naming `sheet.tsx` and `data-open`. **The mutation asserts its own
precondition**: this phase emits the idiom at two sites (scrim and sheet), so if both match the
literal the count is 2 and the criterion ABANDONS. Check first with
`grep -c 'data-open={open || undefined}' "$F"`; if it is not 1, raise it with the operator and amend
ACC-05 in `DESIGN.md` before claiming it, exactly as phase 3 does for ACC-04.

- [ ] **Step 2b.** **Extend `harness/attrs.py` to the real `data-*`, closing the gap phase 1 left
      open.** ACC-06 was demonstrated on `aria-pressed` and on a `title`, because no `data-*` boolean
      existed yet; `data-open` is the first, and it exists as of Step 1. Add the same four holds
      against it — `false` present as `"false"` and matched by `[data-open]`, `undefined` absent and
      unmatched — and mutation-test one of them. Without this, the arm written in 1.4 still rests on
      React treating `data-*` like `aria-*`, which nothing in this repository has measured.
- [ ] **Step 3.** Confirm the restore: `git diff --stat …/sheet.tsx` shows only the intended change.
      A restored file is a claim to re-read, not to assume.
- [ ] **Step 4.** Where a rule asserts the sheet is shown, move it to the attribute:
      `classList.contains('open')` becomes `hasAttribute('data-open')`. Remove the corresponding
      baseline entries in this same commit.
- [ ] **Step 5.** `check-markup-contracts.py` → `exit=0`; `run.sh` → no violation, hold counts
      unchanged. Commit.

## Sub-phase 2.3 — the remaining `open` assertions

One commit: `refactor(maquette-l02): assert data-open rather than the open style class`

The 54 assertions span **18 harness files** — `touch.py` and `audit2.py` hold 8 each, `states.py` 6,
`audit.py` and `bugs.py` 5, the rest fewer. Leaving them behind is worse than doing nothing:
`.screen.open` forces `data-open` to exist anyway for the selection side, so they would go on
reading the class next to it — one state, two sources of truth, free to diverge.

- [ ] **Step 1.** Move every remaining `classList.contains('open')` to `hasAttribute('data-open')`.
- [ ] **Step 2.** For each, confirm the element it asserts on actually **emits** `data-open`. An
      assertion moved onto an attribute nothing emits is always false; a `[data-open]` selection
      onto the same is always true. This is what ACC-06 measured.
- [ ] **Step 3.** Remove the remaining assertion entries in this same commit. The phase total across
      2.1–2.3 is exactly **84**; the file must now hold **258**.
- [ ] **Step 4.** Mutation-test one migrated assertion: break the emitting component so the state is
      never set, confirm the rule FALLS naming the right defect, restore. Commit.

---

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

**ACC-08 is claimed here**, and is the second command read properly: not just `no violation`, but
per-rule hold counts equal to phase 1's. A rule passing while holding fewer things has stopped
measuring. The first command is the oracle — the first phase changing markup is the first where it
can fail.
