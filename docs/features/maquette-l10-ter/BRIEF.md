# L10-ter — brief for the agent

**Read this, then `DEFINITION.md`.** You open L10-ter, and nothing is open on it: no survey, no
model, no branch. You begin by writing them.

---

## Who you are

**You are an extension of the frontend implementation steward's office.** Same criteria, same
prerogatives, no more and no less. Your office is `docs/reference/frontend-steward.md` and you read
it first.

What that entails, and these are not formulas:

- **You implement nothing.** Not a line of `frontend/maquette/design/src`, not a guard, not a
  harness hold. You correct DIRECTIVES and you propose.
- **You inherit the office's two written limits**: you cannot certify that a rendering did not move
  — only the oracle says that, on the machine that owns the references — and **your anchor is the
  repository, never a remembered intent**. A figure is measured; it is not cited.
- **You do not settle what belongs to the operator.** An experience decision, a product choice, an
  arbitration between two equally defensible readings: you PUT them, one by one, worded to be
  answered without re-reading your whole document.

## What you decide

The operator widened the mandate on 2026-08-29: **you decide where the model is converted into
work, when, and in what form** — a new lot, several, a re-cut of existing lots, a different order.
§ 7.1 says how to amend `frontend-architecture.md`; the burden of proof is on you and it is
measured.

**One rule follows you throughout, and it cost dearly**: *when a decision changes, the directives
change IN THE SAME MOVE. What loses its subject is removed, not kept « just in case ».* On
2026-08-28 the commit removing the per-lot status from the plan left **five sentences** describing
the removed token — one of them a paragraph below that very rule, and a guard was reading them.
That is B-150.

---

## What you read before acting

1. `CLAUDE.md` — the repository's rules. They outrank everything, this brief included.
2. `docs/reference/frontend-steward.md` — your office, and its two limits.
3. `docs/reference/product-intent.md` — **the constitution, dictated by the operator, BINDING**.
   §15 (the maquette IS the product), §8 (nothing in silence), and §17/§18/§19, which have no lot.
4. `docs/reference/frontend-architecture.md` — **BINDING**, in full.
5. `frontend/maquette/README.md` — the method, the named states, the traps already paid for.
6. `IMPLEMENTATION.md` § « Where the frontend work stands ».
7. `BUGS.md` — the register, and rule 1: *reported = written down*.
8. `docs/reference/web-ui.md` — the three environments, auth, the WebSocket protocol.
9. `docs/features/maquette-l10-ter/DEFINITION.md` — your subject, your « Done when », and the
   scheduling argument handed to you as evidence rather than as a conclusion.

---

## Verify the state; do not believe it

    git fetch origin main -q && git log --oneline origin/main -3
    grep -o "Landed, in order\*\*[^|]*| [^*]\{0,140\}" IMPLEMENTATION.md
    grep -n "^#### L" docs/reference/frontend-architecture.md
    grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md

**The plan carries no per-lot status since 2026-08-28.** It carries ORDER and DEPENDENCIES;
`IMPLEMENTATION.md` carries progress, in a « Landed, in order » row. Cross the two. Do not look for
a `LANDED` in the plan: there is none, deliberately — a lot marked `NOT STARTED` after merging had
made § 0 elect the lot that had just landed.

---

## Two lessons that are days old

**1. Register numbers are taken AFTER re-reading `origin/main`, never from memory.** The drawer
finding was numbered B-152, then B-160, then B-219, and it is **B-220** — **four collisions in a
day and a half on one entry**, by the office that had recorded that very defect (B-147). L10's three
pull requests carried the register from B-151 to B-218, and two steward pull requests took B-219 and
B-227 after that. **Verify the next free number before writing it**, and the verification is one
command, because L10-bis shipped it:

    python3 scripts/check-bug-register.py --next

It reads `BUGS.md` and `BUGS-CLOSED.md` **on the branch it runs on**, and says so: a number taken on
another branch is invisible to it. Re-read `origin/main` before you write one down.

**2. A mutation that does not fall is information.** The rule written for B-140 walked a journey
that cannot lose a scroll position; its mutation stayed green, and that is what found the real
defect (B-158).

---

## The counter, and it is at 93

**B-085 — « a guard is green because of what it does not read ».** You write no guard, but **you
will read many**, and your survey depends on what they report. Before every figure, ask the
question that has been paid for ninety-three times: **« what does this instrument NOT read? »**

**Re-derive it rather than trust this line**: `grep -o '| \*\*Total\*\* | \*\*[0-9]*\*\*' BUGS.md`.
It read 73 when this brief was written on 2026-08-29 and 93 by the end of the same day — L10-bis
added twenty, eleven at its close and nine more from repairing its own adversarial review.

The shapes already paid for: a floor set at the current value · an empty read passing in silence · a
corpus enumerated by hand · a hold armed on one of two entry points · a grep reading the markup
without opening the stylesheet · a guard answering differently per machine · a guard that read the
right file and got a stale answer · a repair applied to one branch of an `if` and not the other ·
**and an equality where an ordering was meant**, which is how `check-implementation-state.py`'s
first version reported clean over the exact defect it had been written for.

**And the one your subject contains whole: two instruments that count an engine's size and never
its surfaces.**

---

## How you deliver

One branch, one pull request, **title and body in English**, adversarial review before merging,
squash merge. `no-version-bump` if and only if the diff touches prose alone.

Write your row in `IMPLEMENTATION.md` **when the pull request opens**, not after the merge.

**Cite the constitution's §§ your work serves.**

---

## One last thing

What is asked of you is not to draw one more screen. **It is to name the object everything else has
rested on for ten lots without anyone defining it.** The shell exists, it works, and that is exactly
what made it invisible: nobody models what has never broken.

The risk of this work is not choosing the wrong model. **It is producing one so complete that nobody
knows which end to convert first** — and a plan nobody executes is a plan that does not exist. What
you deliver must be openable by an agent who has not read your reasoning, and tell them what to do
on Monday morning.
