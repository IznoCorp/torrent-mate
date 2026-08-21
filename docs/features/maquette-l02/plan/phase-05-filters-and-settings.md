# Phase 5 — filters and settings: `fr`, `fn`, `fk`, `fs`, `settingrow`, `seg`, `sechead`

## Gate

Phase 4 must have produced, all committed:

- `data-part="result/list"`, `suggestion/wrap`, `episode`, `episode/popover` emitted, with `eppop`
  resolved at its own site rather than assumed;
- `classList.contains('ep')` left in place, and ACC-11 recorded: exactly 5 exceptions, each with a
  non-empty reason;
- `frontend/maquette/anchor-baseline.json` down to **405 entries** (448 − 43).

## Emission sites touched

| DOM concept  | `design/index.html` | `engine/legacy.js` | the 23 components | DESIGN row                      |
| ------------ | ------------------- | ------------------ | ----------------- | ------------------------------- |
| `fr`         | no                  | **yes**            | no                | _the engine only_               |
| `fn`         | no                  | **yes**            | no                | _the engine only_               |
| `fk`         | no                  | **yes**            | no                | _the engine only_               |
| `fs`         | no                  | **yes**            | no                | _the engine only_               |
| `settingrow` | no                  | no                 | **yes**           | _the components only_           |
| `seg`        | no                  | no                 | **yes** — 2 files | _the components only_           |
| `sechead`    | no                  | **yes**            | **yes** — 2 files | _the engine AND the components_ |

Four of the seven live **only** in the dying engine. That is not a reason to skip them, it is the
DESIGN's argument for doing them now: a rule still anchored on a class is a rule that breaks on the
day its surface converts out of `legacy.js` — which is exactly the day someone needs it to hold.

## Baseline entries removed

**59**: 57 class token occurrences — 13 distinct tokens, `fr`, `fn`, `fk`, `fs`, `fx`,
`settingrow`, `seg`, `sechead`, `field`, `fieldinput`, `fieldtoggle`, `optlist`, `opt` — plus the
**2** filter-state assertions `classList.contains('fempty')` and `classList.contains('fblocked')`,
which become `hasAttribute('data-empty')` and `hasAttribute('data-blocked')`. The baseline goes
405 → 346.

---

## Resolve the four abbreviations before naming them — do not guess

`fr`, `fn`, `fk` and `fs` are two-letter names in a 34 626-line engine. **Their meaning is not
recoverable from the token**, and a wrong guess bakes a wrong name into a contract that phases
after this one will read as authoritative.

- [ ] For each of the four, read its emission site in `frontend/maquette/design/src/engine/legacy.js`
      and the markup it produces. Name it from **what it is**, not from what the abbreviation looks
      like it might stand for.
- [ ] Write the resolved meaning into the commit message, one line each. A future reader must be
      able to check the naming decision without re-deriving it.
- [ ] The namespace names the owning DOM concept, the leaf names the role — `filter/row`,
      `setting/row`, `section/head`, and so on for the four once resolved.

**This is the phase with the highest naming risk in the lot**, which is why ACC-12 is claimed here:
seven new namespace values, four of them coined from abbreviations nobody can read at a glance. A
value is a name someone chose, so `CLAUDE.md` § Language applies in full — English, built from words
`scripts/code-vocabulary.txt` holds. Add a missing word by typing it into that file under review;
that one line is the whole point of the mechanism.

---

## Sub-phase 5.1 — the four engine-only filter tokens

One commit: `refactor(maquette-l02): anchor the filter contracts on data-part`

- [ ] **Step 1.** Resolve `fr`, `fn`, `fk`, `fs` per the section above, and record each meaning.
- [ ] **Step 2.** Emit the resolved `data-part` values beside the existing classes in `legacy.js`.
      The class stays; L07 removes it.
- [ ] **Step 3.** Check the vocabulary before the guard does:
      `python3 scripts/check-no-french.py; echo "exit=$?"` → `exit=0`. Run it now rather than at the
      gate: a name refused here costs one edit, a name refused at the gate costs a re-migration.
- [ ] **Step 4.** Re-anchor the harness selections via `python3 scripts/rename-identifiers.py`.
      **Two-letter tokens are the worst case for a rename**, and the tool's read-back check is
      skipped for `--values` runs and for Python files. Re-read the diff line by line, not the
      _N file(s) touched_ summary. Both corruptions found in this repository were found this way,
      after the tool reported success.
- [ ] **Step 5.** Remove the corresponding baseline entries in this same commit.
- [ ] **Step 6.** `python3 scripts/check-markup-contracts.py; echo "exit=$?"` → `exit=0`.
- [ ] **Step 7.** `run.sh` — no violation, hold counts unchanged. Commit.

## Sub-phase 5.2 — the filter states `data-empty` and `data-blocked`

One commit: `refactor(maquette-l02): anchor the empty and blocked filter states`

- [ ] **Step 1.** Emit the two states at their sites. Where the site is a component, the imposed
      idiom applies — `data-empty={isEmpty || undefined}`, `data-blocked={isBlocked || undefined}` —
      and the guard's fourth arm refuses `={isEmpty}` at the source. Where the site is the engine's
      template string, the attribute is written only when the state holds; an engine that always
      writes it makes `[data-empty]` match always, which is the same defect by another route.
- [ ] **Step 2.** Move `classList.contains('fempty')` to `hasAttribute('data-empty')` and
      `classList.contains('fblocked')` to `hasAttribute('data-blocked')`.
- [ ] **Step 3.** For each, confirm the element it asserts on actually emits the attribute. An
      assertion moved onto an attribute nothing emits is always false; a `[data-empty]` selection
      onto the same is always true. ACC-06 is what turned that from a belief into a measurement.
- [ ] **Step 4.** Mutation-test both: make each emitting site drop its attribute unconditionally,
      confirm the migrated rule FALLS and names the right defect, restore. Two states, two
      mutations — a single one proves only the arm it exercised.
- [ ] **Step 5.** Remove the 2 assertion entries from the baseline in this same commit.
- [ ] **Step 6.** Commit.

## Sub-phase 5.3 — the setting row, the segment and the section head

One commit: `refactor(maquette-l02): anchor the setting, segment and section-head contracts`

- [ ] **Step 1.** Emit `data-part="setting/row"` and `data-part="segment"` at their component sites.
- [ ] **Step 2.** Emit `data-part="section/head"` at **both** its sites — `legacy.js` and the two
      component files. This is the one concept in the phase that straddles the boundary, so all
      three of its ends move in this single commit.
- [ ] **Step 3.** Re-anchor the harness selections; re-read the diff.
- [ ] **Step 4.** Remove the corresponding baseline entries in this same commit. The phase total
      across 5.1–5.3 is **37**, and the file must now hold **131**.
- [ ] **Step 5.** **ACC-12** — no French entered the vocabulary:

```bash
python3 scripts/check-no-french.py; echo "exit=$?"
```

Expected: `exit=0`. Read the arm that matters here — the guard asks _is this word one we use?_, not
_is this word French?_, so a name built from a word nobody wrote into
`scripts/code-vocabulary.txt` is refused whatever language it comes from.

- [ ] **Step 6.** `run.sh` — no violation, hold counts unchanged. Commit.

---

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

`make check` runs `check-no-french.py` itself, so ACC-12 is re-exercised by the gate. Record both
outputs anyway: the criterion is filled in with what it **actually** printed as this phase lands,
never with what it was meant to print.
