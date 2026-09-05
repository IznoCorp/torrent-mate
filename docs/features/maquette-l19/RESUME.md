# L19 — the rotation brief

**Read this first, then `BRIEF.md`, then `REPORT.md`.** It exists because the session that
executed L19 was asked to stop at the end of round three, and a wave in review is a state that
does not survive in one agent's head. It is written to be read by someone who was not here.

**It describes the wave AS IT STANDS. Where it names a figure, the command that produces it is
beside it — run the command, do not believe the figure.**

---

## 1. Where the work is

| | |
| --- | --- |
| Lot | **L19 — The producers**, `docs/reference/frontend-architecture.md` § 4 |
| Branch | `feat/maquette-l19` |
| Pull request | **#558**, open, not merged, version **0.98.69** |
| Base | `4c0e274a7` at the wave's start; `main` has since moved and the PR reads `BEHIND`, which is ordinary and is not a conflict |
| Phases | **all landed.** The plan under `plan/` is complete; nothing in it is outstanding |
| What is left | the review rounds, and nothing else |

**The wave itself is finished.** Every phase gate passed, the report is written, the register is
current. What remains is whatever a further review round returns.

## 2. The review, round by round

The office's rule is in `docs/reference/frontend-steward.md`: the steward is never the agent who
implemented the lot, the findings come back to the implementer, and **the implementer alone
writes**.

| Round | Verdict | Where it is recorded |
| --- | --- | --- |
| One | 0 blockers · 5 majors · 21 minors | `REPORT.md` § 6, § 8, § 9 · B-316 to B-319 |
| Two | 0 blockers · 2 majors · 1 to establish · 17 minors | `REPORT.md` § 12 · B-320 to B-322 |
| Three | in flight when this was written; two majors known — the stale corpus figure and R120's vacuous first-action hold, both repaired in the commit that carries this file | — |

**The curve is 5 → 2, and both of round two's majors were the REGISTER lagging the repairs rather
than the code.** Expect that shape again: this wave's failures have been in what it *wrote down*
about itself more often than in what it built.

## 3. What must not be reopened

These are settled. Re-arguing them costs a round and changes nothing.

- **The producers moved, and the conversion is faithful.** Three independent readers checked the
  ten descriptors field for field against `4c0e274a7`. Do not re-audit the conversion.
- **The nine large fixture families did NOT die**, and that is measured, not conceded: a producer
  was never their last reader. They belong to **L13**, written into its « Done when ».
- **The delegation's remaining verbs were not moved**, and the operator ratified their placement
  in **L13** and **L21** on 2026-09-05. It is a DEPARTURE from the contract, recorded as
  deviation 10, and it is the only one of the fifteen carrying an operator sign-off.
- **B-322 and B-320 are filed, not repaired**, with the reason in their bodies: B-322's clean fix
  adds lines to `engine/legacy.js`, which D5 permits only against data loss and which the size
  ledger this wave armed refuses with an exit code; B-320 is a hook-order defect in components
  this branch never touches.
- **`hold-counts-baseline.json` is untouched on purpose.** It is the post-merge gesture's file.

## 4. The operator's rulings of 2026-09-05

- « **OK pour le placement L13 et L21** » — the verb remainder's placement, ratified.
- « **Oui, fais-le** » — write those inheritances INTO the « Done when » of L13 and L21. Done.
- « **Oui** », with two conditions, on B-287's arm: it counts **only** a lot code, a phase or a
  date — never a register entry, a clause, a decision or a path — and its **baseline is taken on
  the reworded head**. Both honoured; the steward added a third, that `types.d.ts` is exempt by an
  entry naming its generator and `contract/openapi.json` is read at the source.

## 5. The protocol, which is not optional

1. **Every item comes back with the reading that closes it**, taken on a build of the candidate —
   or a sentence saying what the fixtures cannot show.
2. **Every repair lands with the rule that falls when it is reverted**, mutation-tested through
   `scripts/mutate.sh`. A guard is mutated by hand and judged by its **exit code** (B-273:
   `mutate.sh` cannot judge a guard).
3. **Figures are written ONCE, on the final head.**
4. **Commit before every mutation.** `mutate.sh` refuses a dirty tree because a restore over
   uncommitted work destroys it — this session did exactly that by hand with `git checkout --`
   and had to re-apply the work.
5. **The machine is an instrument.** Every run that starts browsers, builds, or a parallel test
   run is wrapped: `TM_HARNESS_JOBS=2 sh scripts/heavy.sh <who> <command>`. Never a build beside a
   run; never `pytest -n auto` beside a harness run. Kill what you start, delete what you build,
   verify with `ps`. **The harness is one per machine — ask the steward before taking it.**
6. **You do not merge.** The operator gives the word.

## 6. The traps this wave paid for

Each cost a round or a wrong reading. They are the reason the protocol reads as it does.

- **A mutation reading and a control reading that AGREE mean the probe measures nothing.** Three
  times: a scroll probe that never scrolled, a history hold that cleared the whole cache so the
  address was refused before the walk reached the suppression, and one that evicted a query key
  this interface does not have (`/api/configuration`; it is `/api/config/schema`). The tell is
  always that the mutation and the control read the SAME.
- **A `querySelector` selector LIST has no priority** — it answers in DOCUMENT order. `focus.ts`
  claimed « `[autofocus]` first » over one for as long as it existed.
- **Opening a panel through `window.__panel.produce` hides whether any finger can reach it.**
- **A guard proves what it READS.** Three were proved by SUBSTRING and repaired to parse.
- **A floor placed below anything that can happen is not a floor** (the comment arm's was 100
  against a corpus of 316).
- **A property held on ONE instance of a layer is a property nobody holds** — two readers reached
  opposite conclusions about the delete dialogs because R81 walked one of three.
- **`panel.py` runs `asyncio.run(main())` at import**, so importing it to inspect a function
  launches a browser.

## 7. Who to talk to

**The steward is session `personalscraper-70 [2e29f7]`, and no other address.** Every message goes
there. If a message expecting an answer has had none after **15 minutes**, run `ListAgents`, find
that session, and re-send there saying it is a re-send; if it is not listed, tell the operator and
stop waiting. This rule exists because seven hours were lost to a message sent to the wrong
session — this session's own error, and it is recorded here so it is not repeated.

**The steward is preparing its own succession**; its successor re-announces its address before
anything else.
