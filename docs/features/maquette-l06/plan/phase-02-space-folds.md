# Phase 2 — Space folds

**Every `padding`, `gap` and `margin` in BLOCK 2 reads a step of the spacing scale.** 268 of the
316 declarations carry a raw literal today; at the end of this phase the arm's `spacing` count is
zero and the baseline says so.

**The fold is mechanical and its risk is not.** Substituting a token for a literal is the easy
half; the hard half is that this interface is a 390 px column of dense lists, and two pixels
removed from a row's vertical padding is two pixels the row below moves up, 40 rows deep. So the
work goes surface by surface, and each sub-phase reads its own oracle divergences before the next
one starts. A fold that reviews 268 substitutions at once reviews none of them.

**The order is the measured regions' own** (`frontend/maquette/regions.json`) — shell first,
because every page renders inside it and a shell that moved explains a page that moved, while the
reverse is never true.

## 2.1 — The shell

**Files touched**: `frontend/maquette/design/refonte.html` (the rules behind `shell/viewport`,
`shell/page`, `shell/bottom-bar`, `shell/action-button`, `shell/toast`, `shell/drawer`,
`shell/scrim`, `shell/sheet-content`, `shell/dialog`, `shell/save-bar`, `shell/sign-in`,
`shell/install-bar`, `shell/library-list`, `shell/library-count`, `shell/search-field`).

1. Each `padding` / `gap` / `margin` value becomes the step § 1.1 assigns it. Multi-value
   declarations fold per side: `padding: 11px 12px` → `padding: var(--spacing-5) var(--spacing-6)`.
2. **The `calc()` sites keep their shape.** `padding: 11px 14px calc(env(safe-area-inset-bottom) +
11px)` folds to `… calc(env(safe-area-inset-bottom) + var(--spacing-5))`. The inset is a device
   measurement and is not on the scale; only the constant beside it folds.
3. **`shell/sign-in` is where P-1 fires.** The `login:style` chunk holds `padding: 24px 20px`
   (`refonte.html:4091`); the moment it reads `var(--spacing-9)`, the standalone sign-in page needs
   the scale chunk. `--arm login` is what says so, and it must be run — and seen green — in this
   sub-phase, not at the end of the phase.
4. After committing, `pm2 restart torrentmate-design`, or the design host keeps composing the
   previous sign-in page.

**The hold**: `--arm scale`'s `spacing` count drops by the number of declarations this sub-phase
folded, and the baseline is lowered to the new count in the same commit.
**The mutation**: put one folded literal back (`gap: 7px` on the bottom bar). The arm must refuse
it as the spacing count going UP against the just-lowered baseline, naming the selector.

**The oracle**: run it, read every divergence, and expect them to be small vertical shifts in the
bar, the drawer and the sheet. Anything horizontal on a full-width surface is not explained by a
2 px space fold and is investigated before it is accepted.

## 2.2 — The pages

**Files touched**: `refonte.html` — the rules behind `acquisition/*`, `library/*`, `arrivals/*`,
`system/body`, `maintenance/body`, `settings/body`, `account/body`, `not-found/body` and the four
`screen-*` bodies.

1. The same substitution, surface by surface, in that order.
2. **The chip cluster is the tight case, and it is read at 390 px.** `padding: 1px 6px`,
   `2px 7px`, `3px 7px` and their siblings all land on `--spacing-1` / `--spacing-3`; the category
   and filter rows are the surfaces where a 1 px growth per chip becomes a wrapped row. Any state
   whose chip row wraps where it did not is a divergence the scale does **not** explain: the fix is
   the step, not the acceptance.
3. `.dcard .cap`'s `padding: 40px 76px 12px 14px` (`refonte.html:1453`) is the reserved footprint
   § 1.1 named. It becomes `calc()` over the floating button's own size plus a step if that size
   has a name, and otherwise it is entered in the baseline's named exemptions **with the comment
   that already sits above it as its reason** — never rounded to a step.

**The hold**: the `spacing` count drops again; the baseline follows in the same commit.
**The mutation**: restore one literal padding on a chip; the arm names it.

## 2.3 — The margins, including the negative ones

**Files touched**: `refonte.html` — the 49 `margin` declarations still carrying a raw literal when
this sub-phase opens. BLOCK 2 holds 94 in all: 12 are exactly `0`, 15 read `auto` alone, and 18
were already folded by 2.1 and 2.2 with the surfaces they belong to.

1. **The negatives are seven declarations over six atoms, not three.** The plan's first draft named
   `-6px`, `-10px` and `-14px`, which are the three that sit inside a `margin:` shorthand; the
   histogram's extraction never read the longhands, and `-4px`, `-8px` and `-62px` live there.
   Six of the seven are pull-backs of a known step and become `calc(var(--spacing-N) * -1)` —
   writing a negative as the step it pulls back is what stops it drifting away from that step:
   - `-4px` → `calc(var(--spacing-2) * -1)` — `.topbar .burger` `margin-left`, and
     `.settingrow.modified::before` `margin-right`.
   - `-6px` → `calc(var(--spacing-3) * -1)` — the first atom of `.loginsub`'s shorthand.
   - `-8px` → `calc(var(--spacing-4) * -1)` — `.search .searchclear` `margin-right`.
   - `-10px` and `-14px` → `calc(var(--spacing-5) * -1)` / `calc(var(--spacing-7) * -1)` —
     `.sugwrap.gone` `margin-bottom`, and `.herowrap`'s two negative atoms.

   A composite shorthand folds per atom, negatives included: `.herowrap`'s `margin: -10px -14px 0`
   becomes `margin: calc(var(--spacing-5) * -1) calc(var(--spacing-7) * -1) 0`, and `.loginsub`'s
   `margin: -6px 0 4px` becomes `calc(var(--spacing-3) * -1) 0 var(--spacing-2)`.

2. **The seventh negative is exempted, not folded.** `.hero`'s `margin-top: -62px` is on no step of
   anything: the comment directly above it already says what the number is — the title is pulled up
   over the poster's melt, so it belongs to the image. It joins the baseline's named exemptions,
   **value untouched**, with that as its reason, beside `.dcard .cap`. Rounding a composition
   measurement to a step is how a title stops overlapping the thing it was drawn to overlap.
3. `margin: 0 auto` and its siblings keep `auto` — a keyword, exempt by name in the arm.
4. `0` stays `0`.
5. **A `calc(var(--spacing-N) * -1)` reads a step**, and the arm agrees: it strips every `var()`
   call before it looks for a raw literal, so what is left of the value carries no `px` at all.

**The hold**: `spacing` reaches **0**, and the baseline records `0` for that family.
**The mutation**: add `margin: 9px 0` anywhere in BLOCK 2. With the baseline at zero the arm must
refuse it immediately, and its message must be the « went UP » one — the outright refusal is phase
6's, and confusing the two would mean the ratchet is not doing what it says.

## 2.4 — The divergences are reviewed, and the reference re-recorded

1. `make maquette-oracle`, and read the list in full.
2. **Create `docs/features/maquette-l06/ACCEPTED-DIVERGENCES.md`** with its header and this phase's
   section. One row per accepted divergence: state, region, property, before → after, and the
   reason. « The fold moved this » is not a reason.
3. `python3 frontend/maquette/oracle.py --accept`, then read
   `git diff frontend/maquette/oracle-reference.json` — that diff is the review, and the oracle's
   own docstring says so.
4. Commit the reference with this phase.

**A divergence nobody expected fails the phase.** The scale must explain every moved rectangle, and
the two shapes that mean « stop » are a region that changed WIDTH on a full-width surface, and a
state whose height moved by more than the sum of the steps folded inside it.

## Gates before each commit in this phase

```bash
cd frontend/maquette/design && npm run build \
  && cp dist/index.html /tmp/tm-refonte/wrapped.html \
  && rm -rf /tmp/tm-refonte/vite \
  && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
python3 scripts/check-css-tokens.py            # every arm, including login
python3 scripts/check-no-french.py
frontend/maquette/harness/run.sh               # full suite, a11y, oracle
```

No TypeScript moves in this phase.

## Done when

- `python3 scripts/check-css-tokens.py --arm scale` reports `spacing 0`.
- ACC-13's `padding` / `margin` / `gap` share is empty — no raw length left in those families.
- The three mutations above have fallen, named the right defect, and been restored.
- Every divergence of the phase is in `ACCEPTED-DIVERGENCES.md` with a reason, the reference is
  re-recorded, and `make maquette-oracle` reads `no divergence` against it.
- The full suite is green at unchanged hold counts.
