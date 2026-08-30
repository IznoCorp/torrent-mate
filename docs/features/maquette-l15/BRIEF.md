# L15 — The frame

You open **L15**, the first lot L10-ter placed and the one every lot after it depends on. Nothing is
open on it: no design, no plan, no branch. You begin by writing them.

**Your contract is in the plan, not here.** `docs/reference/frontend-architecture.md` § 4, entry
`#### L15 — The frame`, carries the objective, the part-by-part table of what moves where, the four
behaviour changes, the B-142 instrument and the « Done when ». **This brief does not restate it** —
a contract copied into a second file is a contract wrong in one of them. What follows is what the
plan does not say.

---

## What you read before acting

1. `CLAUDE.md` — the repository's rules. They outrank everything here, this brief included.
2. `docs/reference/frontend-architecture.md` — **BINDING**: § 0 (selection), § 2 (D1 to D11), § 3
   (the fifteen invariants), **§ 4's L15 entry — your contract**, § 5 (method and gates), § 6 (the traps
   that cross lots), § 7.1 (how to amend).
3. **`docs/features/maquette-l10-ter/MODEL.md`** — the frame in thirteen parts. **Parts 5, 6, 7 and
   9 are yours.** Each says what it is, where it lives under invariant 10, what it owns, what it
   must not know, and today → target.
4. **`docs/features/maquette-l10-ter/SURVEY.md`** — § 1.1 the inventory command your « Done when »
   re-runs, § 1.2 the nineteen sites by surface, § 2 every node of the frame and who owns it today.
5. `docs/reference/product-intent.md` — the constitution. §8 (nothing in silence) and §20 (the
   tunnel per media) bear on the chrome; every web pull request cites the §§ it serves.
6. `docs/reference/product-intent-map.md` — the 23 clauses, their surface and their verdict. **You
   build the arm that holds it** (B-142).
7. `frontend/maquette/README.md` — the method, the named states, the traps already paid for.
8. `IMPLEMENTATION.md` § « Where the frontend work stands ».

---

## Verify the state; do not believe it

    git fetch origin main -q && git log --oneline origin/main -3
    grep -o "Landed, in order\*\*[^|]*| [^*]\{0,150\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md

**Every figure in the plan and in `MODEL.md` carries the command that produces it. Run them.** They
were right on 2026-08-30 and this repository has watched figures move inside the day they were
written — the L10-ter brief carried three that were already wrong when its agent opened it.

---

## The five things the plan does not tell you

### 1. Four commits are not four repairs — they are the only four behaviour changes in the lot

B-229 (the dialog's rung on the ladder), B-237 (its z-order), B-233 (`theme-color` follows the
theme), B-230 (the viewport fallback removed). **Each lands in its own commit with its own rule,
never inside a conversion commit.**

That is § 5's « one kind of change per wave » held at commit level, and it is not bureaucracy: a
conversion proves the rendering did NOT change, a behaviour change proves it DID. **An edit hidden
inside a move is an edit nobody can review** — and this wave is a very large move.

The oracle is what makes the distinction real. On a conversion commit it must not diverge; on a
behaviour commit it may, and every divergence is **named before it is accepted**.

### 2. The ladder's handler stays in the engine, and that is deliberate

L13 takes it, not you. The drawer and the dialog **register with it** the way the sheet already does
through `window.__panel` — `app/panel-host.ts` is the precedent to copy, and its posture is the
point: **facts cross the seam, markup stays the component's.**

Reaching into the engine to move the ladder early would make L15 a subtraction wave as well as a
conversion wave, which is exactly the mix § 5 refuses.

### 3. Six files are at the ceiling and you may not extend them

`check-frontend-boundaries.py --arm size` names six, and they are two debts, not one. L14's four
surfaces — `features/acquisition/page.tsx`, `features/library/page.tsx`,
`features/media/media-screen.tsx`, `features/arrivals/resolution-screen.tsx` — **L14 owes their
reduction and runs after you.** The engine's two — `engine/legacy.js`, `engine/states.js` — L13
removes, and you touch them only by subtraction (D5). A conversion that grows a grandfathered file turns a promise into a bigger promise.

If a part of the frame has nowhere to go without extending one of the six, that is a finding for
the register and a note for L14 — not a line added.

### 4. B-142's instrument is the deliverable, not the errand

The map exists (`product-intent-map.md`, 23 clauses, verdicts `served` · `served, unproved` ·
`partly` · `to draw` · `outside the interface`). **What does not exist is the arm that refuses a
clause naming no surface**, and it goes in the contracts tier.

Two traps, both already paid for in this repository and both written in `MODEL.md`:

- **Seeding the mapping from what exists today certifies the status quo.** The vocabulary file did
  exactly that and let twenty-four French words in with the rest.
- **A clause with no surface must be REFUSED with its reason readable**, not counted in a printed
  figure nobody compares. A number that is printed and not read is how a control drifted by seven
  inside the pull request that introduced it.

And the arm's own subject must be named by a CI path filter, or it runs in no job:
`tests/scripts/test_ci_filter_covers_the_guards.py` refuses that, and it has already caught an arm
the steward added.

### 5. The counter is at 98, and this lot writes several new instruments

**B-085 — « a guard is green because of what it does not read ».** Before believing each guard you
write, ask the question that has been paid for ninety-eight times: **« what does this NOT read? »**

The shapes already paid for: a floor set at the current value · an empty read passing in silence · a
corpus enumerated by hand · a hold armed on one of two entry points · a grep reading the markup
without opening the stylesheet · a guard answering differently per machine · a guard that read the
right file and got a stale answer · a repair applied to one branch of an `if` and not the other · an
equality where an ordering was meant.

**And the freshest, from L10-ter's own review**: six cited line numbers that pointed past the end of
their file, and counts that included the function's own definition. **Open every proof you cite;
subtract the definition; re-grep every line number last.**

---

## What you do not do

- **You do not open L11, L12 or L19.** The offline shell, the transitions and the ten panel
  producers are theirs. L19 in particular is tempting — the producers are engine `innerHTML` like
  the chrome — and it is not yours.
- **You touch the dying engine only by subtraction** (D5), and the ladder is the named exception
  above: you leave it.
- **No backend work.** What is missing is a demand (D7);
  `docs/reference/backend-demands-architecture.md` already holds the §17/§18/§19/§20 inputs.
- **You do not relitigate settled arbitrations** — D1 to D11, invariants 1 to 15, the operator's
  nine answers in `QUESTIONS.md`. § 7.1 allows amendment and the burden of proof is measured.
- **`docs/features/maquette-l10-ter/` does not archive with you.** § 5 names it exempt: it is the
  frame's model, not a wave's design, and it archives with L13.

---

## The gates

**Per phase**: the oracle, the contract rules, the repository's cheap guards.

**Before merging**: the full suite — `frontend/maquette/harness/run.sh`, **not** the `--contracts`
tier — the `--a11y` tier, and `make check` at zero failures and **zero errors** (an error means
collection crashed and everything after it was skipped).

The script rebuilds and re-copies the prototype first: the harness reads a MANUAL copy at
`/tmp/tm-refonte/wrapped.html`, and a stale one measures the previous build in silence.

**Every rule lands with its mutation, seen red and restored**, at the moment it is written.

**The oracle's references are `Darwin/arm64`-bound.** If you run anywhere else, do not re-record —
hand the gesture back and say so in the pull request.

---

## How you deliver

One branch, one pull request, **title and body in English**, adversarial review before merging,
squash merge. The version bumps.

**Write your « In flight » row when the pull request opens**, not after the merge — and put the
version in it: `scripts/check-implementation-state.py` refuses a row naming a version `main` has
reached, and **cannot see a row that names none** (B-238).

**Cite the constitution's §§ your work serves.**

**The register is written DURING the wave.** L08 merged with twenty findings that lived only in a
commit message; it took another wave to recover them.

---

## One last thing

Every lot after you but L14 depends on this one. L11 caches the chrome — it must be the product's before it
is cached. L12 animates between layers — they must be components before they can be animated. L19
moves the producers into features — they need a host that is not the engine.

**The frame has worked for ten lots without anyone owning it, and that is exactly why nobody
modelled it.** You are converting the part of this application that never broke, which means the
oracle is your only real reviewer on the conversion commits and the four behaviour commits are the
only place anything is allowed to move.
