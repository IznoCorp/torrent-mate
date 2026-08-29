# L10-bis — the correction wave between L10 and L11

**Read this first, then `RULE-3-AMENDMENT.md`, then `CLOSURES.md`.** The three documents are the
wave; this one says how to read them and what governs them.

---

## The two documents beside this one, and their order

| Document | What it is |
| --- | --- |
| `RULE-3-AMENDMENT.md` | **The FIRST commit.** The text that replaces rule 3 of `BUGS.md`. |
| `CLOSURES.md` | The twenty-two entries, group by group, each with the instrument that proves its closure. |

**The amendment goes first, and that is not a formality.** It says an entry is closed by an
instrument that RAN, and that **building the missing instrument is part of the work**. Written
after the closures it would measure nothing. Written before, it governs each of them.

**Then Group 0**, the register guard, before everything else — because this wave will write some
twenty closures into a file whose index can today carry two contradictory rows for one identifier.

---

## What you read before acting

1. `CLAUDE.md` — the repository's rules. They outrank everything here, this brief included.
2. `BUGS.md` — the register, its rules, its status vocabulary. It is your ground.
3. `docs/reference/frontend-architecture.md` — **BINDING**. § 2 (D1 to D11), § 3 (the ten
   invariants), § 5 (the method and the gates), § 6 (the traps that cross lots).
4. `docs/reference/product-intent.md` — the constitution. Every web pull request cites the §§ it
   serves.
5. `frontend/maquette/README.md` — the method, the named states, the traps already paid for.
6. `IMPLEMENTATION.md` § « Where the frontend work stands ».

---

## Verify the state; do not believe it

    git fetch origin main -q && git log --oneline origin/main -3
    grep -o "Landed, in order\*\*[^|]*| [^*]\{0,140\}" IMPLEMENTATION.md
    grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md

**These documents are dated against `main` at `f684486c`. The tree moves.** L10 moved twice under
the audit that measured it — #513 then #514 arrived after #512. **Three figures are to be
re-derived before being written, never copied:**

| Figure | Value on 2026-08-29 | How to re-derive it |
| --- | --- | --- |
| The register's next free identifier | **B-220** | the register's highest identifier, +1. **It has already changed three times** for one entry: B-152, B-160, B-219. |
| The B-085 counter | **73** | the `**Total**` row of § *Guards green over what they do not read* |
| The `no-polling` corpus | **127** | `python3 scripts/check-live-relay.py --arm no-polling` — the module's comment still says 124 |

---

## What a correction wave is, and what it is not

**It CLOSES findings.** It opens no lot, converts no surface, relitigates no settled arbitration.
This repository's `-bis` waves — L07-bis, L08-bis — each executed a list arbitrated by the operator
and closed what they could prove.

**It is not a lot**: it takes nobody's turn. L11 remains the next lot, behind L10-ter.

### The § 5 rule that concerns you most, and it is held per COMMIT

> *One kind of change per wave. A conversion proves the rendering did not change; a behaviour
> change proves the behaviour did. Never both in one wave — an edit hidden inside a move is an edit
> nobody can review.*

A correction wave mixes by nature. **So hold the rule at commit level, and the split is clean:**

- **What moves the PAINTING** — B-139 (the three orphan variants), B-138 (the avatar), B-141 (the
  bare elements), B-146 (the scrollbar). **The oracle will move, deliberately, and that is the
  proof.** Every divergence is NAMED before it is accepted.
- **What changes BEHAVIOUR** — E-002 and E-003, the two gestures. Their proof is a hold, not a
  rendering measurement.
- **What touches neither** — the guards, the names, the register, `ci.yml`.

**Never let a painting fix travel inside a behaviour commit.** That is the exact shape § 5 refuses,
and the one a correction wave produces most easily.

---

## The oracle, and this time it is yours

Four entries will move it. **Re-recording the references is possible only on the machine that owns
them**: they carry `"platform": "Darwin/arm64"` and the oracle refuses any cross-platform
comparison. This wave runs there — that is why the operator wanted it there, and B-146 is in the
list for that reason alone.

**An unnamed divergence is a rendering change nobody decided.** Name them all, with their reason,
before accepting anything — the way L06's 47 folds were accepted.

---

## The fresh lessons, and they are days old

**1. B-208 was applied to ONE of the two branches of the same `try`.** The L10 wave named a shape —
*« printed and could fail nothing »* — repaired it on the disagreement path, and **left the same
shape three lines above** on the import-failure path. That is A-1 in your list. **When you repair a
shape, look for it in the rest of the file before closing.**

**2. A mutation that does not fall is information, not a setback.** The rule written for B-140
walked a journey that cannot lose a scroll position; its mutation did not fall, and that is what
found the real defect (B-158). A wave that, faced with a silent mutation, adjusts the mutation
rather than interrogating the rule, is lying to itself.

**3. Register numbers are taken AFTER re-reading `origin/main`, never from memory.** Three
collisions in twenty-four hours on a single entry, by the very office that had recorded that defect
(B-147). Group 0 ships `--next` for exactly this.

**4. A pull-request body written too early becomes false.** #512's announced ten entries and a
counter at 45; the adversarial reviews then found **forty more**, and the real total is 73.
**Write your body last, or revise it before merging.**

**5. The register is written DURING the wave.** L08 merged with twenty findings that lived only in
a commit message; it took another wave to recover them (B-084). It is the most likely failure mode
of this one.

---

## The counter, and it is at 73

**B-085 — « a guard is green because of what it does not read ».** You will write several new
guards. Before believing each one, ask the question that has been paid for seventy-three times:
**« what does this guard NOT read? »**

The shapes already paid for: a floor set at the current value · an empty read passing in silence ·
a corpus enumerated by hand · a hold armed on one of two entry points · a grep reading the markup
without opening the stylesheet · a guard that answers differently per machine · a guard that read
the right file and got a stale answer · **and A-1's: a repair applied to one branch of an `if` and
not the other.**

**Re-count it at your close** — it is the fifth post-merge gesture of § 5.

---

## What you do not do

- **You open no lot** and convert no surface. The drawer and the tab bar are **L10-ter**'s subject;
  your register entry RECORDS them and does not touch them.
- **No backend work.** What is missing is recorded as a demand (D7) — and the demand register is
  structurally blind to the WebSocket, which is B-153.
- **You touch the dying engine only by subtraction** (D5). E-002 installs on the React side against
  the existing node, the way `installFocusManager()` does: **zero lines added to `legacy.js`.**
- **You do not relitigate settled arbitrations** — D1 to D11, invariants 1 to 10, the status removed
  from the plan, the oracle NOT widened (B-061). § 7.1 allows amendment; the burden of proof is
  measured.
- **You do not close what belongs to the operator.** B-031 and B-032 wait for them to confirm.
  B-052, B-053 and B-054 wait for them to arbitrate. You may PRESENT them; you may not close them
  in their place.

---

## The gates

**Per phase**: the oracle, the contract rules, the repository's cheap guards.

**Before merging**: the full suite — `frontend/maquette/harness/run.sh`, **not** the `--contracts`
tier — the `--a11y` tier, and `make check` at zero failures and **zero errors** (an error means
collection crashed and everything after it was skipped).

The script rebuilds and re-copies the prototype first: the harness reads a MANUAL copy at
`/tmp/tm-refonte/wrapped.html`, and a stale one measures the previous build in silence.

**Every rule lands with its mutation, seen red and restored**, at the moment it is written, never
after.

---

## How you deliver

One branch, one pull request, **title and body in English**, adversarial review before merging,
squash merge.

**Write your « In flight » row in `IMPLEMENTATION.md` when the pull request opens**, not after the
merge. L10 is the first wave in five to have done it at the right moment.

**The version bumps** — this wave touches `scripts/`, `frontend/maquette/design/src` and
`.github/workflows/`. The `no-version-bump` label does not apply.

**Cite the constitution's §§ your work serves.** §8 (nothing in silence) for the gestures, §15 for
everything touching the maquette.

**The post-merge gestures** are in § 5 and the fifth is re-counting B-085. The « In flight » row
goes back to *none* and « Landed, in order » does not move: **a correction wave is not a lot.** Your
trace goes in the « Between L10 and L11 » row, the way L07-bis and L08-bis did.

---

## One last thing

Twenty-two entries is more than L07-bis's thirteen. **This wave's temptation will be to close
quickly what closes easily and leave the instruments for last.** That is exactly what the rule 3
amendment forbids, and the reason it is your first commit: **the absent instrument IS the work**,
and eight entries of this register stayed open for months behind a sentence written in good faith —
*« not fixed here, it needs its own X »*.

If you must cut, cut whole entries and say which. **Never cut the proof of an entry you close.**
