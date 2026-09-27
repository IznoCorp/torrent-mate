# L18 — Accounts, rights and Plex identity (§ 17) · PLAN

Design: `docs/features/maquette-l18/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L18 — §17, accounts, rights and Plex identity` (its « Where it lives » and « Done when » lines).

**Written 2026-09-27 on `origin/main` at `46806a88d`, before the lot opens (after L17).** Every phase file carries an **opening
measure** (auditor's order 42) taken on THAT head, by the commands a STOP D would run on this tree. **Three lots change the tree
this one reads and none has landed** — L22 (Arrivées dies, the card gains a requester line), L16 (the Trackers row), L17 (the
administrator's media-sheet block, on its open PR branch). A figure about a file one of them creates is taken from THEIR
plans and the phase says « does not exist on this head »; the lot's implementer re-takes each phase's figures at the moment that
phase opens (the head will have moved) and reports a difference before moving anything.

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into the next one. Stopping to
announce « phase N done » is the failure mode L12, L14, L19, L20 and L21 each wrote this paragraph to prevent, and it is
written HERE because the chat gets compacted and this file does not.

**Self-check, at the end of every phase, before anything else:** « Am I about to report instead of continuing? » If the answer is
yes, the next phase exists, and none of the STOPs below is the reason, **continue**. The only permitted halts:

- **STOP A** — the oracle diverging on a state the phase did not name (DESIGN § 4.1). **The oracle draws the Operator's
  application and is blind to what another account cannot see** (DESIGN § 4.1): a green oracle proves the Operator's surface is
  unmoved and nothing about a right — the rules of DESIGN § 5 are the proof.
- **STOP B** — the pull request.
- **STOP D** — a measurement that contradicts a home the design decided. The phase re-takes its own figures before it moves
  anything; a figure that no longer supports the home is reported to the steward with the command, and the phase does not
  improvise a new home. **Five are already known**: phase 4 and phase 13 (an act the rights table of DESIGN § 1.2 misclassifies:
  reported, never reclassified), phase 5 (what L22 and L16 left in `app/navigation.ts` and the menu button's mount), phase 9 (what
  L22's default-tab rule stores) and phase 27 (the state of L17's OPEN 1).

**The seven OPEN questions (DESIGN § 7.2) are NOT ruled; none is a STOP and none waits — the plan is drawn so that each reading
is a complete drawing with its cost.** The phases that read one say which and what each reading costs them: **OPEN 1** (where
accounts are managed — a Réglages rubric or a first-level drawer entry) in phase 23, which carries one variant per reading;
**OPEN 2** (how the gate offers Plex) in phase 20, reading B cut into 20 and 20-bis; **OPEN 3** (absent or reserved-and-explained)
in phase 6 (shared) and phase 7 (drawn ONLY under B); **OPEN 4** (who holds the right that opens Trackers and Système) in phase 5
(no cost either way — the model of phase 3 carries it as a parameter); **OPEN 5** (where the reassign gesture starts) in phase 11;
**OPEN 6** (what the guest's request is) in phases 9 and 15; **OPEN 7** (a bar of one place) in phase 9. **L17's OPEN 1**, unruled
on this head, is read by phase 27.

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

**Rule first, seen RED, then the move, then the same rule green with its holds counted.** Where a surface does not exist on
`main`, the rule is red for that reason and needs no mutation. Where a phase reverses a behaviour that exists, the rule is written
against the assertion as it stands and the mutation comes after the move: break it on purpose, confirm the rule falls and NAMES the
right defect, restore. **A right is proved on BOTH sides and separately** (§ 17): a rule that reads only the absent offer, or only
the refused call, is refused by the review — it proves the interface or the security, never both.

**Commit BEFORE every mutation**, and mutate with `scripts/mutate.sh <file> <expression> <rule…>` — by hand leaves the served copy
of the PREVIOUS build in place (B-303). It cannot judge a GUARD (B-273): a guard's exit code is read by hand.

**The numbers R-L18-a … z are LABELS, not rule numbers.** Phase 2 re-takes
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against `origin/main` at the moment it runs (**R223**
on this head; L22 and L16 will have moved it) and binds every label to a number then, writing the mapping into the report. A number
chosen from this file without re-measuring is a collision.

**The identities are INVENTED, and the plan keeps that true in every phase**: `seeds/accounts.json` and `seeds/invented-requests.json`
carry `x-unseeded` rows in the fixture register; they are readable **only while a named state turns a dial**; no real row is
re-attributed; **the resting maquette is the Operator's and no phase may move it without naming the state** (DESIGN § 2.2, R-L18-a).

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule l18 <command>` — with no
`HEAVY_LOCK=` override. A run holding the lock is announced to the steward in one line before it starts and one after (« done, exit
N »). Output to a FILE, exit code read in the same tool call, **never `| tail -N` on a long gate**. Kill what you start, prove it
with `ps`.

**Never `cd` into `frontend/maquette/design/src`** (B-384): absolute paths from the worktree root. **Documents are added BY FILE**:
`git add docs/features/maquette-l18/<name>.md` (B-304 — a directory add once swept `node_modules` into a commit). **No `git stash`**
in this repository, ever. **A renamed identifier goes through `scripts/rename-identifiers.py`**, never by hand and never by an
ad-hoc regex; its read-back is skipped for `--values` runs and for Python files, so the diff is re-read and the harness suite
re-run — an oracle OUTSIDE the tool.

---

## Points, and the mean (measures 11 and 19)

**A phase carries at most 15 points at its opening** (measure 11: the context budget; measure 19: the cadre). The scale is declared
once, here, so every figure in a phase file is reproducible — **the same scale as L22's**:

| Thing | Points |
| --- | ---: |
| a line **edited or deleted** in a site | 1 per 5 |
| a line **written new** | 1 per 10 |
| a file moved, or a file deleted | 1 · ½ |
| a new rule with its mutation(s) | 3 |
| a rule file re-aimed (its walk changes) · one id swapped | 1 · ½ |
| a new named state (re-using a seed) · (needing a new seed row) | 1 · 2 |
| a contract operation edited · declared new | 1 · 2 |
| a mock handler re-answered · a new route | 1 · 2 |
| a sentence rewritten (its key and readers) | 1 |
| a documentation row (the close) | 1 |

**The pre-cut clause.** A phase whose re-measure at its opening exceeds 15 is CUT at that opening, never begun; the plan's numbers
after it shift by one and the steward is told. **Eleven phases are drawn AT the ceiling** (4, 7, 8, 9, 11, 17, 20, 21, 24, 25, 26)
and each says what to cut. Three phases carry a reading whose cost exceeds 15 and are cut in the reading, not at the opening: phase
15 under OPEN 6 = B (15 + 15-bis), phase 20 under OPEN 2 = B (20 + 20-bis), phase 27 under L17's OPEN 1 = B (27 + 27-bis).

| # | Phase | What it lands | Rules | Points |
| ---: | --- | --- | --- | ---: |
| 1 | [The contract](phase-01-contract.md) | `readAccount` re-shaped (role, options, Plex link, ceiling); `signInWithPlex`, `reassignRequester` and `setAcquisitionQuality` declared; `takeQueued` gains its `403`; the register regenerated | — | 12 |
| 2 | [The identities in the mock](phase-02-identities-in-the-mock.md) | `seeds/accounts.json` (five invented accounts), four dials on `MockDials`, `readAccount` answering the dialled identity; the resting maquette proved whole | a | 14 |
| 3 | [The model](phase-03-the-model.md) | `features/account/rights.ts` — one function from the account's answer to its rights — and its door; the unit table | b | 13 |
| 4 | [The refusal side — one guard](phase-04-the-refusal-one-guard.md) | `route()` names a right; one guard in the mock answers `403` for an identity that lacks it; 29 write sites name theirs | c | 15 |
| 5 | [The bar, composed by rights](phase-05-the-bar-by-rights.md) | a right on the navigation table's row; the bar and the menu button's badge filtered by the model; the bar's shares read at each count | d, e | 12 |
| 6 | [The drawer and the address, by rights](phase-06-the-drawer-and-the-address-by-rights.md) | the drawer's entries filtered by the model; a cold address the account may not open never draws the page | e (extended), y | 8 |
| 7 | [The reserved place explains itself — ONLY if OPEN 3 is ruled B](phase-07-the-reserved-place-explains-itself.md) | a place the account does not hold says that it exists, that this account does not hold it, and who can open it — **conditional** | f | 15 |
| 8 | [The lists are the account's](phase-08-the-lists-are-the-accounts.md) | the acquisition reads answer the dialled identity's subset — its own, or all with the option; every count agrees | g | 15 |
| 9 | [Tabs by rights, the section absent, the viewer's memory](phase-09-tabs-by-rights-and-the-section-absent.md) | Acquisition's tabs composed by the model; the section absent for an account that can neither request nor see; the default tab falls back; a bar of one place | x, h (d read again) | 15 |
| 10 | [The accounts can be read](phase-10-the-accounts-can-be-read.md) | `readAccounts` declared and answered; the guard's table gains its row; a door for the roster and the chooser | — (R-L18-c re-swept) | 6 |
| 11 | [The reassign gesture — the offer](phase-11-reassign-the-offer.md) | the chooser panel and its verb; the entry point (OPEN 5); the Operator alone is offered it | i | 15 |
| 12 | [The reassign gesture — the answer moves](phase-12-reassign-the-answer-moves.md) | the reassignment is answered; the card changes hands, its line and its account's list | j | 8 |
| 13 | [Own tunnel, read-only on the others](phase-13-own-tunnel-read-only-on-the-others.md) | the tunnel's acts offered on a card one requested, absent on the others' with the reason said; the guard resolves the target's requester | k | 14 |
| 14 | [The quality profile of an acquisition](phase-14-the-quality-of-an-acquisition.md) | the quality screen writes a per-acquisition choice through its operation; the offer follows the right and the option | l | 14 |
| 15 | [« Suivre » and the request](phase-15-suivre-and-the-request.md) | the follow offered by role; the guest's act as OPEN 6 is ruled | m | 6 (A: 6 / B: 17) |
| 16 | [The Médiathèque and the sheet are read-only, but for the Operator](phase-16-the-library-is-read-only.md) | the selection, the delete and « Re-scraper » absent for every account but the Operator | n | 9 |
| 17 | [The ceiling absorbs the staging role](phase-17-the-ceiling-absorbs-the-role.md) | the settings-only read-only flag dies; the model's ceiling is what every write reads; the ceiling says why | o, b (extended) | 15 |
| 18 | [Profil is the connected account](phase-18-profil-sheds-the-others.md) | « Les autres comptes » leaves Profil; the role is named | p | 11 |
| 19 | [Profil says what the account can do](phase-19-profil-says-what-it-can-do.md) | « Ce que ce compte peut faire »: the rights held, and the reasons for the ones that would surprise | z | 14 |
| 20 | [The gate offers Plex](phase-20-the-gate-offers-plex.md) | « Se connecter avec Plex » beside the password, in its own marker pair; the host's password page unchanged | q | 15 |
| 21 | [The gate's outcomes](phase-21-the-gates-outcomes.md) | a non-Operator's password is refused with its reason; Plex unreachable is said; a rights-less Plex user lands on the library | r | 15 |
| 22 | [« Comptes » — the contract and the mocks](phase-22-comptes-the-contract-and-the-mocks.md) | `createAccount` and `updateAccount` declared and answered; the last Operator cannot be demoted | — (R-L18-c re-swept) | 11 |
| 23 | [« Comptes » exists — where OPEN 1 says](phase-23-comptes-exists.md) | the surface has its place — a rubric of Réglages OR a first-level drawer entry — empty, and closed to every account but the Operator | s | 11 (A: 11 / B: 15) |
| 24 | [« Comptes » — the roster](phase-24-comptes-the-roster.md) | one row per account — name, role, Plex link, options — from the answer; « sans droits » is a row too | t | 15 |
| 25 | [« Comptes » — an account's rights](phase-25-comptes-an-accounts-rights.md) | the role and the two options set on an account; the change reaches the affected account on the stream; the last Operator is protected | u | 15 |
| 26 | [« Comptes » — a new account, and the Plex link](phase-26-comptes-a-new-account.md) | the creation form with its mandatory e-mail; an e-mail matching a Plex account links; a non-Operator cannot use a password | v | 15 |
| 27 | [L17's administrator block, on the model](phase-27-l17s-block-on-the-model.md) | the per-tracker cross-seed block of the media sheet gated on the model, on six identities | w | 9 (A: 9 / B: 22) |
| 28 | [The records of the lot](phase-28-the-records.md) | regions, the oracle, accessibility, the fixture register, the ratchets | — | 10 |
| 29 | [The close](phase-29-the-close.md) | the register, the README, the frame model, the debts, the report | — | 9 |

**Opening measures (2026-09-27, on `46806a88d`), each phase file's own head, at the LOWEST reading of every OPEN question**: 12, 14, 13, 15,
12, 8, 15, 15, 15, 6, 15, 8, 14, 14, 6, 9, 15, 11, 14, 15, 15, 11, 11, 15, 15, 15, 9, 10, 9 — **sum 356 over 29 phases, mean ≈ 12.3,
max 15**, none above measure 19's 15-point ceiling, none cut at this writing. **With OPEN 3 = A, phase 7 is deleted: 341 over 28,
mean ≈ 12.2.** What the other readings add: OPEN 6 = B **+11** (phase 15: 6 → 17, cut into 10 + 7), OPEN 2 = B **+5** (phase 20-bis),
OPEN 1 = B **+4** (phase 23: 11 → 15), L17's OPEN 1 = B **+13** (phase 27: 9 → 22, cut into 13 + 9). **The largest plan, every
costlier reading ruled, is 356 + 11 + 5 + 4 + 13 = 389.**

### Does L18 need a cut into sub-lots? — Yes, at phase 17

L22 was cut at ≈ 300 points into L22a / L22b. **L18 is larger (341 to 389 points), so it is cut, and the seam is drawn where it
is clean:**

- **L18a — the model, the refusal, and every surface that READS it** (phases 1–17, **191 points over 16 phases** with OPEN 3 = A,
  206 over 17 with B). At its end the interface is composed by rights for every surface that exists: the bar, the drawer, the
  addresses, the lists, the tunnel, the quality choice, the library, the ceiling — each proved on both sides, on invented
  identities that a named state turns on. **It is provable without the gate and without the accounts surface**, because the
  identity is a mock dial.
- **L18b — what says who you are, and who may be** (phases 18–29, **150 points over 12 phases**): Profil, the gate's Plex, the
  gate's outcomes, « Comptes » (contract, place, roster, rights, creation), L17's block on the model, the records, the close.
  **`DOIT-12` reads `served` only after L18b**; L18a alone leaves the gate and the management of accounts undrawn.

The seam is between phase 17 and phase 18 (one dated line in `IMPLEMENTATION.md` when L18a merges); nothing in L18b edits a file
L18a leaves half-done.

---

## Why twenty-nine phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** Each is ONE commit (two where the phase says « commit before the mutation »), and
its gate is the contracts tier plus the oracle — minutes, not the full suite. The full gate runs ONCE, before the pull request
(STOP B). The count follows from two rules: **one kind of change per phase** and **the 15-point ceiling**.

**The contract, then the mock's identities, then the model, then the refusal** (1–4) — **the MODEL first**, the architecture's
words, and the contract with it: nothing reads a right until one exists, and nothing offers an act until the call it hangs on can be
refused. **The refusal is one guard in the mock** (phase 4): NE-DOIT-PAS-7 kept in the mock as in the engine — thirty sites that
name their right, one place that decides.

**The frame edits come next and are said as such** (5, 6; the gate at 20 and 21): the navigation table's right, the bar's and the
drawer's filters, the address guard, the menu button's badge. **L18 is the only lot after L15 that edits FRAME code**, and the plan
says so instead of discovering it.

**The lists before the acts** (8 before 11–14): a card must be on the right list before an act on it is offered or refused. **The
accounts can be read** (10) **before the chooser needs them** (11), and the reassign gesture is TWO phases — the offer, then the
answer that moves the card (11, 12) — because an offer with no answer would be a foot that does nothing.

**The ceiling after the surfaces that carry writes** (17): it kills a flag that 24 lines in 12 files read and makes every earlier
gate read one thing. **Profil after the ceiling** (18, 19) so its list can state the ceiling as a reason.

**The gate in two phases** (20, 21): the offer, then the outcomes; the second reads the account after the sign-in, which the frame
model says is a feature's to read, never the gate's.

**« Comptes » is built the way L22 built its fourth tab**: the contract and the mocks first (22), the place next — empty, so the
OPEN 1 placement is decided by what the operator SAW (23) — then the roster, the rights and the creation, each its own kind of
change (24–26). **L17's block on the model** (27) comes after the model has six identities to prove it on. **The records are their
own phase** (28): the memory the tooling keeps of a surface is not the surface. **The close is last** (29) and re-reads the map
and the register rather than trusting what the phases claimed.

---

## Gates

**Per phase**: the shared-lock `frontend/maquette/harness/run.sh --contracts` — the contract rules AND the repository's cheap
guards, the script prints how many of each — and the oracle, with divergences ONLY on the states DESIGN § 4.1 names for that
phase, each accepted with its written reason (D8). Every other state at zero, or it is **STOP A**.

**Before each pull request** (L18a's and L18b's; the maquette wave's own gate — a maquette wave does not run `make check`; CI's `test`
job is the authority, `frontend-steward.md` measure 19): `make lint`; the full suite (`frontend/maquette/harness/run.sh`, not the
`--contracts` tier), expected no failure; the `--a11y` tier at 0 over the new states; `python3 scripts/harness-hold-counts.py
--compare` with **`failed` read FIRST** (B-291 — the baseline is NOT re-recorded while a rule is failing) and every movement written
down; the pre-push pytest; `python3 scripts/check-intent-map.py`, `python3 scripts/check-bug-register.py` and
`python3 scripts/check-docs-cited-paths.py` read by OUTPUT, not by exit code (B-346). Each pull request bumps the version (patch)
— the `version-bump` job enforces it — because it changes `frontend/maquette/design/src/`.

**The steward is told BEFORE a full-suite run.** The harness is one per machine — `served_copy.py` is its lock and its stamp (B-256)
— and a rule that falls while another session held it is re-run alone before it is read, with the re-run's loss of load said in the
same breath (B-277, B-307).

**A right's gate is its two halves**: `python3 scripts/check-mock-seeds.py` (the invented rows), `python3 scripts/compare-contracts.py
--check` (the three artefacts), and the sweep R-L18-c over every write of the contract at that moment. **The « In flight » row is
written when the pull request opens** — pull request number first, then the version; `scripts/check-implementation-state.py` holds the
row by both. **A DRAFT pull request runs no CI** (`CLAUDE.md` § Commit Convention): open it READY, or add `run-ci-on-draft` and read
the run that label dispatches — never both in one breath.

---

## What the plan gets wrong, measured

Recorded here as DESIGN § 8 asks, and written in full in the design. **No file outside `docs/features/maquette-l18/` is edited for
it, except the one dated line under the L18 heading of `docs/reference/frontend-architecture.md`** — the steward amends the plan and
the operator amends the constitution and the map.

1. **« The gate stays `app/sign-in.tsx` »** — there is no such file. The gate's logic is `app/entry.ts` (399 lines) and its markup
   `frontend/maquette/design/index.html` lines 429–480, extracted by `frontend/maquette/serve.py` as the design host's own
   password page. Phases 20 and 21 edit those, and the Plex block takes a marker pair of its own so the host's extraction is
   untouched.
2. **« The drawer's identity block »** — the drawer's block is the host's served identity (branch, commit, dirty mark:
   `lib/served-identity.ts`), not the account. The account's identity is the header avatar and its menu
   (`features/account/panel-account.ts`). This lot edits the drawer's ENTRIES (phase 6), not an identity block.
3. **« Behind the served role the backend already exposes »** (L17's « Dictated »): the backend serves no account role — its
   `/api/auth/me` answers `{username}` — only the instance's deployment role. Phase 1 declares the role on `readAccount`.
4. **§ 17 says the staging ceiling makes every write read-only; the engine's A18 policy leaves acquisition and decision writes
   open** (`tests/unit/web/routes/test_staging_write_policy.py`). The constitution wins and the engine follows the interface:
   DESIGN § 6.2 row N proposes it, and states its consequence — a mutating journey can no longer be walked on the staging instance.
5. **Read-only already exists in the maquette, in miniature, and it is the second mechanism § 17 point 3 forbids**: one flag, read
   by 24 lines in 12 files, set by one named state, connected to nothing served. Phase 17 kills it.
6. **The oracle cannot hold this lot** (DESIGN § 4.1): it draws the Operator's application. Every right is held by a rule on both
   sides, or by nobody.
7. **The organisation rulings of 2026-09-26 (10–15) are cited « organisation ruling N (2026-09-26,
   `docs/reference/operator-method.md`) »**; that file's committed text has no entry of that date yet — they land in a later docs
   PR.

---

## Amended (dated lines)

*None yet.* A ruling on one of the seven OPEN questions, or a re-measure at a phase's opening, adds a dated line here.
