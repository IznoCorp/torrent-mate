# L07 — Tailwind and CVA, surface by surface · plan

**Design** `../DESIGN.md`. **Branch** `feat/maquette-l07`. **Version** 0.98.37.
This file owns the reasoning and the ACCEPTANCE criteria; `IMPLEMENTATION.md` owns the status and
nothing else.

---

## The shape of the wave

Sixteen phases in two movements. **Phases 1–4 build the ground and convert nothing** — the base
layer, Tailwind's arrival, the palette rename, the motion guard. **Phases 5–15 convert one surface
each**, in D-L07-7's order. **Phase 16 removes the scaffolding** and amends the constitution.

The order is not a convenience. Every phase from 5 on composes what the phases before it built, and
L09 walks tiers A and B in the same sequence so its second pass reuses the understanding this one
produced.

### The recipe every conversion phase follows

Phases 5 through 15 differ only in their subject. Each one:

1. **Reads the CSS sections it owns** out of BLOCK 2 — named by line range in the phase file, so
   the scope is a fact rather than a judgement.
2. **Writes the component's variants first**, as CVA, typed. The variant table is the surface's API
   and it is written before a single utility is placed: a variant discovered while converting is a
   variant nobody designed.
3. **Converts, then deletes**. The hand-written rules leave BLOCK 2 in the same commit that adds
   the utilities replacing them. A conversion that leaves the old rules behind proves nothing —
   both sheets are in the document and the oracle cannot tell which one painted.
4. **Runs the oracle**. Zero divergence, or a divergence reviewed and named in
   `ACCEPTED-DIVERGENCES.md` with the fold that produced it. Not accepted on sight.
5. **Runs `--contracts` and the hold-count compare**. Unchanged, unless the phase names the
   movement.
6. **Lands with a rule that bites**, mutation-tested where the phase introduces behaviour that
   nothing already measures.

### Two traps this wave meets by construction, not by vigilance

**A shorthand hides a side.** `padding: 8px 12px` converts to `px-6 py-4`; drop one and the
computed `padding` changes on one axis only, which reads as a small visual nudge and is a defect.
The oracle measures `padding`, `margin`, `border` and `gap` as shorthands, so it catches this — it
is the single most valuable thing it does in this wave, and it is the reason no conversion phase
may close on a divergence it has not read.

**Compositor CSS is load-bearing.** Deleting one selector from a group once took `user-drag: none`
with it; native image drag came back and swallowed the pointer stream — one down, two moves, never
an up — and three gesture tests failed for a reason that looked nothing like a CSS deletion. The
18 declarations are in the base layer and refused by a rule **before phase 5**, which is why
phase 1 exists at all.

---

## The phases

| # | Phase | File |
| --- | --- | --- |
| 1 | The base layer, and what the compositor reads | `phase-01-the-base-layer.md` |
| 2 | Tailwind arrives, confined | `phase-02-tailwind-confined.md` |
| 3 | The palette takes Tailwind's name | `phase-03-the-palette-rename.md` |
| 4 | Motion, and the guard that reads class names | `phase-04-motion.md` |
| 5 | The shell | `phase-05-the-shell.md` |
| 6 | The shared primitives, and the first typed variants | `phase-06-the-primitives.md` |
| 7 | Arrivées, and its resolution screen | `phase-07-arrivals.md` |
| 8 | Médiathèque — the card | `phase-08-the-card.md` |
| 9 | Médiathèque — tiles, selection, filters | `phase-09-library.md` |
| 10 | Acquisition — the deck and the follows | `phase-10-acquisition.md` |
| 11 | Acquisition — the add screen, releases, quality | `phase-11-add-and-releases.md` |
| 12 | Média — the sheet, the matrix, the popover | `phase-12-the-media-sheet.md` |
| 13 | Système, and Maintenance | `phase-13-system-and-maintenance.md` |
| 14 | Configuration — the panel and its eight field kinds | `phase-14-settings.md` |
| 15 | Compte, and the install proposal | `phase-15-account-and-install.md` |
| 16 | BLOCK 1 dies, `refonte.html` dies, §15 is amended | `phase-16-the-scaffolding-dies.md` |

---

## ACCEPTANCE

Every criterion is a command with a documented expected output. A prose criterion is invalid.

### Gates that run at the close of EVERY phase

**The cadence is the operator's, arbitrated 2026-08-24, and it is a machine-cost decision rather
than a rigour one.** The full suite runs 55 rules with eight headless Chrome at a time and
saturates the machine for twenty minutes; the hold-count comparison runs the same 55 rules again.
Sixteen phases × two full runs is not a price this machine pays. **So the per-phase gate is the
two CHEAP instruments — the oracle at ~30 s and the five contract rules — and the full suite plus
the hold-count comparison run ONCE, before the wave merges.**

What that costs, said plainly rather than smoothed over: a rule outside the contract tier can
break at phase 7 and only be seen at phase 16, and it will then be attributable to a range of
phases rather than to one. The mitigation is not a hope — it is that the ORACLE, which is the
instrument this lot actually leans on, still runs at every phase and still names the state and the
region that moved.

| id | command | expected |
| --- | --- | --- |
| ACC-01 | `frontend/maquette/harness/run.sh --contracts` | exit 0, 5 rules |
| ACC-02 | `make maquette-oracle` | `0 divergence`, or divergences that appear in `ACCEPTED-DIVERGENCES.md` with a named fold |
| ACC-03 | `python3 scripts/check-compositor-css.py` and `python3 scripts/check-css-tokens.py` | exit 0 — both cheap, both read what this lot moves |

### Gates that run at the close of the WAVE

| id | command | expected |
| --- | --- | --- |
| ACC-04 | `frontend/maquette/harness/run.sh` | exit 0, 55+ rules, 0 failed |
| ACC-04b | `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` | `unchanged` for every rule, unless a phase named the movement |
| ACC-05 | `make lint` | 0 errors |
| ACC-06 | `make test` | `NNNN passed`, 0 failed **and 0 error** |
| ACC-07 | `make check` | exit 0 |
| ACC-08 | `cd frontend/maquette/design && npx tsc -b && npm run build` | exit 0 both — `tsc --noEmit` is not the gate |
| ACC-09 | `python3 frontend/maquette/a11y.py --check` | 0 violations, contrast included |
| ACC-10 | `python3 scripts/check-css-tokens.py` | exit 0 |
| ACC-11 | `python3 scripts/check-no-french.py` | exit 0 |

### Gates specific to this lot

| id | command | expected |
| --- | --- | --- |
| ACC-12 | `python3 scripts/check-compositor-css.py` | exit 0; the 18 declarations present. **Mutation**: delete one, the check exits 1 and names the property and its selector |
| ACC-13 | `python3 scripts/check-css-tokens.py --arm motion-classes` | exit 0. **Mutation**: write `duration-137` in a component, the arm exits 1 and names the file and the value |
| ACC-14 | `test ! -f frontend/maquette/design/refonte.html` | true at the close of phase 16 |
| ACC-15 | `ls frontend/maquette/design/src/styles/` | exactly `theme.css`, `base.css`, `legacy.css` — no fourth stylesheet |
| ACC-16 | `python3 scripts/check-legacy-css-residue.py` | exit 0; prints the residue's class count. **Mutation**: add a class to `legacy.css`, the check exits 1 and names it |
| ACC-17 | `cd frontend && npm run build && grep -c 'tm-\|\.device\|\.hbtn' dist/assets/*.css` | 0 — the maquette's scan does not reach production output |
| ACC-18 | `grep -n 'refonte.html' docs/reference/product-intent.md` | no match at the close of phase 16; §15 names the tokens and the component catalogue instead |
| ACC-19 | `grep -rln 'refonte\.html' --include='*.py' --include='*.mjs' --include='*.js' frontend scripts \| grep -v node_modules` | no match at the close of phase 16 (14 files on the day the wave opened) |
| ACC-20 | `python3 -c "import personalscraper"` | no output, exit 0 |

**Two of the commands above name something that does not exist, and both are correct.**
`ACCEPTED-DIVERGENCES.md` has no file under `maquette-l07/` because the wave ran at **0
divergence at the close of every phase** — the file is the alternative branch of ACC-02, and
there was nothing to write in it. L06 has one; this lot does not need one. And ACC-04b's
`--compare` reports **one** movement — R74, 9 → 10 — because `hold-counts-baseline.json` is still
the one recorded at L06's squash (`a4418e6a`, verified an ancestor of `HEAD`). That movement is
named in `IMPLEMENTATION.md`, which is what ACC-04b asks; the baseline is re-recorded from
`main`'s tip in the post-merge steps, beside the oracle reference.

**Three of these criteria did not close as written, and the table above is left standing.**
Added 2026-08-25, at the close of the wave; the full reasoning is the amendment at the foot of
`plan/phase-16-the-scaffolding-dies.md`, and § 7.1 of `docs/reference/frontend-architecture.md` is
why the rows are annotated here rather than rewritten.

- **ACC-15 — void as written, and met on its own subject.** BLOCK 1's harness rules could not be
  deleted: the oracle, the rule suite and `html.measuring` are built out of them, and the commit
  that claims « the rendering did not move » cannot also destroy the instrument that says so. They
  are `src/styles/harness.css`, a **fourth** stylesheet, imported once. It IS in the maquette's own
  build — the oracle measures inside the phone frame, so it must be — and it is in **no production
  build**, which is what ACC-17 proves (`grep -c` over `frontend/`'s built CSS → 0). It dies at
  switchover. The criterion's subject — « no hand-written component stylesheet survives » — holds.
  This is the lot's one deviation.
- **ACC-14 and ACC-19 — deferred, not met.** `refonte.html` still exists. It carries zero style
  rules, and it carries the wave's conversion ledger; and R72's hold (a) is the verbatim injection
  of it, so removing the file retires a hold — a rule renegotiation in `regions.json`, not a
  tail-of-session edit. Twelve live readers name the path (14 on the day the wave opened).
  **Recorded against L13**, where the residue, the ledger and the fragment resolve in one move.
- **ACC-18 — its subject is met; its COMMAND was wrong, and is corrected here rather than
  declared satisfied.** §15 no longer names the file as the product (`9c7e7379`). But the
  criterion greps the WHOLE of `product-intent.md` for the string, and § 7.1 forbids erasing the
  old text — so the amendment's own sentence (« ce paragraphe nommait … ») is a match, and so is
  §16's unrelated z-index note. A criterion whose command contradicts the method it serves is a
  criterion nobody can pass honestly. **Read as**: no line of §15 names the file as the visual
  reference; the only mention inside §15 is the dated amendment saying what it replaced.
  <sub>`awk '/^## §15/,/^## §16/' docs/reference/product-intent.md | grep -c 'refonte.html'` → 1,
  and that one line is the amendment's own account.</sub>

**ACC-02 is the one that decides this wave.** It runs at the close of every phase, not at the end.
A wave that runs it once at the end has proved that the sum of sixteen changes renders correctly,
which is exactly the unattributable result "surface by surface" exists to avoid.
