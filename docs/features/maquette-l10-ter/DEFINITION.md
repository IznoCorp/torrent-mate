# L10-ter — the application template

**Definition of the phase.** Dictated by the operator on 2026-08-28, and widened on 2026-08-29:
the agent executing it decides WHERE and WHEN the model is converted into work, and may revise the
implementation plan and the phases.

---

## What L10-ter is, and what it is not

**It is not a lot.** It produces no code. Its deliverables are DIRECTIVES: a measured survey, a
drawn model, and the plan amendments that follow.

**It is not a correction wave.** The `-bis` waves close findings. This one opens them: its normal
product is a plan different from the one it found.

**It must therefore be declared like the other non-lots** — the way the semantic scroll index is
named in § 1: *« it is not a lot: nothing schedules it, and § 0's selection rule must not reach
it »*. Otherwise § 0 elects it and an implementation wave opens a design phase.

**The agent executing it is an extension of the steward's office.** Same criteria, same
prerogatives, no more and no less — so it inherits the two limits written in
`docs/reference/frontend-steward.md`:

1. **It cannot certify that a rendering did not move.** Only the oracle says that, on the machine
   that owns the references.
2. **Its anchor is the repository, never a remembered intent.** A figure is measured; it is not
   cited.

And the rule that bounds the office: **it never carries a fix into implementation code.** It
corrects directives and it proposes.

---

## Its subject, in three parts

### 1. The survey — and it is COMPUTED

**The question nobody can answer today: which surfaces does the dying engine still draw?**

What is established and verifiable:

| Surface | Who draws it | Proof |
| --- | --- | --- |
| The side menu | `legacy.js` → `openDrawer()` | `<aside id="drawer">` is **empty** in `index.html` |
| The bottom tab bar | `legacy.js` → `renderNav()` | `<nav id="nav">` is **empty** in `index.html` |
| **Ten** other `innerHTML` writes | `legacy.js` | **unidentified — that is the first act** |

**Twelve writes in all, two of them identified above.** The steward first published « nine »,
from a grep narrower than the one below; re-derive the count rather than inherit it, and note
that this figure moved once already inside the day it was written.

    grep -n "\.innerHTML = " frontend/maquette/design/src/engine/legacy.js
    grep -rn "#drawer\|#nav\b" frontend/maquette/design/src/app/

On the React side, **nothing renders these two surfaces**. Two modules only touch them:
`app/focus.ts` **watches** `#drawer` (it reads `data-open`), `app/bar-height.ts` **measures** `#nav`.

**Why nobody saw it, and this finding is worth more than the inventory.** Two instruments watch the
engine and **both measure its SIZE, never its surfaces**: the boundaries guard counts its lines,
`check-legacy-css-residue.py` counts its CSS rules. When L09 took `legacy.js` from 35 263 to 33 449
lines, everyone read progress. **A file that shrinks looks like a file that is dying, even if a
whole page never leaves it.**

The survey also covers:

- **What the shell IS** — who owns `#device`, `#shell`, `#view`, `#screen`, `#port`, `#topbar`,
  `#nav`, `#drawer`, `#scrim`, `#sheet`, `#dlg`; which are React, which are static markup the engine
  fills, which are read by React without being rendered by it.
- **The layer ladder** — drawer → screen → sheet — and how `window.__closeLayers` and the back
  gesture walk it.
- **What production `frontend/src` does with the same surfaces.** Not to draw from it: it is
  ARCHIVED at switchover, never harvested (§15). But **an unexplained difference is a decision
  nobody took**, and this phase is the first able to name it.

**The inventory is produced by a command that re-derives it.** Not a hand-kept list: this repository
has already watched a hand-kept number drift by seven inside the pull request that introduced it as
a control.

### 2. The model — and « as close to a mobile application as possible » must become measurable

The dictated objective is that the PWA be as close as possible to a mobile application. **As it
stands that is not auditable: it is a mood.** The work converts it into properties a rule can read
one day. Candidates to confirm, discard or complete:

no visible reload between two surfaces · a persistent chrome that does not redraw on every page · a
back gesture walking a layer ladder rather than raw history · a declared transition between sibling
surfaces, and a shared element surviving navigation · a shell that opens and reads offline · an
install entry point and the application as handler of its own links · safe areas, dynamic viewport
units, contained overscroll, no zoom on focus · touch targets at the floor · gestures that survive
the compositor.

**A property for which no instrument is conceivable is discarded or restated.** Same requirement as
the amended rule 3 of the register: a criterion nobody can measure is a criterion someone will
declare satisfied.

The model then says, **part by part**: what it is, where it lives under invariant 10, what it owns,
and what it must never know of the domain.

**The most uncomfortable fact in the file, and it belongs to this phase**: invariant 10 is called
*« the frame does not name the domain »*. It has been binding since L09, it is cited in three lot
entries, and **its subject — the frame — has never been modelled.** A rule was written about an
object before the object was defined.

### 2.b The instrument nothing has — B-142, assigned here on 2026-08-29

**Three instruments measure this interface and all three compare it to what already exists**:
`IMPLEMENTATION.md` § THE OBJECTIVE counts pages and modules, `frontend-backend-demands.md`
compares the maquette's contract against the running backend, `audit_design_coverage.py` compares
design documents against tests. **None reads `product-intent.md`**, the only document saying what
the product must BE. A capability the constitution requires, that neither the maquette nor the
backend has, is invisible to every gate in this repository — which is how three dictated sections
went a month unnoticed.

**It is this phase's because of what the arm needs, not because of when it fits.** A guard that
checks « every DOIT clause names a surface » needs a **declared mapping from each clause to the
surface serving it**, and a mapping is a design decision rather than a grep. This phase is already
modelling what a surface is; the mapping is a by-product of that subject rather than an errand
beside it.

**Two traps, both already paid for here.** Seeding the mapping from what exists today certifies the
status quo — the vocabulary file did exactly that and let twenty-five French words in with the rest.
And a clause that names no surface must be REFUSED with its reason readable, not counted in a
printed figure nobody compares: a number that is printed and not read is how a control drifted by
seven inside the pull request that introduced it.

### 3. The plan reworked — and the agent decides

With the model drawn, **every lot from L11 to L14 is re-read against it** and the plan says what it
becomes: **unchanged · re-cut · replaced**. No lot left unmentioned — a silence reads as
« unchanged », and that is how a false plan is inherited.

If the model implies conversions, **declared lots carry them**, with their order and their
dependencies. The lesson of L14 and of the drawer finding is the same: **a debt with no named owner
is a debt nobody pays, and it reappears in the last lot.**

---

## The scheduling argument, handed over rather than inherited

Before the mandate was widened, the steward had written that L10-ter should run **after L10-bis and
before L11**. The operator has since given that decision to the agent. **The reasoning is recorded
here so it can be weighed, and it is released in full — including the right to conclude
otherwise.**

- **Not before L10-bis**, because L10-bis draws no surface — it repairs what is seen and what
  measures — so it prejudges nothing, and it produces what a survey needs: instruments that do not
  lie.
- **Before L11**, because L11's objective is *« service worker, offline shell, queued mutations »*
  and **its own « Where it lives » line calls them FRAME, not feature**. Designing a frame after
  building its offline behaviour is the order reversed. L12 follows with view transitions, and a
  transition between two pages is an assertion about what PERSISTS between them.

**Verify it rather than inherit it.** Two reasons to distrust it: the steward did not measure how
many surfaces the engine still draws — ten unread `innerHTML` writes, re-derived — and **that number can change
the answer**. And a scheduling decision taken from reading two lot entries is not a decision taken
from a model. The agent will have the model; the steward did not.

---

## What it does not do

- **No implementation**, no surface conversion, however small, however « illustrative ».
- **No backend work.** What is missing is recorded as a demand (D7). Note: the demand register is
  COMPUTED from OpenAPI paths and **is structurally blind to the WebSocket** — that is B-153, open.
  The stream's demands are hand-written in
  `docs/reference/frontend-backend-demands-stream.md`.
- **It does not relitigate settled arbitrations** — D1 to D11, invariants 1 to 10, the status
  removed from the plan, the oracle NOT widened (B-061: it measures elements, the limit is in D8).
  § 7.1 allows amendment; the burden of proof is on it.
- **It does not touch the dying engine**, by addition or otherwise: it READS it. D5 allows only
  subtraction, and subtraction belongs to lots.

---

## Its « Done when »

A design phase with no measurable criterion is a mood. These are its:

1. **Every surface the engine still draws is named in an inventory a command re-derives**, and the
   command is in the document.
2. **The model of the frame is written, part by part**, each saying where it lives under invariant
   10, what it owns, and what it does not know of the domain.
3. **« As close to a mobile application as possible » is a list of testable properties**, each with
   the instrument that will read it — even if that instrument does not exist yet.
4. **Every lot from L11 to L14 carries, in the plan, what the model does to it**: unchanged, re-cut
   or replaced. No silences.
5. **The where and the when are written**, with their reason, in `frontend-architecture.md` — order
   and dependencies — and in `IMPLEMENTATION.md` for progress. **No conversion promised to a lot
   that does not name it.**
6. **The questions belonging to the operator are asked separately**, in one list, each settleable
   without re-reading the rest.
7. **The register carries what the phase found, written DURING it.** L08 merged with twenty findings
   that lived only in a commit message; it took another wave to recover them.

---

## The tension the steward could not settle

The method says **« the maquette is modified first »**. But this phase implements nothing. Either it
stays documentary and its model waits for a lot to exist, or it draws in the maquette — **and
drawing in the maquette is implementation under another name.**

**The steward's opinion, and it is only an opinion**: documentary, with **STRUCTURE** mock-ups — the
parts, their boundaries, what they own — and not rendering mock-ups. The rendering is already
validated by the operator (mission of 2026-08-19: *« what is already in the maquette is VALIDATED,
do not relitigate it »*). What is missing is not an image; it is a model.

If the agent concludes otherwise, it says why and has the operator settle it before drawing.

---

## The text that lands in the plan

To be inserted in `frontend-architecture.md`, § 1, beside the line declaring the semantic scroll
index — worded so § 0 does not reach it:

```markdown
**L10-ter — the application template.** A design phase whose deliverable is this file rather than
any code: an inventory, computed rather than kept by hand, of every surface the dying engine still
draws; a model of the application's frame, part by part, each saying where it lives under invariant
10; the PWA's « as close to a mobile application as possible » restated as testable properties; and
every lot from L11 to L14 re-read against that model and marked unchanged, re-cut or replaced.
**It is not a lot**: it writes no code, nothing schedules it, and § 0's selection rule must not
reach it. **Where and when its findings are converted is the phase's own to decide**, and it may
amend this file's lots and their order under § 7.1. Invariant 10 has been binding since L09 and its
subject — the frame — has never been modelled; that is the debt this phase pays.
```
