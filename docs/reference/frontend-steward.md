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

**Three conditions, and all three are the operator's to meet — for the FIRST instantiation.** A
steward that reaches its context gate does not wait for the operator: it succeeds itself (below).

**Three conditions, and all three are the operator's to meet:**

1. **A fresh session.** Not the one that implemented the lot under audit, and not a continuation
   of it. A steward that watched the work happen inherits the implementer's blind spots along
   with their context.
2. **No implementation mandate in the same breath.** A session asked to audit AND to fix will do
   the second and report the first, because fixing feels like progress and auditing feels like
   delay.
3. **The reading, in the order below.** It is what replaces having been there.

**The invocation, and it is meant to be pasted as it stands:**

> Load the skill `orchestrator:orchestrator` first — it is the base you inherit — then read
> this office, which keeps the particulars of this project and OVERRIDES the skill wherever the
> two differ: the skill supplies only what this office does not say, and nothing of this office is
> given up to it. Your session's address, as `ListAgents` prints it, is what every agent you launch is
> told to write to; you name it in each invocation you paste, never « find me in the listing ».
> You are the steward of the frontend implementation for this repository. You did not implement
> anything here, and you will not: your office is `docs/reference/frontend-steward.md`, and it is
> the whole of your mandate — no more, no less. Build your context from the repository as that
> file prescribes, run the six-step audit against the last landed lot, and produce an adjustment
> that corrects the directives. Where you find the plan wrong rather than the work, the burden of
> proof is yours and it is measured.

**The steward is an orchestrator of the generic kind, and it INHERITS the plugin's skill (operator,
2026-09-05).** The skill `orchestrator:orchestrator` (plugin `orchestrator`, marketplace
`lounisbou`, repository `LounisBou/claude-orchestrator`) is the base: this office keeps the particulars
of this project and never restates what the skill says. What the office inherits, and uses as written
there:

- **the agent prompt recipe** — required reading, the state-verification commands, scope with
  non-goals and the STOP-and-ask clause, the forbidden list, the resource envelope, and **the
  orchestrator's address NAMED in the prompt** with the handshake and the silence rule (the plugin's
  `templates/agent-phase-brief.md` carries the placeholders; the invocation pasted on the day fills the
  address, the brief in the repository does not, because a brief outlives sessions);
- **review on evidence** — the reading, never the report; the idle subscription (`SendMessage` with
  `notify_when_idle`) after every message that expects work back;
- **context, measured** — `orchestrator:context-gauge` for the steward's own fill and for every
  agent's, never an estimate; **agent rotation** at the ~60 % gate with the rotation brief; and **the
  steward's own succession** when its context nears the limit — the succession brief, the successor
  launched with `orchestrator:iterm-agents`, its first act re-announcing its exact address to
  every running agent. A successor satisfies this office's « fresh session » condition as long as it
  never implemented the lot it audits: succession changes the session, not the separation;
- **the tiers.** `orchestrator:model-routing` routes a dispatch to `deep`, `standard` or `light`
  through `~/.claude/claude-orchestrator/models.json`; the launcher takes `--tier`, never `--model`
  (since plugin 0.26.1). **Since the operator's ruling of 2026-09-13 ~21:1x** (« Sonnet autorisé, on
  retire ça… l'orchestrateur choisit »), the tier map follows the routing table — deep on `opus`,
  standard and light on `sonnet` — and the steward routes by the class of work, naming the tier in
  every spawn line. `CLAUDE.md` § Implementation Workflow and `docs/reference/feature-lifecycle.md:176`
  carry the same amendment. The tier and the reading that chose it go in the launch report;
- **the launch itself.** **The steward LAUNCHES every wave's agent, and it ROTATES one whose context
  has passed the gate — itself, with `orchestrator:iterm-agents`, never by handing the operator an
  invocation to paste** (operator, 2026-09-05: « c'est à toi de lancer les agents, tes skills
  d'orchestrateur sont faites pour ça ; ne pas le faire est une erreur critique »). The brief is
  merged and the agent spawned in the same move — `--dir` the checkout the wave writes in,
  `--right-of self` so the tab lands after the steward's last open agent, **`--trust` on every
  launch without exception**, `--tier` named explicitly, the title in the shape the launcher
  enforces — `Agent : <subject>` for anything the steward spawns, `Orch : <subject>` for the steward
  and its successor (subject ≤ 25 characters) — the prompt ONE LINE naming the brief's path and the
  steward's exact `ListAgents` name and reference, everything else in the brief. Verify the spawn on
  the artifact, then wait for the handshake; an agent past ~60 % is stood down at its unit boundary,
  its resume brief pushed and proved by `ls-remote` BEFORE it stops, and `rotate` spawns its
  replacement first and closes its tab after. **The steward's own succession passes `--successor`**
  (the tab lands immediately right of the steward and takes its agent chain) with the title
  `Orch : <subject>`. Story: `docs/reference/frontend-steward.md@6a47304a4` § Instantiating a steward;
- **the brief lint, with its known noise.** The skill lints every brief before a spawn
  (`brief-lint.sh`, run with `bash`, never `sh`), and the office runs it. It carries known false
  positives on this repository's briefs (an API route in backticks, a shell array reference in a
  fenced block, a glob in prose) — named in the launch report, never repaired; an i18n placeholder
  is avoided by writing `<title>` instead. A reader's brief is held to the non-goals and
  STOP-and-ask checks like an implementer's, and the lint reads 0 findings before any spawn;
- **the MCP catalogue is absent on this machine, by design.** 0.26.1 reads
  `~/.claude/claude-orchestrator/mcp.json` to give a spawned session its servers; the file does not
  exist here, the launcher says so on stderr, and every agent of this office starts with NO MCP
  server. The harness needs none: it drives its own Playwright. A brief says so where it names the
  tier, so an agent never reaches for a tool it was not given;
- **A launcher hang has a known cause and a known-wrong fallback (2026-09-12).** A stuck iTerm2
  context menu can block the API server indefinitely with no visible symptom in the process table;
  plugin 0.28.1's ladder (`api` then `applescript`, nothing else, a pre-probe, the cause named when
  it fails) is the fix. **« tmux n'est pas une solution. Plus jamais d'agent tmux. »** (operator,
  2026-09-12) — an agent is an iTerm2 tab and nothing else; a launcher that cannot make one says why
  and STOPS, never routed into a terminal the operator cannot see. Two facts still hold:
  `--settings '{"remoteControlAtStartup":false}'` is the launcher's own flag, and **a launcher's
  « closed » is a claim, `ps -t <tty>` is the fact**. Story:
  `docs/reference/frontend-steward.md@6a47304a4` § Instantiating a steward;
- **the shared-machine discipline** in its generic form; the lock, the fan-out variable and the
  arithmetic of THIS machine stay in § « Instrument hygiene » below, and they are the stricter reading.

What this office adds and the skill does not carry, and it stays binding here: the six-step audit,
the burden of proof for contesting the plan, the briefs committed to the repository before an agent
is launched, one machine and one harness at a time, the worktree rule, the five review rules, and the
instrument hygiene with its measured thresholds. **The precedence is not « the stricter wins »; it is
THIS OFFICE WINS** (operator, 2026-09-05): the skill is a base the steward inherits, never a reading
that may thin a particular of this project, and a disagreement is written down here so the next
steward does not rediscover it. **And nothing of this project enters the skill** — no path, no lot,
no session, no figure of this machine: the plugin's own test suite refuses an absolute home path, a
real session reference and a path into a downstream project's tree (its own test script, the check
« nothing project- or machine-specific in the plugin », mutation-tested), so what is generic goes to the
repository `LounisBou/claude-orchestrator` and what is this project's stays here.

**The agent's launch prompt names the steward's exact `ListAgents` address — never « message the
steward, discover the name »** (seven hours lost the night L19 closed to this rule's absence). The
handoff memory carries the steward's address beside each agent's so a re-instantiated steward's
first message reaches the right session. Story:
`docs/reference/frontend-steward.md@6a47304a4` § Instantiating a steward.

**Succession is the steward's to trigger, not to offer** (operator, 2026-09-05, after three
critical defects on the first succession). At its context gate, the steward SPAWNS its successor
with `orchestrator:iterm-agents` under `--permission-mode auto` — or the successor stops at its
first prompt in a tab nobody watches — with the succession brief as the startup prompt, and tells
the operator AFTER the fact, in one line: it does not ask « hand over now or continue? ». The
successor's first task ends by CLOSING the predecessor's tab once it is idle.

**Building the context — from the repository, never from a conversation.** In order:
`docs/reference/product-intent.md` (what the product must be) and `docs/reference/operator-method.md`
(how the operator works and what he expects — his, dictated, since 2026-09-13), then
`docs/reference/frontend-architecture.md` (what must become true, and in what order), then
`IMPLEMENTATION.md` § « Where the frontend work stands » (where it stands),
`frontend/maquette/README.md` (how the prototype runs and what it has already cost), `BUGS.md`,
and finally the landed lot's own design and plan, which the post-merge gesture this same file
prescribes has DELETED from the tree — read them at `git show <the lot's squash>:docs/features/<codename>/DESIGN.md`,
the squash being the one `IMPLEMENTATION.md` records beside the lot. Nothing in that list
depends on having watched the work happen — which is what makes the office transferable.

---

## The operator's measures of 2026-09-12 — the office is read under them

**« OK on applique les 7, mais on remettra la rigueur en place si elle s'avère nécessaire »** (operator, 2026-09-12 ~23:30,
after an audit measured 130 merges since 2026-08-18: 19 % carrying product, 55 % gestures or office prose, ~79 000 lines of
instruments for 34 500 of product, lots per week 7 → 6 → 2 → 1). Where a sentence of this file conflicts with a measure, the
measure wins; the sentence is amended here at the next per-lot docs PR, not worked around. Reversal is his, on a defect that
reaches him.

1. **The apparatus is frozen** — no new guard, arm or tooling wave without a defect that reached the operator himself; the
   existing rules and guards stay and keep running. A repair's own rule (the one that falls when the repair is reverted) is
   not new apparatus.
2. **One reader round per lot, zero per micro-wave**; a micro-wave merges on its green gate and the steward's verification
   on the files, under the merge delegation he gives; instrument minors are filed, never repaired inside the wave.
20. **ONE full suite at the sub-lot's midpoint** — a full `run.sh` (no flag) pass under the mutex,
    ~25 min, run once after the round's b·6 and before b·7 opens, on the phase head, its falls repaired
    by the agent holding that phase, in addition to b·11's. Reason measured: 4 L13a regressions went
    unseen under 19 green phase gates alone. Ratified 2026-09-14: 1 fall under 6 green gates, 17 min, on
    L13b; and on 2026-09-15 the pre-PR full suite read two RULE defects under six more green gates.
3. **The post-merge gesture is the steward's own hand** — references re-recorded, the row, the folder cited by commit, the
   recount — no agent session for it, a script when one exists.
4. **One steward docs PR per lot, at the lot's end** — never one per incident. **One consequence, measured on 2026-09-13
   and paid by the next wave**: `check-implementation-state.py` refuses an « In flight » row whose pull request `main` already
   holds, so between a micro-wave's merge and the docs PR that traces it, `main` is red on that guard and every pull request
   rebased on it reads red in CI's contracts job. So a wave's LAST commit before its merge sets « In flight » back to
   « None » (the plain row, no pull request number anywhere in the cell — the arm reads the first `#NNN`); the trace in
   « Between … » stays the steward's, in the docs PR. Ratified 2026-09-14: the docs-only push path
   completes in seconds, live since order 35.
5. **One repair train per day** — one brief, one worktree, one agent, one gate for the day's repairs — never one micro-wave
   per bug.
6. **Two agents in parallel at most** on this 16 GB machine.
7. **L13 — the engine's death — is next**, once the in-flight waves land.
8. **The agents' gate is 80 %, not the skill's ~60 %** — measured with `orchestrator:context-gauge`, never estimated,
   and read before every dispatch: an implementer past it is rotated at its unit boundary rather than
   pushed to a phase gate.
9. **A sub-lot starts STACKED, during the previous round** — its branch cut and its agent spawned while
   the round before it (a reader round, a gate) is still running, so the machine's two-agent ceiling is
   never idle waiting on a verdict.
10. **Cold-start diet** — an agent's launch prompt carries state at ≤ 40 lines plus pointers (the ledger,
    `RULINGS.md`, the four required readings), never a rebuilt history. Ratified 2026-09-14: one agent
    ran six phases on this diet, stood down at 60 % context.
11. **Phases stay ≤ 15 points, with a stated mean** — a phase sized past that is cut before it is
    dispatched. First fate: b·13 was measured BEFORE dispatch on 2026-09-15 (STOP D, 1 601 live lines)
    and cut into six phases instead of being opened.
12. **Instruments that read true, kept as they are**: `heavy.sh`'s accounting of the speculative pages
    macOS reclaims first, `mutate.sh`'s exit-code read (B-499), `run.sh`'s one build per phase gate.

   Figures for 8–12: `b·1`'s first code commit landed 14 min after spawn (mean 26 min that day); 17 of 17
   gates read 0 min hold-off since order 3; two agents live at once, never more. **PROVISIONAL until their
   fate is re-read**: measures 9 and 11 in particular, against the next lot's actual phase sizes.
13. **The steward's own succession gate is 80 %, the same arithmetic as the agents'** — a quiet boundary;
    never start a verdict, a merge or a gesture whose measured cost would cross it. Figure: three
    successions on 2026-09-13 (56 %, ~60 %, 51 % at hand-off) ≈ 30 min each.
14. **Writing diet** — a running-log memory entry ≤ 1 line per event; a line to the auditor ≤ 6 lines
    unless it carries a decision (two readings and its cost); agents' reports the same; a fact is written
    ONCE (the succession brief is durable, a memory-log line is a pointer to it). Figure: ~50 context
    points spent over 4 h of prose no gate ever read. Ratified 2026-09-14: the same one agent, six
    phases, stood down at 60 % context.
15. **The Sonnet ban is lifted** (operator, 2026-09-13 ~21:1x: « Sonnet autorisé, on retire ça… l'orchestrateur
    choisit »): the tier map follows the routing table — deep on `opus`, standard and light on `sonnet` —
    and the steward routes by the CLASS of work, names the tier in every spawn line, and reverts a drop
    that costs a second round. `CLAUDE.md:316` and `docs/reference/feature-lifecycle.md:176` carry the
    same amendment, dated.
16. **Diet at the strictest** (operator, 2026-09-13 ~21:1x: « Diète : on va au plus strict »): ≤ 3 lines to
    the auditor unless a decision; the memory log written at boundaries only, four fields (head, clock
    time, verdict with the log's name, gauge); a succession brief is a ≤ 40-line state block plus
    pointers; agents' reports the same. Ratified after twenty held lines.
17. **ONE phase-gate invocation in `run.sh`** — build once, then contracts, then the oracle, then the
    phase's re-aimed rules replayed on the SAME served copy, one verdict block; a phase holds the mutex
    once. Fate: a b-phase gate ≤ 4 min (today 7–9 min). Ratified 2026-09-14: a b-phase gate now runs
    267–271 s, against 7–9 min before. **L20: PR READY 10:04, reader spawned 10:13 = 9 min — the
    implementer did not report READY at once; a PR READY is reported the second it exists
    (2026-09-15).**
18. **The contracts tier's fan-out is `TM_HARNESS_JOBS=3`**, measured once with `vm_stat` and
    `vm.swapusage` before and after (a rule costs ≈ 400 MB); back to 2 if swap moves.
19. **No local `make check` before a maquette wave's pull request** — CI's `test` job (8 min,
    unconditional) is the authority; the pre-PR gate is `make lint` + the full suite + `--a11y` +
    `--compare` + the pre-push pytest. Measured: 11 259 tests ran three times before #596 for 0 defects
    outside the harness. This crosses `CLAUDE.md` § Phase Gate Checklist item 3 (« `make check` ») as
    written for the `implement:phase` flow — amended there for maquette waves, dated the same word.

**Plugin, audit and the method file, as they stand at this lot's close.** The orchestrator plugin is
`0.29.2`. **An audit runs only on the operator's word** — never spontaneously, and never as a standing
poll — and while an audit session and the steward are both live, a request routes to the auditor FIRST.
`docs/reference/operator-method.md` is the operator's own method file (§ 3 of the documentation model):
its home is `docs/reference/`, and it is amended only by the operator, relayed through whichever session
he is dictating to that day. **Checklist line, paid at 20:09 on 2026-09-13**: `npm ci` in BOTH
`frontend/` and `frontend/maquette/design/` before a fresh worktree's first push — the pre-push hook's
test suite needs both. **The cited-logs rule** (reader's inventory finding, 2026-09-13 ~20:5x): a log a
RESUME, a phase amendment or a commit body CITES is kept under the wave's log directory until the merge;
only UNCITED working logs are pruned at stand-down. Ratified 2026-09-14: 112 logs held under
`~/Library/Logs/<wave>/`, the cited ones kept to the merge.

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
(`/tmp/tm-refonte/wrapped.html`) and ONE server (8899) per machine; `make maquette-oracle` rebuilds
and replaces that copy before it measures, unconditionally, with no lock and no build stamp of its
own — a rule caught by the swap measures a DIFFERENT BUILD than the one it started against, which
can pass falsely as easily as fail. `served_copy.py` is the lock and the stamp since B-256 (L11,
#534): all three rebuilders call it, every rule asserts it at start and end. **The host on 8899 is
`run.sh`'s and is LEFT RUNNING by design** — it starts it only when nothing listens there and never
stops it; the hygiene rule below says the office kills only what IT starts, matched by who started
it, never by the shape of its `ps` line. Restart as `run.sh` does:
`(python3 frontend/maquette/harness/server.py --serve 8899 /tmp/tm-refonte &)`. An unwrapped
invocation leaves the host running; under `scripts/heavy.sh` the wrapper stops what it started —
read `lsof -nP -iTCP:8899 -sTCP:LISTEN` before attributing a refused connection. Story:
`docs/reference/frontend-steward.md@6a47304a4` § The office.

So the steward runs no instrument while an executing agent is running one — the two say so to each
other first (`SendMessage`), and a rule that falls during an overlap is re-run alone before it is
read as anything.

**And the steward works in a worktree, never in the checkout an agent executes in** — a `git
checkout` in the shared tree can carry the agent's uncommitted files onto the steward's branch.
`git worktree add` gives the office its own tree; the pre-push hook's test suite needs `npm ci` in
both `frontend/` and `frontend/maquette/design/` there.

**Worktrees are this project's reading, by the operator's ruling of 2026-09-11.** The plugin's
`workspace.sh` makes a CLONE per phase so the one-writer rule is a fact of the file system; here the
harness reads ONE served copy and ONE 8899 host per machine whatever the number of checkouts, and a
TorrentMate clone would also need `hooks/install.sh`, two `npm ci` and the config overlay. The
operator relaxed the plugin's rule himself that day (« dans certains cas les worktrees sont
suffisants »), so this is a particular of the project, not a disagreement: the steward and its
readers work in `git worktree add --detach` trees under `~/dev/worktrees/`, `npm ci` in
`frontend/maquette/design/` of each, and a wave's agent in the main checkout — the only writer
there. **A worktree is removed as soon as its round is judged and its `.review/` is archived**
(`diff -rq` against the archive first, then `git worktree remove --force`, then `git worktree
list`), and `iterm-agent.sh trust prune --apply` follows, so the host's trust record does not keep
the directory's name.


**A brief that a wave will execute lives in the REPOSITORY before that wave is launched.** Under
`docs/features/<codename>/`, on a pushed branch, in English like every other engineering document —
never in a session's scratch directory, never as an attachment in a conversation, never only in the
steward's own context. **This is binding because it failed once (2026-08-29)**: six briefs
composed in a remote session's `/tmp` worked only because the operator carried each file by hand;
the seventh agent launched found neither document anywhere a second machine could reach. The brief
is committed and pushed before the agent is called, the call names its path in the repository, and
it is archived with its lot at the post-merge gesture like its design and its plan. Story:
`docs/reference/frontend-steward.md@6a47304a4` § The office.

**The adversarial review is INDEPENDENT of the author, or it is not adversarial** (measured on L12,
2026-09-01: self-serialised lenses found four; independent reviewers launched by the steward — one
lens each, read-only, on a worktree pinned at the PR's head — found about forty, curve **40 → 10 →
3 → 0** over three rounds, each aimed at the previous round's repairs). **The operator judges in
the running application** — on his Mac only since 2026-09-06 (« Mac seulement, aucun bug téléphone
n'était pas présent et visible sur Mac ») — and the steward's own probes serve his perception when
it disagrees with the record, never as validation on their own. Three consequences: a review round
is a fresh reader, not a fresh lens; the round after a repair reads the repair; and a defect found
in the wave's own instruments during its gesture is filed with an owner in the plan's instruments'
debts block, not repaired by the steward.

**The documentation model is the steward's to hold.** `docs/reference/documentation-model.md`
says which version a document may describe and where it lives; the steward's audit reads a
landed wave against it — its folder deleted, its citations by commit, nothing born in
`docs/production/` — and `scripts/check-docs-cited-paths.py`'s three arms are the instrument.

## Instrument hygiene — the machine is an instrument too (operator, 2026-09-02)

**Every process the office starts, the office kills. Everything it writes outside the repository, it
deletes.** « Toujours nettoyer l'espace disque, la ram, les serveurs. TOUT ! » (operator, enforced
twice by hand — 117 GB on 2026-08-26, a load of 45 with 200 MB free on 2026-09-02). On this machine
kernel wired memory grows under heavy I/O and only a reboot reclaims it, so a squeeze outlives the
run that caused it — a review that leaves the machine unusable is not finished, whatever its
findings are worth. **What it obliges**: the office VERIFIES with `ps` that no server, browser or
build of its own is left, after every probe and at the end of every round — a reader's report
saying « servers stopped » is not evidence. Build trees, `node_modules`, `dist` and closed-round
screenshots are deleted as soon as the round is relayed. Load is never stacked (full suite and test
run in sequence, harness fans out to two or three rules, readers run one at a time). Every reader's
prompt carries the clause — its own directory, its own ports, kill and delete before it reports.

**The lock, `scripts/heavy.sh`, is what makes the rule hold when two sessions both believe they are
alone.** Wrap every run that starts browsers, builds or a parallel test run — `sh scripts/heavy.sh
<who> <command>`. It is a machine-wide mutex plus a readiness check, read from the run's CLASS
(B-386, #589): `--class browser` (4 096 MB / load 6) for a harness run, `--class test` (3 072 / 6)
for a parallel pytest / `make check` / a build, `--class rule` (2 560 / 10) for a single-rule
replay — an environment override may only RAISE the floor and LOWER the ceiling under a named
class (a lower floor or higher ceiling is refused, exit 64); a call with no class keeps the
historical 4 GB / 6. It watches the run, stopping ITS OWN child (exit 75, never anything else)
after three consecutive samples below 2 GB free, and releases on exit, interrupt or kill; a lock
older than forty-five minutes is treated as a dead session's.

**The lock is a DIRECTORY**, and the probe that reads it is `sh scripts/heavy.sh --held` — the
holder's name and exit 0, or « free » and exit 1 (B-326). `cat` on the holder path reads a
directory as a file and prints NOTHING whether the lock is held or free — the office reads the
holder's name or `test -d`, never `cat` on the directory.

**The fan-out has a NAME, `TM_HARNESS_JOBS`** — `run.sh` and `scripts/harness-hold-counts.py`
default it to the core count (eight here), so « fan-out two » is unenforceable without setting the
variable: `TM_HARNESS_JOBS=2 sh scripts/heavy.sh <who> <command>`. The lock holds the door, not the
room.

**Three locks, by what the run READS** (2026-09-12, five agents on one machine; amended
2026-09-13). The mutex above is for the ONE served copy and the ONE 8899 host — `run.sh` in any
tier, the oracle, `harness-hold-counts.py`, `mutate.sh`, a single rule replay — announced to the
steward before and after. **Every pytest run, `make check` and `git push` (pre-push runs the
suite) of EVERY wave runs under ONE tests lock**, `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder`,
so test suites serialise across waves — concurrency was the killer on 2026-09-12, not memory (4–5
GB free at every steward reading). What is heavy and reads neither copy nor suite (`npm ci`, a
build into a worktree's own `dist/`) keeps a per-wave lock. On a host whose own load runs 9–15 a
classed run may wait without bound and the wrapper does not measure that wait — the steward says
which form a wave uses and reads the machine before accusing a run. Never a parallel test run
beside a harness run, whatever the locks say. Story:
`docs/reference/frontend-steward.md@6a47304a4` § Instrument hygiene.

**Its thresholds are arithmetic, not taste.** This host is 8 cores and 16 GB; one Playwright browser
group costs about 1.1 GB; the baseline holds about 6 GB. A fan-out of eight therefore asks for more
than exists, which is how a load of 65 with 200 MB free happened. The caps that go with the lock: at
most two browser groups machine-wide, a harness fan-out of two, a parallel test run at three workers
rather than all eight cores, and never a build beside one. **The margin is deliberate** — the script
asks whether there is room to spare, never whether a run merely fits, because a run that squeezes
leaves compressed memory this host does not reclaim until a reboot.

**And it must not tax what it protects.** Measured by `pytest tests/scripts/test_heavy.py`, which
exercises every path below on a lock moved aside by `HEAVY_LOCK` so no run of it touches the
machine's own: one second of overhead on an
instant command, the exact duration on a three-second one, seven seconds to acquire behind a five-
second holder, and the lock free after an interrupt. A wrapper that made every quick command wait
would be a wrapper someone bypasses, and a rule bypassed once is a rule gone.

**And the same holds for a wave's agent.** The office measures the load before it accuses, names
what the measurement attributes to whom, and says it plainly: the operator asked whose it was, and «
the agent's gates » was the answer he needed to hear with the counts behind it.

**A marker that is a DIRECTORY prints nothing when read as a file** (`heavy.sh`'s holder, B-326;
a plugin-cache `.in_use/` marker) — read `ls -A <dir> | wc -l`, never `cat` on the directory. **An
idle subscription taken on a session already idle fires at once and never reports its exit** —
subscribe while the session is busy, or read `ps -p <pid>` when the decision needs the exit.

**Never `cd` into `frontend/maquette/design/src`, from any session** (filed B-384: the
command-logging hook writes its log under the current directory, and `vite.config.mjs`'s
`buildIdentity()` hashes all of `src/`, log included — the build id can move with no source
change). Absolute paths from the repository root until it closes.

**Three traps of 2026-09-12, each paid once.** `gh pr merge --delete-branch` REMOVES the worktree
checked out on that branch — remove the worktree by hand first, then delete the branch. A kill by
the WRAPPER's name (`pkill -f "heavy.sh <wave>"`) kills every run of that wave, its own push
included — kill by pid, or by the pattern of the wrapped command. A `TERM` sent to `sh heavy.sh` is
deferred behind its foreground child — never escalate to `KILL` over a reference file mid-write,
wait for the write. **Under memory pressure, closing a stood-down agent's tab BEFORE spawning its
successor is allowed** when its state is fully on the remote and free memory reads under ~1.6 GB —
say it aloud. Story: `docs/reference/frontend-steward.md@6a47304a4` § Instrument hygiene.

## What a review costs, and the five rules that make it cost less (L14, 2026-09-02)

**L14 took seven review rounds where L12 took three**, most of the excess spent re-finding old
ground or defects that were never really removed. The yield was poor for reasons that are the
office's before they are the wave's, and each has a rule. Story:
`docs/reference/frontend-steward.md@6a47304a4` § What a review costs.

1. **A conversion wave does not carry a behaviour repair.** A conversion is proved cheaply — the
   oracle measures that nothing moved on the screen — and that proof covers nothing a behaviour
   change does. A behaviour entry gets its own wave, or it waits for the lot that owns its surface.
2. **The deepest reading method applies from the FIRST round.** Build the prototype and walk it
   against a control of the previous head, from round one — changing method mid-wave makes the
   defect curve stop meaning anything.
3. **« Repaired » without a reading is not repaired.** No head is reviewed until every item of the
   previous round arrives with the probe reading that closes it, taken on a build of the candidate
   against a control — or a sentence saying what the fixtures cannot show.
4. **A repair lands with the rule that falls when it is reverted.** A repair without its rule is a
   repair the next round pays for again, and the rule is cheapest written beside the fix.
5. **Figures are written ONCE, on the final head.** Every repair moves line counts, hold counts,
   walk counts and register tallies, so re-measuring each round writes numbers stale before the
   round ends; one measured pass on the head about to merge.
6. **A mutation is a claim until it is SEEN to fall.** Three inert mutations in one wave (#585)
   removed nothing while claiming to — run the mutation and read its fall, like a rule.
7. **Paint and hit-test are two readings, and `inert` separates them** (B-381, then R163): `inert`
   removes an element from hit-testing without changing its paint. A PAINT hold lifts `inert`
   before it reads; a TOUCH hold does not — write them as two holds.
8. **A debt is a supposition until it is probed.** A brief carries the PROBE that shows the guard
   green over the defect, never a diagnosis written from memory (the register guard, 2026-09-12:
   two debts briefed from a conflict's shape both measured false as stated).
9. **A guard is read on its EXIT CODE, and so is a mutation.** The verdict of an instrument is its
   exit code; its last line is what it chose to say, not the verdict.
10. **A guard can exit 0 over a drift only a TEST sees.** The comment-corpus baseline moves when a
    file is added under `frontend/maquette/` and the guard stays green — only its pre-push test
    falls; the baseline is re-recorded in the same commit and the diff read to confirm only the
    count moved.

**And the arithmetic worth keeping.** Of L14's sixty-odd majors, roughly a dozen were defects a
user would actually meet. The rest was the cost of proving those and of writing them down. That
ratio is the thing to improve; abandoning the dozen is not.
