# Phase 1 — The measurement, the scale, the ratchet

**Nothing after this phase is provable without it.** Every folding phase claims that a declaration
now reads a step; that claim needs the steps to exist in one place and an instrument that counts
what is still outside them. This phase creates both and **changes not one rendered pixel** — which
is what makes it the only phase in the wave whose oracle must read `0 divergence`.

## 1.1 — The histograms, and the steps they support

**The measurement comes first and it is recorded HERE, before anything is folded.** § 6 of the
architecture names the trap this closes: _a derivation must not read back its own output_. Steps
chosen against the stylesheet as it stands are chosen against evidence; steps re-derived later,
from a stylesheet the fold has already touched, are the fold agreeing with itself.

The quick shape, per family, is the one the lot's design uses:

```bash
cd frontend/maquette/design
grep -oE "padding:[^;]+;" refonte.html | sort | uniq -c | sort -rn
grep -oE "gap:[^;]+;" refonte.html | sort | uniq -c | sort -rn
grep -oE "margin:[^;]+;" refonte.html | sort | uniq -c | sort -rn
grep -oE "font-size:[^;]+;" refonte.html | sort | uniq -c | sort -rn
grep -oE "border-radius:[^;]+;" refonte.html | sort | uniq -c | sort -rn
grep -oE "(transition|animation)[^;]+;" refonte.html | sort | uniq -c | sort -rn
```

Those read the whole file. **The tables below read BLOCK 2 only** — BLOCK 1 is the prototype's
scaffolding and stops shipping at switchover, so folding it would be work thrown away with the
block that holds it. This is the command that produced them, and it is the one to re-run:

```bash
cd frontend/maquette/design
python3 - <<'PY'
import collections, re
text = open("refonte.html", encoding="utf-8").read()
start = text.find("<style")
marker = text.find("BLOCK 2", start)
block2 = text[text.rfind("/*", start, marker):text.find("</style>", start)]
for prop in ("padding", "gap", "margin", "font-size", "border-radius"):
    found = re.findall(r"(?:^|[{;\s])" + prop + r"\s*:\s*([^;}]+)[;}]", block2, re.M)
    counts = collections.Counter(value.strip() for value in found)
    print(f"### {prop}: {len(counts)} distinct, {sum(counts.values())} declarations")
    for value, count in counts.most_common():
        print(f"  {count:3d}  {value}")
PY
```

### Space — 25 distinct atoms across `padding`, `gap` and `margin`

The atoms, not the declaration strings: `padding: 11px 12px` is two atoms, and it is the atom the
scale has to answer for. Counts are occurrences in BLOCK 2.

| atom | uses | atom | uses | atom               | uses   |
| ---- | ---- | ---- | ---- | ------------------ | ------ |
| 10px | 35   | 5px  | 14   | 20px               | 3      |
| 12px | 34   | 6px  | 14   | 24px               | 2      |
| 14px | 33   | 7px  | 11   | 13px               | 1      |
| 8px  | 32   | 3px  | 7    | 22px               | 1      |
| 11px | 24   | 18px | 7    | 40px               | 1      |
| 9px  | 23   | 16px | 4    | 76px               | 1      |
| 4px  | 22   | 1px  | 4    | −6px, −10px, −14px | 1 each |
| 2px  | 16   |      |      |                    |        |

A further 25 declarations are exactly `0` — 12 in `margin`, 11 in `padding`, 2 in `gap`. Zero is
the absence of a step and does not become one.

**The distribution is a one-pixel ramp, not a ratio.** Every integer from 1 to 14 is in use, which
is what 66 distinct `padding` strings actually means: nobody chose 9 px over 8 px, the value simply
got typed. The steps therefore pair adjacent integers, which keeps the largest single move to 2 px
across the body of the interface, and reserves the bigger jumps for the seven values used once or
twice each.

| token         | value | absorbs    | uses folded |
| ------------- | ----- | ---------- | ----------- |
| `--spacing-1` | 2px   | 1, 2, 3    | 27          |
| `--spacing-2` | 4px   | 4, 5       | 36          |
| `--spacing-3` | 6px   | 6, 7       | 25          |
| `--spacing-4` | 8px   | 8, 9       | 55          |
| `--spacing-5` | 10px  | 10, 11     | 59          |
| `--spacing-6` | 12px  | 12, 13     | 35          |
| `--spacing-7` | 14px  | 14, 16     | 37          |
| `--spacing-8` | 18px  | 18, 20, 22 | 11          |
| `--spacing-9` | 24px  | 24         | 2           |

**Nine steps rather than the eight the contract estimates, and the ninth is argued rather than
conceded.** 24 px is the sign-in and splash surfaces' outer padding (`login:style:4091`,
`login:splashstyle:4228`) — the one surface in the interface that is not a dense list. Folding it
to 18 px would tighten the only screen whose subject is empty space, to save a token. The estimate
in the lot's contract was made from a distinct-value count, not from the distribution; this is the
arbitration D-L06-2 asks for.

**Three values do not become steps, and each is named rather than rounded:**

- **`1px`** is a hairline — it appears in `padding: 1px 6px` and its siblings on the smallest
  chips, where it is doing the job of a border, not of a space step. It folds to `--spacing-1`
  (2 px) with the rest of the small cluster; nothing keeps a 1 px space step.
- **`40px 76px`** on `.dcard .cap` (`refonte.html:1453`) is a **reserved footprint**: the comment
  above it says so — the caption reserves the room the floating « + » occupies, so the text does
  not run underneath it. That is a measured clearance, the same kind of quantity as
  `--tm-bottom-bar-h`, and rounding it to a step is how a button starts overlapping a caption. It
  is expressed as `calc()` over the button's own size plus a step, or recorded in the arm's named
  exemptions with that reason.
- **The three negatives** (`-6px`, `-10px`, `-14px`) are pull-backs of a known step and stay on the
  scale as `calc(var(--spacing-N) * -1)`.

### Type — 21 distinct sizes

| size   | uses | size   | uses | size                                    | uses   |
| ------ | ---- | ------ | ---- | --------------------------------------- | ------ |
| 12px   | 31   | 13.5px | 7    | 15px                                    | 2      |
| 11px   | 24   | 14px   | 6    | 19px                                    | 2      |
| 11.5px | 22   | 10px   | 3    | 8.5px                                   | 1      |
| 12.5px | 21   | 16px   | 3    | 18px, 21px, 26px, 27px, 30px, 54px, 1em | 1 each |
| 13px   | 11   | 9.5px  | 2    |                                         |        |
| 10.5px | 8    |        |      |                                         |        |

**Sixty-one of the 150 declarations are half-pixel sizes**, and that is the finding: 8.5, 9.5,
10.5, 11.5, 12.5 and 13.5 exist because somebody nudged a label rather than because a scale has a
half-step. They collapse onto their integers.

| token            | value | absorbs                                      |
| ---------------- | ----- | -------------------------------------------- |
| `--text-1`       | 10px  | 8.5, 9.5, 10, 10.5                           |
| `--text-2`       | 11px  | 11, 11.5                                     |
| `--text-3`       | 12px  | 12, 12.5                                     |
| `--text-4`       | 13px  | 13, 13.5                                     |
| `--text-5`       | 14px  | 14, 15                                       |
| `--text-6`       | 16px  | 16 — **and the three form fields** (D-L06-6) |
| `--text-7`       | 19px  | 18, 19, 21                                   |
| `--text-8`       | 27px  | 26, 27, 30                                   |
| `--text-display` | 54px  | 54                                           |

**Eight content steps and one display size, against the contract's estimate of seven.** Collapsing
`--text-1` into `--text-2` would take the fourteen micro-labels at 8.5–10.5 px up by as much as
2.5 px, inside chips whose width is already the tight case at 390 px. The scale's job is to be
defensible, not to hit a round number, and the histogram supports the step: 14 declarations is not
a stray.

**`--text-display` is a step of its own and not the top of the ramp.** 54 px is the letter in the
poster fallback (`refonte.html:1435`); it is sized against the tile it fills, not against the
reading ladder. `1em` on `.pfall b` is relative to its parent and stays as it is — a relative unit
is not a step, and the arm exempts it by name.

### Radius — 16 distinct values

| value  | uses | value   | uses | value                          | uses   |
| ------ | ---- | ------- | ---- | ------------------------------ | ------ |
| 8px    | 39   | 7px     | 7    | 5px                            | 2      |
| 99px   | 25   | 10px    | 3    | 2px, 3px, 9px, 14px, 50%       | 1 each |
| 9999px | 11   | 12px    | 3    | `14px 14px 0 0`, `0 7px 7px 0` | 1 each |
| 6px    | 9    | inherit | 2    |                                |        |

| token           | value | absorbs       |
| --------------- | ----- | ------------- |
| `--radius-1`    | 3px   | 2, 3          |
| `--radius-2`    | 6px   | 5, 6, 7       |
| `--radius-3`    | 8px   | 8, 9, 10      |
| `--radius-4`    | 12px  | 12, 14        |
| `--radius-full` | 999px | 99, 9999, 50% |

Five steps, exactly the estimate. **`99px` and `9999px` are the same intent written twice** — a
pill — and `50%` is that intent on a square element; one token says it once. The two composite
values keep their shape and read a step per corner. `inherit` is a keyword, not a value on the
scale, and the arm exempts it by name.

### Motion — 14 durations, 6 easings

| duration | uses | duration            | uses   |
| -------- | ---- | ------------------- | ------ |
| 0.18s    | 11   | 0.42s, 0.34s, 0.12s | 1 each |
| 0.2s     | 4    | 0.7s (spin)         | 1      |
| 0.15s    | 3    | 1.3s (shimmer)      | 1      |
| 0.26s    | 3    | 1.6s (pulse)        | 1      |
| 0.22s    | 2    | 5s (splash fill)    | 1      |
| 0.28s    | 2    | 0.5s (entrance)     | 1      |

| token               | value                               | absorbs                                 |
| ------------------- | ----------------------------------- | --------------------------------------- |
| `--duration-1`      | 0.15s                               | 0.12, 0.15                              |
| `--duration-2`      | 0.2s                                | 0.18, 0.2, 0.22                         |
| `--duration-3`      | 0.3s                                | 0.26, 0.28, 0.34                        |
| `--duration-4`      | 0.45s                               | 0.42, 0.5                               |
| `--ease-standard`   | `cubic-bezier(0.22, 0.61, 0.36, 1)` | `ease`, `ease-out`, `ease-in-out`       |
| `--ease-emphasized` | `cubic-bezier(0.22, 1.02, 0.36, 1)` | the one overshoot                       |
| `--duration-loop-1` | 0.7s                                | the spinner                             |
| `--duration-loop-2` | 1.4s                                | the shimmer (1.3s) and the pulse (1.6s) |
| `--duration-loop-3` | 5s                                  | the splash fill                         |

**The loop periods are declared, and they are NOT steps of the transition ramp.** A transition is a
response to a touch, measured in fractions of a second; a loop period is a rhythm, and folding a
5 s splash fill onto 0.3 s does not tidy anything, it breaks the surface. They are tokens so the
value has one home; they are named `loop` so nobody folds them later by mistake. `linear` stays on
the three loops, for the same reason: a spinner that eases is a spinner that stutters. It is a
keyword and the arm exempts it by name.

## 1.2 — The `:root` block, at the top of BLOCK 2

**Files touched**: `frontend/maquette/design/refonte.html`, `frontend/maquette/serve.py`,
`scripts/code-vocabulary.txt`.

1. The block goes **immediately above `/* login:palette:start */`** (`refonte.html:255`) — the top
   of BLOCK 2, per D-L06-1 — as a single `:root { … }` carrying every token above, in the family
   order of § 1.1, with the family comments that say what each ramp is for.
2. It is wrapped in `/* scale:start */` … `/* scale:end */`, **and those markers are also
   `login:scale:start` / `login:scale:end`** — one comment pair carrying both names, so a reader
   editing the block cannot see one purpose and miss the other. `serve.py` emits the chunk before
   the palette (P-1 in the plan's index). Without it, every folded declaration inside `login:style`
   and `login:splashstyle` resolves to nothing on the design host: a landmine, not a crash.
3. **Nothing uses the tokens yet.** That is the point — the block is inert, so this phase's oracle
   is a hold rather than an expectation.
4. **The words the new names are built from go into `scripts/code-vocabulary.txt` in the same
   commit.** Measured against the file as it stands: `spacing`, `scale`, `loop`, `standard` and
   `emphasized` are absent; `text`, `radius`, `duration`, `ease`, `display` and `full` are already
   there. The guard's « Custom-property names » arm reads 293 names today and will read these — a
   name built from a word nobody wrote down is refused, and rightly. Re-run the measurement rather
   than trusting this list: it was taken at `ac04c8ca`.
   <sub>`for w in spacing scale loop standard emphasized; do printf "%-12s %s\n" "$w" "$(grep -ixc "$w" scripts/code-vocabulary.txt)"; done`</sub>

## 1.3 — The ratchet arm, and the composition arm

**Files touched**: `scripts/check-css-tokens.py`, `frontend/maquette/scale-baseline.json` (new).

`check-css-tokens.py` already reads BLOCK 2, is already in `make check` (`Makefile:85`) and already
runs in CI (`.github/workflows/ci.yml:138`). Extending it means both arms ride all three for free,
which is the whole of D-L06-3's « never a second script beside it ».

1. **`--arm scale`.** Per family — `spacing`, `text`, `radius`, `motion` — count the BLOCK 2
   declarations whose value carries a **raw literal**: a number with a unit that is not zero. What
   does not count as off-scale, each written down with its reason in the source, the way this
   repository writes every exemption down:
   - `0` and `0px` — the absence of a step, not a step.
   - `var(--spacing-…)`, `var(--text-…)`, `var(--radius-…)`, `var(--duration-…)`,
     `var(--ease-…)` — a step, read.
   - `var(--tm-…)` — a runtime measurement (D-L06-4), and `env(…)` — a device inset. Neither is a
     design constant.
   - keywords and relative units: `inherit`, `auto`, `linear`, `1em`, percentages.
   - the named exemptions listed in the baseline file, each with its reason — today, `.dcard .cap`
     and nothing else.
2. **The baseline**, `frontend/maquette/scale-baseline.json`, written by
   `--record-scale-baseline`: the per-family counts as this phase finds them, the commit they were
   taken at, and the named exemptions. **Indicative figures, measured at `ac04c8ca`** — the arm's
   own accounting is the authority, and where the two disagree it is the arm that is read and the
   difference that is explained:

   | family  | declarations | carrying a raw literal |
   | ------- | ------------ | ---------------------- |
   | spacing | 316          | 268                    |
   | text    | 150          | 150                    |
   | radius  | 108          | 105                    |
   | motion  | 27           | 24                     |

3. **The arm refuses the count going UP**, per family, and says which family and by how much. It
   does not refuse a count going down — that is the folding phases doing their work, and each of
   them lowers the baseline in its own commit.
4. **A second hold in the same arm: the scale is declared in ONE place.** A scale token declared
   outside the `scale:start` / `scale:end` block is refused, whatever its value. Two declarations
   of `--spacing-4` are worse than none: the next reader edits the copy nobody reads.
5. **`--arm login`.** Every `var()` used inside a `login:*` marked chunk must be declared inside a
   `login:*` marked chunk. This is the same hole the script exists for, one level along: a `var()`
   that resolves only because of CSS that does not travel with it.
6. **Bare invocation runs every arm** and keeps its current output, so `make check` and CI pick the
   new arms up with no wiring change.

## 1.4 — The proof

**The mutations, each run once, after the phase is committed** (repository rule: fix, gates,
commit, mutate, restore):

| Mutation                                                                                      | It must say                                                                                                                   |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| append `.scalecheck{padding:13px}` after `/* scale:end */`                                    | `.scalecheck` `padding: 13px` — `13px` is on no step of the spacing scale, and the spacing count went UP against its baseline |
| declare `--spacing-4: 8px` a second time in the palette `:root`                               | the scale is declared in two places                                                                                           |
| remove the `login:scale` chunk from `serve.py`'s composition and fold one `login:style` value | the composed sign-in page uses a token it is not given                                                                        |

**The oracle: `0 divergence`, and it is a hold.** The tokens are declared and used by nothing, so
anything that moved is a defect in this phase — a stray edit, a marker that broke a rule, a
`serve.py` change that reached the prototype. Run `make maquette-oracle`; do **not** run
`--accept`, and open no section in `ACCEPTED-DIVERGENCES.md`: this phase has none.

## Gates before the commit

```bash
cd frontend/maquette/design && npm run build \
  && cp dist/index.html /tmp/tm-refonte/wrapped.html \
  && rm -rf /tmp/tm-refonte/vite \
  && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
python3 scripts/check-css-tokens.py            # every arm
python3 scripts/check-no-french.py
frontend/maquette/harness/run.sh               # full suite, a11y, oracle
python3 scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json
```

No TypeScript moves in this phase, so `npx tsc -b` is not part of its gate. `serve.py` does move —
after committing it, `pm2 restart torrentmate-design`, or the design host keeps serving the
previous composition and any check against it measures the old one.

## Done when

- ACC-01, ACC-02 and the arm's baseline exist and are committed.
- The three mutations above have been seen to fall, to name the right defect, and restored.
- `make maquette-oracle` reads `0 divergence`, and `ACCEPTED-DIVERGENCES.md` has no section for
  this phase.
- The full suite is green at unchanged hold counts — no rule was added in this phase.
