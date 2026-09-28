# L18 — Accounts, rights and Plex identity (§ 17) · PLAN

Design: `docs/features/maquette-l18/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L18 — §17, accounts, rights and Plex identity` (its « Where it lives » and « Done when » lines).

**Written 2026-09-27 on `46806a88d`; re-measured and re-cut 2026-09-27 (this amendment) on `825fdeaad`** — the
merge of L16's re-drawing (#623) and L17's design and plan (#617) into this branch, both now LANDED. **L22b has
NOT landed** (`feat/maquette-l22b`, still building); a figure about a file it creates or moves is taken from ITS
plan, and the phase that reads it re-takes the figure at the moment it opens — the head will have moved again.

**Amended per DESIGN.md's own header**: the operator's rulings of 2026-09-27 (round 8, round 9 — organisation
rulings 20–23 — the auditor's coherence round M1–M9, round 10) and the steward's triage of the coherence audit
(`review-archive/coherence-2026-09-27.md` § C). **Every OPEN question of the first drawing is RULED** (DESIGN §
7.2); none is read here as still open. **Phase numbers are integers throughout (auditor's order 38) — no `-bis` /
`-ter` suffix survives this amendment**, per **F51** and **F68** (a new phase's number is bound against the
highest across this branch's own head AND every open branch running beside it — L22b's, checked at each phase's
own opening, not assumed from this table).

---

## THE PHASES CHAIN. THEY DO NOT PAUSE.

**The operator arbitrates the SCOPE, never the cadence.** A phase that finishes goes straight into the next one.
Unchanged from the first drawing — repeated because the chat compacts and this file does not.

**Self-check, at the end of every phase:** « Am I about to report instead of continuing? » If yes, the next phase
exists, and none of the STOPs below is the reason, **continue**. The only permitted halts:

- **STOP A** — the oracle diverging on a state the phase did not name (DESIGN § 4.1). The oracle draws Admin's
  application and is blind to what another role cannot see.
- **STOP B** — the pull request.
- **STOP D** — a measurement that contradicts a home this plan decided. The phase re-takes its own figures before
  moving anything; a figure that no longer supports the home is reported to the steward with the command, never
  improvised past. **Known already**: phase 6 and phase 15 (an act the rights table of DESIGN § 1.2 misclassifies:
  reported, never reclassified); phase 7 (what L22b and L16 left in `app/navigation.ts` and the menu button's
  mount, re-taken since L22b has not landed); phase 31 (the escalation guard's own measure — DESIGN § 3.9 records
  reading A chosen at ≈ 8–10 points; if phase 31's opening measure disagrees, the phase reports the figure and
  falls back to reading B per round 9 Q14's own instruction, with no new question).

**No STOP C remains** — the first drawing's seven OPEN questions were STOPs of a kind (« reads a question, does not
choose »); DESIGN § 7.2 rules all seven plus L17's OPEN 1, so no phase below reads an unruled question.

Anything believed necessary outside the contract: STOP and ask the steward first.

---

## The rule that governs every phase

Unchanged from the first drawing: **rule first, seen RED, then the move, then the same rule green with its holds
counted.** **A right is proved on BOTH sides and separately** — a rule proving only one side is refused by review.

**Commit BEFORE every mutation**, `scripts/mutate.sh <file> <expression> <rule…>`.

**The numbers R-L18-a … z, plus R-L18-l-bis, are LABELS, not rule numbers.** Phase 3 re-takes
`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against **both** `origin/main` and
the open head of any branch running beside this one (F68 — L22b's, at the moment phase 3 opens) and binds every
label to a number then.

**The identities are INVENTED, ROLES not per-account toggles** (DESIGN § 2.2): `seeds/accounts.json` carries
`x-unseeded` rows; readable only while a named state turns a dial; the resting maquette is Admin's (`izno`,
`account.json`) and no phase may move it without naming the state (R-L18-a).

**Every heavy run is wrapped in the machine's mutex** — `sh scripts/heavy.sh --class browser|test|rule l18
<command>`, no `HEAVY_LOCK=` override — announced to the steward one line before, one line after (« done, exit
N »). Output to a FILE, exit code read in the same tool call, never `| tail -N` on a long gate.

**Never `cd` into `frontend/maquette/design/src`.** Documents added BY FILE. No `git stash`, ever. A renamed
identifier goes through `scripts/rename-identifiers.py`, its diff re-read and the harness suite re-run as the
oracle outside the tool.

---

## Points, and the mean

**A phase carries at most 15 points at its opening** (measures 11, 19). Same scale as L22's and the first
drawing's:

| Thing | Points |
| --- | ---: |
| a line **edited or deleted** in a site | 1 per 5 |
| a line **written new** | 1 per 10 |
| a file moved, or deleted | 1 · ½ |
| a new rule with its mutation(s) | 3 |
| a rule file re-aimed · one id swapped | 1 · ½ |
| a new named state (re-using a seed) · (needing a new seed row) | 1 · 2 |
| a contract operation edited · declared new | 1 · 2 |
| a mock handler re-answered · a new route | 1 · 2 |
| a sentence rewritten | 1 |
| a documentation row (the close) | 1 |

**Every figure below is a STRUCTURAL RE-ESTIMATE against DESIGN.md's own new scope**, on this same scale — as the
first drawing's own figures were, before any of L18's code existed. **The phase's implementer re-takes the
literal, command-based measure at its own opening** (as every lot's plan requires); a figure here that the tree
no longer supports is reported, never trusted blind.

### The re-cut, phase by phase — why it changed

**F28 and F30 split the first drawing's single phase 4 (« the refusal, one guard », already at its 15-point
ceiling for 29 writes) into THREE**: the guard mechanism, the now-larger set of write sites (`library.delete` /
`.rescrape` split, `trackers.control`, the staging writes, `setAcquisitionPause` — F28), and the READ side that
had no phase at all (F30). **F31 makes the model's rights table grow** (one row split into three: `trackers.view`
/ `system.view` / `configuration.view`) but the model stays ONE phase — a table growing by rows, not a mechanism
growing in kind. **F46 deletes the first drawing's phase 10** (« the accounts can be read »): the reassign
chooser's read is now a NARROW read implied by holding `acquisition.reassign` itself, folded into the reassign
offer phase, never a door of its own. **Round 10 Q6 (pause) roughly doubles the quality phase's shape**, split
into two. **Ruling 23 turns the ceiling from a boolean into a per-instance list**, splitting the mechanism from
its seeds. **F47 gives the gate's password disclosure its own phase**, as its own fix asks in so many words.
**Ruling 20 adds a roles editor Comptes never had** (the first drawing assumed three fixed roles), splitting the
Comptes-contract phase into accounts and roles, and the rights-change phase into a role's own rights and the
escalation-guarded assignment (round 9 Q14's own measured phase). **F25 re-prices L17's media block at ≈ 27
points, cut into two.**

| # | Phase | What it lands | Rules | Points |
| ---: | --- | --- | --- | ---: |
| 1 | [The contract](phase-01-contract.md) | `readAccount` re-shaped; `signInWithPlex`, `reassignRequester` (keyed card+follow), `setAcquisitionQuality`, `setAcquisitionPause` declared; `grabForFollow` re-aimed per F42 (`takeQueued` retired by L22b phase 33, already declares `403`); `Follow`/`QueueCard` gain `requesters: AccountId[]` (F27); register regenerated — opening measure re-taken at phase open | — | 14 |
| 2 | [The identities in the mock](phase-02-identities-in-the-mock.md) | `seeds/accounts.json` — six seed ROLES, not per-account options (DESIGN § 2.2); `MockDials` with `setForbiddenWrites(list)` replacing `setCeiling(bool)`; resting maquette proved whole | a | 14 |
| 3 | [The model](phase-03-the-model.md) | `features/account/rights.ts` — role → rights over the full 18-row table (DESIGN § 1.2), Admin's bypass, Default's seed, the unit table | b | 15 |
| 4 | [The refusal — the guard mechanism](phase-04-the-refusal-guard-mechanism.md) | `route()` names a right; one guard in the mock; the original write families (acquisition, pipeline, configuration, accounts) named | c | 14 |
| 5 | [The refusal — the new write families](phase-05-the-refusal-new-writes.md) | `library.delete`/`.rescrape`, `trackers.control`, the staging writes (F28), `setAcquisitionPause` swept into the same guard | c (extended) | 10 |
| 6 | [The refusal — the read side](phase-06-the-refusal-reads.md) | every gated read (`/api/system`, `/api/maintenance`, `/api/trackers`, `/api/config`) answers `403` for a non-holder (F30) | c (extended) | 9 |
| 7 | [The bar, composed by rights](phase-07-the-bar-by-rights.md) | a right on the navigation table's row; Découvrir's row (round 8 Q20); the bar and menu badge filtered by the model; a role with no page routes to `/no-access`; the entry-page rule (round 10 Q7) wired | d, e | 15 |
| 8 | [The drawer and the address, by rights](phase-08-the-drawer-and-the-address-by-rights.md) | every drawer entry drawn, MARKED not absent for a non-holder (F29); a cold address and an in-page link into a gated page draw the reserved form (F32) | e (extended), y | 9 |
| 9 | [The reserved place explains itself](phase-09-the-reserved-place-explains-itself.md) | a place not held says what it is, that this account lacks it, and who grants it by default — **unconditional now** (F29, was conditional on OPEN 3) | f | 15 |
| 10 | [The lists are the account's](phase-10-the-lists-are-the-accounts.md) | the acquisition reads answer the dialled identity's subset, or everyone's read-only with `see.others`; every count agrees, never counting another's cards (F33) | g | 15 |
| 11 | [Tabs by rights, the section absent, the viewer's memory](phase-11-tabs-by-rights-and-the-section-absent.md) | Acquisition's THREE tabs composed by rights (Découvrir left the section at L22b); a `see.others`-only identity gets tab content with no `+` (F33); the section absent for neither right; the remembered tab falls back | x, h (d read again) | 13 |
| 12 | [The reassign gesture — the offer](phase-12-reassign-the-offer.md) | the chooser panel and its verb; OPEN 5 = A (card's and follow's panel); the chooser's own narrow read (F46, folds in the first drawing's deleted phase 10); filtered to accounts that SEE the card (M9) | i | 15 |
| 13 | [The reassign gesture — the answer moves](phase-13-reassign-the-answer-moves.md) | the reassignment answered, keyed for card AND follow (F27); the card changes hands, the line updates, plural where more requesters remain | j | 9 |
| 14 | [Own tunnel, read-only on the others](phase-14-own-tunnel-read-only-on-the-others.md) | the tunnel's acts offered where the caller is AMONG the requesters (F27, membership not single ownership), absent on the others' | k | 14 |
| 15 | [The quality profile of an acquisition](phase-15-the-quality-of-an-acquisition.md) | the quality screen writes a per-acquisition, per-requester override; only role-holding requesters enter « highest wins » | l | 14 |
| 16 | [The pause preference of an acquisition](phase-16-the-pause-of-an-acquisition.md) | `setAcquisitionPause`; « paused » holds only when every right-holding requester asked for it (round 10 Q6 precision) | l-bis | 10 |
| 17 | [The Médiathèque and the sheet are read-only](phase-17-the-library-is-read-only.md) | the selection, delete and « Re-scraper » gated on the SPLIT rights (`library.delete`/`.rescrape`) | n | 9 |
| 18 | [« Suivre » and the request](phase-18-suivre-and-the-request.md) | the follow offered by `acquisition.request`/`.follow`; **OPEN 6 = A firm, no guest branch to build** | m | 6 |
| 19 | [The forbidden-writes list](phase-19-the-forbidden-writes-list.md) | the settings-only `readOnly` flag dies; the model reads a served LIST and subtracts it from every role, Admin included; `readConfigurationStatus` drops `readOnly` (F66) | o, b (extended) | 15 |
| 20 | [The per-instance seeds and the ceiling's reason](phase-20-per-instance-seeds-and-the-reason.md) | `:8711`-today's list (every write) and preprod's list (`library.delete` alone, ruling 23); the banner and Profil name the forbidden right(s) specifically | o (extended) | 8 |
| 21 | [Profil is the connected account](phase-21-profil-sheds-the-others.md) | « Les autres comptes » leaves Profil; the role's NAME is shown, never compared | p | 11 |
| 22 | [Profil says what it can do](phase-22-profil-says-what-it-can-do.md) | « Ce que ce compte peut faire »: the rights held, the reasons for the ones lacking (including a partial forbidden-writes list) | z | 15 |
| 23 | [The gate offers Plex, primary](phase-23-the-gate-offers-plex.md) | « Se connecter avec Plex » first, in its own marker pair; the password form collapsed behind a disclosure; the host's password page unchanged | q | 15 |
| 24 | [The gate's password disclosure](phase-24-the-gates-password-disclosure.md) | closed by default; opens by hand; auto-opens when Plex is unreachable (F47); `auth.password` gates who it admits | q (extended) | 10 |
| 25 | [The gate's outcomes](phase-25-the-gates-outcomes.md) | a non-holder's password refused with its reason; a rights-less (Default-only) Plex user lands on the Médiathèque | r | 15 |
| 26 | [« Comptes » — the contract and mocks: accounts](phase-26-comptes-contract-accounts.md) | `createAccount`, `updateAccount`, the last-Admin and last-`auth.password`-holder guards (F2) | — (R-L18-c re-swept) | 11 |
| 27 | [« Comptes » — the contract and mocks: roles](phase-27-comptes-contract-roles.md) | role create / rename / set-rights operations, ordinary roles only — never Default's name, never Admin | — (R-L18-c re-swept) | 10 |
| 28 | [« Comptes » exists](phase-28-comptes-exists.md) | a first-level menu page, `/accounts`, grouped `configuration` — **OPEN 1 = B firm, no rubric variant to draw** | s | 15 |
| 29 | [« Comptes » — the roster](phase-29-comptes-the-roster.md) | one row per account — name, ROLE, Plex link — from the answer; « sans droits » (Default-only) is a row too | t | 15 |
| 30 | [« Comptes » — a role's own rights](phase-30-comptes-a-roles-rights.md) | a role's rights set from § 1.2's list; the change reaches every account on that role via the stream event on a REAL carrier (F37); last-Admin, last-`auth.password`-holder guards refuse | u | 15 |
| 31 | [« Comptes » — assigning a role, escalated](phase-31-comptes-assigning-a-role.md) | one role per account; a non-Admin manager assigns only a subset of their own role's rights, never touches their own role or an Admin account (round 9 Q14 = A, measured here; M7) | u (extended) | 12 |
| 32 | [« Comptes » — a new account, and the Plex link](phase-32-comptes-a-new-account.md) | the creation form, mandatory e-mail; a matching e-mail links; `auth.password` gates whether the account can sign in without SSO | v | 15 |
| 33 | [The media-sheet block, on the model](phase-33-media-cross-seed-block.md) | the per-tracker cross-seed block drawn fresh (F25, taking over L17's demand C); `media-cross-seed` / `media-cross-seed-hidden` | w | 14 |
| 34 | [The media-sheet block's gate](phase-34-media-cross-seed-gate.md) | gated on `trackers.view`, refused `403`; R-L18-w carries L17's R-L17-b/-k holds; proved on the six seed identities | w (extended) | 13 |
| 35 | [The records of the lot](phase-35-the-records.md) | regions, the oracle, accessibility, the fixture register, the ratchets | — | 10 |
| 36 | [The close](phase-36-the-close.md) | the register, the README, the frame model, the debts, the report; hands over demands M and N (F67) | — | 10 |

**Opening measures (this amendment, 2026-09-27, on `825fdeaad`), each phase's re-estimate**: 14, 14, 15, 14, 10, 9,
15, 9, 15, 15, 13, 15, 9, 14, 14, 10, 9, 6, 15, 8, 11, 15, 15, 10, 15, 11, 10, 15, 15, 15, 12, 15, 14, 13, 10, 10 —
**sum 449 over 36 phases, mean ≈ 12.47, max 15**, none above the 15-point ceiling.

**The first drawing's phase 10 (« the accounts can be read ») is DELETED** — F46 folds its narrow read into the
reassign-offer phase (now phase 12); no phase file survives it, and no citation of the old number is left standing
elsewhere in this document.

### The L18a / L18b cut, restated

**L18a — the model, the refusal, and every surface that READS it (phases 1–20, 254 points over 20 phases, mean ≈
12.7).** At its end the interface is composed by rights for every surface that exists: the bar, the drawer, the
addresses, the lists, the tabs, the reassign gesture, the tunnel, quality, pause, the library, and the
forbidden-writes list — each proved on both sides, on invented identities a named state turns on. Still provable
without the gate and without the accounts surface, because the identity is a mock dial.

**L18b — what says who you are, and who may be (phases 21–36, 195 points over 16 phases, mean ≈ 12.2).** Profil,
the gate's Plex offer and its disclosure, the gate's outcomes, « Comptes » (contract for accounts, contract for
roles, the place, the roster, a role's own rights, assigning a role with its escalation guard, creation), L17's
media block on the model, the records, the close. `DOIT-12` reads `served` only after L18b.

The seam is between phase 20 and phase 21 (one dated line in `IMPLEMENTATION.md` when L18a merges); nothing in
L18b edits a file L18a leaves half-done.

---

## Why thirty-six phases, and what a phase costs

**A phase is a unit of attribution, not a gate.** One commit each (two where the phase says « commit before the
mutation »); the gate is the contracts tier plus the oracle. The full gate runs once, before the pull request
(STOP B). Two rules drove the count, unchanged from the first drawing: **one kind of change per phase**, **the
15-point ceiling** — and this amendment's own re-cut follows both exactly where F28, F30, F25, ruling 20, ruling
23 and round 10 Q6 grew a single phase past 15.

**The contract, the mock's identities, the model, the refusal — in three parts now, not one** (1–6): the MODEL
first, then the guard mechanism, then the write families the model's growth added, then the read side no phase
had before (F30). Nothing reads a right until one exists; nothing offers an act until the call it hangs on can be
refused; nothing that VIEWS a place is left ungated just because writing to it was.

**The frame edits next, said as such** (7, 8; the gate at 23–25). **This lot is NOT the only one after L15 to edit
frame code** (F49 corrects the first drawing's own claim): L22b and L16 both edit `app/` first; this lot re-reads
what they left.

**The lists before the acts** (10 before 12–14): a card must be on the right list before an act on it is offered
or refused. **The reassign chooser needs no door of its own any more** (F46) — its narrow read is the right's own,
folded into phase 12, which is why the first drawing's phase 10 does not survive this cut.

**Quality and pause are now two phases, not one** (15, 16): round 10 Q6 gave pause the same shape as quality,
doubling the surface a single phase would have carried.

**The ceiling is a mechanism, then its seeds** (19, 20): ruling 23 turned a boolean into a per-instance list; the
mechanism (the model reads a list, subtracts it) is one phase, the two instances' own lists and the reason text
are the next.

**The gate in three phases now** (23–25): the offer, its own disclosure (F47 asks for this explicitly), then the
outcomes.

**« Comptes » in seven phases, not five** (26–32): the contract splits into accounts and roles (ruling 20 gave
Comptes a roles editor the first drawing never needed); the rights-change phase splits into a role's own rights
and the escalation-guarded assignment (round 9 Q14's own instruction to MEASURE the escalation at one phase).

**L17's block in two** (33, 34), re-priced by F25 at ≈ 27 points total — too large for one phase at the ceiling.

**The records are their own phase** (35); **the close is last** (36) and hands over M and N (F67).

---

## Gates

Unchanged from the first drawing. **Per phase**: `frontend/maquette/harness/run.sh --contracts` and the oracle,
divergences only where DESIGN § 4.1 names them (D8).

**Before each pull request** (L18a's and L18b's): `make lint`; the full suite, expected no failure; `--a11y` at 0
over the new states; `python3 scripts/harness-hold-counts.py --compare` with `failed` read FIRST; the pre-push
pytest; `check-intent-map.py`, `check-bug-register.py`, `check-docs-cited-paths.py` read by OUTPUT. Each pull
request bumps the version (patch).

**The steward is told BEFORE a full-suite run.** **A right's gate is its two halves**: `check-mock-seeds.py`,
`compare-contracts.py --check`, the sweep over every write AND every gated read at that moment (F28, F30). **A
DRAFT pull request runs no CI.**

---

## What the plan gets wrong, measured

Recorded here as DESIGN § 8 asks. **No file outside `docs/features/maquette-l18/` is edited for it**, except the
one dated line under the L18 heading of `docs/reference/frontend-architecture.md`.

1. **« The gate stays `app/sign-in.tsx` »** — no such file. `app/entry.ts` plus `index.html` markup.
2. **« The drawer's identity block »** — the host's served identity, not the account.
3. **« Behind the served role the backend already exposes »** — the backend serves no account role.
4. **§ 17's blanket read-only staging ceiling is SUPERSEDED, not merely disputed** — ruling 23 makes it a
   per-instance list; phases 19–20 draw the list, not a boolean.
5. **The oracle cannot hold this lot** — it draws Admin's application; DESIGN § 5's rules are the proof.
6. **The first drawing's own claim of being the only lot after L15 to edit frame code is WRONG** — L22b and L16
   both edit `app/` first (F49).
7. **The organisation rulings are cited by number and date** — `docs/reference/operator-method.md`'s committed
   text lands them in a separate, no-version-bump docs PR (steward's C1).

---

## Amended (dated lines)

- **2026-09-27 — this amendment.** Ported the operator's rulings of round 8 (17 L17+L18 questions), round 9 (17
  organisation-and-coherence questions, rulings 20–23), the auditor's decision-coherence round (M1–M9), round 10
  (7 questions), and the steward's triage of the coherence audit (F2, F9+C8 [C8's tunnel-history half routed to
  L22b, not this plan — DESIGN § 7.1], F25, F27–F38, F46, F47, F49, F65–F68, C2 [L18 half — read-gating now
  covered by phases 6 and 9's own reserved-address rule, closing C2's L18 share]). Re-cut from 29 to 36 phases
  (sum 356 → 449, mean 12.3 → 12.47); deleted the first drawing's phase 10 (F46); split phases 4, 15, 17, 20, 22,
  27 of the first drawing where a fix grew them past 15 points; every phase number is now an integer with no
  reading-conditional branch left in the table (F51). L18a/L18b seam restated at phase 20/21 (was 17/18).
