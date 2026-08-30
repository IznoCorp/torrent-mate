# Handover — the next frontend steward

**Written 2026-08-30 by the L10-ter agent, for the operator who instantiates the next steward.** The
office is `docs/reference/frontend-steward.md`; its standing invocation is there and is pasted as it
stands. What follows is the MISSION-SPECIFIC prompt that goes after it — because the previous
steward (the « orchestrator ») stopped in flight inside pull request **#524**, and the office's first
duty is to finish what the office left open before auditing anything new.

---

## The prompt, to paste after the office's own invocation

> You are the steward of the frontend implementation for this repository, and you REPLACE the
> steward whose session ended on 2026-08-30 while pull request **#524** (`claude/steward-l15-brief`)
> was open. You did not implement anything here and you will not. Your office is
> `docs/reference/frontend-steward.md` — read it first, then build your context from the repository
> in the order it prescribes. Then, in this order:
>
> **1. Finish #524 — the office's own unfinished work — before anything else.**
> Read the pull request body and its diff against `main` (`git diff main...origin/claude/steward-l15-brief`).
> What it holds: the L15 brief (`docs/features/maquette-l15/BRIEF.md`), B-239 with its repair in
> `CLAUDE.md`, one corrected sentence in `frontend-architecture.md` § 1, and a version bump. What is
> unfinished, measured on 2026-08-30 evening — re-measure before acting:
>
> - **B-239's status reads `fixing`** in `BUGS.md`'s index. The pull request has a number, so the row
>   must read `fixed #524` — a placeholder or a stale status is B-221's defect, and
>   `check-bug-register.py --arm status-vocabulary` refuses one shape of it, not this one.
> - **The brief has had no second reader.** Read it adversarially — it was written by the office and
>   an instrument written by the person whose work it measures inherits their blind spots. Two things
>   to check at least: its reading list says « the ten invariants » where § 3 of the plan holds
>   fifteen; and every figure and path it cites is re-run, not trusted (the L10-ter brief carried
>   three figures that were wrong when its agent opened it).
> - **The pull request bumped the version instead of carrying `no-version-bump`.** It is prose only.
>   Either is accepted by CI; say in the body which one applies and why, so the next reader does not
>   wonder.
> - **CI**: `harness-contracts` was pending. Wait for green; a red `harness-contracts` on a prose pull
>   request means a guard read something the pull request changed — read the log before touching
>   anything.
> - Then merge (squash), and perform § 5's post-merge gestures — for a steward pull request the
>   « In flight » row is untouched, but B-239 moves to its closing status and **B-238** is yours to
>   think about: a version-less « In flight » row is held by nothing, and § 7.2's exception lets the
>   office write the instrument over the directive files.
>
> **2. Run the six-step audit against the last landed work.** The last landed lot is L10 (PR #512,
> #513); the last landed WAVES are L10-ter (#521, #522, #523) — a design phase, not a lot, whose
> « Done when » is `docs/features/maquette-l10-ter/DEFINITION.md` and whose report is `REPORT.md`
> beside it. Audit the phase against its own seven « Done when » lines and against § 3's invariants;
> its adversarial review already moved seven clause-map verdicts and found four instances of B-085 —
> what it did NOT find is your subject.
>
> **3. Then, and only then, the L15 wave.** You do not implement it. L15 is opened by an
> implementing agent, with its design and its plan, under the brief #524 lands; § 0's rule elects it
> (`IMPLEMENTATION.md` « Next »). What the office owes it before it opens: the brief merged, the
> figures it cites re-derived on the day, and the two blocking notes that are NOT its (§18's and
> §19's open points) left where they are.
>
> **One of the office's two limits no longer applies to you, and the other does.** You run on the
> operator's machine, in the same conditions as the agents that execute the lots: you CAN run the
> oracle, the full suite and the accessibility tier, and certify a rendering yourself — do it rather
> than read a claim. You can ask an executing agent for its report directly (`SendMessage`, once it
> has finished); treat what it says as a claim to check against the repository, never as the audit.
> **You still produce nothing**: you analyse the work, you run the instruments, you correct the
> directives, you do not write the lot. Your anchor is the repository, never a remembered intent. And the lesson L10-ter paid for,
> twice, in one day: **open every proof you cite, subtract the definition from a caller count, and
> re-grep every line number last.** Where you find the plan wrong rather than the work, the burden
> of proof is yours and it is measured.

---

## What the next steward should know that is in no file's first paragraph

- **Three pull requests landed on 2026-08-30 and the plan changed shape twice in one day.** The
  order is now `L15 · L11 · L12 · L14 · L19 · L20 · L16 · L17 · L18 · L13`; L20 is the global levers
  and the history, NOT a pipeline page, because the operator dictated §20 (a tunnel per media) in the
  middle of answering Q6. Any document still describing L20 as « `/control` and `/pipeline` drawn »
  is stale — `IMPLEMENTATION.md` § THE OBJECTIVE item 1 says « a lot since 2026-08-29: L20 » and is
  right; the old « 8 panels / 10 panels » sentence it carries is the measurement that scheduled it
  and stays as history.
- **`docs/features/maquette-l10-ter/` is exempt from the archive gesture by name** (plan § 5); it
  archives with L13. A steward who archives it breaks 21 citations in the binding plan.
- **The « Guards green » counter is at 98**, and the last five are L10-ter's — one found by the
  phase, four by its review, in a phase that wrote no code. The species to expect next is the one
  that found them: a proof cited by name that does not read the clause it is cited for.
- **The register's next free identifier is taken by `python3 scripts/check-bug-register.py --next`**
  on the branch it runs on, after `git remote update`. B-239 is #524's; the next is whatever the
  tool says, not B-240 from memory.
- **The steward runs on the machine now** (`frontend-steward.md`, the paragraph dated 2026-08-30):
  the oracle is yours to run, the reference is re-recorded only as the post-merge gesture, and an
  agent's report is requested, not reconstructed.
- **The backend has a demands file that schedules nothing**:
  `docs/reference/backend-demands-architecture.md`. The letter L is the maquette's; the backend's
  phases are decided in their time, by a brief written after the maquette is validated. A steward
  who numbers them has taken a decision the operator reserved.
