# L10-bis — the twenty-two closures, one by one

**Incomplete by construction.** What follows is the wave's standing body of work, fixed on
2026-08-29 against `main` at `f684486c`. Groups 0 to 5 were arbitrated by the operator between
2026-08-28 and 2026-08-29; Group 6 was added by the steward's audit of L10.

**The rule governing the whole document**: the rule 3 amendment is the FIRST commit. Every entry
below closes with a command whose output is in the entry. Where the instrument does not exist,
**writing it is part of the work** — and it is mutation-tested before it is believed.

---

## Group 0 — the guard that comes first

*One entry, and it precedes every other correction. Placement dictated by the operator on
2026-08-29.*

### B-102 — seven duplicated index rows, once `fixed` and once `open`

**The defect, measured on `main` at `f684486c`.** B-079 to B-085 appear **twice** in the `## Open`
table — lines 115-121 with `fixed #505`, lines 136-142 with `open`. Both occurrences are in the
SAME table; the closed index is a bullet list (`- B-NNN — … (closed …)`) and cannot produce this
duplication. All seven bodies say « FIXED by #505 ».

**Why it goes first, and this is not tidying.** This wave will close some twenty entries and write
each one into this file. **While the index can carry two contradictory rows for one identifier,
this wave's own closures can be written twice and nobody will see it** — including the ones proving
the amended rule 3 is respected. The guard protects the record of everything that follows, itself
included.

The cost of its absence is already paid and measurable: the count handed to the operator on
2026-08-28 announced **48 open entries** where there were **42**. A register whose index
contradicts itself makes every figure drawn from it false.

**It is also the first exercise of the amended rule 3**, and the cleanest one available: an
instrument built where none existed, mutation-tested before it is believed.

**The instrument — `scripts/check-bug-register.py`, four arms.**

| Arm | What it refuses |
| --- | --- |
| `duplicate-row` | an identifier appearing more than once among the `\| B-NNN \| … \| \`status\` \|` rows. **This is the exact defect**, and it is unambiguous: the file's two tables have different formats. |
| `status-vocabulary` | a status outside the declared vocabulary — `open`, `fixing`, `to confirm`, `fixed #NNN`, `closed`. Catches a typo that would make a row invisible to every count. |
| `invariant-numbers` | **B-103**: two invariants carrying the same number in `frontend-architecture.md`. Same family, same guard file — the numbers are CITED in briefs, and a brief has already instructed a wave on « invariant 10 » meaning the wrong one. |
| `corpus` | **the number of rows read is PRINTED, with a floor.** A reader that finds zero rows and reports clean is the shape this repository has paid for seventy-three times. The floor is seeded BELOW today's count, never at it — a floor set where the count already sits is pre-satisfied (B-075). |

**A tool in the same script, and it is what stops the real recurrence: `--next`.** It prints the
next free identifier. The defect that repeated **three times in twenty-four hours** — B-152, then
B-160, then B-219 for a single entry — is not a duplicate row: it is **two branches taking numbers
from a register another wave is writing**. No guard on `main` can see a neighbouring branch. What
helps is that nobody has to guess any more. That is B-147, recorded, then repeated three times by
the office that recorded it.

**What this guard does NOT read, and it must be written into the module.**

- **It reads the index, never the bodies.** A row marked `open` whose body says « FIXED by #505 »
  is invisible to it once the duplicate is removed — and that is precisely the state of these seven
  entries. Reconciling index against body is a text heuristic and fragile; **naming the blind spot
  is worth more than an arm that gets it wrong.**
- **It reads `BUGS.md` alone.** `BUGS-CLOSED.md` carries moved bodies and is not in its corpus.
- **It cannot see other branches** — see `--next`, which answers that and is not a guard.

**The mutation, both ways.** Duplicate a row with a different status: `duplicate-row` falls and
**names the identifier**. Write `fixed` with no pull-request number: `status-vocabulary` falls.
Empty the table: `corpus` falls instead of reporting clean.

**The repair itself is trivial** — remove the seven `open` rows, the bodies already saying
`fixed #505`. **The guard is the deliverable**, not the deletion.

---

## Group 1 — the oracle and the browser

*These could not be done remotely. The oracle's references carry `"platform": "Darwin/arm64"` and
refuse any cross-platform comparison.*

### B-139 — three typed variants exported and never called

**The defect.** `addFooterAction`, `resultList` and `suggestionChip` in
`features/acquisition/variants.ts` each return **exactly one grep hit: their own declaration**. The
button at `add-screen.tsx:369` is therefore bare; preflight is deliberately not imported (L07's
decision, and a right one); the browser then paints its own button — light ground, dark text —
which is **the white rectangle the operator photographed on 2026-08-28 at 23:02**.

**What changes.** Wire all three. Nothing else: the six declarations `.addfoot button` carried are
already written in the variant.

**The instrument — and it must be built, because the oracle CANNOT prove this today.** The entry
measures it itself: the bar paints only when `added.size > 0`, and that screen's two named states
are `acq-add-empty` and `acq-add-results` — the second searches « star wars » and adds nothing.
**No measured state ever paints this bar.** Not a coverage gap: a STATE gap.

Two routes, and **the second is recommended**:

1. Add a named state that adds a medium. But `engine/states.js` is the dying engine's scenario
   table, which L13 removes — it would grow what must die.
2. **A Playwright hold walking the real journey**: search, add, assert the button's computed colour
   is the `primary` token and its background transparent. That is the register's rule 4 — *the rule
   covers the path the operator actually walks* — and it does not grow what must die. What is lost
   is nameable: the oracle will not cover this bar; a rule will.

**The arm that prevents the fourth.** Twenty lines: *every `cva` exported from a `variants.ts` is
called from another file*. It would have returned all three at once. It asks what no existing guard
asks — `check-markup-contracts.py` reads the classes that ARE emitted; nothing reads the ones that
were meant to be.

**The mutation.** Unwire `addFooterAction`: the hold falls on the colour, the arm falls on the
orphan export, and both name the right defect.

**The half the operator must arbitrate, and they have just lived it.** The entry says: the bar is
`sticky`, nothing reserves the space beneath it, it covers a card, and *it has no dismissal by
design*. The operator read it as a stuck notification — because its only exit was unreadable.
**Put the question before coding**: once the button is legible, does the bar keep that shape, or
does it reserve its space?

### B-138 — the panel's avatar is unconstrained, and the probe reads only the container

**The defect.** `ui/panel/index.tsx:221-222`: the `<span class="avatar …">` carries its classes,
the `<img>` inside carries none. The header (`index.html:193`) carries the full set on both. The
named probe measures the container, never the child: **it is green over an unconstrained image.**

**The instrument.** A named rule reading the `<img>`'s computed box, the way R26 covers a
pseudo-element. Widening the probe to children is the other route — **that is D8's arbitration, not
this wave's** (B-061 already settled it the other way: the oracle measures elements, and the limit
is written into D8).

**The mutation.** Remove `object-fit: cover`: the rule falls, the oracle moves.

### ~~B-140~~ — CLOSED by L10 (#512), and the diagnosis was wrong about the journey

**Removed from this wave.** The steward had written that the position was lost by « scrolling a
page, opening an item, coming back ». L10 measured that **this journey cannot lose it** — a screen
overlays the page, `#port` is never unmounted. What loses it is a **top-level page switch**: back at
**0** with the old selector, at **300** with the repair, on one build and one selector apart.

The rule written for B-140 passed over the defect and its mutation did not fall. The wave filed it
against itself: **B-158**. The second half — the stored `0` treated as absent — was closed too,
after being flagged as still present: **B-178**.

**The posture matters more than the fact: a mutation that does not fall is information.**

### B-219 — the drawer and the tab bar are converted by no lot

**Deferred to L10-ter**, whose subject it is. Nothing to do here — but **the number must be verified
before it is written**: it has changed three times (B-152, B-160, B-219) because L10's three pull
requests carried the register from B-151 to B-218.

### B-146 — D11 is decided and no stylesheet styles a scrollbar

**The defect.** D11 says the scrollbar is **STYLED, never replaced** — `scrollbar-width`,
`scrollbar-color`, `::-webkit-scrollbar`. No declaration exists.

**The instrument, and it is THE reason this wave runs on the machine.** Narrowing the gutter can
move **every measured rectangle** in that container. Re-recording the references can happen nowhere
else.

**The method.** Style, measure, **then** name every divergence before accepting it — the way L06's
47 folds were accepted. A broad divergence is not a reason to abandon D11; it is a reason not to
slip this change into a wave whose proof rests on the oracle staying at zero.

**What D11 does not fix, and says so**: the gutter still exists on a desktop. The comparison that
prompted it was `harness.css`'s phone frame, which ships nowhere.

### B-055 — the accessibility floor measures the dark theme only

**The defect.** 154 findings in light, invisible to the `--a11y` tier, which drives dark only. Found
during L06 by a sub-agent who drove `data-theme="light"` by hand.

**The split, and it is deliberate.** The wave **arms the measurement**; it does not remediate the
154. Remediation is a campaign with its own design and plan
(`docs/archive/features/maquette-l06/drafts/a11y-floor-measures-one-theme.md` carries the
inventory). Arming stops the floor reporting zero over a theme it does not look at — **and that is
the defect the entry names.**

**Not decided, to be settled in the wave**: does the tier drive both themes (doubling its runtime)
or does a lighter arm audit palette pairs in light? Write the decision and its reason.

**The mutation.** Break a contrast in light only: the tier must fall. If it stays green, the
measurement is declared, not armed.

### B-042 — an orphan `http.server` holds port 8900

**The defect.** Residue of an accessibility probe launched by hand during L03. 9.6 MB, harmless,
**on the operator's machine** — which is precisely why no remote wave could close it.

**The instrument.** Kill the process; `lsof -i :8900` returns nothing. Verifiable in one command.

---

## Group 2 — an arm that does not exist yet

*Three entries whose closure IS the construction of the instrument. This is the heart of the
amendment.*

### B-141 — ten elements carry no class, eight of them unread

**Mind what the entry says.** It is a list of **CANDIDATES**, not of ten defects. Two are confirmed
because the operator saw them (B-138, B-139). **The other eight are unread**, and the entry exists
to be checked, not believed. Two carry more risk: `panel-field.tsx:139` is a bare `<input>`, which
keeps the platform's own field — light ground, system border.

**What changes.** Read the eight. Fix the ones where the browser's painting is wrong; write, for
the others, why it is not. **An `<img>` its parent fully constrains is fine**, and saying so is the
work as much as fixing is.

**The instrument.** An arm counting elements with no class at all in `design/src/**/*.tsx`, **with
a ratchet**. The ratchet is seeded **after** the fix, never at the current value: a floor set where
the count already sits is pre-satisfied and can never fall. That is B-075, found twice in two waves.

**The mutation.** Remove a class: the count rises, the arm refuses.

### B-100 — invariant 10 is written and unarmed

**The defect.** *« The frame does not name the domain »* has no arm. Nothing counts the frame's
domain words.

**The instrument.** The arm counts, per directory of `design/src`, domain words outside comment
lines. **Two requirements the entry sets and that must not be trimmed**: the refusal must carry its
readable reason, the way `code-vocabulary.txt` does, or it gets worked around; and the ratchet
**must not be seeded at the current value without being read**.

**The mutation.** Name a domain in `app/` or `lib/`: the arm falls.

### B-041 — the newest guard is the only one of its family with nothing to re-run

**Careful, the entry has stopped being true.** `tests/scripts/test_check_frontend_boundaries.py`
exists **since #484**, the L05 repair wave, and carries 42 tests — three added by #511.

**What remains real.** The entry faulted the absence of tests for **eight arms**; nobody verified
the eight are covered, and the guard carries twelve today.

**The instrument.** A coverage assertion: every `arm_*` function is named by at least one test. Then
the row closes as `fixed #484` — or the gap is real and it is named.

**The mutation.** Add an arm with no test: the assertion falls.

---

## Group 3 — an arm that exists and does not read far enough

### B-036 — `panne` and `groupe`, two state identifiers still in French

**The defect.** Four occurrences in `engine/states.js`. Found by driving the 82 states for L01,
**not by a guard**: `check-no-french.py` has fourteen arms and **none reads the state table**, so
the count went from 51 to 2 and then stopped moving with nothing to notice.

**The instrument.** The missing arm. **The rename without the arm does not close this entry** —
that is literally what the entry asks: *« its fix should carry the missing arm rather than only the
two renames »*.

**The rename goes through `scripts/rename-identifiers.py`**, never by hand. And the tool is not the
proof: its read-back is skipped for `--values` runs and for Python. **Re-read the diff**, not the
« N file(s) touched » line.

### B-040 — names in files no arm reads

**The defect.** `frontend/maquette/oracle.py` uses « entérine » three times, and **line 953 is
`--accept`'s help string** — a message the tool prints, which `CLAUDE.md` requires in English.

**The instrument.** `check-no-french.py`'s scope widened to the messages printed by the maquette's
Python tools. The arm is the proof; the rename alone is not.

### B-051 — a feature-owned reader escapes the boundaries arm

**The defect.** `toFollows()` carries its page identity in a query parameter, inside a feature file
the ninth arm does not reach: it reads route files, not every function that shapes a query.
**D1 — path carries identity, query carries state — is enforced here by no guard.**

**The instrument.** The arm reaches feature-owned readers.

**The mutation.** Put the identity back in the query elsewhere: the arm falls.

### B-057 — R12 measures four contexts of five, in silence

**The instrument.** R12 measures five of five, and **the count is printed** — an arm measuring less
than its corpus must say so; that is B-085's shape.

**The mutation.** Break the fifth context: R12 falls.

### B-104 — the contract's generated types live under `mocks/`, and are not one

**The defect.** It is the CONTRACT's shape — what the interface may ask for — filed in the bucket
L04 declared for « handlers and fixture seeds ».

**What makes the move safe.** Five ends: the `package.json` script, `make check-contract-types`,
`check-mock-seeds.py --arm generated`, the boundaries guard's `GENERATED` table, and four importers.
**Three instruments already exist**; the proof is that they all pass after the move, in one commit.

---

## Group 4 — the machine settles a question of class

### B-049 — a rule reads the operator's live `acquire.db`

**The defect.** The follows fixture mirrors the live database; the watcher cron moves it
independently of any wave — twice within 24 h during the L05 repair. **Not a code defect, a
question of class**: does a rule reading live data belong in a gate at all, and at what cadence does
it re-sync?

**The constraint that decides.** The `--contracts` tier runs in CI on every pull request touching
the maquette, and **a rule reading the operator's live databases cannot be there** — `arrivals.py`
was, and failed on the runner for want of `library.db`, which said nothing about the change under
test.

**The instrument.** The tier green twice, either side of a cron window. That is the only proof the
question was settled rather than moved.

### B-058 — `commit-msg`'s AI-attribution pattern is unanchored

**The defect.** It catches a sentence quoting the forbidden thing. The entry notes that the commit
describing it tripped the hook it describes.

**Why it was not fixed on the spot, and that must be respected.** The two real alternatives are
anchored to a line start **on purpose** — a trailer, not prose. Giving this one the same anchor
needs its own mutation, to confirm it still catches a genuine footer while releasing a quoting
sentence. *« A same-commit reflex fix on a compliance-relevant guard is exactly the haste this
register exists to slow down. »*

**The mutation, both ways**: a real `Co-Authored-By:` trailer falls; a sentence quoting it passes.

---

## Group 5 — the two with no automatic proof

*Named in advance, so the exception is not discovered at the moment it happens to be convenient.*

### B-024 — the entry cites a phase that no longer exists

**The defect.** *« Settles when `data-go` migrates to the shell (SP4d) »*. SP4d no longer exists;
today that is L13.

**No instrument.** It is prose in a document no guard greps. The repair is one sentence. **The
closing entry must say so** — this is the first of the two exceptions the amendment allows.

*A lead, if the wave has time and not otherwise*: an arm refusing a dead phase name cited in the
directive documents would close the whole class. Five such sentences were found on 2026-08-28 in
the plan, and it was the arbitration commit itself that had left them.

### B-151 — `coverage-merge` blames a missing artefact when lint failed

**The defect.** `needs: [changes, test]` with `if: always() && !cancelled()`, and every step gated
on « did Python change », **never on « did the job that produces the artefact run »**. When `lint`
fails, `test` is skipped, and `coverage-merge` runs anyway and fails blaming the artefact. Two red
checks, one cause, and the second points nowhere.

**The repair.** `needs.test.result == 'success'` on the steps — or the job does not carry
`always()` past a skipped dependency.

**No automatic proof without making CI red on purpose.** The honest form: repair the condition, and
write in the entry that **the next genuinely red run is its verification.** Second and last
exception.

---

## Group 6 — what the audit of L10 added

*Two findings from the audit of 2026-08-29, against `main` at `f684486c`. Both have an instrument.*

### A-1 — the cross-check B-208 built never runs in CI

**The defect, and it is sharp.** `check-live-relay.py`'s `backend_events()` compares TWO oracles:
the bus registry (`_EVENT_CLASS_REGISTRY`, what the wire actually carries) and a regex source scan.
That is B-199, and it was the right repair.

**B-208 then made the DISAGREEMENT blocking** — « printed and could fail nothing » was the shape the
wave had just named two arms over. The disagreement now returns a reason, and the caller counts a
violation.

**And the IMPORT failure, three lines above in the same `try`, still prints and passes.**

```python
except Exception:
    print("… the corpus is the source scan alone, which is a
           re-implementation nothing is cross-checking here.", file=sys.stderr)
    return from_source, None        # ← no reason, no violation
```

**B-208 was applied to one of the two branches of the same `try`.** And the docstring above still
says *« The two are compared rather than one being trusted »*, which is false on the branch CI
takes.

**Because CI always takes that one.** The `harness-contracts` job installs `playwright` and
`jsonschema` — **never `personalscraper`**. So on every pull request touching the maquette, the arm
runs on the re-implementation alone and reports clean. The cross-check exists only in `make check`,
which is a WAVE gate, not a per-pull-request one.

**The remedy is written three lines above in the same job**, for `jsonschema`: *« installing the ONE
package keeps this to seconds… Without it the arm answers "not installed" and the tier is red for a
reason foreign to every change under test. »* jsonschema goes red. This one goes green.

**Two possible repairs, and one must be chosen explicitly**: install the package in
`harness-contracts` (seconds; the pattern is already there), or make the non-import a violation like
the disagreement. **The second is more honest and costs a red the day the environment is
incomplete.** Decide and write the reason.

**The instrument.** The arm refuses, or the job installs. Proof: the tier runs and the degradation
message no longer appears. **Mutation**: uninstall the package — the arm must fall, not print.

### A-2 — a floor at 60 against 127, and a figure already drifted inside its own comment

`POLLING_CORPUS_FLOOR = 60`, and the comment says « 60 against **124** files ». The tree reads
**127** — it read 126 when #512 merged, and 120 when the pull-request body was written. **Three
values for one hard-coded number in a comment, in three days.**

The floor itself declares its blind spot — *« a real floor against total collapse and blind to
targeted loss »* — and **that posture is right; it is not the defect**. The defect is the number
frozen beside it.

**The instrument.** The comment cites the command, or cites no number. That is the plan's own rule
applied to a guard comment: *no figure without the command that produces it.*

---

## Two evolutions dictated by the operator

**Arbitrated: L10-bis, and proved with a REAL FINGER.** These are not defects: they are requested
evolutions, to be recorded as `E-002` and `E-003` in § *Requested evolutions*, in `E-001`'s format.

### How the operator's marks were measured

The screenshots are **1200 × 2670 px**. The drawer is `w-[288px]` and its right edge falls at
**76.8 %** of the width ⇒ the viewport is **375 CSS px**, DPR **3.2**. Every value below follows.

**They are hand-drawn marks: intentions, not a specification.** The round number is proposed;
confirmation happens with a finger on the device.

### E-002 — the menu closes on a leftward swipe from its right edge

**The band.** ~67 px measured, **72 px proposed**, ending exactly on the drawer's right edge
(x = 288). A quarter of its width.

Written as an **arbitrary value** (`w-[72px]`), and that is the theme's rule, not a shortcut:
*« a size that is genuinely not a spacing step — a 44px touch target — is written as an arbitrary
value and says so by its shape »* (`styles/theme.css`, around line 137). The scale stops at 24 px;
72 is not one of its steps and must not pretend to be.

**`touch-action: pan-y`, not `touch-none`.** The menu scrolls vertically; the band claims the
horizontal only. That is compositor-facing, so `check-compositor-css.py` holds it — as it already
holds the sheet's `touch-none`.

**Where the code lives, and why this is NOT a D5 violation.** `index.html:451` carries
`<aside class="drawer …" id="drawer" aria-label="Menu"></aside>` — **empty**. The dying engine fills
it, opens it and closes it. Writing the gesture into `legacy.js` would be an addition, and D5 allows
only subtraction.

**The precedent is written in the repository**: `installFocusManager()` watches `data-open` on
`#drawer` with a `MutationObserver` and — the sentence is in `app/shell.tsx` around line 262 — *« it
asks nothing of the engine: it watches the `data-open` attribute both worlds already emit »*. So:
**`installDrawerDismissGesture()` in `app/`**, attached to the existing node, mounted with the rest
of the shell. **Zero lines added to `legacy.js`.**

**Closing goes through `window.__closeLayers?.()`** — the seam the sheet's scrim already calls
(`ui/sheet.tsx`), published by the engine at `legacy.js:9614`. The layer ladder is
**drawer → screen → sheet**, so with the drawer open, `__closeLayers` closes the drawer. Do not
invent a second closing path: a second path is a second navigation history.

**The gesture in detail, and every point was paid for elsewhere:**

- **`setPointerCapture` on `pointerdown`, mandatory.** The reason is written in `ui/sheet.tsx`:
  without it a real finger delivers `pointerdown`, two `pointermove`s, then **`pointercancel`** —
  the compositor takes the gesture, the stream dies, `pointerup` never comes, and the layer stays
  open. Capture also keeps events coming once the finger leaves the band, which happens within the
  first centimetre of a gesture that must travel seven.
- **`pointercancel` puts the drawer back; it does not close it.** A cancel is not a lift.
  `sheet.tsx` already does this (`endDrag(true)`); copy the posture, not the code.
- **The drawer follows the finger** in negative `translateX`, clamped at 0, as the sheet follows in
  `translateY`. Without following, it is no longer a manipulation but a blind command.
- **A `dragging` class that cancels the transition.** The drawer carries
  `transition-[transform] duration-300 ease-standard` in its markup: during the drag it must be
  neutralised, exactly as `.sheet.dragging` is — and for the reason written in `layout.ts`: the
  state that CANCELS the transition is not a prop, it is written to the DOM by the handler through a
  ref.
- **The threshold.** The sheet uses `CLOSE_THRESHOLD = 70`. Reuse 70 for the horizontal **unless a
  finger measures otherwise** — a different threshold per axis can be justified; it cannot be
  guessed.

### E-003 — the sheet closes on a downward swipe from a widened top edge

**What exists.** Drag-to-dismiss already works, but from `#sheetgrab` alone:
`h-[22px] grid place-items-center flex-none touch-none cursor-grab`
(`ui/variants/layout.ts:103`). The operator asks for four times that.

**The band.** ~100 px measured: **~88 px inside the sheet and ~12 px above its edge.**

**The structural tension, and it is real.** `#sheetin` (`overflow-y-auto`) is the **sibling
immediately after** `#sheetgrab`, and it holds the poster, the title, the chip and the seasons. An
88 px `touch-none` band takes 88 px from scrolling: either it pushes content down inside a sheet
capped at `max-h-[78%]`, or it covers the poster and the title, which stop scrolling.

**The arbitration retained, and it is one condition:**

> **if `#sheetin.scrollTop === 0`, a downward drag is a dismissal; otherwise it is a scroll.**

A sheet that opens is always at the top, so the first gesture is always a dismissal, and the content
keeps its scrolling. **One condition, not a gesture engine** — the full press/drag/scroll
arbitration remains L12's subject, and the plan already writes the two facts that make it hard: a
drag is claimed on the first movement, and Chrome delivers **no `touchmove` at all** for a drift of
a few pixels.

**The band overlays the top of `#sheetin`**, it does not push it. Consequence to verify and write:
within those 88 px a tap no longer reaches what is underneath. Establish that nothing interactive is
there — the poster and the title, presumably not, **but that is to be measured, not assumed**.

**The 12 px above the edge are a separate decision, and it is not the wave's to take.** That zone is
the **scrim**, and the scrim closes on tap (`onClick={() => window.__closeLayers?.()}`). Turning it
into a grip removes 12 px of tap-to-close and makes it a drag zone. Both end up closing, so the cost
is small — but a tap that becomes a failed drag closes nothing. **Put it to the operator before
coding**: does the overhang exist, or does the band stop at the edge?

### The instrument, for both — and this is where « real finger » bites

The plan says it of L12, and it governs both holds:

> **A synthetic event is not a finger. It is never cancelled, so it cannot tell whether a gesture
> survives the compositor. Two gestures were lost that way and no script noticed. A real mouse on a
> browser with no touch at all found two more.**

**So the proof is three exercises, and none replaces the others:**

1. **A real touch stream under Playwright** — `page.touchscreen`, or `Input.dispatchTouchEvent` over
   CDP. **Never `mouse.move`**: a synthetic mouse produces no `pointercancel` and validates a
   gesture the compositor would take away.
2. **A pass by hand, with a finger, on the phone**, recorded in the entry with its date and the
   device. **It is the only proof of `pointercancel`**, and the reason the operator wanted this wave
   on the machine.
3. **A real mouse on a browser with no touch** — the case that found two lost gestures. The drag
   must work or be cleanly inert, never half.

**The mutations, asymmetric on purpose:**

- Return the band to its previous size (`w-[0px]` / `h-[22px]`): the holds fall, each naming its
  gesture.
- **Remove `setPointerCapture`**: the touch hold falls and **the mouse hold stays green**. That is
  exactly the lesson `sheet.tsx` paid for, and a mutation replaying it is the best proof the three
  exercises are not three of the same.
- Close on `pointercancel` instead of restoring: the cancel hold falls.
- For E-003, set `scrollTop` to something other than 0 and drag down: the sheet must scroll, not
  close.

**What these two gestures cost the oracle: nothing, and that is to be verified rather than
believed.** Neither changes a resting painting — the band is transparent, and the size of a grip
zone is not a colour. If a reference moves, the layout was changed while believing only a grip was.

---

## B-219 — the drawer and the tab bar are converted by no lot

**The finding.** `index.html:451` declares an **empty** `<aside id="drawer">`; the dying engine
fills it, opens it, closes it, draws its entries (`#drawer a[data-navgo]`) and pushes its layer.
`index.html:436` declares an **empty** `<nav id="nav">`; `renderNav()` fills it. On the React side,
nothing renders either: `app/focus.ts` **watches** the drawer, `app/bar-height.ts` **measures** the
bar.

**And the plan names the drawer once** — in D1's address table, as an example of screen state (« an
actions panel, a filter drawer »). **L13**'s objective enumerates what survives subtraction: the
document-level delegation, the boot, `/login`, the splash. **Neither the drawer nor the tab bar is
there.**

**Why nobody saw it, and this matters more than the inventory.** Two instruments watch the engine
and **both measure its SIZE, never its surfaces**: the boundaries guard counts its lines,
`check-legacy-css-residue.py` counts its CSS rules. When L09 took `legacy.js` from 35 263 to 33 449
lines, everyone read progress. **A file that shrinks looks like a file that is dying, even if a
whole page never leaves it.**

**It is L14's class**, discovered the same way: a surface whose conversion nobody owes. Here it is
the application's main navigation.

**What it changes for E-002: nothing.** The React-side installer works against the node as it is,
and that is precisely what makes the gesture feasible today. **What it changes for the plan is
L10-ter's**, whose subject it is.

<sub>`sed -n '448,454p' frontend/maquette/design/index.html` · `grep -rn '#drawer' frontend/maquette/design/src/app/` · `grep -in 'drawer' docs/reference/frontend-architecture.md`</sub>

---

## What the wave does not take, and why

| Entries | Reason |
| --- | --- |
| **B-142, B-143, B-144, B-145** | §17 accounts/Plex SSO, §18 ratio, §19 cross-seed, and nothing measuring the interface against the constitution. They need **lots** and the operator's arbitration. A correction wave does not create surfaces. |
| **B-052, B-053, B-054** | Three readings the L05 repair wave settled alone. **None was ever put to the operator.** They wait for them, not for an agent. |
| **B-071, B-056** | Inside the dying engine. **L13**, and B-071 exists precisely so L13 does not rediscover them as live features. |
| **B-030** | 87 sheets with no genre and no cast: a defect of **data**, not of drawing. Excluded from the batch closure by the operator. |
| **B-033, B-034, B-035** | Python tests of the engine, unrelated to the maquette. |
| **B-031, B-032** | Fixed and mutation-proven; they wait for the operator to confirm. **The wave may present them**; it cannot close them in their place. |
| **B-061, B-068, B-101** | Arbitrated (the oracle is NOT widened, D8 writes it) · L07's drift inventory archived with the wave · a lesson about a brief that predicted instead of measuring. Nothing to fix. |

---

## The order of execution

1. **The rule 3 amendment.** First commit, before any correction: a closing rule written after the
   closures measures nothing.
2. **Group 0 — the register guard.** Immediately after, and before everything else. It is the first
   exercise of the rule just written, and what makes every figure this wave produces about itself
   trustworthy.
3. **Group 1**, the oracle last within it (B-146): it re-records the references, so let it do so
   against an already-corrected tree.
4. **Groups 2 and 3**, each arm mutation-tested at the moment it is written, never after.
5. **Groups 4 and 5.**
6. **E-002 and E-003**, proved with a real finger.
7. **Group 6** — A-1 and A-2.

## The gates

**Per phase**: the oracle, the contract rules, the repository's cheap guards.
**Before merging**: the full suite (`frontend/maquette/harness/run.sh`, **not** the `--contracts`
tier), the `--a11y` tier, and `make check`. Pull-request title and body in English. Adversarial
review before merging.

## The counter

**B-085 is at 73.** This wave writes a new guard in almost every group. Before believing each one,
ask the question that has been paid for seventy-three times: **« what does this guard NOT read? »**

The shapes already paid for: a floor set at the current value · an empty read passing in silence · a
corpus enumerated by hand · a hold armed on one of two entry points · a grep reading the markup
without opening the stylesheet · a guard answering differently per machine · a guard that read the
right file and got a stale answer · **and A-1's: a repair applied to one branch of an `if` and not
the other.**
