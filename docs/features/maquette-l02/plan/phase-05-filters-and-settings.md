# Phase 5 — filters and settings: `fr`, `fn`, `fk`, `fs`, `settingrow`, `seg`, `sechead`

## Gate

Phase 4 must have produced, all committed:

- `data-part="result/list"`, `suggestion/wrap`, `episode`, `episode/popover` emitted, with `eppop`
  resolved at its own site rather than assumed;
- `classList.contains('ep')` left in place, and ACC-11 recorded: exactly 5 exceptions, each with a
  non-empty reason;
- `frontend/maquette/anchor-baseline.json` down to **444 entries** (490 − 46).

## Measured on the committed baseline, not estimated

**57 token occurrences**: `.fr` 11, `.fx` 9, `.settingrow` 7, `.sechead` 6, `.fieldinput` 6,
`.fn` 4, `.seg` 4, `.fk` 3, `.fs` 2, `.field` 2, and one each of `.optlist`, `.opt`,
`.fieldtoggle`. By file: `settings.py` 14, `machine.py` 13, `arrivals.py` 6, `page_host.py` 6,
`address.py` 4, `audit.py` 3.

Emitters: **the five abbreviations — `.fr`, `.fn`, `.fk`, `.fs`, `.fx` — are the engine's
alone**, which is why the section below insists they are RESOLVED before they are named. The
setting/field/option tokens are components-only; `.sechead` straddles.

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

**76, and the first draft could remove 52.** It counted FOUR engine abbreviations where there are
five — `.fx` is the fifth, 10 occurrences — and named none of the field family. Measured on the
committed 834-entry baseline, call + held:

| Sub-phase | Removes | Tokens |
| --- | --- | --- |
| 5.1 | **30** | `.fr` 11 · `.fn` 4 · `.fk` 3 · `.fs` 2 · **`.fx` 10 (1 held)** — the five engine abbreviations |
| 5.2 | **2** | the `fempty` / `fblocked` assertions → `data-empty` / `data-blocked` |
| 5.3 | **20** | `.settingrow` 8 (1 held) · `.seg` 6 (2 held) · `.sechead` 6 |
| 5.4 | **24** | `.fieldinput` 14 (**8 held**) · `.field` 3 (1 held) · `.fieldtoggle` 3 (2 held) · `.opt` 3 (2 held) · `.optlist` 1 |

30 + 2 + 20 + 24 = **76**. The baseline goes **444 → 414 → 412 → 392 → 368**. **`option` is absent
from `scripts/code-vocabulary.txt`** (measured 2026-08-21); 5.4 adds it in the same commit.

## Resolve the four abbreviations before naming them — do not guess

> **Resolved on 2026-08-21, by reading `legacy.js:7586-7591` and `refonte.html:1687-1720` — they are
> not filters.** They are the rows of the **flux**, the pipeline status list on Arrivées:
>
> | Class | What it is | `data-part` |
> | --- | --- | --- |
> | `.fx` | one row — `<li class="fx">`, with `fempty` / `fblocked` / `fclick` modifiers | `flux/row` |
> | `.fn` | the row's name (`ligne.l`) | `flux/name` |
> | `.fr` | the row's value — a badge or a figure (`ligne.ton`, `value`) | `flux/value` |
> | `.fs` | the row's sub-line (`ligne.k`, `ligne.s`) | `flux/detail` |
> | `.fk` | the key inside the sub-line (`ligne.k`) | `flux/key` |
>
> **`.fr` serves two concepts.** `legacy.js:9943` also emits `<span class="fr">` as a library TILE's
> sub-line (`sousLigne`), and 9 of the harness's 11 `.fr` selections are bare `'.fr'` — their
> concept is the STATE the rule drives, not the class: `machine.py`'s belong to the flux,
> `audit.py`'s `#libitems … .fr` to a tile. Each bare one is resolved by reading the rule, and the
> tile ones take `tile/subtitle` (the tile container itself is phase 6's). **`flux` is absent from
> the vocabulary** — English, added by 5.1. `fempty` / `fblocked` are rendered in the same template
> string as the class (`class="fx${empty ? " fempty" : ""}"`), so 5.2 emits `data-empty` /
> `data-blocked` in that template, not through a `classList` toggle.

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

> **Never the Edit tool on `legacy.js`.** A formatter hook reformats the whole engine (33 000 lines) on
> the first `Edit`, silently in a `--stat`; 3.2 reverted and re-applied by script. Every engine change
> is applied by a script that rewrites exactly the bytes meant, then `git diff --stat`-checked.

> **`py_compile` every harness file after every rewrite.** A `data-part` value carries a `/`, so its
> selector needs quotes; substituted into a single-line double-quoted Python string, the raw `"`
> breaks the file — and the guard, the baseline, the oracle and the classifier all stayed green over
> two unparseable rule files in 4.1. `python3 -m py_compile frontend/maquette/harness/*.py` takes two
> seconds and must print nothing, before any proof.

> **Rewrite per string token, never per line.** The baseline's `line` is where the string literal
> BEGINS; in a multi-line `"""…"""` JS block the token can sit lines below, and a per-line
> rewrite aborts there (3.1 ran one, discarded it, and redid its 79 through `tokenize`). For each
> entry, locate the string token starting at (file, line), rewrite your class token inside it, and
> reconcile the whole-corpus count of your tokens against the baseline's before you start. Then
> re-host any single-line double-quoted string now carrying `[data-part=\"` in `'…'` or a
> triple-quoted string — the guard refuses the escaped shape.

## Sub-phase 5.1 — the five engine-only tokens: the flux's rows

> **Five, not four.** `.fx` is emitted by `legacy.js` alone like the other four and is selected 10
> times; the first draft counted it among the tail. It is resolved and named with them.

One commit: `refactor(maquette-l02): resolve and anchor the five engine filter tokens on data-part` — « filter » kept in the subject as the name these classes carried; they are the flux's rows

- [ ] **Step 1.** Resolve `fr`, `fn`, `fk`, `fs`, **`fx`** per the section above, and record each meaning.
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

## Sub-phase 5.2 — the flux row's states `data-empty` and `data-blocked`

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

## Sub-phase 5.4 — the field family and the options

One commit: `refactor(maquette-l02): anchor the setting fields and options on data-part`

Components only. More than half of these occurrences are HELD — `page_host.py`'s tables select
`.fieldinput` by the dozen — so the classifier's `held` entries are most of the work here.

| Token | `data-part` | Emitted by |
| --- | --- | --- |
| `.field` | `field` | components (4 sites) |
| `.fieldinput` | `field/input` | components |
| `.fieldtoggle` | `field/toggle` | components |
| `.optlist` | `option/list` | components |
| `.opt` | `option` | components |

- [ ] **Step 1.** Add `option` to `scripts/code-vocabulary.txt` (re-check first), sorted, DESIGN section.
- [ ] **Step 2.** Emit each anchor beside its class at every component site.
- [ ] **Step 3.** Re-anchor the 24 occurrences — 13 of them held — by literal replacement with
      asserted counts.
- [ ] **Step 4.** `--write-baseline` → `24 removed`, landing at **368**. Guard exit 0. This
      sub-phase CLOSES phase 5.
- [ ] **Step 5.** `run.sh` / hold counts — no violation, unchanged. Commit.

## Closing proofs — run all three, record what they printed

```bash
python3 frontend/maquette/oracle.py --check          # no divergence, exit 0
frontend/maquette/harness/run.sh                     # no violation, per-rule hold counts UNCHANGED
make check                                           # exit 0
```

`make check` runs `check-no-french.py` itself, so ACC-12 is re-exercised by the gate. Record both
outputs anyway: the criterion is filled in with what it **actually** printed as this phase lands,
never with what it was meant to print.
