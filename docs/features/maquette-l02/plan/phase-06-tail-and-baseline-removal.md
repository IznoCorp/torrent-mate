# Phase 6 — the tail, then the baseline is emptied and deleted

## Gate

Phase 5 must have produced, all committed:

- the filter, setting, segment and section-head contracts anchored, with `fr`, `fn`, `fk`, `fs`
  resolved at their sites and their meanings recorded in the commit messages;
- `data-empty` and `data-blocked` emitted and asserted through `hasAttribute`;
- `frontend/maquette/anchor-baseline.json` down to **346 entries** (405 − 59);
- ACC-12 recorded as `exit=0`.

## Emission sites touched

**All three, and this is the only phase that touches the shell at scale.** The tail is a long one —
the DESIGN measured 96 distinct root tokens across 133 distinct selectors in 36 files, not a few hot
spots — so it is worked by site, and each site is finished before the next begins.

| Group                 | Site                               | What it holds                                                                                              |
| --------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| the shell-only tokens | `design/index.html`                | 9 tokens — `bottombar`, `loginscreen`, `loginsubmit`, `splashbar`, `dlg`, `hbtn`, `installgo` and the rest |
| the engine-only tail  | `engine/legacy.js`                 | the remainder of the 17 — `dlgbtn`, `deck`, `manifest`, `nm`, `sel` and the rest                           |
| the component tail    | the 23 components                  | the remainder of the 48 — `sact`, `body`, `field` and the rest                                             |
| the straddling tail   | `legacy.js` **and** the components | the remainder of the 34 — `chip`, `tile` and the rest                                                      |
| the computed tokens   | resolved per site                  | `announced`, `modified`, `selbar` — `eppop` was resolved in phase 4                                        |

**Eleven tokens have an end in the shell, which no lot converts** — `index.html` keeps its
`data-part` for good. That makes this the most durable work in the wave, not the leftovers.

## Baseline entries removed

**346 — the remainder, and the file reaches zero.** 343 class token occurrences across **93
distinct tokens**, plus the last **3** state assertions: `classList.contains('show')` →
`hasAttribute('data-shown')`, `classList.contains('in_library')` → `hasAttribute('data-in-library')`,
`classList.contains('announced')` → `hasAttribute('data-announced')`.

Running total across the wave: 117 + 129 + 43 + 59 + 346 = **694**.

---

## Sub-phase 6.1 — the shell tail

One commit: `refactor(maquette-l02): anchor the application shell contracts on data-part`

- [ ] **Step 1.** Work `frontend/maquette/design/index.html` — 374 lines, 47 `class=` — and emit a
      `data-part` beside each class the harness selects on. The shell is the site both earlier
      analysis passes missed; enumerate from the baseline's remaining entries rather than by reading
      the file for likely candidates.
- [ ] **Step 2.** Re-anchor the corresponding harness selections; re-read the diff.
- [ ] **Step 3.** Remove those baseline entries in this same commit.
- [ ] **Step 4.** `python3 scripts/check-markup-contracts.py; echo "exit=$?"` → `exit=0`;
      `run.sh` → no violation, hold counts unchanged. Commit.

## Sub-phase 6.2 — the engine tail and the straddling tail

One commit: `refactor(maquette-l02): anchor the remaining engine-side contracts on data-part`

- [ ] **Step 1.** Emit the remaining `data-part` values in `legacy.js`, and — for every token the
      components also emit — at the component sites in the **same** commit. A concept whose markup
      sits on both sides of the engine boundary moves as one contract or not at all.
- [ ] **Step 2.** Beware the short tokens. `nm` and `sel` are two letters, and `sel` is a substring
      of `selbar` and `selection`. Re-read the diff; the rename tool's read-back check does not
      cover `--values` runs or Python files.
- [ ] **Step 3.** Re-anchor the harness selections, remove the baseline entries in this same commit.
- [ ] **Step 4.** `check-markup-contracts.py` → `exit=0`; `run.sh` → no violation, hold counts
      unchanged. Commit.

## Sub-phase 6.3 — the component tail, the computed tokens and the last three states

One commit: `refactor(maquette-l02): anchor the component tail and the last three states`

- [ ] **Step 1.** Emit the remaining component-side `data-part` values.
- [ ] **Step 2.** Resolve `announced`, `modified` and `selbar` **at their own sites**. Each is a
      conditional `className` expression; read what each branch evaluates to and anchor where the
      element is built. A token nothing emits is a rule already selecting nothing — if one of the
      three turns out to be emitted by no branch, record that finding rather than inventing an
      anchor for it.
- [ ] **Step 3.** Emit the last three states in the imposed idiom — `data-shown={isShown ||
  undefined}`, `data-in-library={isInLibrary || undefined}`, `data-announced={isAnnounced ||
  undefined}` — and move their three assertions to `hasAttribute`.
- [ ] **Step 4.** Mutation-test each of the three: make the emitting site drop the attribute
      unconditionally, confirm the rule FALLS and names the right defect, restore. `announced` is
      also computed, so its mutation proves both halves at once.
- [ ] **Step 5.** Remove the last baseline entries in this same commit. **The file now holds 0.**
- [ ] **Step 6.** `check-markup-contracts.py` → `exit=0`; `run.sh` → no violation, hold counts
      unchanged. Commit.

## Sub-phase 6.4 — the floor becomes a hard zero in code

One commit: `refactor(maquette-l02): delete the anchor baseline and make the floor a hard zero`

The burn-down was a ratchet, not a promise. An empty file is a floor someone can raise again, so the
file goes and the tolerance goes with it.

- [ ] **Step 1.** Delete `frontend/maquette/anchor-baseline.json`.
- [ ] **Step 2.** Remove every reference to it from `scripts/check-markup-contracts.py`, including
      the `--write-baseline` mode. The arm now refuses the **first** class-anchored selection, with
      no list to consult. Update the per-arm docstring so the file still says what it actually
      measures.
- [ ] **Step 3.** **ACC-10** — the baseline is empty and gone:

```bash
ls frontend/maquette/anchor-baseline.json; echo "exit=$?"
grep -c "anchor-baseline" scripts/check-markup-contracts.py
```

Expected: `No such file or directory`, `exit=1`, and `0` references left in the guard.

- [ ] **Step 4.** Mutation-test the hard floor, because a guard whose baseline just disappeared is a
      guard nobody has seen fail in its final form: re-introduce one class-anchored selection in any
      `harness/*.py`, confirm `exit=1` and that it is named, restore.
- [ ] **Step 5.** **ACC-01** — zero class-anchored selection calls remain:

```bash
python3 scripts/check-markup-contracts.py; echo "exit=$?"
```

Expected: a line reporting `0 class-anchored selection call` over `harness/*.py`, and `exit=0`.

- [ ] **Step 6.** **ACC-02** — the same conclusion from a reader that is not the guard:

```bash
python3 scripts/classify-rule-anchors.py --summary; echo "exit=$?"
```

Expected: `687 selection calls` with `class 0`, and `exit=0`. **The total must still be 687**: a
classifier that stopped SEEING calls would also report zero class anchors, and the two failures are
indistinguishable from the exit code alone.

- [ ] **Step 7.** Commit.

---

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

**ACC-07 is claimed here**, over the whole wave: the oracle green means 694 anchors were added
across three emission sites and no pixel moved. That is checkable rather than asserted because the
stylesheet's only attribute selectors are `[aria-checked]`, `[aria-selected]`, `[aria-pressed]`,
`[aria-current]`, `[data-theme]` and `[data-depth]` — none on `data-part` or the seven states.

**ACC-13 is the third command**: `make check; echo "exit=$?"` → `exit=0`. It now runs
`oracle.py --contracts` too, wired in phase 1, so the dormant arm that held half of D4 and executed
nowhere is part of the gate this wave closes on.
