# Phase 1 — vocabulary, the guard arm, the baseline, the dormant arm wired

## Gate

Nothing is required of a previous phase: this is the first. What must hold is the inherited state of
L01 — `oracle.py --check` exits 0 against the recorded reference, and `harness/run.sh` reports no
violation. Both are re-run as this phase's closing proofs, so a pre-existing failure must be known
now rather than attributed to this wave.

**This phase migrates zero selections.** It builds the instrument that judges phases 2 to 6.

## Emission sites touched

None, in any of the three sites (`design/index.html`, `design/src/engine/legacy.js`, the 23
non-engine sources). The only edits are to `scripts/`, `harness/attrs.py`, `Makefile` and the CI
workflow.

## Baseline entries removed

**Zero — this phase CREATES the baseline at 342 entries** (281 class-anchored selections + 61 state
assertions). Every later phase removes from it.

---

## Sub-phase 1.1 — the vocabulary, fixed before a single name is coined

One commit: `docs(maquette-l02): fix the data-part vocabulary before any name is coined`

- [ ] **Step 1.** Write the vocabulary into `frontend/maquette/README.md`, in a section the guard's
      docstring points at. Exactly three rules, no more:

```
1. One attribute, data-part, value namespaced by "/" — card, card/title, card/poster.
   The namespace names the owning DOM concept; the leaf names the role.
2. Seven boolean state attributes, no value: data-open, data-no-poster, data-empty,
   data-blocked, data-announced, data-in-library, data-shown.
3. In a component: data-open={isOpen || undefined}. Never data-open={isOpen}.
```

- [ ] **Step 2.** A value is a name someone chose, so § Language applies in full. **Three words are
      already MEASURED absent, and they block `data-part` itself: `part`, `announced`, `manifest`.**
      `check_data_attributes` refuses a `data-*` name built from a word `scripts/code-vocabulary.txt`
      does not hold, so without this step the very first attribute fails the gate. Add those three,
      then diff the rest and add only what is missing: `title, poster, cover, body, foot, sheet,
    scrim, screen, row, key, name, section, head, episode, suggestion, result, list, setting,
    segment, filter, blocked, shown`.
- [ ] **Step 3.** `python3 scripts/check-no-french.py; echo "exit=$?"` → `exit=0`. Commit.

## Sub-phase 1.2 — ACC-06, the React trap demonstrated BEFORE the arm that rests on it

One commit: `test(maquette-l02): demonstrate React attribute rendering in the live document`

This runs **before** sub-phase 1.4 writes the `|| undefined` arm. The DESIGN states the belief and
refuses to let it be load-bearing: if the demonstration contradicts it, the arm and the DESIGN
paragraph change together.

### The subject had to be found, because the obvious one does not exist

The rule must demonstrate **React's** rendering, not the DOM's. React is not exposed on `window`
(`shell.tsx` republishes `__bridge`, `__go`, `__store`, … and no renderer), and **no `data-*`
boolean exists in the maquette yet** — the first one is written in phase 2. Written as first
planned, this sub-phase had no subject.

It has two, both in the live document today, both rendered by the React the maquette actually
bundles:

| Half of the trap | Where | What it establishes |
| --- | --- | --- |
| `false` renders as the **string** `"false"` | `add.tsx:239` `aria-pressed={addKind === value}`, and five `aria-checked={…}` in `profile.tsx` | a presence selector `[aria-pressed]` MATCHES an attribute whose value is false |
| `undefined` is **omitted** | `resolution.tsx:114` `title={opts.noPoster ? … : undefined}` | the imposed idiom really does remove the attribute |

**The gap, stated rather than glossed.** Those are `aria-*` and a standard attribute; the guard
concerns `data-*`. React routes `aria-*` and `data-*` through the same passthrough, but « the same
passthrough » is a belief, and refusing to rest on a belief is this criterion's entire reason for
existing. So the gap is closed where it can be: **sub-phase 2.2 extends `attrs.py` with the same
four assertions against the real `data-open`**, on the day that attribute first exists. It is an
obligation in phase 2's plan, not an implication left for someone to notice.

- [ ] **Step 1.** Create `frontend/maquette/harness/attrs.py`, following an existing browser rule's
      shape — read `harness/logout.py` for the `common.open_page()` idiom, the `common.Journal`
      verdict printing and the exit-code convention. It drives the app to a state where the
      subjects above are rendered, and asserts all four facts, each as its own named hold.
- [ ] **Step 2.** Run it and read the OUTPUT, not the exit code alone:
      `python3 frontend/maquette/harness/attrs.py; echo "exit=$?"` → `exit=0` (ACC-06). Record what
      each hold printed; a hold that passed while its probe returned `None` is a hold that measured
      nothing.
- [ ] **Step 3.** Mutation-test the rule itself: invert one of the four assertions, re-run, confirm
      it FAILS and names which fact fell, restore. A demonstration that cannot fail demonstrates
      nothing.
- [ ] **Step 4.** Run the full suite and **record the printed rule count**:
      `frontend/maquette/harness/run.sh 2>&1 | tail -3`. `run.sh` globs `harness/*.py` minus
      `common.py`, so this file becomes a rule and the count moves 50 → 51. Write down what it
      actually printed — ACC-08 is filled in with the real output, never the intended one.
- [ ] **Step 5.** Commit.

## Sub-phase 1.3 — the independent classifier

One commit: `feat(maquette-l02): add an independent classifier for rule anchors`

It lives in `scripts/`, **not** in `harness/`: `run.sh` runs every file there but `common.py` as a
rule, so a tool dropped beside them would be executed as one.

- [ ] **Step 1.** Create `scripts/classify-rule-anchors.py`. It reads the string argument of every
      `querySelector` / `querySelectorAll` / `locator` / `matches` call across `harness/*.py` and
      classifies each by its anchor. Its docstring states the **precedence rule** it applies,
      because that rule is the whole measurement: a naive "any `.token` outside `[…]`" classifier
      returns 687 calls and 428 class anchors over this same corpus, against the DESIGN's 687 and 281.
- [ ] **Step 2.** Three modes: `--summary`, the per-anchor table and total as ACC-02 reads it;
      `--exceptions`, the five permanent genre entries (`h2`, `flux`, `ep`, `radio`, `note`) each
      with a non-empty reason — a reason-less entry is itself a violation, as for `french-ok`
      pragmas; `--baseline`, the machine-readable list the guard's baseline is generated from.
- [ ] **Step 3.** `python3 scripts/classify-rule-anchors.py --summary`. Expected **today**: **`687
    selection calls`**, `class 281`, `data-* 95`, `id 278`, `tag 32`, `role 1`. **Not 684** — D4 and
      this lot's first pass both read only QUOTED selectors and were blind to three template-literal
      ones (`cards.py:82` and two more), every one of them `data-*`-anchored. A classifier reporting
      684 is reproducing that blind spot, not agreeing with D4. **`class 281` is unchanged and is
      the figure every number in phases 2 to 6 descends from** — if IT moves, stop and reconcile.
- [ ] **Step 4.** `--exceptions` → exactly 5 entries, each with a reason. Commit.

## Sub-phase 1.4 — the guard arm and the generated baseline

One commit: `feat(maquette-l02): refuse class-anchored rule selections, with a burn-down baseline`

The arm goes into `scripts/check-markup-contracts.py` — already in `make check` and in CI, 149 lines
carrying one arm, while `oracle.py` is 972 against a 1000-line ceiling.

- [ ] **Step 1.** Extend the module docstring **per arm**. The file describes one question over one
      corpus today; it gains a second (`harness/*.py`), and the docstring must say which arm reads
      which — or the file becomes a place where a reader cannot tell what is actually measured.
- [ ] **Step 2.** Add the DESIGN's four refusals. Over `harness/*.py`: a selector anchored on a CSS
      class, and `classList.contains('<state>')` for any of the 7 migrated states. Over the sources:
      a `data-part` value the harness selects and no source emits — the three-ends defect caught
      from the markup end, reading all three emission sites, `index.html` included — and
      `data-<state>={x}` written without `|| undefined` in a component.
- [ ] **Step 3.** Generate the baseline, **never type it**:
      `python3 scripts/check-markup-contracts.py --write-baseline` produces
      `frontend/maquette/anchor-baseline.json` with **342 entries** (281 + 61), the shape
      `scripts/french-exemption-baseline.json` already uses. The five genre assertions are not in
      it: they are permanent, and live in the classifier's exception list with their reasons.
- [ ] **Step 4.** Cross-check the two readers, which is the point of having two: the baseline's 281
      selection entries must equal `classify-rule-anchors.py --summary`'s class count. A
      classification cross-checked only by the guard that produced it proves nothing.
- [ ] **Step 5.** `python3 scripts/check-markup-contracts.py; echo "exit=$?"` → `exit=0`, its output
      stating how many baselined violations it tolerates.
- [ ] **Step 6.** Mutation-test the arm now, while there is something to catch: append a
      class-anchored selection to a `harness/*.py` file, confirm `exit=1` naming the file, the line
      and the selector, restore. A baseline that swallows a NEW violation ratchets the wrong way.
- [ ] **Step 7.** Commit the arm, the baseline and the docstring together.

## Sub-phase 1.5 — the dormant arm wired

One commit: `ci(maquette-l02): run the dormant oracle contract arm in make check and in CI`

`oracle.py --contracts` already holds half of D4 and runs nowhere. It is static — no browser, no
`library.db`, ~0.1 s — so it also satisfies the constraint that kept `arrivals.py` out of the
per-PR tier.

- [ ] **Step 1.** Add `python3 frontend/maquette/oracle.py --contracts` to the `Makefile` check
      target, and the same line to `.github/workflows/ci.yml` in the job already running
      `check-markup-contracts.py`.
- [ ] **Step 2.** ACC-09: `make check 2>&1 | grep -c "regions declared"` → `1`. On `main` before this
      wave the same command prints `0`; confirm that too, so the criterion measures the change
      rather than the status quo.
- [ ] **Step 3.** Commit.

## Sub-phase 1.6 — the `data-part` VALUE arm, without which ACC-12 measures nothing

One commit: `feat(maquette-l02): read the values of the naming data-* attributes`

`check_data_attributes` reads `data-*` NAMES and deliberately not their values — « `data-go="profil"`
names a page, and a page id is an address. » That is right for `data-go` and **wrong for
`data-part`**: a part value is a structural name someone chose, and this lot coins ~130 of them at
once. Without this, ACC-12 exits 0 over a vocabulary nothing looked at — the vacuous criterion L01
already paid for with `data-region`.

- [ ] **Step 1.** EXTEND `check_data_attributes`, do not add an arm. `check_arm_count` holds the arm
      count against the module docstring's numbered headings AND a sentence in `CLAUDE.md`; a new
      arm costs both edits, an extension costs neither.
- [ ] **Step 2.** Read the VALUES of the NAMING attributes only — `data-part` and `data-region`,
      which has the same status and the same hole. Split each on `/` and `-` and check every word
      against `scripts/code-vocabulary.txt`. Address-valued attributes (`data-go`, `data-key`,
      `data-panel`, …) stay unread; the docstring says which list a new attribute joins and why.
- [ ] **Step 3.** Make the count visible: `--counts` must print how many `data-part` values were
      examined. **A printed number nobody compares is a number nobody reads** — ACC-12 reads this
      one, because a gate proves what it READS, not what it exits.
- [ ] **Step 4.** Mutation: rename one `data-region` value (18 exist today) to a French word,
      confirm `exit=1` naming the file, the line and the word, restore. Run it against `data-region`
      because no `data-part` exists yet — the arm must bite on the day it lands, not in phase 2.
- [ ] **Step 5.** `python3 scripts/check-no-french.py; echo "exit=$?"` → `exit=0`. Commit.

## Sub-phase 1.7 — the per-rule hold-count capture, without which ACC-08 cannot be run

One commit: `feat(maquette-l02): capture and compare per-rule hold counts`

`run.sh` captures each rule's output into `out="$(python3 …)"` and prints it **only on failure**. A
passing rule's `N rules EXECUTED — no violation` never reaches the log, so « the suite is green at
unchanged per-rule hold counts » is not obtainable from the command ACC-08 named. The wave needs
this at all six gates.

- [ ] **Step 1.** Create `scripts/harness-hold-counts.py`. It runs every rule the way `run.sh` does
      — same glob, `harness/*.py` minus `common.py` — and keeps each one's printed
      `N rules EXECUTED` figure instead of discarding it.
- [ ] **Step 2.** Two modes: `--record <file>` writes the table; `--compare <file>` exits non-zero
      naming every rule whose count MOVED, in either direction. **A count that fell is a rule that
      stopped measuring; a count that rose is a rule measuring something it was not asked to.**
- [ ] **Step 3.** Record the baseline into `frontend/maquette/hold-counts-baseline.json` and commit
      it. It is taken at the state before any migration — the suite reads
      `harness: 51 rule(s), no violation.` once `attrs.py` exists, against the **50** captured on
      `f7e8073f` on 2026-08-21 before this phase. Record both figures and which is which.
- [ ] **Step 4.** Mutation: delete one assertion from any rule, re-run `--compare`, confirm it names
      that rule and its `-1`, restore. A comparator that cannot see a lost hold is the thing it was
      written to replace.
- [ ] **Step 5.** Commit.

---

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

The hold counts are the load-bearing half of the second command. This phase adds one rule file
(`attrs.py`), so the **suite count** legitimately moves 50 → 51 while every pre-existing rule's hold
count stays equal. Record both.
