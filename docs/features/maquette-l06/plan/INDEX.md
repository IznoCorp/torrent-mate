# L06 — The scale · implementation plan

**Design**: `docs/features/maquette-l06/DESIGN.md`
**Lot contract**: `docs/reference/frontend-architecture.md` § « L06 — The scale », Phase 2
**Branch**: `feat/maquette-l06` · **version**: 0.98.28 → 0.98.29

---

## The order, and why it is this one

**Phase 1 comes first because nothing after it is provable.** The four folding phases each claim
« this declaration now reads a step ». That claim is empty until two things exist: the steps
themselves, declared in one place, and an instrument that counts what still sits outside them. A
fold measured against nothing is a diff someone read once. So phase 1 declares the scale, records
the ratchet's baseline, and **changes not one rendered pixel** — which is also the only moment in
this wave at which the oracle can be required to read `0 divergence`. Every phase after it moves
rectangles on purpose.

**The ratchet is what makes the middle phases independent.** Each fold lowers one family's count
and the guard refuses it going back up, so phase 3 cannot silently undo phase 2, and a folding
phase that misses a surface is visible as a number rather than as a memory. That is D-L06-3, and
it is the reason there is no flag day.

**Phase 5 is placed after the folds and before the closing phase for a reason of measurement**:
the contrast repairs are palette decisions, and a palette decision taken while the type sizes are
still moving is taken against a target that is moving too — axe's large-text rule (3:1 rather than
4.5:1) reads the rendered font size. Repairing contrast at 12.5 px and then folding that text to
11 px re-opens findings that were reported closed.

**Phase 6 is not paperwork.** The ratchet exists to be dismantled: a baseline is a tolerance, and a
tolerance nobody removes is how the disorder comes back one declaration at a time.

**Each phase carries its own hold, mutation-tested.** A rule that never bit proves nothing.

| #   | Phase                                        | File                                      | Status |
| --- | -------------------------------------------- | ----------------------------------------- | ------ |
| 1   | The measurement, the scale, the ratchet      | `phase-01-the-scale-and-the-ratchet.md`   | [ ]    |
| 2   | Space folds                                  | `phase-02-space-folds.md`                 | [ ]    |
| 3   | Type folds, and the fields reach 16 px       | `phase-03-type-folds.md`                  | [ ]    |
| 4   | Radius, motion, and the runtime token's home | `phase-04-radius-motion-runtime-token.md` | [ ]    |
| 5   | The palette pays its debt                    | `phase-05-the-palette-pays-its-debt.md`   | [ ]    |
| 6   | The ratchet dies, the gate closes            | `phase-06-the-ratchet-dies.md`            | [ ]    |

---

## Two plan-level decisions, taken here and named

Neither widens the lot; both close a hole the design's letter does not reach. They are listed in
the pull request beside D-L06-1…6.

**P-1 — The sign-in page is composed from marked chunks, and it does not get BLOCK 2.**
`serve.py` builds the standalone sign-in page by text search over `login:font`, `login:socle`,
`login:palette`, `login:style` and `login:splashstyle` (`refonte.html:10…4279`) — never by block.
Two of those chunks sit inside the folding perimeter: `login:style` holds `padding: 24px 20px` and
`login:splashstyle` holds the splash animation. Folded onto tokens declared in a `:root` block
that the composer does not emit, every one of them resolves to **nothing** on the live design
host — a landmine, not a crash, which is the exact shape § 6 of the architecture names. So the
scale block is wrapped in `login:scale:start` / `login:scale:end`, `serve.py` emits it first, and
a second arm of `check-css-tokens.py` holds the composition closed: every `var()` used inside a
`login:*` chunk is declared inside a `login:*` chunk.

**P-2 — The token names are the ones Tailwind v4 already reads.** D-L06-1 says the block lifts
into `@theme` wholesale when L07 lands. Tailwind v4's theme namespaces are `--spacing-*`,
`--text-*`, `--radius-*` and `--ease-*`; naming the steps anything else would make that lift a
rename, which is a second conversion for no proof. `--duration-*` has no Tailwind namespace and
stays an ordinary custom property.

---

## ACCEPTANCE — every criterion is an executable command with its expected output

Run from the repository root unless stated. `frontend/maquette/harness/run.sh` builds and
re-copies the prototype first, so nothing below measures a stale build. Where a criterion reads
the stylesheet directly it reads **BLOCK 2 only**: BLOCK 1 is the prototype's scaffolding, it
stops shipping at switchover, and it is outside this lot exactly as it is outside
`check-css-tokens.py`.

| ID     | Command                                                                                                                                          | Expected                                                                                                                                       |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | the block « ACC-01 — the scale is declared in ONE place » below                                                                                  | `1 N N` — one scale block, and every scale declaration in the file is inside it                                                                |
| ACC-02 | `python3 scripts/check-css-tokens.py --arm login`                                                                                                | `login: N var() use(s) in the composed chunks, all declared there.`, exit 0                                                                    |
| ACC-03 | `python3 scripts/check-css-tokens.py --arm scale`                                                                                                | `scale: spacing 0, text 0, radius 0, motion 0 — every declaration reads a step.`, exit 0                                                       |
| ACC-04 | see **The mutation tests** below, row « an off-scale declaration »                                                                               | exit 1, and the line names the selector, the property and the literal                                                                          |
| ACC-05 | `test -f frontend/maquette/scale-baseline.json; echo "exit=$?"`                                                                                  | `exit=1` — the baseline was dropped in phase 6, and the arm now refuses the first off-scale declaration outright                               |
| ACC-06 | `grep -c "tm-bottom-bar-h" frontend/maquette/design/src/engine/legacy.js; grep -rl "tm-bottom-bar-h" frontend/maquette/design/src/app/ \| wc -l` | `0` then `1` — no publisher left in the engine, exactly one in the shell                                                                       |
| ACC-07 | `grep -c "var(--tm-bottom-bar-h, 0px)" frontend/maquette/design/refonte.html; python3 scripts/check-css-tokens.py`                               | `8`, then `no unresolved \`var()\``, exit 0 — every use keeps its fallback                                                                     |
| ACC-08 | `python3 frontend/maquette/harness/runtime_tokens.py`                                                                                            | its holds, no violation, exit 0                                                                                                                |
| ACC-09 | `python3 -c "import json;print(json.load(open('frontend/maquette/a11y-contrast.json'))['counts']['byRule'])"`                                    | `{}` — the contrast run reads empty                                                                                                            |
| ACC-10 | `python3 frontend/maquette/a11y.py --check --rules color-contrast; echo "exit=$?"`                                                               | `a11y: 83 states, rules: color-contrast, 0 violation(s) over 0 rule(s)`, `exit=0` — and non-vacuous by the mutation below                      |
| ACC-11 | the block « ACC-11 — the three fields, resolved through the scale » below                                                                        | three lines, each naming a step whose value is **≥ 16px**                                                                                      |
| ACC-12 | `python3 frontend/maquette/harness/type_scale.py`                                                                                                | its holds, no violation, exit 0 — including the three fields measured in the browser                                                           |
| ACC-13 | the block « ACC-13 — no raw length left in the folded families » below                                                                           | `['0px']` at most — no raw length left in the folded families                                                                                  |
| ACC-14 | `make lint`                                                                                                                                      | 0 error                                                                                                                                        |
| ACC-15 | `make test`                                                                                                                                      | `NNNN passed`, 0 failed **and 0 error**                                                                                                        |
| ACC-16 | `make check`                                                                                                                                     | exit 0 (it runs `check-css-tokens.py`, so both new arms ride it)                                                                               |
| ACC-17 | `python3 scripts/check-no-french.py`                                                                                                             | 0 violation, exit 0                                                                                                                            |
| ACC-18 | `cd frontend/maquette/design && npx tsc -b`                                                                                                      | exit 0                                                                                                                                         |
| ACC-19 | `frontend/maquette/harness/run.sh`                                                                                                               | `harness: N rule(s), no violation.`, then the a11y tier at hard zero, then the oracle at `no divergence`, exit 0                               |
| ACC-20 | `frontend/maquette/harness/run.sh --contracts`                                                                                                   | 5 rules, no violation, exit 0                                                                                                                  |
| ACC-21 | `python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json`                                                   | no movement, exit 0 — the baseline having been re-recorded in the phases that add a rule, and each such re-record named in that phase's report |
| ACC-22 | `make maquette-oracle`                                                                                                                           | `no divergence` over 83 states × 33 regions, exit 0, against the reference re-recorded on this branch                                          |
| ACC-23 | `python3 frontend/maquette/a11y.py --check`                                                                                                      | hard zero, exit 0, and **no** « recorded for L06, not part of this floor » line — that carve-out is gone                                       |
| ACC-24 | the block « ACC-24 — every accepted divergence carries a reason » below                                                                          | `N 0` — N accepted divergences, **not one without a written reason**                                                                           |

### The four criteria that do not fit a table cell

They are shell blocks rather than one-liners for one reason: a command a reader has to unescape
before running is a command nobody runs. Each is run from the repository root.

**ACC-01 — the scale is declared in ONE place.** It answers two questions at once: how many scale
blocks exist, and whether any scale token is declared outside the one that does.

```bash
python3 - <<'PY'
import pathlib, re
text = pathlib.Path("frontend/maquette/design/refonte.html").read_text(encoding="utf-8")
blocks = re.findall(r"/\* scale:start \*/(.*?)/\* scale:end \*/", text, re.S)
name = r"--(?:spacing|text|radius|duration|ease)-[\w-]+\s*:"
print(len(blocks), len(re.findall(name, text)), len(re.findall(name, "".join(blocks))))
PY
```

**ACC-11 — the three fields, resolved through the scale.** A grep on the selector proves only that
it names a token; what the criterion is about is the pixel value that token carries.

```bash
python3 - <<'PY'
import pathlib, re
text = pathlib.Path("frontend/maquette/design/refonte.html").read_text(encoding="utf-8")
steps = {k: v.strip() for k, v in re.findall(r"--(text-[\w-]+)\s*:\s*([^;]+);", text)}
for selector in (".search input", ".fieldinput", ".fieldinput.mono"):
    body = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text).group(1)
    token = re.search(r"font-size:\s*var\(--(text-[\w-]+)\)", body).group(1)
    print(selector, token, steps[token])
PY
```

**ACC-13 — no raw length left in the folded families.** BLOCK 2 only, comments stripped: a value
commented out used to satisfy a rule in this repository, and reading CSS as text is the mistake
that let it.

```bash
python3 - <<'PY'
import pathlib, re
text = pathlib.Path("frontend/maquette/design/refonte.html").read_text(encoding="utf-8")
start = text.find("BLOCK 2")
block2 = re.sub(r"/\*.*?\*/", " ", text[start:text.find("</style>", start)], flags=re.S)
props = r"padding|margin|gap|row-gap|column-gap|border-radius|font-size"
values = re.findall(r"(?:^|[{;\s])(?:" + props + r")[\w-]*\s*:\s*([^;}]+)[;}]", block2, re.M)
print(sorted(set(re.findall(r"(?<![\w-])\d*\.?\d+px(?![\w-])", " ".join(values)))))
PY
```

**ACC-24 — every accepted divergence carries a reason.** The last cell of each row is the reason;
an empty one is an entry that was waved through.

```bash
python3 - <<'PY'
import pathlib, re
lines = pathlib.Path(
    "docs/features/maquette-l06/ACCEPTED-DIVERGENCES.md"
).read_text(encoding="utf-8").splitlines()
rows = [line for line in lines
        if line.startswith("|")
        and not re.match(r"^\|\s*-", line)
        and not line.lower().startswith("| state")]
print(len(rows), sum(1 for row in rows if not row.rstrip("| ").rsplit("|", 1)[-1].strip()))
PY
```

**ACC-24 is the criterion that says this wave did not wave the oracle through.** This lot moves
pixels on purpose, so `no divergence` at the end proves only that the reference was rewritten. What
proves the review happened is that every rectangle that moved has a line saying why. The list lives
at `docs/features/maquette-l06/ACCEPTED-DIVERGENCES.md`, on the branch, one section per folding
phase, and phase 6 copies it into the pull request body.

**ACC-13 has a floor of `['0px']` rather than `[]`, and the difference is deliberate.** `0px` is
the absence of a step, not a step: writing `var(--spacing-0)` for it would add a token that means
nothing and cost a lookup at every use. A raw `0` is left as `0`.

---

## The mutation tests — each hold is broken on purpose, once

Per the repository's rule the fix is **committed first**, then the mutation is applied, observed
and restored. A hold lands only after it has been seen to fall **and to name the right defect**.

| Hold                                     | The mutation                                                                                       | It must say                                                                                    |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `scale` arm — an off-scale declaration   | append `.scalecheck{padding:13px}` after `/* scale:end */`, run `--arm scale`, restore             | `.scalecheck` `padding: 13px` — `13px` is on no step of the spacing scale                      |
| `scale` arm — the scale declared twice   | declare `--spacing-4: 8px` a second time in the palette `:root`                                    | the scale is declared in two places; one block, or the next reader edits the copy nobody reads |
| `scale` arm — the ratchet                | with phase 1's baseline in place, add one off-scale `gap`                                          | the spacing count went UP against its baseline                                                 |
| `login` arm                              | fold one `login:style` declaration onto a token and remove the `login:scale` chunk from `serve.py` | the composed sign-in page uses a token it is not given                                         |
| `type_scale.py` — the fields             | set `.search input` back to `font-size: 13px`                                                      | the search field renders at 13 px, under the 16 px at which a focused field zooms iOS          |
| `type_scale.py` — the steps              | give one heading a literal `font-size: 17px`                                                       | a rendered size that is on no step                                                             |
| `runtime_tokens.py` — the publisher      | delete the shell's `publishBarHeight()` call                                                       | `--tm-bottom-bar-h` is never published; everything above the bar sits on its fallback          |
| `runtime_tokens.py` — one publisher only | re-add the publisher to `legacy.js` alongside the shell's                                          | the runtime token has two publishers, and the engine is the one that dies                      |
| `a11y.py` — contrast in the floor        | restore the count badge's pre-repair foreground                                                    | `color-contrast` in the enforced total, exit 1                                                 |
| the arm with **no** baseline (phase 6)   | after dropping the baseline, add one off-scale `padding`                                           | there is no baseline any more; every declaration reads a step                                  |

---

## The oracle protocol for this lot

Unlike L04 and L05, **the whole point here is that pixels move**, so the wave cannot hide behind a
green oracle and cannot be gated on one either. Per phase, in this order:

1. `make maquette-oracle` — read the divergence list in full, never a count.
2. For each divergence: decide whether the scale **explains** it. A divergence the scale does not
   explain **fails the phase** — it is a fold that went somewhere unintended, and it is repaired
   before anything is accepted.
3. Write each accepted divergence into `ACCEPTED-DIVERGENCES.md` under that phase's section, with
   its reason. « The fold moved this » is not a reason; « `.chip` padding 9 px → `--spacing-4`
   (8 px), the row is 2 px shorter » is.
4. `python3 frontend/maquette/oracle.py --accept`, then **read
   `git diff frontend/maquette/oracle-reference.json`** — the oracle's own docstring says it, and
   it is where the review actually happens.
5. Commit the reference with the phase.

**Phase 1 reads 0 divergence**, and that is a hold rather than an expectation: it declares tokens
nothing uses yet.

---

## What this plan refuses to do

- **Convert anything to Tailwind or CVA.** That is L07, and this lot exists to give it a scale to
  convert onto.
- **Touch BLOCK 1.** The prototype's scaffolding is deleted at switchover, not folded.
- **Change markup or behaviour**, with the single exception D-L06-4 names: the publisher of
  `--tm-bottom-bar-h` moves from the engine to the shell.
- **Fold `--tm-bottom-bar-h` into the scale.** It is a measured height, and replacing a
  measurement with a constant is replacing it with a hope.
- **Repair the `page_host.py` / `oracle.py` module-size WARNs**, B-036, B-040, B-041, B-042, or the
  live-database rule class open since #484.
