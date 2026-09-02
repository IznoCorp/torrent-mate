# L14 — The surfaces that outgrew their file

You open **L14**, the head of Phase 5 and the lot the operator pulled forward on 2026-08-30 so that
L19 works in files already cut: the four feature surfaces over the 400-line ceiling come back under
it by decomposition, nothing on the screen moves, and two register entries that only these files can
repair are repaired. Nothing is open on it: no design, no plan, no branch. You begin by writing them.

**Your contract is in the plan, not here.** `docs/reference/frontend-architecture.md` § 4, entry
`#### L14 — The surfaces that outgrew their file`, carries the objective, the four files, why the lot
exists at all (a promise that expired unpaid under a stale word), where an extraction lives
(invariant 10), the two entries it owns, and the « Done when ». **This brief does not restate it** —
a contract copied into a second file is a contract wrong in one of them. What follows is what the
plan does not say.

---

## What you read before acting

1. `CLAUDE.md` — the repository's rules. They outrank everything here, this brief included. Read
   § Language twice: it changed on 2026-09-01.
2. `docs/reference/documentation-model.md` — **BINDING since 2026-09-01, and new**: which version a
   document may describe, where it lives, how history is cited. Your wave's folder is deleted at its
   post-merge gesture and cited by commit; there is no `docs/archive/` any more and the guard refuses
   one coming back.
3. `docs/reference/frontend-architecture.md` — **BINDING**: § 0 (selection), § 2 — D5 (the engine is
   subtracted from, never edited), D8 (what the oracle proves, its descendants clause, and the
   2026-09-01 line on what a RULE may read that the oracle never does), D9 (where motion lives; a
   proven library beats re-coding) —, § 3 invariants 6 (the 400-line ceiling), 7 (`ui/` never
   imports a feature; two features never import each other), 10 (the frame does not name the
   domain), 11 (every change lands with a rule that bites), **§ 4's L14 entry — your contract**, § 5
   (method, gates, the post-merge gesture as it is written NOW, the instruments' debts block), § 6
   (the traps — read the L12 rows), § 7.1 (how to amend).
4. `docs/reference/frame-model.md` — the frame's thirteen parts under invariant 10 and the 30
   properties; **P29** (no layout shift) and **P24** (the windowed list, `ui/virtual-rows.tsx`) live in
   two of your four files and must survive the cut. `docs/reference/frame-survey.md` — what the engine
   still draws, so you know which markup in your files is React's and which is the engine's.
5. `docs/reference/product-intent.md` — the constitution. §12 (the phone first), §13 (real data,
   never an assertion about data in flight — that is B-283's clause), §16 (the back gesture); every
   web pull request cites the §§ it serves.
6. `git show 79ccebe2:docs/archive/features/maquette-l12/REPORT.md` — L12's report, read from
   history: the thirty instruments that lied, § 6f and § 6g on what three review rounds returned and
   where (inside the repairs), and the reduce/decode/one-owner traps of transitions your files carry.
7. `docs/reference/frontend-steward.md` § « One machine, one harness at a time » and its last two
   paragraphs — the steward audits on this machine and launches your adversarial reviewers;
   coordinate by message before running `run.sh`, the oracle, `mutate.sh` or
   `harness-hold-counts.py`.
8. `frontend/maquette/README.md` — the method, the named states, the traps already paid for.
9. `IMPLEMENTATION.md` § « Where the frontend work stands » — and `BUGS.md`, the L12 block
   (B-271 to B-291) and the two entries you own, B-247 and B-283.

---

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    grep -o "Landed, in order\*\*[^|]*| [^*]\{0,150\}" IMPLEMENTATION.md
    grep -o "| \*\*Next\*\*[^|]*| [^.]\{0,80\}" IMPLEMENTATION.md
    python3 scripts/check-bug-register.py --next
    grep -o "| \*\*Total\*\* | \*\*[0-9]*\*\*" BUGS.md
    python3 scripts/check-frontend-boundaries.py --arm size | grep -E "at or over|features/"
    for f in features/acquisition/page.tsx features/media/media-screen.tsx features/library/page.tsx features/arrivals/resolution-screen.tsx; do printf '%-45s %s\n' "$f" "$(grep -cve '^\s*$' frontend/maquette/design/src/$f)"; done
    grep -rn -E '^(export )?function Icon\b' --include='*.tsx' frontend/maquette/design/src
    python3 scripts/check-frame-domain.py | tail -1

**Every figure in the plan carries the command that produces it. Run them.** Measured on
2026-09-01 at `81ad0492`, for you to re-run: `acquisition/page.tsx` **756**, `media-screen.tsx`
**796**, `library/page.tsx` **613** — exactly the ceiling L12 was held to, zero slack —,
`resolution-screen.tsx` **430**; six files at or over 400 counting the engine's two; the frame's
domain floors `ui/ 0, lib/ 18, app/ 129`; the counter at **174**; `--next` says **B-295**.

---

## The eight things the plan does not tell you

### 1. `Icon` is not written twice — it is written four times, and one of them is already right

`ui/icon.tsx` exports `Icon` (line 13). Three features keep a local `function Icon({ paths,
strokeWidth })` anyway: `features/media/media-screen.tsx:68`, `features/arrivals/resolution-screen.tsx:61`,
`features/releases/releases-screen.tsx:27`. The plan's sentence — « a component two features draw is
vocabulary, and vocabulary lives in `ui/` » — is already obeyed by the file in `ui/`; what is owed is
the three deletions, each proved by the oracle (the icon draws the same) and by `grep -rn "function
Icon"` reading **one**. Check the signatures agree before you swap; if they do not, the difference is a
drawing decision and it is written beside the class that applies it, not papered over.

### 2. The size arm reads `.ts`, `.tsx` and `.js` — and it refuses a grandfather entry for a file back under

`scripts/check-frontend-boundaries.py` holds invariant 6 at 400 non-blank lines on every `.ts`,
`.tsx` and `.js` under `design/src` (not `.css`, not the generated `contract/types.d.ts`). Its
`GRANDFATHERED` table names your four files with the label « L14 — decomposition ». **The arm refuses
two states**: a file at or over the ceiling with no entry, and **an entry for a file that is back
under it**. So each file you bring under 400 has its entry removed in the SAME commit, and the
« Done when » reads through `--arm size`: only `engine/legacy.js` and `engine/states.js` remain,
labelled L13. Two of the files carry a second history worth knowing: `library/page.tsx` sat at 613
because L12's phase 8 was gated at « ≤ 613 » — substitution only — and `app/shell.tsx` is at 398 of
400, not yours and not grandfathered: a line added to it fails the arm.

### 3. This is a CONVERSION lot, and the oracle is its whole proof — with two known blind spots

Every extraction is « proved by the oracle, whose whole subject is that nothing moved on the
screen »: zero divergence over its 2 958 measurements at every phase, like L15 and L11 before you.
D8 names what it cannot see and what you must hold with a rule instead: a **pseudo-element** or a
**child node** that carries a function (its descendants clause — the dialog's paragraph colour
and the danger action's contrast were the lived examples, held by R116 since L12). And L12's
newest trap: **node identity**. An extraction that re-keys a component, moves a `key`, or splits a
tree so that React replaces nodes on a store write is invisible to the oracle (it measures at rest)
and it is exactly B-247 — see § 4. The transitions L12 declared on your surfaces (`screen-banner`,
`screen-body` on the media screen; `view-transition-name` is a name on ONE element) must survive
the cut too: R115's holds read them by name, and a name that lands on two elements is dropped by
the browser without a word — L12 measured that once.

### 4. B-247's surface half is yours, and it needs a rule that does not exist yet

`BUGS.md` B-247: a store write between `pointerdown` and `click` replaces a page's DOM nodes and
the tap is lost — no event, no error. L15 held the CHROME's node identity (its P2) and scoped it to
the chrome by name; **a page's rows have the same property and nothing reads it**. The repair is in
the surfaces — a page whose nodes keep identity across a store write — and the entry says where the
hold goes: `harness/persistence.py`. L12's `virtual-rows.tsx` already keeps a `Map<index, Element>`
so a windowed row survives a scroll (R117 holds a row's identity across a downward scroll and the
gallery's ORDER across a scroll down and back up — the second exists because the first was green
over rows shuffled on the way up); your decomposition must not lose that, and the rule you write must FALL on a component that
re-keys — mutate it, see it red, restore. L19 owes the same for the producers it moves; you owe it
for the four files you cut.

### 5. B-283 is one line in `media-screen.tsx`, and the maquette cannot show you the defect

While the media sheet's read is in flight, the screen prints its unknown parts as ANSWERS
(`synopsisUnknown`, `castUnknown`, `noTrailer`, « unknown » seasons) — §13 refuses an assertion
about data still in flight. The operator's decision of 2026-08-31 (« A généralisée + amorçage »)
says skeletons for the unknown parts only. **The maquette's placeholder is the engine's COMPLETE
sheet**, so no field is ever missing during priming here — measured, 8 children at 120 ms and 8 at
2 400 ms. Your rule drives a PARTIAL placeholder (the mock layer's own knob,
`window.__mocks.setDefaultLatency` and a projection you thin on purpose) and reads
`[data-part="no-info"]` absent while `status === "pending"`. A rule that reads the full placeholder
is green over the defect it is written for: B-085's species, the one L12 paid thirty times.

### 6. Where an extraction lives, measured by a guard, not by taste

Invariant 10 and `scripts/check-frame-domain.py`: the frame — `ui/`, `lib/`, `app/` — does not
name the domain, and its floors today are **`ui/ 0`, `lib/ 18`, `app/ 129`**, held from going up.
A component that names a medium, a season, an acquisition stays in its feature folder (the plan's
rule); a component two features draw and that names nothing goes to `ui/` — and `ui/` at zero
domain words is the reading that proves it. Invariant 7 is the other edge: `ui/` never imports a
feature, and two features never import each other; a tab extracted from `acquisition/page.tsx`
that the library page also wants is a `ui/` component or it is two components.

### 7. The documentation model changed on 2026-09-01, and your deliverables follow it

- Your design, plan and report live in `docs/features/maquette-l14/`, force-added
  (`git add -f <file>` — `docs/` is ignored globally, B-251), in **English**; harness and maquette
  comments carry no date, no lot, no phase (B-287 counts 263 of them and refuses more).
- **There is no archive.** At your post-merge gesture your folder is `git rm -r`'d and every living
  citation of a file in it becomes `` `path@<squash sha>` `` — the squash commit is the one that
  holds the folder for good, which is why the step is the gesture's and never your branch's
  (§ 5, gesture four). `scripts/check-docs-cited-paths.py` holds all of it in three arms: a cited path
  answers `git ls-files`, a `path@sha` is held by that commit, nothing tracked under
  `docs/archive/`, `docs/production/` equals its manifest.
- `docs/production/` describes the version in production and is frozen: you do not add to it, and
  you do not cite it as the next version's truth — `docs/reference/` is the only authority on what
  you build.
- The state is one row in `IMPLEMENTATION.md`; write your « In flight » row when the pull request
  opens (pull request number first, then the version).

### 8. The counter is at 174, and its freshest shapes are L12's thirty

**B-085 — « a guard is green because of what it does not read »**, and its criterion is written
in the table now: an instrument whose READING does not decide what it claims to decide, in either
sign. L12's shapes, beyond the older list: a rule written for the exact defect it then missed,
blinded by its own stated principle (« the group, not the pixels ») · a hold turned tautology by
the repair beside it · a delay set by hand that a drawn duration outlived, three times · an entry
animation that starts AFTER the view transition, so the same element is drawn twice · a
discriminator that answers the same on both sides (a race that always loses) · `getKeyframes()`
synthesising the implicit keyframe, so a hold on it cannot fall · a moment stamped BEFORE the read
it times · a probe that truncated its own evidence · a paragraph that is not an arm (B-291: the
dangling pointer one file over from the sentence that names the species). Before believing each
rule you write, ask what it does NOT read, and what it would still read if the behaviour were gone.

---

## What you do not do

- **You do not move a pixel.** Every part's rendering is validated (mission of 2026-08-19); a
  conversion lot's oracle is green at zero divergence or the divergence is a defect.
- **You do not move a producer or its engine-side gesture callers** (L19), nor the ladder's handler
  (L13 — B-275 and B-290 are L13's), nor extend `app/shell.tsx` (398 of 400) or the engine's two.
- **You do not touch `docs/production/`**, and you do not re-create `docs/archive/`.
- **You do not adopt a library without its D9 row** — and you do not re-code what a reliable
  library already does (rule 2, reversed 2026-08-31).
- **No backend work** (D7). B-283's repair is a line in the screen, not a projection change.
- **You do not relitigate settled arbitrations** — D1 to D11, invariants 1 to 15, the operator's
  answers of 2026-08-30 (`git show 79ccebe2:docs/features/maquette-l10-ter/QUESTIONS.md` — never archived, deleted by docs-cleanup),
  §18/§19 as dictated.
- **You do not stop between phases.** Phases chain without pause — the operator arbitrates the
  SCOPE, never the cadence; write that constraint at the head of your plan's INDEX as L12 did, with
  its self-check. The only stops are the ones your plan names: an anomaly that needs a sign-off, or
  a gate you cannot repair inside the plan.

---

## The gates

**Per phase**: the oracle (green at zero divergence — this is a conversion lot), the contract rules,
the repository's cheap guards — `run.sh --contracts` prints how many.

**Before merging**: the full suite — `frontend/maquette/harness/run.sh`, not the `--contracts`
tier — the `--a11y` tier, `scripts/harness-hold-counts.py --compare` (no rule loses a hold by
accident; every movement written down; the recorder writes a baseline over a FAILED rule without a
word — B-291 — so read `failed` in the totals before you trust a record), and `make check` at zero
failures and **zero errors**.

**The harness is one per machine** (`served_copy.py` is its lock and its stamp). It rebuilds and
re-copies the prototype under a lock; a rule that falls while another session held the harness is
re-run alone before it is read as anything — and a re-run that removes the load the failure needed
is said in the same breath as the verdict (B-277).

**Every rule lands with its mutation, seen red and restored**, at the moment it is written —
`scripts/mutate.sh` refuses a dirty tree and restores from the index (it cannot judge a GUARD,
B-273: mutate a guard by hand and read its exit code).

---

## How you deliver

One branch `feat/maquette-l14`, one pull request, **title and body in English**, then squash
merge. The version bumps.

**The adversarial review is independent of you, or it is not adversarial** — measured on L12: the
author's serialised lenses found 4, four independent readers found ~40, and the curve ran
40 → 10 → 3 → 0 over three rounds each aimed at the previous round's REPAIRS. When your pull request
is ready, you message the steward (`ListAgents` names the session); the steward launches the
readers on a worktree pinned at your head and relays their findings; you alone write. Plan for
more than one round.

**Write your « In flight » row when the pull request opens** — pull request number first, then
the version: `scripts/check-implementation-state.py` holds the row by both.

**The register is written DURING the wave**, and your report lands in your folder with your design
and plan before the pull request is marked ready — the post-merge gesture deletes the folder and
cites it, so a report that is not in git by then is a report nobody can read.

**Cite the constitution's §§ your work serves.**

---

## One last thing

L12 filed B-283 rather than fixing it because the line it needs is in a file no wave before you
may extend. Two lots wrote beside your four files without touching them. You are the one that
opens them — and the oracle, green at every step, is the whole of what says you closed them the
same.
