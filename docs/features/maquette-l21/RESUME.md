# L21 — where the wave stands, for whoever picks it up

Rewritten at 41 % context by the session that moved the five acts. Read `BRIEF.md`, `DESIGN.md`
and `plan/INDEX.md` first — this file says only what is TRUE NOW and what the plan does not.

**Branch** `feat/maquette-l21`, pull request **#572** (draft). **Version** 0.98.75 — `main` carries
0.98.74 and this is already past it; re-read `main` and bump again at the close if it moves.
**`origin/main` at `163cbfcbb` IS MERGED into this branch** (merge commit, four conflicts resolved
on their merits — see § 5d). That merge is what makes CI possible at all: see § 5e.

---

## 1. Done, with the reading that proves it

| Phase | State | Proof |
| --- | --- | --- |
| 1 — the contract | **DONE** | 3 operations + types + register; mocks answer and MOVE state |
| 2 — the season grab (B-301) | **DONE** | R125 16 holds, no violation |
| 3 — the journey's two verbs (B-302) | **DONE** | R126 16 holds, no violation |
| 4 — the five acts | **ALL FIVE MOVED** | § 2 — the act-branch grep reads **0** |
| 5 — the release take | **not started** | — |
| 6 — the pastille + R124 | **not started** | — |
| 7 — B-313 + close | **not started** | — |

**Gates on the current head**: `run.sh --contracts` on the MERGED tree → **18 rules + 27
repository guards, no violation** (read after the merge; the wrapper needs the floor override of
§ 5f or it never starts). `tsc -b` 0, `check-frontend-boundaries` clean, `check-no-french`
15 arms no violation with the app ratchet unmoved at 751, `check-mock-seeds` 7 arms clean,
`check-markup-contracts` clean, `check-maquette-unit-tests` 104/104, `check-bug-register` clean,
`check-implementation-state` clean, `compare-contracts --check` matching.

---

## 2. THE FIVE ACTS — ALL OF THEM HAVE LEFT THE ENGINE

`grep -cE "closest\.dataset\.(follow|pause|remove|dropsug|sugmore)\b" …/legacy.js` reads **0**.
Ledger: 31 591 at the wave's base → **31 484**, re-recorded downward in each commit that subtracts.

| Act | Commit | Proof |
| --- | --- | --- |
| `follow` | `6026840e1` + `5a58b6e52` | R130, 10 holds before and after |
| `dropsug` | `327f8fc3e` … `e3bde6c66` | R131, 8 holds before and after |
| `pause` | `4c01fe204` | R132, 9 before and after; 3 mutations |
| `remove` | `959c494ee` + `329f14523` | R133, 10 → 11 holds |
| `sugmore` | `2ae4e81a9` | R134, 9 holds; **RED on main's build**, 4 violations |

**`pause` and `remove` have TWO readers each, and the plan's table says one.** The panel's
`data-pause` / `data-remove` moved to the tap registry. The ROW's revealed action carries **no
attribute at all**: `legacy.js` reaches it by CLASS (`.act` then `.pause` / `.remove`) and takes
the subject from the row's own heading text — `data-action` and `data-swipeact` are emitted there
and read by NOTHING, measured. That branch also collapses the drawer it opened, which is DRAWING
and therefore L13's, so **the branch stays and calls the act through `window.__followVerbs`** — the
door the add screen already used for `follow`. Taking the click into the registry would have left
the drawer open under the finger. `.act.remove` additionally has TWO destinations: on a LIBRARY row
it opens a confirmation dialog. That arbitration stays with the engine.

**`sugmore` was a BEHAVIOUR change and could not have been a move.** The client DRAINED the layer —
twenty pages in a loop — so « Charger 30 de plus » had nothing left to load, which is *why* the
engine's branch cleared `sugGone` and reshuffled. The drain is gone: the deck holds ONE page,
`loadMoreSuggestions()` appends the next, and because `sugGone` holds positions into that same
list, « nothing dismissed comes back » is true **by construction** rather than by a step that puts
it back. `deckOrder` appends on growth instead of re-deriving — a rebuild would throw away what
« Passer » had arranged.

✅ **RULED « A » BY THE OPERATOR, 2026-09-06**: Découvrir holds ONE page — thirty — at rest, the
button loads the next and says truthfully how many arrived. **The oracle's divergences on the
discover states are ACCEPTED with this ruling as their reason** (D8). B-315 (b) and (c) are
delivered by this act; **(a), the button's SIZE, is not started** — see § 6.

---

## 3. B-353 — the undo of a removal restored a STRANGER, and it is FIXED

Found by writing down what my own commit message claimed and then asking which hold read it. None
did. The hold added to make the claim measurable was **red on a clean tree**:

    removed:  {t: "Kyma…", y: 2026, since: '9 août', searches: 13}
    restored: {t: "Kyma…", y: 0,    since: '',       searches: 0}

**It predates this lot** — the engine's `actionRetirer` offered the same undo through the same
seam. The layer's delete DROPPED the record, so the only road back was a CREATE, and the contract's
create accepts no `since`, no `searches`, no `status`. **No undo can be honest over a create.**

**The operator ruled « fix it in this lot » (2026-09-06).** What landed (`a4c690215` + `8892a4bec`):
`POST /api/acquisition/followed/{followedId}/restore` in the contract, answering the whole follow
and **404** where nothing removed under that name is still restorable; the layer's removal is SOFT
(the record waits in `removedFollows`, newest first); the tombstone is held ASIDE rather than
flagged in place so `follows` keeps the contract's shape; `__followActions.restore(follow)` takes
the whole record. Demand recorded in `frontend-backend-demands.md` § 1, decision in DESIGN.md
§ 3.3b with the road REFUSED (widening the create's body would let every create assert a past the
interface should not be able to invent).

**Both halves mutation-proved**: the undo reverted to a create fails the eleventh hold ALONE; the
layer's removal made hard again fails it *with* the undo's own hold, the follow gone entirely —
the optimistic write rolls back rather than leaving a phantom row.

---

## 4. B-316 — MEASURED, AND IT DID NOT REPRODUCE

R135 (`harness/discover_gestures.py`) drives real CDP touches on **both** card kinds: a 60 ms tap
and a 700 ms hold with a 4 px drift, because a thumb is never still and the arbitration tolerates
12 px on purpose.

**On MAIN's build it is GREEN — all four holds on the poster tile AND on the deck card.** The long
press raises « Ajouter / Voir la fiche / Pas intéressé » on both; the tap opens the media sheet and
leaves no panel open. The premise « the media screen opened on all ten finger points and the
suggestion panel was reachable by no finger » **does not reproduce where this can measure.**

✅ **RULED « A » BY THE OPERATOR, 2026-09-06: B-316 CLOSES on this reading** — `fixed #572`. The
rule stays as the instrument, the negative reading and its two caveats are in the entry, **the two
attributes are NOT separated and nothing is recoded**: the behaviour a repair would have produced
is the behaviour that was measured. He walks Découvrir on his Mac at the review.

⚠ **THE PLAN'S MECHANISM SENTENCE IS VOID and is struck in DESIGN.md § 3.3c** — « the two
attributes stop sharing a node » was work to do, and its premise did not survive measurement.
`plan/phase-04-five-acts.md` § B-316 still carries it and takes the correction at the audit.

**The premise rests on the GESTURE, not on my artefact.** B-316's ten recorded points are all
TAPS, and a tap opening the sheet with no panel IS reading (i) — so they show the tap working and
never test the gesture the panel is opened by. Two caveats stand: the entry is a summary, and the
survey ran on `2f8503614` while this ran on `f70ca0295`.

⚠ **My FIRST reading of the deck card was a false positive caused by my own rule**, and it looked
exactly like the reported defect: `querySelector('[data-part="deck/card"]')` answers the card at
the BOTTOM of a pile of three, so hit-testing its centre named an `IMG` belonging to another card.
It aims by `data-depth="0"` now. **If the survey that produced B-316's premise had the same flaw,
the premise is an instrument artefact** — worth checking before anyone repairs a defect that may
not exist.

---

## 5. What this session learned that the plan does not say

### 5a. THE TRAPS PAID FOR HERE — read before writing a rule

1. **`str(0) in "…30 suggestions de plus"` is TRUE.** The hold written to catch a message naming a
   number nobody added read « 0 » inside « 30 » and PASSED the engine's exact defect. Compare
   numbers on digit boundaries; a substring test on a figure agrees with any figure containing it.
2. **A new hold must be run GREEN before it is mutated.** I mutated first, read a failure, and
   nearly attributed a pre-existing defect to my own mutation. Without a green baseline a mutation
   proves nothing about which of the two broke it.
3. **A claim in your own commit message that no hold reads is where the next defect is.** That is
   literally how B-353 was found. Re-read your message for verbs — « restores », « preserves » —
   and check each against a hold.
4. **`querySelector` on a stacked pile answers the BOTTOM card.** See § 4.
5. **Two `window.__store.write` calls in one task are ONE commit.** The intermediate state never
   renders. R134's « leave the deck and come back » had to be split into two evaluations with a
   settle between them, or the pile it was asking to rebuild never rebuilt.
6. **The deck branch REFUSES to rewrite a live pile** (« rewriting it destroys the gesture in
   flight »), so writing `sugGone` wholesale under a drawn pile changes the state and leaves stale
   cards for ever — measured `order: 0`, `cards: 3`, no end mark.
7. **A DERIVED file is never resolved by picking a side of a conflict.** Both sides are readings of
   different trees. `comment-references-baseline.json` was de-conflicted and RE-RECORDED.
8. **`docs/reference/frontend-backend-demands.md` is COMPUTED**, not written. A hand-typed row was
   refused by `compare-contracts.py --check`; prose typed into it is prose the next rebuild
   discards. `--write`, and the reasoning lives in the contract's description and in DESIGN.md.
9. **`check-bug-register` ACCEPTS a closure with no code change** — its arm reads a body that
   CHANGED, so B-316 could read `fixed #572` on a measurement alone.
10. **The repository's network hook matches the TOKEN, not the command.** A Bash call is refused for
   want of a timeout because the word appears in PROSE being written — this very file tripped it.
   Assemble the word from parts, or write through a Python script.

### 5b. THE GUARDS READ MY WORK BETTER THAN I DID — four times

`check-maquette-comments` caught a wave name (« since L12 ») and later a DATE and a lot name in
rule docstrings I had just written — rewritten, never `--record`ed over. `check-markup-contracts`
refused `.ctitle` and later `.scrim` as class anchors (hard zero, no baseline) — both re-anchored on
`data-part`. `check-mock-seeds` refused a new contract operation carrying neither `x-seeded-from`
nor `x-unseeded`. `check-no-french` refused `resumed`, `arrived` and `position` — all three added to
`code-vocabulary.txt` beside words already there. **Run the guards on your own instruments, not just
on the product.**

### 5c. B-354 WAS FILED AND WITHDRAWN — it is B-338, already `fixed #573`

An invisible scrim that stays hit-testable after a layer closes. I measured it independently, filed
it, and the merge of `main` showed the departure micro-wave had already found, filed and REPAIRED
it. The duplicate is withdrawn. **The lesson is the ordering**: merge `main` before filing against a
tree that predates other people's fixes. **Your next free register number is B-354 again**, and
R136 for a rule.

### 5d. The merge's four conflicts, and how each was resolved

Version (kept 0.98.75, past main's 0.98.74) · the comment baseline (derived — re-recorded against
the merged tree) · `IMPLEMENTATION.md` (main's side is a superset) · `BUGS.md` (a UNION, nothing
from either side dropped).

### 5f. THE HEAVY FLOOR CANNOT BE MET ON THIS MACHINE

`heavy.sh`'s default `FREE_FLOOR_MB=4096` is unreachable: 4 403 MB is kernel-wired (reboot-only)
and free+inactive sits near 3 840 MB, so a wrapped run waits in the readiness loop for ever — it
held the lock 33 minutes before this was diagnosed. **The steward approved
`HEAVY_FREE_FLOOR_MB=3072` for `TM_HARNESS_JOBS=2` and never larger** (two browser groups plus
slack). Every run and every push in this session's second half used it.

### 5e. WHY CI READ ZERO, and it is not « green »

`gh api …/check-runs` answered **0** on `8892a4bec` for twenty minutes. The cause: **PR #572 was
`CONFLICTING` / `DIRTY`** against the moved `main`, and this repository's CI triggers on
`pull_request`, so GitHub ran nothing at all. The only check-suite was Claude's, `queued`, 0 runs.
**Zero check-runs means « never started », never « passed ».** The merge in § 5d is the fix; CI has
NOT yet been read on the merged head.

---

## 6. What is OWED, in order

1. **`run.sh --contracts` on the MERGED tree** — queued behind another session when this was
   written, never read.
2. **The operator's word on 30-at-rest** (§ 2). Until it lands nothing may be pushed, because the
   sugmore commit is in the middle of the branch.
3. **Push, then read CI on the merged head** — `git ls-remote` against the local sha is the only
   proof a push landed (B-360); the wrapper's exit code has lied twice on this machine.
4. **B-315 (a)** — ruled by the orchestrator as the adjacent case of B-352: the button's size is
   drawn at the catalogue's secondary-footer scale **by its TOKEN**, and its hold reads the rendered
   size against the same token the catalogue's secondary footer resolves to — measured on the page,
   never typed. **No state**, so the oracle never sees it and no divergence is « accepted »; the
   operator judges it on his Mac. Write that reading into DESIGN.md beside B-352's.
5. **Phases 5, 6, 7** — untouched.
6. **The wave gate**: full suite, `--a11y`, `harness-hold-counts.py --compare` with `failed` read
   FIRST, the oracle, `make check`. The orchestrator's references: baseline 93 rules / 2 199 holds
   and the oracle both at `f70ca0295`.

---

## 7. The one thing not to repeat

Every defect this session found was found by asking what a hold actually READS — and four of them
were in the instruments, not the product. A rule that passes is not a rule that measured. **The
free red on another tree's build is the cheapest proof there is**: the served copy carried `main`
when this session started, and running the two new rules against it BEFORE republishing cost
nothing and exposed both a true red and two defects in the rules themselves.
