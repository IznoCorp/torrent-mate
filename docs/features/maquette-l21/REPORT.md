# L21 — The tunnel's verbs · REPORT

Pull request **#572**, branch `feat/maquette-l21`, version **0.98.75**. Design:
`DESIGN.md`. Plan: `plan/INDEX.md`. Brief: `BRIEF.md`.

**What the lot was for.** The interface showed what the operator wanted and gave him no way to ask
for it. A season printed « 6/7 · 1 manquant » and offered no verb; the journey sheet — which IS the
tunnel as he sees it — offered one action and neither of the two §20 names; five acquisition acts
were still read by the dying engine. Three declared operations went uncalled. DOIT-3 is « agir là
où l'on observe », and these were the clearest places in the application where one could not.

---

## 1. What landed, phase by phase, with the reading that proves it

| Phase | What it landed                                                           | Rule                              | Register         |
| ----- | ------------------------------------------------------------------------ | --------------------------------- | ---------------- |
| 1     | Three operations declared, their types generated, three demands recorded | —                                 | —                |
| 2     | « Récupérer cette saison » on the seasons panel                          | R125, 16 holds                    | B-301            |
| 3     | « Remettre en file » and « Re-scraper » on the journey                   | R126, 16 holds                    | B-302            |
| 4     | `follow · dropsug · sugmore · pause · remove` leave the engine           | ARM 7 of `check-markup-contracts` | B-315 (a), B-316 |
| 5     | The release screen's take, one sentence, the 260 ms gone                 | R137 + `exits.py`                 | B-322, B-323     |
| 6     | DOIT-4's « En file » pastille, and R124 repaired                         | R138, 7 holds · R124, 15          | DOIT-4           |
| 7     | The panel's doubled action, and B-247's producer half                    | R139, 3 holds                     | B-313, B-247     |

**The numbers that gate the wave**: `legacy.js` **31 467** non-blank against a record of 31 467 ·
`grep -cE "closest\.dataset\.(follow|pause|remove|dropsug|sugmore|take)\b"` reads **0**, from 12 ·
**107 rule files**, 103 at the wave base — R136, R137, R138 and R139 are the four added.

---

## 2. Three decisions that were arbitrated, not chosen

**Road C for the take (phase 5), ruled by the orchestrator.** The plan's mechanism and its own gate
could not both hold: two doors telling themselves apart by what a shared `data-take` value NAMES
keeps the engine calling both, so it goes on naming the attribute — and `lib/verbs.ts` holds ONE
handler per name, so a name two features claim can never reach the registry at all. The collision
was therefore REMOVED rather than guarded: the picker emits `data-pick-release`, the panel keeps
`data-take` and MOVED ONTO THE SAME REGISTRY. That second move is what makes the six-verb grep read
0 while arrivals keeps its name — the engine was `__arrivalsVerbs`'s only reader. B-309's root
cause is closed rather than fenced.

**Road A plus the hand path for the pastille (phase 6), and NO NAMED STATE.** `states.js` is
grandfathered at 786 lines against a record of 786, and the size arm refuses both the growth and
the raise of the record — so no surface born after L19 can be given a named state, and a state
nobody names is a surface the oracle never measures. That is **B-352**, filed rather than worked
around: road B (funding a state by subtracting inside the file) was refused by the orchestrator,
and road C is the operator's. `DESIGN.md` § 4.0 carries the hand path instead — Arrivées → start
the pipeline → a follow → ask for a season — which works because the mock decides `queued()` from
`pipelineState` and not from `setOperationOutcome`.

**Thirty at rest in Découvrir, accepted by the operator.** The « charger plus » repair could not be
a move: the client DRAINED the layer in a loop of twenty pages, which is why the engine's branch
cleared `sugGone` and reshuffled instead. Découvrir therefore holds ONE page — thirty — at rest
rather than thirty-eight, and the oracle's divergences on the discover states carry that ruling as
their reason (D8).

**And one departure from the plan's letter, made deliberately and reported.** The plan's close asks
for the DOIT-3 **and** DOIT-4 rows of the clause map to read `served`. DOIT-4 does. **DOIT-3 stays
`partly`**, because L20's « relancer le watcher » and global levers and L16's tracker policy are
still owed on that clause: writing `served` over them would have emptied the ledger of what is
owed, which is the exact failure `check-intent-map.py` was given a `MUST_NAME_A_LOT` set to
prevent. What L21 serves is written into the row with its two rules. The same reasoning holds the
« Next » row of `IMPLEMENTATION.md` at L21 rather than moving it to L20 before the squash — § 0
elects the first lot the history does not record as LANDED, and a lot in flight is not landed. The
row names L20 as the election and its condition instead.

---

## 3. B-313, and why the rule is not shaped like the bug

The defect was one line wide and the register had already named the rule it should land with, so
that it would not be invented twice: **a panel's actions are counted BY LABEL, and a label
appearing twice is refused.** « Voir la fiche » was guarded against exactly this — `hasSheet &&
(toResolve || toTake || incomplete || isFollowed)`, whose comment says « it is omitted only when it
is ALREADY the primary action » — and « Voir le parcours » had no such guard. The repair is that
condition, mirrored.

**R139 is written around the FAMILY, not the instance.** It raises every panel a finger can reach
on `arr-queued` and `acq-follows-list` — eighteen of them — and refuses a repeated label in any.
Three things it is anchored on, each because the obvious alternative is green over the very
screenshot that opened the entry:

- **It counts LABELS, never destinations.** Both of the operator's two buttons carried the SAME
  destination. A rule reading destinations would have passed the defect it exists for.
- **The subject hold reads `data-journey`** — the action's own destination — and never the French
  word. An anchor on the copy stops measuring the day the copy is retouched, and reports « no
  violation » while doing it.
- **The panels are raised by a FINGER**: the row is scrolled to, its own centre is hit-tested, and
  the click is dispatched at that point by the mouse. A row under a scrim fails here instead of
  being reached through it.

**RED FIRST ON `main`'s PRODUCER, WITH NO MUTATION.** `git diff origin/main HEAD` over
`features/acquisition/follow-actions.ts` was EMPTY when the reading was taken, so the red is
literally main's:

    FAIL no panel offers the same label twice — 18 panel(s) read; arr-queued ·
      « Stuart Fails to Save the Universe (2026) » offers « Voir le parcours » twice —
      ['Voir le parcours', 'Voir le parcours']

That is the operator's own subject, by name. Green after: 18 panels read, no repetition — **and the
panel count is unchanged between the two runs**, so the condition removed the duplicate and not the
case.

---

## 4. The instrument defects this lot paid for — the part worth reading

**Every defect this wave found in its own work was found by RUNNING an instrument, never by reading
one**, and most of them were holds that PASSED over the thing they existed to catch. The mutation
is not a formality at the end; it is the only evidence that a hold has a subject. R137's docstring
argued, at length and persuasively, against the very design the mutation then forced on it.

1. **A DOM observer CANNOT see two writes in one task.** R137's « exactly one sentence » hold was
   vacuous and only a mutation said so: the message host is a component, both writes are batched
   into one render, and the DOM never holds the first value. **B-322's own first reading says
   « sampled every 180 ms, only the second is ever observed » — that sentence describes the limit
   of the instrument it was taken with, and the rule reproduced the limit while quoting it.** The
   count is at the seam now.
2. **A hold green over an unreadable value is not a hold.** R138's first « the pipeline is running »
   read `window.__mocks.mockState()`, which is not published: it answered `unknown`, and
   `unknown != "idle"` passed. It reads the layer AND the interface now, and disagreement fails.
3. **`window.__go` RE-SEEDS the mock layer.** A pipeline started before the state is driven is idle
   again by the time the act lands, so the walk measures a clause it has itself switched off.
4. **R137 counted the prototype's welcome hint** — which the engine toasts on a timer after boot —
   as a sentence of the gesture.
5. **R137 read the screen bar whole**, so its subject came out « Retour Silo » and appeared in no
   message it was comparing.
6. **R124 pressed with `act.click()`**, which dispatches on the node whatever covers it. Proved by
   raising the scrim (`z-[46]` → `z-[60]`): four holds fall now and name the coverer, where the old
   rule would have been ENTIRELY GREEN over a panel no finger could use.
7. **R124's own non-vacuity guard was written wrong first**: it collected Playwright response
   events, and the layer answers IN THE PAGE, so an ask that really happened produced no event at
   all — « nothing was refused » would have been green over an empty list, for ever and invisibly.
   It reads the layer's own record now, keyed by operationId.

8. **R124's « no mutation was answered 409 » hold reads a network the refusal never crosses.**
   It fills its list from Playwright's `page.on("response")`, and the mock layer replaces
   `globalThis.fetch` and answers IN THE PAGE — so no response event can ever carry a 409 from
   it. Green over nothing, permanently, and it is the SAME defect as the one repaired three
   lines above it: that sibling's first version read response events too and was rewritten to
   read the layer's own record; the repair did not travel next door.

⚠ **EIGHT IS A CLAIM UNDER RECOUNT, not a total.** `DESIGN.md` § 3.1c records FOUR instrument
defects **phase 2** found, and at least two of the eight above are those same units seen again:
« `window.__go` re-seeds the mock layer » is § 3.1c's third, and the eighth is an instance of
its first. Worse for the eighth: § 3.1c names it outright — « `busy.py`'s « no mutation was
answered 409 » hold is vacuous for this reason … **Phase 6 owns `busy.py` and repairs it
there** » — so it is not a discovery at all but an obligation this lot wrote down, owned and
missed, while the design document went on saying it would be met. The recount is owed before
the squash.

**What the eighth is still worth taking away is HOW it was established**: one mutation moved
its sibling and not it. The question that
finds these is not « did a hold fall? » but **« did EVERY hold that claims this clause fall? »**
— the fallen set against the set of holds whose text names the clause, which is a set difference
on strings `common.Journal` already prints. A third hold on that same clause was unmoved too and
is **legitimately orthogonal**: it reads whether the INTERFACE says « occupé », which a caught
409 need not. Saying which of the two an unmoved hold is, is the whole difference.

**Three adjacent findings are named and NOT counted**, because saying which is which is the
difference between a count that means something and a count that flatters: **B-363**
(`residue.py` cannot read a factory built from a shared constant) and **B-364** (a hit test that
throws on an SVG instead of pressing it) are both LOUD — one reports, the other raises, and this
table's species is a hold that PASSES; and **B-366** (a grid tile promising a media sheet a
follow has not) is a PRODUCT defect that `audit.py` CAUGHT, so the instrument worked.

**And `check-markup-contracts` caught an eighth that was the wave's, not an instrument's**:
selecting `[data-pick-release]` by CSS attribute PRESENCE enrols a VALUE attribute in the derived
list of boolean states, where the refusal is that it must vanish when false — which an index does
not do. Anchor on `data-part`, read the verb from the dataset.

---

## 5. The register

**Closed by this pull request**: B-301, B-302, B-313, B-315, B-322, B-323 — each `fixed #572`, each
by rule 3: the rule, the mutation, the run.

**Filed by this lot**: B-329, B-330, B-350, B-351, **B-352** (no surface born after L19 can be
given a named state), **B-363** (`residue.py` and the shared constant), **B-364** (the hit test
that cannot press an icon).

**B-247's producer half** is discharged for this wave's surfaces: `persistence.py` now reads
`followsheet-complete`, `followsheet-gaps`, `sheet-journey` and `screen-releases`. Each floor was
READ, by the means that file's own docstring prescribes — raised to 999, and the capture taken from
what the hold printed: 423, 63, 14, and 158 captured on the release screen of which only **7** are
the screen's own, which is what set that floor rather than the union.

**B-085's tally: SEVEN for this wave, 250 + 7 = 257.** Zero by independent readers at the time this
report is written — which, on that table's own evidence, is a figure awaiting its readers and not a
total.

---

## 6. What is measured and NOT done, said rather than implied

- **B-352 is open and it blocks a class of work, not a task.** While `states.js` is grandfathered
  at its own record, no surface born after L19 can be given a named state, and the oracle therefore
  measures none of them. The pastille is the first casualty; it will not be the last.
- **B-363 and B-364 are open**, both in instruments this wave depends on. B-364 does not bite today
  only because the actions R124 presses carry their text across the centre.
- **DOIT-3 is `partly`**, with L20 and L16 named on the half that is owed.
- **The 44 px trade on « charger 30 de plus » goes to the operator at his Mac walk.** The footer
  scale carries no touch-target floor, so the box is about a third shorter than the action-button
  system's. It clears the 24 px minimum and is the size the catalogue's other footer action already
  ships at — but it IS smaller under a thumb, and that is the substance of the amendment rather
  than a side effect of it.
