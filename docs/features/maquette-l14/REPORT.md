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
| `features/acquisition/page.tsx`           |    756 |  **48** | `acquisition-tabs.tsx` 53 · `now-tab.tsx` 142 · `follows-tab.tsx` 254 · `follows-filters.tsx` 105 · `discover-tab.tsx` 192 |
| `features/media/media-screen.tsx`         |    796 | **240** | `sheet-fields.ts` 36 · `season-list.tsx` 245 · `media-hero.tsx` 150 · `media-cast.tsx` 77 · `media-library-facts.tsx` 140 · `media-details.tsx` 131 |
| `features/library/page.tsx`               |    613 |  **102** | `library-head.tsx` 144 · `library-list.tsx` 241 · `library-count.tsx` 76 · `library-empty.tsx` 52 · `incomplete-lens.tsx` 67 |
| `features/arrivals/resolution-screen.tsx` |    430 | **213** | `resolution-cards.tsx` 208 |

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
- **`features/maintenance/page.tsx`'s own tap defect is NOT closed by this wave**, though its two
  markup sites go through the memo with the rest: the page's own re-render path is the producers'
  and hold (f) does not drive it. Named here rather than left to be inferred from a repair that
  touched the file.
- **The engine still bumps the store** on every action and every cache landing. A re-render keeps
  its nodes now; the engine does not bump less.
- **No producer, no engine-side gesture caller, no ladder handler, no line into `app/shell.tsx`**
  (398 of 400) and nothing into the engine's two files.
- **The instruments' debts** (B-269, B-272, B-273, B-276, B-277, B-278, B-287, B-291) are not
  taken: no phase opened `served_copy.py`, `mutate.sh`, `harness-hold-counts.py` or `exits.py`.
  The rule is that the next wave that touches the tool takes its debt, and this one did not touch
  them.
- **Three deviations from the design, each recorded in the phase file that took it** — a reader
  found the count wrong at one, which is the shape of a paragraph nobody re-reads. (1) The
  « written twice » guard is `scripts/check-component-once.py`, its own file, not an arm of
  `check-frontend-boundaries.py` — that file stands at 952 non-blank lines against a hard ceiling
  of 1 000, and L07-bis's precedent is to split a guard on a SUBJECT rather than on a line count.
  (2) `media-information.tsx` is `media-details.tsx`: the vocabulary arm refuses « Information »,
  and it is right — the block is identifiers and actions. (3) `ui/markup.ts` with `useMarkup` at
  every site is `ui/markup.tsx` with a `<Markup>` component at every site: a hook cannot be called
  inside a `.map` and several sites are, so the component is where the hook is called once.

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
| The oracle, after every phase and every repair| 87 states × 34 regions, **2 958 measurements, no divergence**, every time |
| The full suite (`run.sh`, no flag) | **87 rules and 26 repository guards, no violation**, re-taken after round 1 |
| `--a11y`                           | **0 violations** over 87 states; the light theme unmoved at its ceiling of 166, re-taken after round 1 |
| `harness-hold-counts.py --compare` | **three movements, all upward and all this wave's**: `persistence.py` 11 → 33, `virtual.py` 17 → 19, `priming.py` new at 18. No rule lost a hold. `failed` read first: **1** — `outbox.py`, which passed alone (21 holds, no violation) and in the full suite; B-277's species under the recorder's parallel load, said in the same breath as the verdict |
| `make check`                       | **11 023 passed, 4 skipped, 2 xfailed, 0 failed, 0 errors**, exit 0, re-taken after round 1 and after the merge of `main`. Its seven eslint warnings are in `frontend/src`, the production app, and pre-date this branch |
| `--contracts`, at every phase      | 13 rules and 26 guards, no violation                                                                                                                                       |
| CI on the head sha                 | read on the LOCAL sha's check-runs, never through the pull request's record, which lags a push. The sha it was read on is named in the message that reports it — a commit cannot carry its own verdict, and the first version of this row was written into the commit it described |

**Two gates went red during the wave and each is written down rather than smoothed over.** R80 fell
when `skeletonLine` first carried the residue's `sk` anchor inside its variant: a variant wearing a
residue anchor owes the residue's every term, and the variant declared neither the gradient nor the
animation. The anchor moved onto the component as a literal beside the box, exactly as `Skeletons`
wears `sk tile` — which is also what makes the shimmer move to the variant on the day the residue
dies. And `check-markup-contracts.py` refused R119's selector written with escaped quotes: the arm
reads the harness as raw text, so an escaped quote makes a selection invisible to it. It is hosted
in a triple-quoted string now.

---

## 7. The review — round 1: five readers, 0 blocker, 13 majors, every one repaired

**The gate was green in every tier when this round opened**, which is the only interesting fact
about it: 87 rules, `--a11y` 0, `make check` at zero, the oracle at 2 958 with no divergence, and
every rule of this wave mutation-tested. Five independent readers on that gate returned thirteen
majors. The reports are `git show <squash>:docs/features/maquette-l14/` — they were read whole
before anything was touched.

### What the readers found that the wave's own instruments could not

**A REGRESSION the wave introduced and no rule held.** The library's draw key named the first
page's identity; the cache's structural sharing returns an unchanged page as the same object, so a
swipe-delete of a row on any page but the first left the key still, the window untouched, and the
deleted row on screen until the network answered — for good on a mutation the layer holds. 321 of
the fixture's 345 rows. The reader established it from three quoted facts plus a measurement of
the cache's own sharing, without running the harness. **The repair is not a better key**: the
window remembers the string each live row was built from and replaces only the rows whose markup
moved. The key answers what it can answer — is this a different drawing — and the rows are the
window's own business. R117 gained the hold that was missing, and the old behaviour restored by
mutation falls it.

**THE REPAIR WAS INCOMPLETE, and the register entry said nine where the tree held thirty-two.**
Seventeen inline `{ __html }` sites remained, four on components that re-render on every bump —
the Add screen is B-247's mechanism verbatim — and the shared `Icon` rebuilt every `<path>` on
every parent render. The reader measured what that costs: Chromium delivers no `click` at all when
the `pointerdown` target has been replaced, and a surviving ancestor does not rescue it, so a press
landing on the stroke of an icon-only control was lost on any store write. All 32 sites go through
the memo now, and hold (f)'s selector names `path`.

**THREE ASSERTIONS ABOUT DATA IN FLIGHT SURVIVED B-283's repair**, each in a place the rule could
not see: the hero's metadata line was gated on the WHOLE sheet being null, so a placeholder
carrying the title and not the year printed « année inconnue · Série »; « Possédés 0 » is a number
about seasons still out; and the season list says « Épisodes non détaillés » about the sheet's
episode lists while the seasons have landed and the sheet has not. **And the error path, which the
design had reasoned about and got wrong**: the query library drops its placeholder the moment a
read errors, so what the tap knew vanished and the screen printed « le provider n'en fournit pas »
over a 502 — a sentence that cannot change when the reality does, which is §13's first bullet.

**AND THE INSTRUMENTS.** R119 held a floor of six against eleven measured and read « no-info », a
part name two of nine sites wear — so the synopsis, the director and the three season lines could
all revert to printing their answer and every hold stayed green: three of the four examples the
register entry names, in the rule written for that entry. `check-component-once.py` said « exported
or not » and refused `export default function`. Hold (f) drove `touch()` alone, the one door a
surface reading `useUiState()` bails out of, and did not drive the state the design itself measured
as replaced.

### What repairing it taught, which is the part worth keeping

**A rule can be blind for want of a WALK, not for want of a reading.** The mutation putting
« Épisodes non détaillés » back fell nothing, three times, for three different reasons — and each
was mine, not the rule's. The season rows draw their matrix from owned numbers the reference
answers synchronously, so the branch is unreachable for a series the library owns: the walk had to
open a suggestion. Both reads shared one latency, so the interval where one has landed and the
other has not did not exist: the walk had to give the seasons a latency of their own. And the
thinning named one title while the walk opened another, so it measured a COMPLETE placeholder and
printed zero skeletons — the number said so and the hold did not read it. **Three vacuities in one
hold, each invisible to a verdict and each visible in the figures the rule prints beside it.**

**The same shape twice more.** « In flight » was read as the mock layer's total, which is true on a
page whose sheet landed long ago; it is the sheet query's own state now. And a walk on the leanest
placeholder cannot decide « field by field » at all: with nothing known the hero draws one skeleton
for its whole line and the per-field branches are never reached. That is why a PARTIAL placeholder
is a walk of its own — the year known, the kind not — and it is where the kind mutation falls.

**A repair that breaks a green rule elsewhere is the rule doing its work.** Making the metadata
line wait per field made it print « année inconnue · Série » for an identifier nobody carries — a
kind asserted about a medium that does not exist, the very defect this wave removes, introduced by
its own repair. R75's hold on the honest empty case went red and named it. A sheet with fields
missing waits per field; no sheet at all says « Métadonnées inconnues », once.

**And a reading taken against a stale served copy proved nothing.** A mutation applied by hand,
built, run, and then restored WITHOUT rebuilding left the served copy holding the mutated build;
the next three readings measured it. The suite's own header warns about exactly this and it was
still paid for. `scripts/mutate.sh` does the rebuild itself, which is the argument for never doing
it by hand.

### What the round cost, in numbers

| | |
| --- | --- |
| Majors returned | 13, deduplicated by the steward from five lenses |
| Repaired | 13, each with a commit of its own and a mutation seen red |
| New holds | R119 (b-i) exact count, (b-ii) assertion text, (b-iii) busy, (b-iv) actions, (e) a failed read, (f) a partial placeholder, (g) the two reads landing apart; R100 (f) x2 doors x9 states, `path`, the screens' own floor; R117 the deleted row |
| Rules' hold counts | R119 7 → 18, R100 18 → 33, R117 17 → 19 |
| Defects the repairs themselves introduced, caught by a rule | 1 (the empty case, R75) |
| Vacuities in the wave's own new holds, caught by reading the figures they print | 5 |

**Round 2 reads these repairs**, which is where every round in this repository has found its
sharpest defect.
