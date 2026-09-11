# L21 — where the wave stands, for whoever picks it up

Rewritten at a CLEAN PAUSE called by the operator (« on s'arrête maintenant, on reprendra après le
reset, on s'arrête proprement »). Read `BRIEF.md`, `DESIGN.md` and `plan/INDEX.md` first — this file
says only what is TRUE NOW and what those do not.

**Branch** `feat/maquette-l21`, pull request **#572** (draft). **Version** 0.98.79.

⚠ **#572 CARRIES THE `run-ci-on-draft` LABEL**, put there by the orchestrator. So this branch's
pushes DO dispatch CI even though the pull request is a draft. « A draft dispatches no CI » is true
in general and **NOT true of this pull request**: `BLOCKED` on it means checks PENDING, not checks
missing. Read the label before diagnosing an absent run.

⚠ **`origin/main` IS MERGED into this branch**, proven by `git merge-base --is-ancestor origin/main
HEAD`. This branch carries FOUR merge commits, so reading any one of their second parents says it is
behind. Re-read `main` before touching it again.

⚠ **B-377 IS FIXED ON `main` (#579).** The old warning here — that
`scripts/check-implementation-state.py` infers « that wave has landed » from a version comparison and
would refuse this live « In flight » row — no longer applies. The arm now asks whether the pull
request merged. **Do not spend time on it.**

⚠ **`main` HAS MOVED PAST WHAT THE PREVIOUS EDITION OF THIS FILE RECORDED.** It said « next free
number is B-377 »; `main` has since taken **B-376 and B-377**. The pause took B-378; the § 3.4 build
took **B-379, B-380 and B-381**, so **next free is B-382**. Rules R125–R139, R155, R156, R157 and
**R158** are spent, and **R159 is reserved** for the hold B-381's repair lands with (§ 3.5); **R160+**
are free.

---

## 0. THE PAUSE — read this before anything

**Nothing was left half-done. The tree was CLEAN when the stop came** and no increment was in
flight: this session had finished a reading, reported it, chosen a shape, had it approved, and was
reading `scripts/rename-identifiers.py`'s interface when the stop arrived. **No source file under
`design/src`, `harness/` or `contract/` was edited by this session.** The only commit at the pause is
documentation: this file and the B-378 register entry.

So the gate figures in § 4 still cover the tree exactly as they did — see the condition there.

**What the next session picks up is a fully specified, fully approved, NOT-YET-STARTED build.** It
is § 3. Every ruling it needs has been given; nothing in it is awaiting an arbitration.

---

## 1. Done

| Phase                               | State          | Proof                                    |
| ----------------------------------- | -------------- | ---------------------------------------- |
| 1–7                                 | **DONE**       | `REPORT.md` § 1, one row each            |
| **the operator's four rulings**     | **DONE**       | § 2 — three repaired, one filed          |
| **the wave gate**                   | **TAKEN**      | § 4                                      |
| **review round one, six findings**  | **DONE**       | § 5 — five repaired, one filed           |
| **A5's third surface — the READING**| **DONE**       | § 3.1 — and it inverted the assumption   |
| **A5's third surface — the BUILD**  | **1–6 DONE**   | § 3.4 — the commits named there          |

**Register**: B-301, B-302, B-313, B-315, B-322, B-323, B-350, B-353, B-365, B-368 read `fixed #572`.
**Filed by this lot**: B-329, B-330, B-351, B-352, B-363, B-364, B-366, B-367, B-369, B-370, B-371,
**B-378**.

---

## 2. The operator's four rulings

**B-365 — REPAIRED.** The refusal hold read Playwright response events; the mock layer answers IN
THE PAGE, so that list is empty whatever is answered. It reads `window.__mocks.answered()` across
EVERY operation now, network read kept beside it, guarded on an empty record. Mutation: BOTH refusal
holds fall naming `409 POST grabSeasonForFollow`, the third does not move.

**B-315 (a) — REOPENED, and it was a DEFECT, not a scale.** The button rendered **332 x 245** with a
**227 x 227** icon: `svgIcon` emits an `<svg>` with no size, and this button wears none of the legacy
classes whose descendant rules size the system's icons. **R136's four holds read steps and passed all
of it.** `actionButton` now carries a bounded `size` (`screen` | `footer`, each branch a string
LITERAL so `residue.py` keeps reading it); the `footer` branch carries the icon's size; all 19 call
sites across 9 files pass no argument and their emitted class set is unchanged, held token for token.
**Height settled at 40 px with a 16 px icon by the operator.** R136's fifth hold compares the
RENDERED BOX to the system's own.
⚠ The type-level hold is a **conditional type**, not the compiler directive that expects an error:
this tree counts every such directive as a typing escape against a floor of hard zero, **and its
guard reads them inside COMMENTS too**.

**B-367 — FILED ONLY**, owner the settings micro-wave. Measured on a real drawer: pressing `light`,
`dark`, `system`, `light`, the stored value and `data-theme` follow every press and `aria-pressed`
moves NOT ONCE; a close and a reopen draws it correctly. `drawer.tsx`'s own comment beside
`window.__store.touch()` claims « The bump is what redraws the pressed state », which that
measurement contradicts.

**B-368 — REPRODUCED and REPAIRED.** A stale node: the deck's body is filled imperatively, React
reuses that element when the mode leaves the deck and appends its own children after what it never
rendered. The sweep knew `.body > .deck` and a SPENT pile is not a `.deck`.

**B-366 — RE-RULED, and the repair is NOT done.** R156 refuses a sheetless follow by asking the
DRAWING'S OWN resolver. ⚠ **It is a GATE, not the repair.** Making the state unrepresentable leaves
this lot on all three routes (the engine's drawing, `SHEETS_RAW`'s 20 538 lines, contract surgery).
**Owner L13.** A follow with no EPISODE data is a different absence and stays legitimate.

---

## 3. A5's THIRD SURFACE — the reading, the rulings, and the build that is owed

This is the live work. Everything in it is settled except the doing.

### 3.1 The reading — and it inverted round one's assumption

Round one asked whether the library's « Incomplets » lens needed the season-grab act ADDED to it.
**It does not: it already offers the act, and that is the defect.** The premise A5's gate rests on is
FALSE, and it is written verbatim in the code — `season-list.tsx:318-325`:

> « The operation is `/api/acquisition/follows/{title}/seasons/{n}/grab`: it asks about a FOLLOW.
> **The panel is only ever drawn for one, so it needs no test**; this list is drawn for any medium. »

The panel is NOT only ever drawn for a follow. Every step below was read in the source:

1. `incomplete-lens.tsx:51` draws its cards with `cardHTML({t,s,f,chip})` — **no `panel` key**.
2. `legacy.js:5327` therefore emits the card body as `data-panel="media:${t}"` (`hasSheet` is true
   for an owned show). The tile branch, `legacy.js:7733`, emits the same.
3. `legacy.js:9491` delegates `data-panel` to `openPanel`.
4. `legacy.js:7807-7811` — `openPanel` splits on the FIRST colon and switches on the genre: `sug` →
   suggestion, `add` → add, **`else` → `panel.produce("follow", ref)`**. The genre `media` is
   DISCARDED; only the title travels. **That is why `producePanel('media', …)` raises « unknown panel
   producer » and yet the addresses work — nothing ever asks for a `media` producer.** The previous
   edition of this file named that raise as an open thread; this is its answer.
5. `follow-facts.ts:85-95` — `followFacts` has a THREE-STEP FALLBACK its own docstring names as the
   engine's: a real follow, **else an INCOMPLETE-SHOW record synthesised `{st:"to_grab", own,
   aired}`**, else a synthetic `up_to_date`. `isFollowed` is computed SEPARATELY and is false for
   both fallbacks.
6. `panel-seasons.tsx:200-212` draws the grab verb over any incomplete season with **no `followed`
   test at all**.

**MEASURED AGAINST THE FIXTURE, not reasoned:** the intersection of `incomplete-shows.json` and
`follows.json` is **EMPTY** — 12 titles and 14, zero overlap — so **every** card in that lens reaches
this path. Of the twelve, exactly two carry `SEASONS` data and therefore actually draw the matrix and
the verb: **« Les Animaniacs »** and **« Les aventures de Tintin »**, both also present in
`seasons.json` so `absorbedCount` is genuinely non-zero for them. The other ten fall to the
`noSeasonData` note — **which is why nobody met this by accident, and why those two are the named
subjects of the hold.**

**So the « third surface » is not a third surface — it IS the follow panel, reached from that lens.**
Round one looked for season rows inside the lens, found tiles and cards, and stopped. The rows are
one tap further in.

### 3.2 The defect found on the way — B-378, FILED, NOT REPAIRED

`acquisition-verbs.ts:165` moves the follow's status only `if (found !== undefined)`. For a
non-follow `found` is `undefined`, so **the handler answers a success (200 today — the layer ignores the declared code, B-379) with a real `absorbedCount` and moves
NOTHING** — success reported over an unchanged world, which is exactly the shape this lot's phase-1
rule refuses. The interface says « Saison 3 demandée — 5 épisodes à récupérer », refetches the
follows, gets the identical list, and redraws the identical panel. Full entry in `BUGS.md` § B-378.

### 3.3 THE RULINGS — all given, none awaiting anybody

**THE OPERATOR, and he overruled BOTH this session's recommendation and the orchestrator's:**
**« Offer it — the backend follows. »** The act is NOT hidden. From « Incomplets », a person who owns
an incomplete show and does not follow it may ask for a missing season, and the CONTRACT grows to
accept that rather than the interface drawing less. That is his standing rule applied literally — a
backend limitation is not a reason to draw less.

**THE ORCHESTRATOR, on the two points left open:**

- **The sheet's gate is `owns && !complete`.** The orchestrator's first ruling here was « delete the
  `followed &&` clause — the true test is no test », on the reasoning that the list is drawn only where
  a sheet exists and `!complete` IS the hole. **Measurement falsified it**: `complete` is
  `owns && …`, so `!complete` is true for anything not owned, and a sheet exists for a suggestion too —
  on `mediasheet-suggestion-series` (The Venture Bros, neither owned nor followed) the list offered
  **seven** season grabs, invisible to the oracle because they sit inside closed `<details>`, with the
  contracts tier green over them. Re-ruled `owns && !complete`, the condition the « manquants » mark is
  already drawn on. The `followed` prop is still deleted, and the false comment with it. Whether a
  FOLLOWED show with nothing owned should be offered the act from its sheet is put to the operator,
  not built.
- **Three parallel sentence keys, never one appended sentence.** The discipline is chosen sentences,
  never composed ones, and this repository has just paid for the other way: A4 of round one was
  « 1 épisode(s) », a parenthesis stuck onto a sentence that should have been chosen. Six keys for
  one act is cheap; a composed sentence is a defect that renders correctly. A follow started is a
  second FACT, and the answer's new field is what SELECTS the sentence — NE-DOIT-PAS-1 exactly.
- **And a FOURTH key, re-ruled on the same principle — eight keys for the act, not six.** The queued
  path is a real path (`seasonQueued` is chosen when the answer says `queued`), and the act creates the
  follow on it too — `pending`, since nothing runs yet. Three parallel keys would leave that fact
  unsaid there, so `seasonQueuedNewlyFollowed` stands beside `seasonQueued`: one chosen sentence per
  combination of facts the answer can carry, never a sentence built from two keys.

**THE SHAPE, chosen by this session and APPROVED: (a) THE ACT IMPLIES THE FOLLOW.** The address
stays; the operation follows-then-grabs. Four reasons, **the third decisive**:

1. It makes the address TRUE rather than merely tolerated: by the time the season is taken the
   subject IS a follow, so `/api/acquisition/follows/{followedId}/…` stops lying. Under (b) the route
   is renamed and one is left with « take a season of something nothing tracks », which has nowhere
   to record that the ask happened.
2. It is the operator's own identification ruling applied — « si on a un suivi, c'est qu'on a
   identifié le média ». An incomplete library show is identified by construction: sheet, year,
   owned/aired counts.
3. **IT IS THE ONLY ONE OF THE TWO THAT CAN SATISFY PHASE 1'S MOCK RULE.** Under (a) the mock APPENDS
   the follow with status BEING_ACQUIRED: the refetch returns a longer list, `isFollowed` flips true,
   `window.__panel.redraw()` redraws a genuinely different panel — all observable, all readable by a
   hold. **Under (b) there is still nothing to move**, the grab of an untracked medium stays an
   acknowledgement over an unchanged world, and the rule would be UNSATISFIABLE.
4. Smaller instrument surface: the operation id is unchanged, so `season_grab.py:67`, `busy.py:68`
   and `acted_surface_redraws.py:220,246` keep reading the name they read now.

### 3.4 THE BUILD — in committable increments, in this order

**Landed on 2026-09-11**, one commit per increment, each through its gate: 1 `9472524a3` · 2
`b2036180c` · 3 `c208b0e02` · 4 `5c4277bef` (the gate `owns && !complete`, § 3.3) · 5 `6a871adaa`
(R158, `harness/season_grab_unfollowed.py`) and the register `b84f4e7ce` (B-378 fixed, B-379 and B-380
filed) · 6 `b197632ff`, the backend demand, `backend-demands-architecture.md` § 7 · docs `d65679c0f` ·
register `6087237ae` and `959d3719a` · **7 PARTIAL**, § 3.5.

The orchestrator's instruction, and it is the shape to keep: **never leave the tree in a state where
the next session must reconstruct what you were in the middle of.**

1. **Untangle the name that lies about its type.** The `saisons` block payload is
   `{ isFollowed: Follow; seasons: Season[] }` — a field named `isFollowed` that **holds the follow
   RECORD**, destructured `const { isFollowed: follow } = block`. Rename that field to `follow`.
   ⚠ **`FollowFacts.isFollowed` is a GENUINE boolean and must NOT be touched** — `follow-facts.ts:53,
   101,116` and `follow-actions.ts:50,83,88,96,113,119`. Only four sites move: `contract.ts:62` (a doc
   comment), `panel-seasons.tsx:32` and `:224`, `panel-follow.ts:54`. **This is done FIRST**, because
   a gate written near a field named `isFollowed` reads as already present when it is not.
   ⚠ A rename goes through `scripts/rename-identifiers.py` — but the tool takes a JSON mapping FILE as
   `sys.argv[1]` and has no `--help`; it refuses chained and merging tables. Since the same property
   name must SURVIVE elsewhere, check whether `--properties` can be scoped to these files before
   running it, and **verify by re-reading the diff, not the « N file(s) touched » line.**
2. **Contract + its two generated artefacts, ONE commit** — `--check` refuses them separated, and the
   commit message should say they move as one. `grabSeasonForFollow` gains one required response
   field saying whether the act started the follow. Summary and the `followedId` description change
   from « the follow » to « the medium; it is followed by this act if it was not already ». The
   operation carries **`x-unseeded`** (not `x-seeded-from`) and its text already explains why —
   EXTEND that text rather than adding a second annotation. Then `npm run generate-contract-types` in
   `design/`, then `python3 scripts/compare-contracts.py --write`.
3. **The mock MOVES STATE** — `acquisition-verbs.ts`. Create the follow when absent, then grab; the
   answer says it did. A follow record's fields, from `follows.json`: `title, showStatus, since,
   searches, kind, year, status, fresh` (`owned`/`aired` appear on some). This repairs B-378.
4. **The surfaces.** Delete `followed &&` in `season-list.tsx:326` and the now-dead prop
   (`season-list.tsx:15,25-26`); kill the false comment at `:318-325` — **it must not survive, it is
   the kind of sentence a later session reads as established fact.** Three parallel i18n keys beside
   `seasonAsked`/`seasonAskedOne`/`seasonAskedNone` in `verbs.media`.
5. **The hold, SEEN RED FIRST**, reading BOTH surfaces: the act offered and answered on an incomplete
   NON-follow. Subjects « Les Animaniacs » and « Les aventures de Tintin » — **and the rule must SAY
   why those two** (the only incomplete shows with `SEASONS` data; the other ten fall to the
   no-season note), so the next reader does not think the choice arbitrary.
6. **The backend demand** in `docs/reference/backend-demands-architecture.md`: what the operation
   must accept, and why the interface asks it.
7. **The on-screen confirmation, LAST** — watch the button appear and answer for real on a build, on
   one of the two subjects. It is required before calling the unit done; it is **not** the gate for
   increments 1–6.

### 3.5 Increment 7 — PARTIAL, and the three entries the build filed

**Read on screen** on `d65679c0f` (build `de36920b9ce9`, a port of its own, a finger on every step):
from « Incomplets », « Les aventures de Tintin »' follow panel offers « Récupérer la saison 3 », the tap
calls the operation, the show is followed (`acquiring`) and the panel redraws « En cours
d'acquisition ». **The sentence the act chose is NOT visible**: it is in the document, visible, at full
opacity, and a finger at its centre lands on the panel's own button — **B-381**, the message ranked
under the bottom sheet, dated on `origin/main` and not L21's; owner pending the operator's ruling. The
second reading, « Les Animaniacs »' sheet, season 5, reads « Saison 5 0/23 23 manquants » and answers
« … aucun épisode à récupérer » — **B-380**.

- **B-379** (`open`, « mock layer » micro-wave): the layer answers 200 whatever the contract declares.
  R158 holds a success as `2xx` for that reason.
- **B-380** (`open`, « mock layer »): the season grab counts `seasons.json`, the sheet draws its own
  catalogue; 13 of 49 seasons disagree. The operator ruled « manquant » = aired and not owned, so the
  SHEET's count is the defect. Not built here.
- **B-381** (`open`, owner pending): R125 and R158 read `window.__toast.read()` and cannot see it.
  **R159**, `message_over_layers.py`, hit-tests the message's own text over `sheet-user`, over the
  follow panel after its season verb, and over `mediasheet-series`: read RED, 5 holds, 3 violations
  naming the covering layer. **It is not in `harness/`**, because a red rule cannot enter the suite and
  every harness file is read by `make check` and the push: it is committed as TEXT at
  `docs/features/maquette-l21/message_over_layers.py.txt` (the orchestrator's ruling), and the
  repairing wave moves it into `harness/` and deletes that copy in the same commit.

Still open and not built: whether a FOLLOWED show with nothing owned is offered the act from its sheet
(`(owns || followed) && !complete`) — put to the operator.

---

## 4. The wave gate

**Gated on `6087237ae` after the § 3.4 build** (the commits after it touch `BUGS.md` only), verdicts:
full suite « 111 rule(s) and 27 repository guard(s), no violation » (exit 1 is the oracle inside it) ·
a11y 87 states 0 violations, light 162 against 162 · oracle 44 divergences, the list identical to the
one below · hold counts `--compare frontend/maquette/hold-counts-baseline.json` on `959d3719a`: baseline
`failed` 0, 111 rules no violation, the same 4 upward changes, 18 new (R158 at 41) · `make check` exit 0,
11 220 passed, 0 failed. The figures below are the pause's and are rewritten once, on the final head.

⚠ **WHICH SHA THE GREEN COVERS.** Every tier below was run on **`00ee56ae3`**. The commits after it
are DOCUMENTATION ONLY — a merge of `origin/main` at `b46643abf`, and this pause's own commit
(this file plus the B-378 register entry). **None of them touches any source the suite, the oracle or
the a11y audit reads**, so the figures still stand. **If you touch anything under
`frontend/maquette/design/src` or `frontend/maquette/harness`, the figures below stop covering your
tree** — which increment 1 of § 3.4 does immediately.

Every tier was written to a FILE and its verdict lines read out of it — never piped.

- **Full suite: 110 rules and 27 repository guards, NO VIOLATION.** Its exit is 1 for one reason
  only: **the full tier runs the oracle inside it**, and the oracle's divergences are this wave's
  accepted ones. Read the `no violation` line, not the exit.
- **`--contracts`: exit 0.**
- **a11y: 87 states, 0 violations.** Light **162 against a ceiling of 162** — the ceiling was lowered
  by this wave and the count now sits exactly on it.
- **Oracle: 44 divergences.** Forty-three are the wave's, unchanged; **ONE is A5's**:
  `mediasheet-series` · `screen-media/body` 1960 → 2014, **+54 px, one button**, on the one surface
  the repair draws on and on no other. That is D8's accepted shape — a divergence carrying the
  finding it serves. **A divergence on any other state is a defect and a STOP.** The reference is
  **NOT re-recorded by this wave**.
- **Hold counts, `failed` READ FIRST**: the baseline's own `totals.failed` is **0**, so it was
  recorded over a clean suite and the comparison means something. Then: **110 rules, no violation**;
  4 changed and every one UPWARD — `busy.py` 10 → 16, `cards.py` 65 → 70, `drawer.py` 28 → 30,
  `persistence.py` 47 → 57 — and 17 new since the baseline, `acted_surface_redraws.py` at 10 among
  them. **Exit 1 is drift against a baseline this wave does not re-record, not a failure.**
- **`make check`: exit 0 — 11 217 passed, 0 failed**, 4 skipped, 2 xfailed; the maquette's own unit
  suite 110/110 over 7 files against floors of 7 and 107.
- **`legacy.js` 31 467** non-blank against a record of 31 467 · **six-verb grep 0** · ledger exit 0.
- **110 rule files** (103 at the wave base).

### ⚠ What the a11y ceiling cost, because the number lies about its own itemisation

The debt file CANNOT name the four that left. Recorded and diffed: **no state's entry count moved at
all** — 34 selectors before, 34 after — while `counts.total` went 166 → 162, and **eleven states had
their selectors RESPELLED with their counts unchanged** (`.chip[data-part="chip"]` →
`.waiting.chip`), which is markup this branch moved; that file is keyed by SELECTOR. **The totals and
the selector map are not the same quantity.**
So it was attributed by MEASUREMENT: the wave base `7fecb0258` — computed as the parent of the
branch's first commit, and confirmed an ancestor of `origin/main` — built in a throwaway worktree
reads **166**; this head reads **162**. The branch earned four. A ratchet is lowered by the wave that
earned the room, on a wave-level reading, which is the only kind that file can support.

---

## 5. Review round one — six findings

**A1 + A2 — ONE MECHANISM.** A panel producer is a function from the cache to a descriptor and NOT a
component: nothing subscribes while the panel is open. A verb pressed inside a panel moved the layer,
the list BEHIND updated — that one is observed — and the sheet the operator was looking at did not.
`window.__panel.redraw()` re-produces the open panel from the cache as it is now, history suppressed,
silent when nothing is open. The season's `invalidateQueries` became a REFETCH.

⚠ **THE FIRST VERSION OF THAT MECHANISM HAD A HOLE, and it is the thing to read twice.**
`producePanel` recorded what was open only on its SYNCHRONOUS path. The deferred path is not the rare
one: a named state CLEARS the cache and any kind whose `needs` depends on its subject is excluded
from the boot's prefill, so **the first ask for any subject is always cold and always defers**. The
panel was opened by a path that recorded nothing and `redraw` went silently home. Found because the
rule stayed RED after the repair and that was not explained away.

**A2's second half** — one ask in flight per `title|season`, released in a `finally` so a refused ask
can be made again, answered with silence rather than « occupé » (NE-DOIT-PAS-3).

**A3 — FILED as B-371, owner L20, by the operator's ruling.** The pastille is reachable by no path a
finger can take: two pipeline notions, and the hand moves only the one it does not read. DOIT-4 drops
`served` → `partly` in the clause map. **DESIGN § 4.0 carried a three-step hand path that does not
work**; it is corrected where it stands.

**A4** — three sentences chosen by the caller, the deck's own pattern. Three and not two: a season
nothing is known about absorbs NOTHING, and « 0 épisodes » is wrong in French, where zero takes the
singular.

**A5** — the media sheet's season list offers the same act, through the shared `askForSeason` so the
two cannot drift. ⚠ **ITS `followed` GATE IS NOW RULED WRONG AND IS TO BE DELETED — see § 3.** The
justification written beside it is false, and the reading that falsified it is § 3.1.

**A6** — an emptied list draws the deck's own end mark.

**R157** (`harness/acted_surface_redraws.py`, 10 holds) holds A1 and A2 on the OPEN surface. Its
discriminator is the operator's own test: the panel on screen must say what a panel produced fresh
from the cache says. It also holds the surface MOVED, so a build where the verb does nothing cannot
pass by agreeing with a cache that never changed. Mutation (the redraw's body emptied): 4 holds fall.

⚠ **WHAT R157 DOES NOT HOLD**: any refusal branch, and the picker reached by hand from « En cours » —
`window.__releases()` is `[]` for every medium the queue holds, on both builds. **Do not manufacture
a repair for either.**

⚠ **R155 WAS FALSIFIED BY A6 AND IS SHARPENED.** It held « the offer is GONE after leaving the deck »;
an emptied list now draws an offer of its own, correctly, so that hold went red on a build that is
RIGHT. Presence was never the property — CONTAINMENT is.

---

## 6. Two corrections this wave owes its own record

**« eslint 0 » in `55c375c14`'s message is FALSE, twice over.** The maquette is outside eslint's scope
BY NAME — `frontend/eslint.config.js` ignores `maquette/**`, it being a separate npm project held by
its own harness and typecheck — and the figure was never eslint's anyway: **the command was piped
through `tail`, so the status captured was TAIL's.** The commit is not rewritten; a squash composes
its message fresh. **A gate piped into anything yields the LAST command's status**; `set -o pipefail`
or `${PIPESTATUS[0]}` is the answer. **Never pipe a long gate into `tail`** — redirect to a file and
read the verdict lines out of it.

**One gate pass compared NOTHING while looking like it ran.** `harness-hold-counts.py --compare`
takes a FILE; without one it exits **2** on an argparse usage error, which a gate reading exit codes
cannot tell from a comparison that found drift. **B-370, filed, NOT to be repaired here** — the
orchestrator ruled it stays filed: a tool repair in a lot's diff is the mixed-nature change this
office splits waves to avoid, and the defect predates this lot. **Pass the file explicitly to
`--compare` every time**, which sidesteps the failure mode entirely.

---

## 7. What is OWED

1. **§ 3.4's seven increments** — approved, specified, not started. This is the work.
2. **The pull request out of draft**, and **rounds two and three** — the orchestrator's word, and
   only his. **Round two's reader is spawned by the office**, fresh, one lens, in a worktree pinned
   at this head with a control at round one's. **An agent here dispatches no reviewer and no writing
   delegate**; read-only search subagents are the one thing that may be forked. A round the author
   runs inline is not adversarial whatever its rigour — measured on L12, where the wave's own lenses
   found four findings and the office's independent readers found about forty on the same head, two
   of them blockers.
3. **B-366's real repair** (L13) · **B-367** (settings micro-wave) · **B-371** (L20) · **B-370** ·
   **B-378** (repaired by § 3.4 increment 3).

### How to push, because it is not what it looks like

A push runs the parallel suite through its pre-push hook, so **it IS a heavy run and is wrapped like
one, every time**:

    PYTEST_XDIST_AUTO_NUM_WORKERS=3 HEAVY_FREE_FLOOR_MB=3072 sh scripts/heavy.sh l21 \
      git push origin feat/maquette-l21 > <a file> 2>&1

then prove it with `git ls-remote --heads origin feat/maquette-l21` against the local sha (B-360).
**That proof earns its keep**: a push once exited the wrapper and did NOT land, because the pre-push
hook refused it on a failing test, and `ls-remote` is what said so.

### The design host the operator walks

`torrentmate-design` (pm2) serves `frontend/maquette/design/dist` from THIS checkout. After any
change under `design/src`, build once (wrapped) so the host serves the head. **Do not restart pm2** —
it serves the directory, not a snapshot. `dist/build.json` is a CONTENT HASH of `design/src` plus
four root files, so it does NOT move when a build repeats over unchanged sources: an unchanged value
after a commit touching nothing under `design/src` is the instrument working, not a stale copy.
`/tmp/tm-refonte` is a DIFFERENT artefact — the harness's served copy, rebuilt by `run.sh`.

---

## 8. The machine, and the traps that live in it

**One served copy machine-wide**, on 8899 from `/tmp/tm-refonte`. The host is a **nohup process
started OUTSIDE the wrapper** — read `lsof -nP -iTCP:8899 -sTCP:LISTEN`, never trust a number written
here, and never restart it under the wrapper.

⚠ **The heavy lock is SHARED with sibling agents and it works.** `sh scripts/heavy.sh --held` names
the holder; waiting is correct and is never bypassed. **`cd` persists between commands** — a wrapped
run launched from a subdirectory fails with `sh: scripts/heavy.sh: No such file or directory`, which
is exit 127 and not a gate result.

⚠ **READ THE `EXECUTED` LINE BEFORE THE `FAIL` LINES** (B-273). A mutation that produces no verdict
line is not a mutation that found nothing.

⚠ **A `str.replace` mutation matches EVERY occurrence.** Print the mutated region BEFORE running it.

⚠ **`mutate.sh` REFUSES a dirty tree**: fix → gates → commit → mutate → restore.

⚠ **A worktree at another commit is the honest way to attribute a figure**, used three times here.
Symlink `node_modules` from the main checkout, build, publish, read, then REMOVE the worktree and
republish the main copy.

⚠ **`docs/` is globally gitignored**: a file under it needs `git add -f`, one at a time.

⚠ **`check-no-french` refuses a name built from a word the vocabulary does not have.** Rename to
words it already holds; **do not add a word to let your own identifier through** — that is the case
the gate exists to refuse.

⚠ **Adding a harness rule grows the maquette comment CORPUS**, and
`test_check_maquette_comments.py::TestTheCorpusFloor` fails on the count until
`check-maquette-comments.py --record` is run. Diff that record before committing it: only `read`
should move.

⚠ **The gauge is the LAST tool call before any message carrying a figure**, or the message says
« not measured this turn » and carries none.

---

## 9. The two things not to repeat

**A fixture edit is not a contained edit.** B-366's workaround renamed two paused follows precisely
BECAUSE it touched no code — and one of the new titles is the subject of the state « Fiche —
suggestion NON possédée (série) ». One rename, two instruments: it silenced the one it was made for
and falsified another two files away, and only the FULL suite could see it (B-369).

**A rule that stays red after a repair is telling the truth.** Both of round one's sharpest findings
came from refusing to explain one away: the deferred-open branch that recorded nothing, and a strip
whose state lives in a DOT and is invisible to `textContent`. A rule agreeing with the defect it was
written to catch reads exactly like a rule that passed.

**And the one this session adds: a COMMENT stating a premise is not evidence of it.**
`season-list.tsx:318-325` asserted « the panel is only ever drawn for one » in a carefully argued
paragraph, and it was false — the delegation four files away discards the genre and produces a follow
panel for anything. The paragraph was written by someone who had reasoned about the gate and not
walked the path into it. **Follow the address to the code that answers it, every time.**
