# Phase 2 — `.screen` / `.sheet` / `.scrim`, and the static-`open` correction

## Gate

Phase 1 must have produced, all committed:

- `frontend/maquette/anchor-baseline.json` holding **694 entries** (633 class token occurrences + 61 assertions),
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

| DOM concept | `design/index.html` (shell) | `engine/legacy.js` | the 23 components |
| --- | --- | --- | --- |
| `screen` | **yes** — `:350`, the engine's own screen host | **yes** — `openScreen()` toggles `open` on it | **yes** — 5 sections |
| `sheet` / `scrim` | no | **yes** — `#scrim` toggled at 5 sites | **yes** — `sheet.tsx:84,95` |
| `open` (state) | no | **yes** — 14 toggle sites on `#screen`, `#dlg`, `#drawer`, `#scrim` | **yes** — `sheet.tsx` |

**All three sites, and the engine most of all.** The first draft said the engine was not touched
here; it toggles the `open` class at 14 sites on four layers, and every one of those toggles must
set `data-open` in the same breath or the attribute lies about the class. The 54 assertions this
phase moves read FIVE layers — `#sheet` (21+), `#screen` (6), `#dlg` (5), `#scrim` (2),
`#drawer` (2) — and only `#sheet`/`#scrim` are React's; the other three are the engine's alone.

## Baseline entries removed

**201**, the third recalibration of this figure and the one taken from the instrument as it finally
reads — 117 counted `.screen.open` as one token, 189 counted it as two, and 201 adds the selectors
the harness HOLDS in variables and tables, which no reader had counted until phase 1 taught them to:

| Sub-phase | Removes | What |
| --- | --- | --- |
| 2.1 | **138** | 69 `.screen` + 69 `.open` — the prefix rewrite, on 63 call arguments and **6 held** (`scroll.py:43`, `audit.py:203`, `audit2.py:155`, `:156`, `:52`'s returned string, `panel.py:58`) |
| 2.2 | 0 | emits `data-open`; moves no selection and no assertion |
| 2.3 | **63** | 9 `.open` behind an id head (`#sheet.open`, `#screen.open`) + 54 `classList.contains('open')` assertions |

The baseline goes **834 → 696 → 696 → 633**. No sub-phase may remove an entry whose markup end it
did not also move.

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

> **Measured on the committed baseline**: the 63 phase-2 occurrences are **all `.screen`** — zero
> `.sheet`, zero `.scrim`, which confirms the harness reaches those two by their ids. They sit in 12
> files: `screen_addresses.py` 13, `screens.py` 13, `bugs.py` 9, `audit2.py` 7, `bridge.py` 6,
> `attrs.py` 3, then `audit.py`, `ident.py`, `surfaces.py` 2 each, and one each in `decision.py`,
> `dest.py`, `gallery.py`.

## Sub-phase 2.1 — the `screen` contract, all three ends in one commit

One commit: `refactor(maquette-l02): anchor the screen contract on data-part`

> **THREE READINGS OF `.screen.open`, and only the third is measured.** The first draft said
> `open` was static and could be dropped. A correction said `index.html:350` was a mere mount node
> deserving its own `screen-host` value. A second correction said `open` was the token telling two
> kinds of screen apart — React sections in `#shell` versus the engine's own `#screen`, opened by
> `openScreen()` at `legacy.js:10911`. Each was reasoned from the code; the third was checked
> against what RUNS:
>
> - `openScreen` has one caller: nobody. It is republished on `window` (`legacy.js:34575`) and
>   referenced by two past-tense comments in `releases.tsx:7` / `resolution.tsx:7`. No harness rule
>   calls it, no named state in `states.js` mentions `#screen`. The two sites that REMOVE `open`
>   from `#screen` (`hideLayers()` at `:10736`, a close path at `:10943`) are defensive clears of a
>   class nothing adds any more.
> - Probed in `mediasheet-series`: `.screen.open` → the SECTION; `#screen` carries no `open`.
>
> **So the engine-screen path is dead today**, `#screen` never opens, `.screen.open` bare only ever
> matches a React section, and the six `#screen.classList.contains('open')` assertions are
> vestiges that always read false. The target is STILL `[data-part="screen"][data-open]`, for a
> more modest reason than disambiguation: **the attribute mirrors the class exactly**. `open` is on
> the sections, so `data-open` is on the sections; `#screen` has neither, and gets `data-open` from
> the same engine helper that would give it `open` — so the day someone revives `openScreen()`, the
> contract already holds and the guard already reads it. A mirror that skips the dead branch is a
> mirror that lies the moment the branch wakes. `screen-host` stays struck.
> <sub>the six vestigial assertions move to `hasAttribute('data-open')` in 2.3 and keep reading false — removing them is a later tidy-up, not this lot's</sub>

- [ ] **Step 1.** Emit the anchor at the six sites, ONE value. The five sections
      (`add.tsx:155`, `releases.tsx:48`, `resolution.tsx:316`, `media.tsx:385`, `profile.tsx:85`)
      become `className="screen open" data-part="screen" data-open=""` — the class stays beside it,
      L07 removes it. `index.html:350` becomes `<div class="screen" id="screen" data-part="screen">`,
      and its `data-open` is DYNAMIC: the engine sets it wherever it sets `open`.
- [ ] **Step 2.** Re-anchor the 63 `.screen` occurrences: the prefix `.screen.open` becomes
      **`[data-part="screen"][data-open]`** — BOTH attributes, because both classes were needed. The
      19 distinct shapes all start with that prefix and all 63 are single-quoted, so a prefix
      rewrite inside the quotes is well-defined. **Only the prefix moves**: `.screen.open .fback`
      becomes `[data-part="screen"][data-open] .fback`, and `.fback` waits for the phase that owns
      it — the baseline is keyed on the token occurrence, so that entry stays.
      **`scripts/rename-identifiers.py` is struck for this step**: its own header says a selector
      is a STRING that is « NEVER renamed here », and `--values` is the mode whose read-back proof
      is skipped. The rewrite is a literal replacement that ASSERTS its counts — 63 `.screen.open`
      before, 0 after, 63 `[data-part="screen"][data-open]` after — and is then judged by three
      oracles outside itself: the guard's selection ⇒ emission arm, `classify-rule-anchors.py
      --tokens` (63 fewer `.screen`), and `harness-hold-counts.py --compare` (unchanged).
- [ ] **Step 3.** The tool is not the proof. Re-read the diff itself — not its _N file(s) touched_
      line — and confirm no compound selector lost its leaf. Two corruptions in this repository were
      found this way, after the tool reported success.
- [ ] **Step 4.** Remove the 30 selection entries from the baseline **in this same commit**.
- [ ] **Step 5.** `python3 scripts/check-markup-contracts.py; echo "exit=$?"` → `exit=0`. The
      selection ⇒ emission arm proves the ends met: if the harness selects `[data-part="screen"]` and
      no source emits it, this exits 1 and names it.
- [ ] **Step 6.** `run.sh` — no violation, and **compare the per-rule hold counts against phase 1's
      run**, rule by rule. Equal, or stop. Commit.

## Sub-phase 2.2 — `data-open` on the five layers: React's two, and the engine's four

One commit: `refactor(maquette-l02): mirror the open class into data-open on every layer`

**The engine toggles `open` imperatively at 14 sites, and the two ends must move as one.** A
`setOpen(element, on)` helper in `legacy.js` that adds/removes the class AND sets/removes
`data-open` together, used at all 14 (`legacy.js:10735-10745, 10818-10823, 10911, 10943,
11584-11593`), is the one shape where the attribute cannot drift from the class. Fourteen paired
lines would be fourteen places for the pair to come apart.

`#scrim` has TWO writers — React renders it (`sheet.tsx:84`) and the engine toggles it (5 sites).
That is the strangler state and this phase does not resolve it; it mirrors it: React writes
`data-open={open || undefined}` for the sheet's own state, the engine's helper writes it for the
drawer's and the dialog's. The class already lives that double life; the attribute follows it.

- [ ] **Step 0.** In `legacy.js`, add `setOpen(element, on)` beside `select()`, and route the 14
      sites through it. `grep -c 'classList.add("open")\|classList.remove("open")' legacy.js`
      must read **0** afterwards — a site left behind is an attribute that lies.



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
      2.1–2.3 is exactly **201**; the file must now hold **633**.
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
