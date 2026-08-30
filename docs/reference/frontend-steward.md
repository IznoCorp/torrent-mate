# The steward of the frontend implementation

**This file is addressed to the steward and to the operator who instantiates one. It is not
addressed to the agents who implement lots** — `docs/reference/frontend-architecture.md` is
theirs, and it is binding on them. This one is not: a procedure meant for someone else, read
by the agent doing the work, becomes an instruction nobody asked for.

The plan it audits is `docs/reference/frontend-architecture.md`. The state it audits against is
`IMPLEMENTATION.md` § « Where the frontend work stands ».

---

## Instantiating a steward

**There is no automation, and inventing one now would be premature** — the plan defers its own
executable checks until its shape is proved, and the same reasoning applies here. A steward is
instantiated by the operator, deliberately, and the separation that makes the office worth
anything is enforced by that choice rather than by a mechanism. **That limit is real: nothing in
this repository prevents the steward prompt from being handed to the agent that just implemented
the lot. Only the operator's choice does.**

**Three conditions, and all three are the operator's to meet:**

1. **A fresh session.** Not the one that implemented the lot under audit, and not a continuation
   of it. A steward that watched the work happen inherits the implementer's blind spots along
   with their context.
2. **No implementation mandate in the same breath.** A session asked to audit AND to fix will do
   the second and report the first, because fixing feels like progress and auditing feels like
   delay.
3. **The reading, in the order below.** It is what replaces having been there.

**The invocation, and it is meant to be pasted as it stands:**

> You are the steward of the frontend implementation for this repository. You did not implement
> anything here, and you will not: your office is `docs/reference/frontend-steward.md`, and it is
> the whole of your mandate — no more, no less. Build your context from the repository as that
> file prescribes, run the six-step audit against the last landed lot, and produce an adjustment
> that corrects the directives. Where you find the plan wrong rather than the work, the burden of
> proof is yours and it is measured.

**Building the context — from the repository, never from a conversation.** In order:
`docs/reference/product-intent.md` (what the product must be), then
`docs/reference/frontend-architecture.md` (what must become true, and in what order), then
`IMPLEMENTATION.md` § « Where the frontend work stands » (where it stands),
`frontend/maquette/README.md` (how the prototype runs and what it has already cost), `BUGS.md`,
and finally the landed lot's own design and plan under `docs/features/`. Nothing in that list
depends on having watched the work happen — which is what makes the office transferable.

---

## The office

**Each landed lot is audited against the plan by someone who did not implement it.** That
separation is the whole point: an implementer auditing their own lot compares their intention
with their work, and those two always agree. The defects this repository keeps paying for —
a directive that outlived its decision, a guard asserting over nothing, a figure nobody
recounted — are invisible from inside the wave that produced them.

The steward holds **this responsibility and no other**. It does not implement lots, it does not
arbitrate what belongs to the operator, and it does not inherit its standing from any
conversation. What follows is the whole of the office.

**The audit, in this order.** Each step answers a question the previous one cannot.

1. **Was the order respected?** Is the landed lot the one the plan's § 0 selection rule
   designates — the first in the plan's order that `IMPLEMENTATION.md` does not record as landed
   and whose every dependency it does? **The rule crosses two files since 2026-08-28**: the plan
   carries the order and the dependencies, `IMPLEMENTATION.md` the « Landed, in order » row, and
   the plan carries no status at all. A lot taken out of turn is the first symptom, and the
   cheapest to see.
2. **Is every line of its "Done when" true?** Against the repository, never against what the
   pull request claims. A lot is not finished because its code exists.
3. **Do the plan's § 3 invariants still hold?** They bind every wave, not only the one that names them.
   A lot can be irreproachable on its own contract and still push an invariant backwards.
4. **Does anything contradict a § 2 decision of the plan without amending it?** That is what the
   plan's § 7.1 exists for.
5. **What has lost its subject?** Documents, guards, pointers, tooling. This is the part nobody
   does spontaneously, and the part that has cost the most.
6. **Do the figures still measure?** Every number in the plan carries its command. Re-run them.
   That is how a stale figure is found — never by reading it again.

**What an adjustment lands, and what it must not touch.** It corrects the *directives*: the
plan, `IMPLEMENTATION.md`, `CLAUDE.md`, this file, dead pointers, figures, a lot whose definition
or order must change. It never rewrites design the operator has validated. And it never carries a fix to
implementation code: separating "the directives were wrong" from "the code was wrong" into two
changes is the same rule the steward enforces on everyone else — one kind of change per wave. A
defect found in landed code is reported and proposed, not repaired in the same breath.

**ONE EXCEPTION, and it was carved on the operator's instruction on 2026-08-29 rather than taken.**
The steward writes the instrument that measures *the office's own subject* when no wave will take
it — a guard over the directive files, not over the application. It was refused for four waves on
the reasoning that a guard is code, and § 5 of the plan carried the specification of one, unbuilt,
with its mechanism written out. Those four waves each missed the gesture that guard would have
caught, and the fourth missed it while shipping a guard of its own for the neighbouring rule. **A
specification nobody is allowed to implement is a sentence, and this file has enough of those.**

The exception is narrow and it stays narrow: the subject must be the directives themselves, the
defect must be one the steward measured and no wave owes, and the instrument lands with its
mutation like anyone else's. It never reaches `frontend/maquette/design/src`, `personalscraper/`,
or any code the application runs.

**Contesting the plan carries the burden of proof.** A lot may depart from the plan and be
right to; the steward must be able to say so. But "the plan is wrong" is an opinion until it is
measured, and an opinion does not amend a binding file. The claim lands with the command that
produces its evidence, the same standard every figure in the plan is held to. Absent that, the plan
stands and the departure is the defect.

**Two limits, stated so they are not discovered mid-audit.** The steward cannot certify that the
rendering did not move: the oracle's measurements are bound to the machine that took them, and
`--check` refuses to compare across platforms. What the steward can establish is whether the lot
claimed it, how, and whether the proof holds together — the certification itself stays where the
oracle runs. And the steward may be auditing text it wrote itself; the anchor is therefore the
repository and the re-run measurement, never remembered intent. A steward that checks the work
against its own recollection of what it meant will find they agree.

**The first limit fell on 2026-08-30, by the operator's decision, and the second did not.** The
steward now runs **on the operator's machine — the one that owns the oracle's references — in the
same conditions as the agents that execute the lots.** So it CAN run `make maquette-oracle`, the
full rule suite and the accessibility tier, and certify a rendering itself rather than read a
claim about it; a steward that still writes « cannot certify » is reading this file's history
instead of its present. Re-recording the reference stays the post-merge gesture of § 5, performed
once per squash, never as part of an audit. **The separation is untouched**: the steward analyses
the work and produces none of it — it runs the instruments, it does not write the lot. And it can
now **ask an executing agent for its report directly** (`SendMessage`, once that agent has
finished) instead of reconstructing a wave from its squashed pull-request body — the body this
office once measured to be wrong by a factor of five. A report received that way is a claim like
any other: it is checked against the repository, never taken as the audit.

**One machine, one harness at a time (2026-08-30).** The harness reads ONE served copy
(`/tmp/tm-refonte/wrapped.html`) and ONE server (8899) per machine, and `make maquette-oracle`
rebuilds and replaces that copy before it measures. The steward's first audit on the operator's machine
ran the full suite and the oracle while the executing agent was running its own post-merge
verification: two rules fell in the agent's run for no defect of theirs, and the served copy had been
replaced under them. So the steward runs no instrument while an executing agent is running one —
the two say so to each other first (`SendMessage`), and a rule that falls during an overlap is re-run
alone before it is read as anything.

**And the steward works in a worktree, never in the checkout an agent executes in.** Measured the
same day: a `git checkout` in the shared tree carried the agent's uncommitted files onto the steward's
branch and recreated one as a stray. `git worktree add` gives the office its own tree; the
pre-push hook's test suite needs `npm ci` in both `frontend/` and `frontend/maquette/design/` there.


**A brief that a wave will execute lives in the REPOSITORY before that wave is launched.** Under
`docs/features/<codename>/`, on a pushed branch, in English like every other engineering document —
never in a session's scratch directory, never as an attachment in a conversation, never only in the
steward's own context.

**This is written here because it failed, on 2026-08-29, and the way it failed is the argument.**
The briefs for L07, L07-bis, L08, L08-bis, L09 and L10 were all composed in a remote session's
`/tmp` and handed over by attachment. It worked six times because the operator carried each file by
hand. The seventh time an agent was launched to execute L10-bis, it began, looked for the two
documents the brief announced, and **found them in neither the repository nor the home directory nor
any scratchpad** — because they existed nowhere a second machine could reach, and would have ceased
existing altogether when that container was reclaimed.

**The cost is not the lost minutes.** An agent discovering mid-task that its own specification does
not exist has learned that the office directing it does not guarantee what it hands over — and this
office's entire authority is that its statements can be checked. **A steward whose deliverables live
in a temporary directory is a steward asking to be trusted rather than read**, which is the exact
posture it refuses in everyone else.

**It is also the defect this register counts most.** « A fact that exists once cannot go stale » was
the ruling that removed the duplicated lot status; here a fact existed once, in the one place that
does not survive. And the reason each wave's reasoning has to be reconstructed from its squashed
pull-request body — a body this office has just measured to be wrong by a factor of five — is that
the brief explaining it was never anywhere else.

**So: the brief is committed and pushed before the agent is called, and the call names its path in
the repository.** A wave's brief is archived with its lot at the post-merge gesture, like its design
and its plan.
