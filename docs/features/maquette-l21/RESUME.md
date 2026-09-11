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
took **B-379, B-380 and B-381**, review round two took **B-382**, so **next free is B-383** — and
round two's ruling assigns B-383 to the « said, not done » entry (§ 3.7). Rules R125–R139 and
R155–**R160** are spent; **R161+** are free.

---

## 0. WHERE IT STANDS — read this before anything

**A ROTATION, at a clean boundary. Nothing is half-done in the tree.** The head is the commit that adds
this text, on top of `0ad30191f` (docs), `fadd79086` (B2) and `a056d6330` (B1), all pushed.

- **Done**: the placement unit (§ 3.6); round two's **B1** (B-382, R160) and **B2** (B-381's third half,
  R159's screen legs), each with its rule seen red, its mutation and its run (§ 3.7 and the entries).
- **Owed, in the orchestrator's order**: **B3 → B6 → B4 → B8 → B7 → the docs** (B5's two corrections,
  B-380's extent, B-383 filed). Each is specified in § 3.7 with its hold and its mutation. **B6 is
  RULED** — the leave-and-reappear version, § 3.7.
- **Next free**: **B-383** (already assigned by the ruling to the « said, not done » entry), **R161**.
- **Gates**: contracts + oracle **per commit** (the oracle's accepted list is 44 over the same 23
  states, none on the message); **no full suite has run since `1e9e7c48e`** — ONE on the final head at
  the end of the list, then hold-counts with the baseline file, `make check`, `design/dist` rebuilt, the
  wrapped push, the report with each mutation line, the gauge last.
- **Mutate only on a clean tree**, and write `.md`/`.ts` changes by script or re-read `git diff --stat`
  before every commit (§ 3.7's hook note).

---

## 1. Done

| Phase                               | State          | Proof                                    |
| ----------------------------------- | -------------- | ---------------------------------------- |
| 1–7                                 | **DONE**       | `REPORT.md` § 1, one row each            |
| **the operator's four rulings**     | **DONE**       | § 2 — three repaired, one filed          |
| **the wave gate**                   | **TAKEN**      | § 4                                      |
| **review round one, six findings**  | **DONE**       | § 5 — five repaired, one filed           |
| **A5's third surface — the READING**| **DONE**       | § 3.1 — and it inverted the assumption   |
| **A5's third surface — the BUILD**  | **1–7 DONE**   | § 3.4 and § 3.5 — the commits named there |
| **the message's placement**         | **DONE**       | § 3.6 — `cf1677e5e`, its gate there      |

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
`noSeasonData` note IN THE FOLLOW PANEL — **which is why nobody met this by accident, and why those two
are the named subjects of the hold.** ⚠ **On the SHEET that is false** (review round two, B5): the sheet
draws its own catalogue, and six of the ten offer the act — 21 acts, every one answering « aucun
épisode ». That is B-380's extent, recorded in its entry.

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
  already drawn on. The false comment is still deleted.
- **And the operator ruled it wider** (decision round of 2026-09-11, question 2, answer « B »): the
  sheet offers the act on a FOLLOWED show nothing is owned of, the same act wherever the show is looked
  at — and **a season not yet aired is not offered, on any show — the operator's definition of
  missing**: « Manquant : les épisodes diffusés et non possédés ! S'il n'existe pas (pas encore diffusé)
  alors je ne peux pas les avoir donc ils ne manquent pas encore, mais ils sont là pour informer
  l'utilisateur de sorties à venir d'épisodes. » The gate is `(owns || followed) && !complete &&
  !seasonUpcoming` (`1e89d7688`); the `followed` prop is back, from its one caller. Three readings, in
  order: no test → `owns` → `owns || followed`, with the date clause.
  **The operator can walk it by hand on the design host**: open « Agent Elvis » from Découvrir, tap
  « Suivre », open its season 1 — « Récupérer la saison 1 » is there; do the same on « Grimsburg » and
  its third season, not yet aired, offers nothing.
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
   why those two** (the only incomplete shows with `SEASONS` data; in the follow panel the other ten
   fall to the no-season note — not on the sheet, B-380), so the next reader does not think the choice
   arbitrary.
6. **The backend demand** in `docs/reference/backend-demands-architecture.md`: what the operation
   must accept, and why the interface asks it.
7. **The on-screen confirmation, LAST** — watch the button appear and answer for real on a build, on
   one of the two subjects. It is required before calling the unit done; it is **not** the gate for
   increments 1–6.

### 3.5 Increment 7 — COMPLETE, and the three entries the build filed

**First reading, partial** on `d65679c0f` (build `de36920b9ce9`): from « Incomplets », « Les aventures de
Tintin »' follow panel offered « Récupérer la saison 3 », the tap called the operation, the show was
followed and the panel redrew « En cours d'acquisition » — and the sentence the act chose was in the
document and painted UNDER the panel (B-381). **Retaken after B-381's repair** on `0e2c25bc1` (build
`6bc3e1d72aef`, a port of its own, a finger on every step): « Série suivie et saison 3 demandée — 6
épisodes à récupérer. » is on top at its own text at +400 and +1200 ms, not `inert`, and the show is
followed (`acquiring`). The second reading, « Les Animaniacs »' sheet, season 5, reads « Saison 5 0/23
23 manquants » and answers « … aucun épisode à récupérer » — **B-380**.

- **B-379** (`open`, « mock layer » micro-wave): the layer answers 200 whatever the contract declares.
  R158 holds a success as `2xx` for that reason.
- **B-380** (`open`, « mock layer »): the season grab counts `seasons.json`, the sheet draws its own
  catalogue; 13 of 49 seasons disagree. The operator ruled « manquant » = aired and not owned, so the
  SHEET's count is the defect. Not built here.
- **B-381** (`fixed #572`, `0e2c25bc1`, the operator's ruling): the message is ranked 57, above every
  layer a verb is pressed from, and is left out of the background `app/focus.ts` marks `inert` so its
  close and « Annuler » take a finger. **The media screen never covered it** — that first reading was
  `inert`. **R159**, `harness/message_over_layers.py`, holds paint and touch; its two mutations (the rank,
  the exemption) are in the entry. **Its second half, the placement, is § 3.6** (`cf1677e5e`).

**After the build, two ruled units landed**: B-381's repair (`0e2c25bc1`, above) and the sheet's act on a
followed show nothing is owned of, never on an unaired season (`1e89d7688`, § 3.3). R158 holds 56 holds
since; its two new mutations — the date clause dropped (Grimsburg's third season offered, 1 violation)
and the gate back to `owns &&` (Agent Elvis offered nothing, 2 violations over 53 executed: the leg's
later holds do not run once nothing is offered) — are recorded here.


### 3.6 The message's placement — RULED and BUILT (`cf1677e5e`)

**The operator's ruling, 2026-09-11, second decision round** — the option as he read it, worded by the
steward: « A. En haut de l'écran quand une couche est ouverte, en bas comme aujourd'hui sinon ». Rank
57 and the `inert` exemption of B-381's repair STAND.

**The measurement that forced it.** After B-381's repair (`0e2c25bc1`) the full suite went RED on four
rules that were green on `6087237ae` (the message sat UNDER the sheet there, 49 < 52):
`deck_verbs.py` 8 EXECUTED / 5 violations, `journey_verbs.py` 16 / 2, `remove_verb.py` 11 / 4,
`stacking.py` 12 / 1. Each, run alone, hit a `SPAN` of the message at the covered button's centre:
« Pas intéressé » y=737, « Re-scraper ce passage » y=740, « Retirer de la liste » y=750. The message's box
is the whole bottom band — x 14→376, about 54 px tall, y ≈716–784 depending on the state
(`acq-now-loaded` 716–770, `acq-follows-list` 730–784, `lib-selection` 788–842). The message covering
them in the rules is the design-note boot hint, emitted by the engine at `engine/legacy.js:31650`
through the same `window.__toast.show` as any verb's answer: measured on a fresh page, it appears ~0.6 s
after load and stays 5.0 s (`MESSAGE_MS` 5000, 6000 with an undo), and each rule's first tap lands 1–2 s
after load. A hand meets it too (`app/message-presence.ts` already records « the first tap of a session
did nothing while the boot hint was up »), and any verb's answer covers the band for 5–6 s, so a second
act in the same layer within that time is covered. `stacking.py` (b)'s probe point (the selection bar's
top edge + 4 px) falls inside the message's box: it read the message painted ABOVE the confirmation
(57 > 56), which is real, not a probe error. **The four rules read right and are not to be touched.**

**What was built** — `cf1677e5e`, one commit, the build and its rule together. DESIGN § 3.1g is the
full account; B-381's entry carries its second half.

- **Step 0, MEASURED before any code**, on the served copy of `cc96f981b` (the head's sources): a
  layer was open at every covered tap — `deck_verbs.py` the sheet (the hit a `SPAN` in `#toast` at
  195, 737), `journey_verbs.py` the sheet (195, 740), `remove_verb.py` the sheet (195, 750),
  `stacking.py` (b) the confirmation (probe 195, 793, inside the message's box 774–828). None on a bare
  screen, so no STOP.
- **The signal**: `app/focus.ts`'s `setBackgroundInert` publishes whether a layer is open through
  `app/layer-presence.ts` — the drawer, a screen, the sheet, the confirmation. **The host**
  (`app/toast-host.ts`) moves a SHOWN message with it, keeps a leaving message's place through its
  400 ms exit, then returns the hidden host to the bottom box the oracle measures. **The drawing**:
  `messageHost`'s `edge` variant — `edge` because `placement` is not in the code vocabulary, and no
  word was added. No line in `legacy.js`.
- ⚠ **A screen is a layer**, as `setBackgroundInert` counts it: on `mediasheet-series` the top
  position covers « Retour » (y 10) where the bottom one covered « Fermer » (y 731). One way out stays
  free in either place. Written here so a reader does not meet it as a surprise.
- **R159** gains five holds on boxes, nothing lifted: seen RED 4 of 16 before the change, green 16 of
  16 after. **m1** (the `top` branch given the bottom string): R159's four placement holds fall AND
  `deck_verbs.py` 8 / 5, `journey_verbs.py` 16 / 2, `remove_verb.py` 11 / 4, `stacking.py` 12 / 1.
  **m2** (the return to rest disarmed): the at-rest hold alone, `[30, 76]` against `[738, 784]`. **The
  confirmation leg was aimed three times**; the rule and DESIGN say why.
- **Increment 7 retaken** on build `c8978713bb5e`, a finger on every step from « Médiathèque » and
  « Incomplets », on « Les aventures de Tintin »: a TAP opens its media screen, a LONG PRESS its follow
  panel. On both, « Récupérer la saison 3 » says « Série suivie et saison 3 demandée — 6 épisodes à
  récupérer. » at the top (box 16–70), on top at its own text at +400 and +1200 ms, not `inert`; a
  finger on its close takes it off screen; the show is `acquiring`.
- ⚠ **The editing tool's formatter hook** (it arrived with the `.claude` move of 2026-09-11) rewrote
  `BUGS.md` whole — 1 152 changed lines — for two added paragraphs, and reflowed this file. Every
  document of this unit was rebuilt from `HEAD` with its own text inserted by script. The hook was
  then narrowed by the maintenance session (`.md`, `.json`, `.yaml` are no longer formatted); **read
  `git diff --stat` before every commit anyway** — it still formats `.py`, `.ts`, `.css` and `.html`.

**Gated on `cf1677e5e`**, every tier written to a file and its verdict read out of it: contracts
« 18 rule(s) and 27 repository guard(s), no violation » · oracle 44 divergences over 23 states, none
naming the message's region · a11y 87 states, 0 violations, light 162 against 162 · **full suite
« 112 rule(s) and 27 repository guard(s), no violation »** (exit 1 is the oracle inside it: the same
44, no `toast`) · hold counts `--compare frontend/maquette/hold-counts-baseline.json`, the baseline's
`failed` read FIRST — 0, taken at `f70ca0295` — then « 112 rule(s), no violation », the same 4 upward
changes (`busy.py` 10 → 16, `cards.py` 65 → 70, `drawer.py` 28 → 30, `persistence.py` 47 → 57), 19 new
since the baseline (R159 at 16, R158 at 56), 11 unparseable on both sides; its exit 1 is drift against
a baseline this wave does not re-record · `make check` exit 0 — 11 220 passed, 4 skipped, 2 xfailed,
maquette units 110 of 110 over 7 files, vitest 134 files and 1 374 tests (its first pass fell ONE
test, the comment corpus floor, `read` 348 against 349: re-recorded, only `read` moved, then whole
again) · `design/dist/build.json` `c8978713bb5e`,
served by the design host. The commits after `cf1677e5e` touch documentation and the comment corpus
record only (`read` 348 → 349 — the new `app/layer-presence.ts`).

### 3.7 Review round two — eight findings, two repaired, six ruled and owed

The reader's report is `/Users/izno/dev/worktrees/review-l21/.review/r2-B.md` (candidate `1e9e7c48e`,
control `8f926738a`); its walks `b01`…`b16` are the shape of the holds below. **Read it whole.**

**Repaired**, each with its rule seen red, its mutation and its run — the entries carry the lines:

- **B1 → B-382** (`a056d6330`): the season act on a followed show's sheet addresses THAT follow. R160,
  `harness/followed_sheet_act.py`: red 24 / 12, mutation 24 / 12 (the phantoms named), green 24.
- **B2 → B-381's third half** (`fadd79086`): on a screen the message sits below the screen's bar, via
  `--tm-screen-bar-bottom` published by `app/layer-presence.ts`. R159 +10 holds: red 26 / 10, mutation
  26 / 10, green 26. DESIGN § 3.1g's « Fermer » sentence corrected in that commit (it was the message's
  own close). Contracts clean and the oracle at the same 44 over the same 23 states on both commits.

**Ruled and NOT built, in this order** (the orchestrator's words, condensed):

1. **B3 — repair.** The redraw throws the panel's scroll to 0 and moves the pressed control out from
   under the finger (Silo 171 → 0; Animaniacs 698 → 0, button y 764 → 1462). Keep the panel's scroll
   across `window.__panel.redraw()` — restore an index or offset, not a pixel guess; `preventScroll` on
   any focus. Hold in R157: `scrollTop` unchanged after the verb on a panel scrolled by a real touch
   stream; mutation = the restore removed.
2. **B6 — repair, RULED.** A screen that closes while its message is up threw the message from the top
   to the bottom in one frame at full opacity (y 16 → 724). **The property is the reader's**: a shown
   message that must change edge LEAVES (its fade) and reappears at the new edge — never a teleport at
   full opacity. Hold in R159: during a layer change, no frame shows the message at full opacity outside
   both its old and its new edge; mutation = the immediate move in `followTheLayers`. **The four rules
   the placement unit turned green (`deck_verbs.py`, `journey_verbs.py`, `remove_verb.py`,
   `stacking.py`) and R159's leg 5 stay green** — a message up before a sheet opens still moves off it.
   ⚠ **The orchestrator's first rule (keep the edge) was withdrawn: it would re-cover the layer's bottom
   actions** — the boot hint back over « Pas intéressé » and the four rules felled again.
   ⚠ **Known, not repaired, by ruling**: WITHIN one edge a shown message still follows the layer's bar by
   a slide at full opacity — a screen with a sheet opened over it, 62 → 16, measured 46 px. Not an edge
   change and not the ruled property; a hand that finds it a defect brings it back with a measurement.
3. **B4 — repair, minimal.** Under `__mocks.setOperationOutcome('grabSeasonForFollow',
   {latencyMilliseconds: 2500})` the pressed act shows nothing and further presses vanish. Draw it as
   TAKEN while its ask is in flight — the button system's existing busy affordance if one exists
   (`aria-busy`, what `busy.py` reads), else `aria-busy="true"` with the disabled look and no text
   change, and one sentence in DESIGN for the operator's walk. Hold: `aria-busy` true between press and
   answer, false after; mutation = the state never set.
4. **B8 — repair.** The season sentence names no show, so a held answer lands over another show's panel
   reading as about it. The eight keys name the show, as the take's sentence does (« … pour « Silo » »);
   say in DESIGN the operator may reword. Hold: the sentence contains the subject's title; mutation = the
   placeholder removed. R158 and R160 build their expected sentences from `fr.json` and will follow.
5. **B7 — repair.** The emptied list's end mark says « La réserve en garde d'autres » under a footer
   saying the loaded reserve ended, and after « Réserve épuisée ». Chosen sentences: three states, three
   keys, the deck's own pattern. R155 or the list's rule reads the words; mutation = the wrong key.
6. **Docs.** B5 — record only: RESUME § 3.1 and R158's docstring say the ten other « Incomplets » shows
   « draw no matrix and no verb », TRUE of the panel and FALSE of the sheet (21 acts on six shows, every
   one answering « aucun épisode »; Furious and President Curtis offered because the sheet counts unaired
   catalogue episodes) — correct both sentences and extend B-380's entry with the reader's table; the
   repair stays B-380's owner's. **File B-383**, not repaired: the « said, not done » class identical on
   the control — « Re-scraper les métadonnées » on the follow panel, « Remplacer la valeur » (secret),
   « Lancer à blanc » (action), « Lancer la veille maintenant » (more) — citing `b13`/`b15`/`b16`; owner a
   follow-up of this lot, scheduled by the operator.

**Rules re-aimed, said out loud in each commit**: R158 stops running `EMPTY_THE_TOAST` (it blinds every
hold to the message on screen, and its comment is false since R159's close leg) — B1's press on the three
twins is already R160's; R157 gains a finger leg (centre tap, hit test, never `element.click`) and B3's
and B4's legs; R159 gains B6's hold once ruled.

**Gates for the rest**: contracts + oracle per commit; **one** full suite at the END of the list,
hold-counts with the baseline file, `make check`, `design/dist` rebuilt; wrapped push; report with named
sections and each mutation line; gauge last. **No full suite has run since `1e9e7c48e`.**

---

## 4. The wave gate

**Gated again on `cf1677e5e`, after the placement unit — § 3.6 carries those verdicts.** What follows
is the earlier gate, kept as it was read.

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

1. ~~**§ 3.4's seven increments**~~ — DONE, and the placement unit after them (§ 3.5, § 3.6).
2. **Round two's six remaining items** — § 3.7, in its order. Then **the pull request out of draft**
   and **round three** — the orchestrator's word, and
   only his. **Round two's reader is spawned by the office**, fresh, one lens, in a worktree pinned
   at this head with a control at round one's. **An agent here dispatches no reviewer and no writing
   delegate**; read-only search subagents are the one thing that may be forked. A round the author
   runs inline is not adversarial whatever its rigour — measured on L12, where the wave's own lenses
   found four findings and the office's independent readers found about forty on the same head, two
   of them blockers.
3. **B-366's real repair** (L13) · **B-367** (settings micro-wave) · **B-371** (L20) · **B-370** ·
   **B-378** (repaired by § 3.4 increment 3) · **B-383** (filed by review round two; a follow-up of
   L21, scheduled by the operator).
4. **`features/acquisition/discover-feed.ts` sits at 399 non-blank lines against a ceiling of 400**
   (B7 brought it there): the next change to it SPLITS it first — owner, the lot that touches it. A
   wave that discovers this by a red `check-frontend-boundaries` has not read this line.

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

⚠ **A docs chain without `set -e` commits a subject its message does not deliver**: an assertion failed
on one file, the chain went on, and the commit carried one file of the three its message named. Stop the
chain on the first failure, and read the commit's `--stat` before trusting its message.

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
