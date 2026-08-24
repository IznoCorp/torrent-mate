# Phase 3 — Type folds, and the fields reach 16 px

**21 sizes become 8 steps and one display size, and three form fields stop zooming iOS.** The
second half is D-L06-6, and it widens the lot's letter on purpose: the contract names
`.search input` at 13 px, but `.fieldinput` at 14 px and `.fieldinput.mono` at 12 px are the same
defect one tap away, and leaving two sub-16 field sizes inside a freshly declared type scale would
grandfather the defect into the scale rather than out of it.

**Why iOS zooms**: Safari auto-zooms a focused input whose computed size is under 16 px. L03
removed `maximum-scale=1, user-scalable=no` — correctly, because those directives were forbidding
the pinch-zoom a low-vision reader depends on — and the auto-zoom that had been suppressed became
visible. The repair is the field's size, not the meta tag.

## 3.1 — The half-pixel collapse

**Files touched**: `frontend/maquette/design/refonte.html`.

1. The 61 half-pixel declarations — 8.5, 9.5, 10.5, 11.5, 12.5, 13.5 — fold onto their integers per
   the table in phase 1 § 1.1. This is the single largest movement of the wave in declaration
   count and the smallest in pixels.
2. **`1em` on `.pfall b` (`refonte.html:970`) is not folded.** It is relative to its parent by
   design — the letter matches the text around it — and a relative unit is not a step.

**The hold**: `--arm scale`'s `text` count drops by the number folded; the baseline follows in the
same commit.
**The mutation**: restore one `font-size: 11.5px`. The arm names the selector and the literal.

## 3.2 — The three fields reach 16 px, and a rule measures it in the browser

**Files touched**: `refonte.html` (`.search input:556`, `.fieldinput:1909`, `.fieldinput.mono:1912`),
`frontend/maquette/harness/type_scale.py` (new), `frontend/maquette/hold-counts-baseline.json`.

1. The three fields read `var(--text-6)` — 16 px. `.fieldinput.mono` keeps its monospace family and
   loses only its smaller size: a monospace face at 16 px is wider than the sans at 16 px, so the
   surfaces holding a path or a hash are checked at 390 px in the same sub-phase, and a field that
   overflows is repaired by its container, never by taking the size back down.
2. **`harness/type_scale.py`**, a new rule in the suite, holding:
   - **the fields**: `getComputedStyle` on each of the three, in the states that show them, reads
     ≥ 16 px. A static grep proves the selector names a token; only the browser proves the pixel.
   - **the steps**: over the named states, every element inside the measured regions has a computed
     `font-size` belonging to the declared step set. This is the hold the static arm cannot have —
     it sees a size set by script or by an inline style, and the static arm never will.
3. The rule joins the full suite (the `*.py` glob picks it up) and **not** the `--contracts` tier:
   it reads no name that moves, it measures rendering, and the contracts tier answers one question.
4. `python3 scripts/harness-hold-counts.py --record frontend/maquette/hold-counts-baseline.json`
   after the rule lands, and **the report names the new rule and its hold count** — a re-recorded
   baseline that nobody itemises is a baseline that can absorb a rule that stopped measuring.

**The mutations**, both run and restored:

| Mutation                                      | It must say                                                                           |
| --------------------------------------------- | ------------------------------------------------------------------------------------- |
| `.search input { font-size: 13px }`           | the search field renders at 13 px, under the 16 px at which a focused field zooms iOS |
| one heading given a literal `font-size: 17px` | a rendered size that is on no step of the type scale                                  |

## 3.3 — The remaining sizes, and the display size

**Files touched**: `refonte.html`.

1. Everything not yet folded lands on its step: 15 → `--text-5`, 18 and 21 → `--text-7`, 26 and
   30 → `--text-8`, 54 → `--text-display`.
2. **`text` reaches 0** on the arm, and the baseline records it.

**The mutation**: add `font-size: 17px` in BLOCK 2; with the baseline at zero the arm refuses it as
the count going up.

## The divergences are reviewed, and the reference re-recorded

The protocol of the plan's index, § « The oracle protocol for this lot », run at the end of this
phase: read the list in full, write each accepted divergence into `ACCEPTED-DIVERGENCES.md` under
this phase's section with its reason, `oracle.py --accept`, read the reference diff, commit.

**This phase's divergences are the wave's largest, and two shapes are not acceptable**: a text that
now WRAPS where it did not — a folded size is at most 2.5 px and must not change a line count on a
label — and a control whose height moved by more than the size change, which means a line-height
was inherited rather than set.

## Gates before each commit in this phase

```bash
cd frontend/maquette/design && npm run build \
  && cp dist/index.html /tmp/tm-refonte/wrapped.html \
  && rm -rf /tmp/tm-refonte/vite \
  && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
python3 scripts/check-css-tokens.py
python3 scripts/check-no-french.py
python3 frontend/maquette/harness/type_scale.py
frontend/maquette/harness/run.sh
```

No TypeScript moves in this phase; `type_scale.py` is Python, like every other rule.

## Done when

- ACC-11 prints three fields, each resolving to a step of at least 16 px.
- ACC-12 — `type_scale.py` — is green, and both of its mutations have been seen to fall.
- `--arm scale` reports `text 0`.
- The hold-count baseline is re-recorded, and the new rule's count is named in the phase report.
- Every divergence is accepted with a reason and the reference re-recorded.
