# SP5a — the visual vocabulary becomes shippable

> Wave 18 of the `shell-mobile` mission. Serves `docs/reference/product-intent.md` **§15**
> (the maquette IS the product; it is modified first and the code derives from it) and the
> mission engraved on 2026-08-19 (every screen is redrawn; the UX, the interaction language and
> the prototype's ARCHITECTURE are consolidated before the interface is frozen).

## Why this wave exists

SP5 is « the visual language ». Before a language can be tightened, it has to be **shippable**,
and today it is not. Every figure below was measured on 2026-08-20 and carries its command.

### 1. The vocabulary is declared in the block that is never shipped

`design/refonte.html` is split in two: **BLOCK 1** (lines 4-266) carries the header
`PROTOTYPE HARNESS. NEVER EXTRACTED INTO THE APP`, and **BLOCK 2** (267-4216) is the application
CSS the extraction transplants.

| Measure                                                      | Value                   |
| ------------------------------------------------------------ | ----------------------- |
| token declarations in BLOCK 1                                | **35**                  |
| token declarations in BLOCK 2                                | **1**                   |
| of BLOCK 1's tokens, how many the application's own CSS uses | **34**                  |
| genuinely harness-only                                       | **1** (`--mq-white-70`) — it moved anyway, see below |

So the sheet the extraction produces — `frontend/src/styles/ps/app-surface.css`, which **is** the
redesign — **uses 35 tokens and defines 1**, across **449** `var()` calls (`grep -oE 'var\(\s*--[a-zA-Z0-9_-]+' frontend/src/styles/ps/app-surface.css | wc -l`). Ten of them are defined
nowhere in production either:

`--danger-texte` · `--info-texte` · `--primary-texte` · `--success-texte` · `--warning-texte` ·
`--mq-scrim-doux` · `--mq-shadow-badge` · `--mq-shadow-carte` · `--mq-shadow-pop` ·
`--mq-tile-overlay`

That is the shape of B-014: **named, and defined by nothing**. It is also the material reason the
redesign cannot simply be switched on — wiring `app-surface.css` in today would resolve those ten
to nothing.

> `--tm-bottom-bar-h` is NOT one of them, and the distinction matters: it is published at runtime
> by JavaScript in both trees (`legacy.js:11499`, `frontend/src/components/layout/bottom-bar-metrics.ts:24`)
> and every use carries a documented `, 0px` fallback. A token set by script is not a token owed.

### 2. Seven tokens carry French names, in BOTH trees

`--danger-texte`, `--info-texte`, `--primary-texte`, `--success-texte`, `--warning-texte`,
`--mq-scrim-doux`, `--mq-shadow-carte` — present in `design/refonte.html` and in
`frontend/src/styles/`.

`CLAUDE.md` §Language is unambiguous: « English names, everywhere and always: identifiers,
function/type/class names (code **AND CSS**) ». A custom-property name is a name someone chose.

**And no arm reads them.** Arm 4 reads CSS _class_ names only
(`declared_css_classes`, `scripts/check-no-french.py`). This is the pattern the repository has
now paid for three times — « `data-*` names had a rule and no arm », « `frontend/scripts/` was
outside every scope ». A rule with no arm is a sentence in a file.

### 3. The parity probe CANNOT see any of this, and says so itself

Before trusting the probe as this wave's oracle, read what it does — the comment is in
`scripts/parity-probe.py` (~line 170):

> `// The DOM is untouched: only the dressing changes. BLOCK 1 stays, because it is the phone`
> `// frame the prototype lives inside and removing it would move every region for a reason`
> `// that has nothing to do with the extraction.`

**BLOCK 1 stays in the document for BOTH passes.** So the tokens it declares are available to the
extracted sheet while it is being measured — which is precisely why the probe reports
`0 divergence` even though `app-surface.css` defines one token out of the thirty-five it uses.
The probe measures the extraction of BLOCK 2 *with BLOCK 1 still in the room*.

That is not a defect of the probe — removing BLOCK 1 really would move every region for an
unrelated reason. It is a **limit of what it proves**, and it changes this wave's acceptance:

- The probe proves **the move changed no rendering**. Keep it; it is the right hold for that.
- It proves **nothing** about whether the vocabulary ships. A separate, cheap hold does:
  *every `var()` in the generated sheet must resolve to a declaration in that same sheet.*

**That hold is the wave's real deliverable.** Moving the tokens once is an edit; a gate that
refuses the next `var()` with no definition is what makes it stay true — and a count nobody
compares is a count nobody reads.


### 4. The extractor silently drops the light theme — and nothing would notice

`apply_scope()` rewrites `:root[data-theme="light"]` to **`.tm`**, discarding the attribute:

```
:root                          → .tm
:root[data-theme="light"]      → .tm          ← the qualifier is gone
:root[data-theme="light"] body → :root[data-theme="light"] .tm body
```

Both theme blocks would collapse onto one selector of equal specificity, and the later one would
win unconditionally: **the theme switch dies**, while the extracted text stays exactly what the
extractor emits — invisible to `--check`, which is textual.

Three facts make this the wave's first task rather than a footnote:

- The light theme is **live in the maquette** (`legacy.js:11660` sets `data-theme="light"`) and
  **absent from production** (zero `data-theme` in `frontend/src`) — it is a feature of the next
  version, exactly what this prototype is for.
- **No named state exercises it.** Neither the 82 states of `states.js` nor the 49 the probe
  drives touch the theme, so `parity-probe.py` measures the dark theme only.
- It is **latent today** only because the theme tokens sit in BLOCK 1 and are never extracted.
  Task 3 of this wave moves them — which turns a dormant bug into a shipped one **unless the
  oracle is repaired first**.

## What this wave does — and the order is the design

**The oracle is repaired before the change it has to catch.** Reversing these two steps would
move the tokens under a probe that cannot see the theme, and the wave would go green over a dead
theme switch.

| #      | Work                                                                                                                                                                  | Proof                                                                                                               |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **A1** | `apply_scope()` preserves attribute and class qualifiers on `:root` / `html` / `body`: `:root[data-theme="light"]` → `:root[data-theme="light"] .tm`                        | Unit test written RED first; mutation — restore the drop, confirm the test names the theme                          |
| **A2** | A named light-theme state in `states.js`, and in `regions.json`'s `states`, so the probe drives both themes                                                           | The probe's measurement count RISES; the new state is listed in its summary                                         |
| **A3** | Move the 34 application tokens — both the `:root` and the `:root[data-theme="light"]` blocks, in that order — from BLOCK 1 into BLOCK 2. `--mq-white-70` travels with them | `parity-probe.py`: 0 divergence at the new baseline. Computed values are identical, so this is a move, not a change |
| **A4** | Rename the 7 French tokens to English, in the maquette AND in `frontend/src/styles/` in the SAME step — a contract has ends and they move together                    | `parity-probe.py`: 0 divergence. `grep` for the old names: zero hits outside dated records                          |
| **A5** | Arm 14 of `check-no-french.py`: custom-property NAMES are names                                                                                                       | Mutation — reintroduce `--danger-texte`, confirm the arm falls and names it                                         |
| **A6** | Regenerate `app-surface.css`                                                                                                                                          | `make check` — `extract-maquette-css.py --check` green                |
| **A7** | **`scripts/check-css-tokens.py`**, wired into `make check` and CI: every `var(--x)` in the generated sheet resolves to a declaration in that sheet, or to a documented runtime token (`--tm-*`, published by script, every use carrying a fallback) | Mutation — delete one declaration, confirm the guard falls and names it. This is the hold the parity probe structurally cannot provide |

### What this wave deliberately does NOT do

- **It does not touch a single value.** Not one `font-size`, `padding`, `border-radius` or `gap`
  changes. Tightening the scale — 21 distinct type sizes, 16 radii, 64 padding values, and three
  spellings of one pill (`99px` ×25, `9999px` ×11, `50%` ×1) — is **SP5b**, and it is a different
  KIND of proof: SP5a's probe must stay green, SP5b's must go red exactly where a value moved.
- **It does not wire `app-surface.css` into the app.** Nothing imports it, and adopting it IS
  shipping the redesign — the operator's decision, never a wiring detail
  (`CLAUDE.md` §Design Reference, `product-intent.md` §15).
- **It draws no surface.** `/control` and `/pipeline` are owed since the 2026-08-19 mission and
  are their own wave.

## Acceptance

Every criterion is an executable command with its expected output.

| ID         | Command                                                                                                 | Expected                                                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **ACC-01** | `python3 scripts/parity-probe.py`                                                                       | `0 divergence(s)`, exit 0, at a measurement count **strictly greater** than the 807 recorded on 2026-08-20 (A2 adds a theme) |
| **ACC-07** | `python3 scripts/check-css-tokens.py` | exit 0 — no `var()` in the generated sheet is undefined |
| **ACC-02** | `python3 -c` on `apply_scope(':root[data-theme="light"]')` | `:root[data-theme="light"] .tm` — the scope FOLLOWS the qualified root. `.tm[data-theme="light"]` is the 7 300-divergence form, not the fix |
| **ACC-03** | `python3 scripts/check-css-tokens.py` | exit 0. NOT « zero tokens used-and-undeclared »: `--tm-bottom-bar-h` is used and declared nowhere ON PURPOSE — it is published at runtime and carries a `0px` fallback, which the guard knows and a hand-counted grep does not |
| **ACC-04** | `grep -rE '\-\-[a-z-]*(texte\|doux\|carte)' frontend/src/styles/ frontend/maquette/design/refonte.html` | no match                                                                                                                     |
| **ACC-05** | `python3 scripts/check-no-french.py`                                                                    | exit 0, and its summary names **14** arms                                                                                    |
| **ACC-06** | `make check`                                                                                            | exit 0                                                                                                                       |

## Risks, and what makes each survivable

| Risk                                                                | Why it is contained                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Moving the tokens changes the cascade                               | Both blocks move together, preserving relative order; `:root` and `:root[data-theme="light"]` keep their different specificities. Custom properties resolve at computed-value time, so position within one `<style>` does not matter — and the probe measures the computed result, not the text |
| A token is declared twice and the move splits the pair              | 22 tokens ARE declared twice (the two theme blocks). Measured before designing; the pair is the unit that moves                                                                                                                                                                                 |
| Renaming a token in production « derives app code »                 | It does not: this is the English-names rule applied to production's own stylesheet, precedented by #455, which renamed a `controle/` directory and 19 French names there. No rendering changes                                                                                                  |
| The probe passes because the new state does not really switch theme | A2's own hold: the state must be shown to produce a DIFFERENT computed background from its dark twin, or it is measuring nothing                                                                                                                                                                |

---

## What actually happened — recorded 2026-08-20

**The order paid off on the first day.** A1 repaired the extractor, A3 moved the tokens, and the
probe went to **7 300 divergences** — because A1's first repair was wrong in a way that reads as
correct: it kept the qualifier but welded it to the scope, `.tm[data-theme="light"]`. The
attribute sits on `<html>` and the scope class on `<body>`, so that selector asks ONE element for
both and matches nothing; the whole light theme fell back to dark. Had the tokens moved first,
that would have shipped under a green textual guard.

**The probe was measuring one theme, and nobody had chosen which.** `parity-probe.py` set no
`color_scheme`, so it took Playwright's default — light — while `harness/common.py` pins its own
contexts to `dark`. Both are measured now (`THEMES`), the theme is in every divergence label, and
the count went 807 → **1 614**.

**Arm 14 found no French — because A4 had already removed it — but it found something else.**
Sixty-six ordinary English design words (`background`, `muted`, `radius`, `tracking`, the size
scale) were unknown to `code-vocabulary.txt`: the list had been seeded from identifiers and had
never met a stylesheet. They are merged in. **Not « none of them was French »** — `accent`,
`danger`, `signal`, `normal`, `modal`, `font` are French words too, and saying otherwise
would be the very mistake this file exists to end: the question is « is this a word we use? »,
never « is this French? ». The merge widens what every arm accepts, deliberately. One real exception is pinned by NAME with its reason:
`--font-sans` is the CSS `sans-serif` family, and `sans` is also a French preposition — adding
`sans` to the vocabulary would have licensed it in every identifier in the repository.

**Two module splits, both forced by the 1 000-line block**: `nofrench_ratchets.py` (the arms that
COUNT rather than refuse) landed in the previous wave, and `nofrench_css.py` (the arms and
helpers that read a STYLESHEET) in this one, taking `vocabulary()` back to the lexicon it reads.

**`lint-tokens.sh` (C19) gained one exemption, with its reason.** It refuses raw colours outside
`src/styles/ps/tokens/`; `app-surface.css` is generated and now carries the redesign's own token
block, so it is a token SOURCE. « Use a DS token » has no reader in a file no hand may edit — and
what its `var()` calls resolve to is held by `check-css-tokens.py` instead.

### Two entries of the table above describe work that did not happen as written

Recorded rather than quietly amended, because a plan that is edited to match the outcome
teaches nothing about how plans go wrong.

- **A3 said `--mq-white-70` stays behind. It moved.** The unit that travelled was the whole
  `login:palette` region, markers included — the login gate finds it by text search, so moving
  it in one piece is what kept that gate working. `--mq-white-70` sits inside that region, so
  35 tokens moved where the table said 34. The cost is one dead token in the shipped sheet, and
  `check-css-tokens.py` does not flag it: it refuses a `var()` with no declaration, not a
  declaration with no `var()`. That asymmetry is deliberate — an unused token is 40 bytes, an
  unresolved one is a broken surface — but it is worth naming.
- **A2 said « a named light-theme state in `states.js` ». No such state was written.** The theme
  became an axis of the PROBE instead (`THEMES`), which is stronger for this purpose: it measures
  every one of the 49 states under both schemes rather than adding a 50th. But A2's own hold —
  « the state must be shown to produce a DIFFERENT computed background from its dark twin » —
  was then never exercised by anything in this wave. The 7 300 divergences did exercise it, by
  accident and in the other direction. A named state remains owed for SP5b.
