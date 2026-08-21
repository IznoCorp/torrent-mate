# Phase 3 — `.card` and its parts: `ctitle`, `cbody`, `cfoot`, `poster`, `cov`

## Gate

Phase 2 must have produced, all committed:

- `[data-part="screen"]`, `[data-part="sheet"]`, `[data-part="scrim"]` emitted, with
  `data-open={open || undefined}` in `sheet.tsx`;
- all 54 `classList.contains('open')` assertions moved to `hasAttribute('data-open')`;
- `frontend/maquette/anchor-baseline.json` down to **577 entries** (694 − 117);
- ACC-05 recorded as `exit=1`, the guard naming `sheet.tsx` and `data-open`;
- ACC-08 recorded: `run.sh` green with per-rule hold counts equal to phase 1's.

## Emission sites touched

**Every concept here straddles the engine boundary.** The DESIGN lists `card`, `ctitle`, `cbody`,
`cfoot`, `poster` and `cov` under _the engine AND the components_ — the first phase where cutting by
DOM concept rather than by file kind pays, because cutting by file would split one contract across
two commits.

| DOM concept              | `design/index.html` | `engine/legacy.js`                  | the 23 components                      |
| ------------------------ | ------------------- | ----------------------------------- | -------------------------------------- |
| `card`                   | no                  | **yes**                             | **yes**                                |
| `card/title` (`ctitle`)  | no                  | **yes** — `legacy.js:7141`, `:9995` | **yes** — `resolution.tsx:121`, `:195` |
| `card/body` (`cbody`)    | no                  | **yes**                             | **yes**                                |
| `card/foot` (`cfoot`)    | no                  | **yes**                             | **yes** — widest spread, 6 files       |
| `card/cover` (`cov`)     | no                  | **yes**                             | **yes**                                |
| `card/poster` (`poster`) | no                  | **yes**                             | **yes**                                |

The shell emits none of them. `legacy.js` also **reads** `.ctitle` at `:12402` and `:12412`
(`closest(".card")?.querySelector(".ctitle")`) — engine-internal reads, not harness selections, and
**out of this lot's scope**: the guard reads `harness/*.py`, not the engine. Leave them, and do not
let a rename tool rewrite them by accident.

## Baseline entries removed

**129**: 127 class token occurrences across the card family — 14 distinct tokens, `card`,
`ctitle`, `cbody`, `cfoot`, `poster`, `cov`, `csub`, `cmeta`, `ctop`, `creason`, `pfall`, `dcard`,
`freshtag`, `caption` — plus the **2** `classList.contains('noposter')` assertions, which become
`hasAttribute('data-no-poster')`. The baseline goes 577 → 448.

## The ACC-04 conflict this phase found — RESOLVED, and the criterion moved out

This phase's planning caught ACC-04 asserting a precondition its own subject breaks: it mutated
`data-part="card/title"` in `resolution.tsx` under `assert t.count(old) == 1`, and that file emits
`ctitle` **twice** (`:121`, `:195`), which this phase must anchor both of.

**The abandonment was the smaller half of the problem.** `card/title` has FOUR emitters — two here
and two in `legacy.js` — so renaming one, or even both in this file, leaves the value still emitted
and the selection ⇒ emission arm still green. **A half-moved-contract mutation is only decisive on a
target with exactly ONE emitter**, and no member of the card family qualifies: every one of them
straddles the engine boundary.

Forty tokens do qualify. `DESIGN.md` now names `.reslist` — one emitter in `screens/add.tsx`,
selected 15 times — so **ACC-04 is claimed by phase 4**, where `data-part="result-list"` is created.
Nothing is owed here beyond anchoring both `ctitle` sites.

---

## Sub-phase 3.1 — the card container, its title and its body

One commit: `refactor(maquette-l02): anchor the card, title and body contracts on data-part`

- [ ] **Step 1.** Emit the anchors beside the existing classes **at both sites**. In the components:
      `<span className="ctitle" data-part="card/title">`. In `legacy.js`, the same values in its
      template strings: `<span class="ctitle" data-part="card/title" …>`. The class stays; L07
      removes it.
- [ ] **Step 2.** The namespace names the owning DOM concept, the leaf names the role, per the
      vocabulary fixed in phase 1: `card`, `card/title`, `card/body`. English, built from words
      `scripts/code-vocabulary.txt` holds.
- [ ] **Step 3.** Re-anchor the harness selections through `python3 scripts/rename-identifiers.py`,
      then **re-read the diff** — not the tool's _N file(s) touched_ line. `cards.py` alone carries
      `.ctitle` at `:145`, `:214`, `:339`, `:398`, `:405`, `:442`, `:494`; it also appears in
      `library_sort.py:37,90` and `page_host.py:450`. A compound such as
      `'#libitems .ctitle, #libitems .tile .nm'` is a **selector list**: migrate the `.ctitle` limb
      and leave `.tile .nm` to the phase that owns it.
- [ ] **Step 4.** Remove the corresponding baseline entries in this same commit.
- [ ] **Step 5.** `python3 scripts/check-markup-contracts.py; echo "exit=$?"` → `exit=0`. The
      selection ⇒ emission arm proves the ends met across **both** emission sites.
- [ ] **Step 6.** **ACC-03** — the guard falls on a re-introduced class anchor, and names it:

```bash
F=frontend/maquette/harness/cards.py; cp "$F" /tmp/l02-acc03.bak
python3 -c "
import pathlib
p = pathlib.Path('$F'); t = p.read_text()
old = '[data-part=\"card/title\"]'
assert t.count(old) >= 1, f'{t.count(old)} occurrences — mutation ABANDONED'
p.write_text(t.replace(old, '.ctitle', 1))"
python3 scripts/check-markup-contracts.py; echo "exit=$?"
cp /tmp/l02-acc03.bak "$F"
```

Expected: `exit=1`, the output naming `cards.py`, its line, and the selector `.ctitle`.

- [ ] **Step 7.** **ACC-04** — the guard falls on a half-moved contract, once amended per the section
      above. Expected: `exit=1`, naming `card/title` as selected by the harness and emitted by no
      source. This is the three-ends defect caught from the markup end.
- [ ] **Step 8.** Confirm both files were restored: `git status --short` clean apart from the
      intended change. A restored file is a claim to re-read, not to assume.
- [ ] **Step 9.** `run.sh` — no violation, hold counts unchanged. Commit.

## Sub-phase 3.2 — the foot and the cover

One commit: `refactor(maquette-l02): anchor the card foot and cover contracts on data-part`

`cfoot` has the widest component spread in this phase — 6 files — plus its engine site. That spread
is why it gets its own commit: a contract half-moved across six files is the state this lot exists
to make impossible, and a reviewer must see all of its ends in one diff.

- [ ] **Step 1.** Emit `data-part="card/foot"` and `data-part="card/cover"` at every site, engine
      included.
- [ ] **Step 2.** Re-anchor the harness selections; re-read the diff.
- [ ] **Step 3.** Remove the corresponding baseline entries in this same commit.
- [ ] **Step 4.** `check-markup-contracts.py` → `exit=0`; `run.sh` → no violation, hold counts
      unchanged. Commit.

## Sub-phase 3.3 — the poster, and the `data-no-poster` state

One commit: `refactor(maquette-l02): anchor the card poster and its no-poster state`

- [ ] **Step 1.** Emit `data-part="card/poster"` at every site, engine included.
- [ ] **Step 2.** Emit the state. In a component it is written
      `data-no-poster={hasNoPoster || undefined}` — never `={hasNoPoster}`, and the guard's fourth
      arm refuses the second form at the source. ACC-06 is what makes that arm rest on a measurement
      rather than on a belief about React.
- [ ] **Step 3.** Move the **2** `classList.contains('noposter')` assertions to
      `hasAttribute('data-no-poster')`, confirming for each that the element actually emits the
      attribute. An assertion moved onto an attribute nothing emits is always false; a
      `[data-no-poster]` selection onto the same is always true.
- [ ] **Step 4.** Remove the selection and assertion entries in this same commit. The phase total
      across 3.1–3.3 is **129**; the file must now hold **448**.
- [ ] **Step 5.** Mutation-test the state: make the emitting site drop the attribute
      unconditionally, confirm the migrated rule FALLS naming the right defect, restore. Commit.

---

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

`legacy.js` is edited here for the first time. That markup is **not** thrown away with the engine: a
surface converting into a component keeps its `data-part` and loses only its class. The oracle is
what proves those template-string edits moved no pixel.
