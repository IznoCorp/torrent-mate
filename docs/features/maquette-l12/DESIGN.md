# L12 — Native interaction · DESIGN

**Contract**: `docs/reference/frontend-architecture.md` § 4, `#### L12 — Native interaction`. Its
« Done when » is the definition of finished and this document does not restate it — a contract
copied into a second file is a contract wrong in one of them.

**Constitution served**: **§12** (the phone is *the* workstation — every property below is a
phone property), **§16** (Back re-walks the path — the transitions this lot declares must not
disturb the ladder L05 delivered), **DOIT-9** and **DOIT-10**.

**What kind of wave this is.** A BEHAVIOUR wave — the first since L07 whose whole subject is what
the oracle cannot see. § 6's newest trap is this lot's governing fact: *the oracle's silence over
a behaviour wave is evidence of nothing*. L11 measured it — no divergence over 2 958 measurements
while four adversarial rounds found ~40, 13, 7 and 0 product defects under a permanently green
gate. **Every property below lands with a rule that DRIVES it**, under both motion preferences,
each mutation seen red.

---

## 1. What was measured before this design was written

Run on 2026-08-31, on `bcd2f4a4`, this branch's base. **Every figure carries the command that
produces it** (§ 0). Re-run them; do not believe them.

| Fact | Command | Read |
| --- | --- | --- |
| No transition, no dvh, no tap-highlight, no `interactive-widget` anywhere | `grep -rc "100vh\|100dvh\|interactive-widget\|tap-highlight\|view-transition" frontend/maquette/design/src frontend/maquette/design/index.html \| awk -F: '{s+=$2} END{print s}'` | **0** |
| The long list is infinite scroll, not virtualisation | `grep -n "IntersectionObserver" .../features/library/page.tsx` | `:371` |
| The viewport meta declares no `interactive-widget` (B-234) | `grep -n 'name="viewport"' .../design/index.html` | `:18`, `width=device-width,initial-scale=1` |
| The frame's height is `100%`, not `100dvh` (P11) | `sed -n '54p' .../styles/base.css` | `height: 100%;` |
| Reduced motion is honoured in exactly one place | `grep -rn "prefers-reduced-motion" .../design/src` | `base.css:137`, `legacy.css:1308,1749`, one comment |
| The press arbitration's three parts live in the engine | `grep -n "swallowClick\|function armPress\|followPress" .../engine/legacy.js` | `8105`–`8232`, re-exported at `32962`, `32975` |
| Motion tokens already exist and are on the scale | `grep -n "duration\|ease" .../styles/theme.css` | `--duration-1..4`, `--duration-loop-1..3`, `--ease-standard`, `--ease-emphasized` |
| Posters declare their box (P29's precondition) | `grep -n "aspect-ratio" .../styles/legacy.css` | `2/3` at `454, 457, 823, 1612, 1760` |
| `app/shell.tsx` is at 398 of 400 | `python3 scripts/check-frontend-boundaries.py --arm size` | `[WARN] app/shell.tsx: 398` |
| The transition host does **not** need the shell | `grep -cve '^[[:space:]]*$' .../app/navigation.ts` | **197** non-blank — room, and it is where navigation already happens |
| Register state at the wave's open | `python3 scripts/check-bug-register.py --next` · `grep -o "\| \*\*Total\*\* \| \*\*[0-9]*\*\*" BUGS.md` | next **B-271** · total **143** |

**Two of these change what the plan assumed, and saying so is this wave's duty under § 7.1**, not
an amendment:

1. **`app/shell.tsx` is not on the path.** The lot's contract warns that a transition host or a
   gesture root might need it, and it is at 398 of 400 with the hard ceiling one line away. It does
   not: `document.startViewTransition` wraps a *navigation*, and navigation is `app/navigation.ts`
   (197 non-blank) and `lib/navigate.ts` (76). **No phase of this plan opens `shell.tsx`**, so the
   subject-split the contract holds in reserve is not needed and is not done. Written down because
   « we considered the split and it was unnecessary » must not read, next wave, as « nobody looked ».
2. **`features/library/page.tsx` is one of L14's four files** — § 3 below.

---

## 2. The library question — REVERSED by the operator on 2026-08-31, and this section is rewritten

**⚠ THIS SECTION ARGUED THE OPPOSITE UNTIL 2026-08-31, and the argument is void.** It read D9's
rule 2 — *a library is adopted for maths nobody has written* — as a presumption against adopting,
concluded that windowing a uniform list is « arithmetic, not maths nobody has written », and
proposed a **refusal**. **The operator reversed rule 2 the same day**:

> Hand-written code is for maths NOBODY has written. When a reliable, maintained, proven, widely
> used library solves EXACTLY our problem, it is **preferred** to re-coding it. The question to ask
> first is « does such a library exist? » — and if yes, **propose the candidates** with the criteria
> each meets, so the operator chooses.

The steward is transcribing the amendment into D9 itself (rule 2, its table's « because » cells, and
a row for the list virtualiser as « candidates to propose »). **Rule 1 is UNCHANGED** — what is
declarative lives in the stylesheet — so the page-transition and spring verdicts stand exactly as
they are, and this lot adopts the View Transitions API and refuses a JavaScript animation library
for page transitions on rule 1's authority, which was never in question.

**The old argument is kept above rather than deleted** because § 7.1's rule is that a decision is
amended by naming what it makes void, never by quietly editing the old text — and because the next
wave should be able to see that « it is only arithmetic » was tried and overruled, rather than
proposing it again as if new.

### What replaces it

**Question one is now « does such a library exist? », and for a list virtualiser the answer is
plainly yes** — several mature ones. So this lot **surveys and proposes; it does not write the
windowing by default and it does not decide the adoption.** Phase 8 puts the candidates to the
operator with the criteria each meets, and adopts the one the operator names.

**The criteria, from the operator's own words plus rule 1, which still binds:**

| Criterion | Where it comes from |
| --- | --- |
| **Solves exactly our problem** — windows a long list, in BOTH the grid and the list mode | the operator |
| **Maintained** — releasing, answering issues, not in archive | the operator |
| **Proven / reputation** — widely used, not a promising newcomer | the operator |
| **Headless** — imposes no markup and no styling | **rule 1**, which is unchanged: a virtualiser that ships its own CSS moves drawing out of the stylesheet and out of the design reference. This is the criterion the operator's list does not name and this lot must not drop |
| **Handles both fixed and measured item heights** | § 3's measurement below — the two modes differ |

**The two-arm split this section used to propose has COLLAPSED, and that is the amendment's doing.**
It existed only to weigh « write it » against « adopt it » on either side of item geometry. Under the
new rule one library covers both modes, so geometry no longer decides *whether* to adopt — it
decides only which MODE of the adopted library each surface uses (fixed size, or measured).

**The measurement is still owed, and phase 8 still takes it.** The library page draws two modes:
`grid` (tiles, `aspect-ratio: 2/3` — uniform by construction) and list (`.card`,
`grid-template-columns: auto 1fr` — height follows the text, and §12 requires a long title to take
the whole line and **wrap rather than truncate**, so a two-line title is a taller card). Which mode
is configured fixed and which measured follows from that reading, and getting it wrong produces a
list that jumps under the reader — the exact defect no green gate would show.

---

## 3. `features/library/page.tsx` is L14's, and P24 lives inside it

`--arm size --list-grandfathered` records four feature files against **L14**, and
`features/library/page.tsx` (613 non-blank) is one of them. The brief forbids **extending** L14's
four files. P24's only unvirtualised long list is in that file, at `:371`.

**This is a real tension in the contract and it is not resolved by ignoring either half.** The
resolution:

- The windowing vocabulary is a **`ui/` primitive** — it is vocabulary by invariant 10, exactly as
  the gesture arbitration is. The page does not learn to virtualise; it *uses* a component.
- The page's own change is therefore a **substitution, not an addition**: the `IntersectionObserver`
  block and the raw `.map()` go, the component comes. **The gate is arithmetic and it is in the
  phase's definition of done — `features/library/page.tsx` must come out of phase 5 with a
  non-blank count less than or equal to 613**, measured by the same command that recorded it.
- Its grandfather label stays **L14**: L14 still owes the decomposition. This lot does not pay it
  and does not claim to.

If phase 5 cannot hold that count, **the phase stops and reports** rather than extending an L14
file quietly — § 0's third rule, and B-152's shape.

---

## 4. Where each property lands

Invariant 10 governs every placement: an arbitration is **vocabulary**; what stays feature-local is
*which* gesture a surface offers, never *how* a press, a drag and a scroll are told apart.

| Property | Lands in | Kind |
| --- | --- | --- |
| **P25** tap highlight, **P26** long-press selects nothing | `styles/base.css` (base layer — a document-wide default is a name the document defines once, the precedent `spin` and `pulse` set) | behaviour |
| **P11** `100dvh`, contained overscroll | `styles/base.css` | behaviour |
| **P17** `interactive-widget=resizes-content` (**B-234**) | `design/index.html` viewport meta | behaviour |
| **P5** declared page transition | `app/navigation.ts` (the `startViewTransition` wrap) + `styles/base.css` (`::view-transition-*`) | behaviour |
| **P6** shared element (poster card → sheet) | the poster's variants + the sheet's | behaviour |
| **P20** reduced motion per transition | `styles/base.css`, beside each transition it governs | behaviour |
| **the press/drag/scroll arbitration** | `lib/press-arbitration.ts` — **moved**, not replaced (D9 rule 2) | conversion |
| **pull-to-refresh** (`#ptr`, engine-driven at the time this table was written; `index.html:258` — the line was cited as `:241`, which is the skip link's comment, and that is **B-271**) | the gesture vocabulary in `lib/` (`MODEL.md` Part 8 assigns it here) | conversion |
| **the feedback seam** | `lib/feedback.ts` — one `feedback(kind)` call site, visual today (D9) | conversion |
| **P29** declared poster box | the gallery variants | behaviour |
| **P24** windowing | `ui/` primitive, used by `features/library/page.tsx` (§ 3) | behaviour |
| **B-252**'s two rules | `harness/` — no source change; they read what L15 shipped | rule only |

**What this lot does not touch**, and the list is the brief's: a producer or its engine-side gesture
callers (**L19** — the deck's and the rows' use of the arbitration moves with them), the ladder's
handler (**L13**), L14's four files beyond § 3's substitution, the engine's two beyond *subtraction*,
and `app/shell.tsx` (§ 1).

**Moving the arbitration out of `legacy.js` is a SUBTRACTION and therefore allowed by D5.** The
engine keeps calling it — `panelUnderFinger` and `openPanel` are its producers and stay — but the
timer, the 12 px tolerance, the point-identified click swallow and the `contextmenu` refusal become
`lib/` vocabulary that the engine and the React surfaces both consume. `app/drawer-gesture.ts`
already set this posture and wrote down why (« ZERO LINES ARE ADDED TO THE ENGINE »).

---

## 5. One kind of change per commit — how this wave obeys § 0

§ 0 forbids mixing a conversion and a behaviour change. This lot's contract requires both: it
*moves* the arbitration and it *adds* transitions. The precedent that resolves it is L15's and
L11's — **the split is per COMMIT and per PHASE, not per wave** (L15 « carries it as a behaviour
change in its own commit »; L11 held it over 36 commits with zero mixed).

So: **a conversion phase lands at zero oracle divergence and moves no behaviour. A behaviour phase
names its divergences in its own commit.** No phase does both. Where a phase's name does not make
its kind obvious, its file says which it is.

---

## 6. What every rule in this wave must survive

The instrument's own two traps, from the brief, are design constraints and not afterthoughts:

1. **A synthetic event is not a finger.** It is never cancelled, so it cannot tell whether a gesture
   survived the compositor. Two gestures were lost that way and no script noticed; a real mouse on a
   touchless browser found two more. Every gesture rule drives a **real pointer stream** (R55's and
   `drag.py`'s discipline — `Input.dispatchTouchEvent`) **and a real mouse** (`mouse.py`'s).
   A rule that passes with `dispatchEvent` alone has proved nothing.
2. **The oracle measures at rest, under `html.measuring`.** A state captured mid-transition is a
   flicker. **Named states are measured settled** — the oracle's own two-frame wait is the
   precedent — so a transition must be *driven* by its rule and read while it runs, never left for
   the oracle to stumble into.
3. **Both motion preferences, every time** (invariant 14). A transition must be seen to **run**
   under `no-preference` and seen **not to run** under `reduce`. A rule that only ever asserts the
   first has certified half a designed state.

And B-085's freshest shapes, which are the counter at **143**: before believing each rule, ask what
it does **not** read — a rule that lives in the file it measures, a floor calibrated by hand near
its own corpus, an edit reported done by a `str.replace` that matched nothing (**every edit carries
an `assert old in s`**), a hold satisfied on a consequence while the mechanism it names is gone, a
repair shipped with no regression hold, a cited line number past the end of the file.

---

## 7. Decisions taken in this design

| # | Decision | Because |
| --- | --- | --- |
| **D-L12-1** | ~~The D9 verdict row is conditional on item geometry~~ **VOID since 2026-08-31.** The row **surveys CANDIDATES and proposes them to the operator**, who chooses; this lot does not write the windowing by default | The operator reversed D9's rule 2: a reliable, maintained, proven, widely used library that solves exactly the problem is **preferred** to re-coding it. § 2 carries the reversal, the criteria and what it makes void |
| **D-L12-2** | **P29 is ordered before P24** and treated as its precondition, not its neighbour | **The reason changed with D-L12-1 and the ORDER survives it.** It used to be « a declared box makes the uniform arm true »; it is now that a virtualiser measuring an undeclared box measures a box that is still growing, so the declaration must land first either way |
| **D-L12-3** | `app/shell.tsx` is **not opened**, and no subject-split is done | The transition host is `app/navigation.ts`; the split the contract held in reserve has no subject (§ 1) |
| **D-L12-4** | The windowing is a **`ui/` primitive**, and `features/library/page.tsx` must leave phase **8** at **≤ 613** non-blank lines | Invariant 10 makes windowing vocabulary — **and it survives D-L12-1 unchanged**: an adopted library is wrapped in the `ui/` primitive rather than imported by the page, so the page still uses a component and the dependency has one call site. The count keeps § 3's promise checkable rather than asserted. (« phase 5 » here was a slip for phase 8 — the phase table has always said 8) |
| **D-L12-5** | The arbitration is **moved** to `lib/press-arbitration.ts`, its engine-side callers left where they are | D9 rule 2 and D5 — subtraction, not editing; the callers are L19's |
| **D-L12-6** | Conversion and behaviour split **per phase and per commit**, not per wave | § 0's rule, on L15's and L11's precedent (§ 5) |
| **D-L12-7** | B-268, B-269 and B-270 are **left for whoever next touches `served_copy.py`** | The brief assigns them conditionally; this plan has no phase that opens that file, so it does not claim them |

---

## 8. The register, written DURING the wave

`BUGS.md`, next number **B-271** (`python3 scripts/check-bug-register.py --next`; a number taken on
another branch is invisible here). Entries land as they are found, not at the close. **B-234** and
**B-252** are this wave's to close; the fifth post-merge step — recounting « guards green over what
they do not read » — is this wave's too, **and zero is a real answer written down with the same
authority as six**.

## 9. The gates

**Per phase**: the oracle (green, or divergences named as a behaviour commit's), `run.sh
--contracts` (13 rules + the repository's cheap guards, which the script counts and prints).

**Before merging**: the **full** suite (`run.sh`, not `--contracts`), the `--a11y` tier,
`scripts/harness-hold-counts.py --compare` with every movement written down, and `make check` at
zero failures **and zero errors**.

**The harness is one per machine** — `served_copy.py` is its lock and its stamp. The steward may be
auditing here; **announce by message before `run.sh`, the oracle, `mutate.sh` or
`harness-hold-counts.py`**. A rule that falls while another session held the harness is re-run alone
before it is read as anything.

**Every rule lands with its mutation, seen red and restored, at the moment it is written** —
`scripts/mutate.sh` refuses a dirty tree and restores from the index, so the fix is committed first.
