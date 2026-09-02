# L14 — The surfaces that outgrew their file · REPORT

**Contract**: `docs/reference/frontend-architecture.md` § 4, `#### L14 — The surfaces that outgrew
their file`. **Design**: `docs/features/maquette-l14/DESIGN.md`. **Plan**:
`docs/features/maquette-l14/plan/INDEX.md`. Every figure here carries the command that produces it;
re-run them rather than believe them.

---

## 1. What this wave produced

The four feature surfaces over the 400-line hard ceiling came back under it by decomposition,
nothing moved on the screen, and the two register entries only these files could repair were
repaired.

| File                                      | Before |   After | What went beside it                                                                                                                                 |
| ----------------------------------------- | -----: | ------: | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `features/acquisition/page.tsx`           |    756 |  **48** | `acquisition-tabs.tsx` 53 · `now-tab.tsx` 142 · `follows-tab.tsx` 254 · `follows-filters.tsx` 105 · `discover-tab.tsx` 192                          |
| `features/media/media-screen.tsx`         |    796 | **214** | `sheet-fields.ts` 36 · `season-list.tsx` 232 · `media-hero.tsx` 121 · `media-cast.tsx` 77 · `media-library-facts.tsx` 132 · `media-details.tsx` 122 |
| `features/library/page.tsx`               |    613 |  **98** | `library-head.tsx` 144 · `library-list.tsx` 245 · `library-count.tsx` 76 · `library-empty.tsx` 52 · `incomplete-lens.tsx` 58                        |
| `features/arrivals/resolution-screen.tsx` |    430 | **213** | `resolution-cards.tsx` 208                                                                                                                          |

<sub>`for f in features/acquisition/page.tsx features/media/media-screen.tsx features/library/page.tsx features/arrivals/resolution-screen.tsx; do printf '%-45s %s\n' "$f" "$(grep -cve '^\s*$' frontend/maquette/design/src/$f)"; done`</sub>

**`python3 scripts/check-frontend-boundaries.py --arm size` reads 2 at or over the ceiling** —
`engine/legacy.js` and `engine/states.js`, both labelled L13. That is the contract's own line, and
each of the four grandfather entries left in the same commit as the file it named: the arm refuses
an entry for a file back under the ceiling, so the count cannot climb again in silence.

**One file sits above the 250 soft warning and is named rather than left to be found**:
`follows-tab.tsx` at 254. « Suivis » is one surface with four display branches, and cutting it
further would have split a single decision across two files to satisfy a warning. The warning is
what it is for.

**`Icon` is written once.** Three private copies were deleted (`media-screen.tsx`,
`resolution-screen.tsx`, `releases-screen.tsx`); the signatures agreed with `ui/icon.tsx`'s and the
`<svg>` was identical, so the swap was a deletion, not a merge. `ui/panel/index.tsx`'s private
`ActionButton` — a different component wearing the frame's name — became `PanelActionButton`
through `scripts/rename-identifiers.py`, and the diff was re-read rather than trusted to the tool's
own report.

---

## 2. The two behaviour changes

**B-283 — an unknown part of the media sheet is a skeleton, never an answer (§13).** The brief's
reading of the flag was `status === "pending"`; that is not the state the defect lives in. With
placeholder data the query reports `success` and `isPlaceholderData` while the read is still out,
and `pending` is the case with no placeholder at all — so a rule reading `status` alone is green
over the primed case, which is the whole case. The flag is
`isPending || (isPlaceholderData && isFetching)` on the sheet and `isPending` on the seasons. Field
by field: a part the placeholder carries is drawn as content, a part it lacks stands as a
`SkeletonLine` inside the element that will carry the answer, and the assertion prints once landed.
The body holds its eight children at every instant, which is what R115's priming hold counts.

**B-247's surface half — and it had TWO mechanisms, one of which nobody had named.** The library
replaced its rows because its window was keyed on the store's `version`, which every action and
every cache landing bumps. The acquisition page replaced its cards for a reason no document
carried: **React 19 assigns `innerHTML` whenever the `dangerouslySetInnerHTML` prop is a new
object**, without comparing the string React 18 compared — and `{ __html: … }` written inline is a
fresh object per render. Measured before the design was written: the `<section>` was the same node,
its markup byte-equal at 1 968 characters, and every card inside it new. Filed as **B-295** at the
design, with the probe. The repair is `ui/markup.tsx` (the object memoised on its string, thirteen
sites) and a draw key naming what makes a row's markup differ — the mode, the selection mode, and
the first page's identity.

**One consequence is named for the operator rather than assumed (D-L14-3)**: a swipe left open on a
row now survives a store write that changed nothing about the rows, where it used to snap shut. No
rule held the snap, and `ui/virtual-rows.tsx` already treats a row replaced mid-gesture as the
defect. Overruling it is one line.

---

## 3. What was NOT done, and why

- **The producer half of B-247 is L19's**, and R100's hold (f) says so in its own docstring rather
  than reading Découvrir's engine-filled containers and calling them kept.
- **`features/maintenance/page.tsx`**, where B-247 was first seen, is not one of the four and was
  not opened. It still loses a tap.
- **The engine still bumps the store** on every action and every cache landing. A re-render keeps
  its nodes now; the engine does not bump less.
- **No producer, no engine-side gesture caller, no ladder handler, no line into `app/shell.tsx`**
  (398 of 400) and nothing into the engine's two files.
- **The instruments' debts** (B-269, B-272, B-273, B-276, B-277, B-278, B-287, B-291) are not
  taken: no phase opened `served_copy.py`, `mutate.sh`, `harness-hold-counts.py` or `exits.py`.
  The rule is that the next wave that touches the tool takes its debt, and this one did not touch
  them.
- **One deviation from the design, recorded in the plan's phase 1 in the same move**: the
  « written twice » guard is `scripts/check-component-once.py`, its own file, not an arm of
  `check-frontend-boundaries.py` — that file stands at 952 non-blank lines against a hard ceiling
  of 1 000, and L07-bis's precedent is to split a guard on a SUBJECT rather than on a line count.

---

## 4. The rules this wave added, and what each does not read

**R119 — `frontend/maquette/harness/priming.py`** (7 holds, full suite). It thins the reference's
`sheetFor` to `{t, k, y}` for one title and holds the read back 2 000 ms, both through setters
installed by an init script — a wrapper installed after `load` arrives after the placeholder has
been computed on a cold load. It reads 11 skeletons and 0 assertions in flight, 0 skeletons and one
no-info (the trailer) landed, and the same block count at both instants. It does not read the
skeleton's rendering (no named state shows the priming at rest, so the oracle never measures it),
nor any sheet but Broadchurch's.

**R100 hold (f) — `frontend/maquette/harness/persistence.py`** (R100 rises 11 → 18). On seven named
states, every card, tile, row, button, pill, image and key-value row is asked `isSameNode` after
`window.__store.touch()`, with a floor of ten captured per state: 56, 88, 35, 61, 61, 110 and 27,
all kept. It does not read the Découvrir containers, a write that legitimately redraws, or the
maintenance page.

**`scripts/check-component-once.py`** — every `.ts`/`.tsx` under `design/src` outside `engine/` and
`mocks/`, for a top-level PascalCase function declared in more than one file. Hard zero, no
allow-list, corpus printed with a floor on both files and declarations. It does not read camelCase
helpers (`announce` ×4, `isOpen` ×2 are private helpers of their own modules; `useStaging` ×2 is a
hook written twice, a finding for a reader and not this guard's subject) nor a component copied
under a different name.

**Every one was mutation-tested, seen red, restored.** R119: `inFlight` forced false, and the
cast's branch forced to its assertion — hold (b) falls both times. R100 (f): the window keyed on a
value that moves every draw (16 of 61 kept on `lib-list`), and the markup object made fresh per
render (5 of 56 kept on `acq-now-loaded`). `check-component-once.py` is a GUARD, which
`scripts/mutate.sh` cannot judge (B-273), so a second `Icon` was written back by hand and its exit
code read: 1, naming both files.

---

## 5. Guards green over what they do not read — this wave's figure is 2

Both were found by the wave in its own instruments, and **both are the RED form**, which the
criterion admits in either sign: an instrument whose reading does not decide what it claims to
decide.

1. **R119's own control**, written as « the complete placeholder draws ZERO skeletons » and red on
   its first run — correctly. The seasons carry no placeholder and this sheet's served creator is
   absent, so four lines stand there legitimately. A control that fails over the design working as
   drawn is the shape whose natural repair is to weaken the drawing. It reads « fewer skeletons,
   and the parts the placeholder carries are CONTENT » now: 4 against 11, the cast strip drawn and
   the synopsis a sentence.
2. **`check-component-once.py`'s first floor**, set at 50 declarations against a corpus of 69. A
   floor a quarter under the value it guards goes red the day a wave legitimately merges two
   components, and its author lowers it then. Measured before it was written down, and set at 30.

The readers have not run at the time of writing; the register's row says so rather than counting
them at zero. **Total 174 + 2 = 176.**

---

## 6. The gates

| Gate                               | Read                                                                                                                                                                       |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The oracle, at every phase         | 87 states × 34 regions, **2 958 measurements, no divergence**, seven times                                                                                                 |
| The full suite (`run.sh`, no flag) | **87 rules and 26 repository guards, no violation**                                                                                                                        |
| `--a11y`                           | **0 violations** over 87 states; the light theme unmoved at its ceiling of **166**                                                                                         |
| `harness-hold-counts.py --compare` | **two movements, both upward and both this wave's**: `persistence.py` 11 → 18 (hold (f), seven states), `priming.py` NEW at 7. No rule lost a hold. `failed` read first: 0 |
| `make check`                       | **11 023 passed, 4 skipped, 2 xfailed, 0 failed, 0 errors**, exit 0. Its seven eslint warnings are in `frontend/src`, the production app, and pre-date this branch |
| `--contracts`, at every phase      | 13 rules and 26 guards, no violation                                                                                                                                       |
| CI on the head sha                 | **14 jobs, all green** — read on the LOCAL sha's check-runs, never through the pull request's record, which lags a push |

**Two gates went red during the wave and each is written down rather than smoothed over.** R80 fell
when `skeletonLine` first carried the residue's `sk` anchor inside its variant: a variant wearing a
residue anchor owes the residue's every term, and the variant declared neither the gradient nor the
animation. The anchor moved onto the component as a literal beside the box, exactly as `Skeletons`
wears `sk tile` — which is also what makes the shimmer move to the variant on the day the residue
dies. And `check-markup-contracts.py` refused R119's selector written with escaped quotes: the arm
reads the harness as raw text, so an escaped quote makes a selection invisible to it. It is hosted
in a triple-quoted string now.

---

## 7. The review

To be filled, round by round, as the steward's independent readers return. Each round is aimed at
the previous round's REPAIRS, which is where every round in this repository has found its sharpest
defect.
