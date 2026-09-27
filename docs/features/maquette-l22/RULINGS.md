# L22 — the lot's rulings (the steward's, on the implementers' STOPs), one numbered file, non-reopenable

The operator's rulings are not here: organisation rulings 1–15 are in `docs/reference/operator-method.md`, the eleven
on the design's open questions in DESIGN § 7.2. This file holds the steward's rulings on the lot's STOPs, from 1.

## 1 — a state id inside a `page.evaluate` string (auditor, 2026-09-26 16:3x; phase 3)

**The STOP.** `scripts/rename-identifiers.py --values` moves a Python string only when its whole body is an id token, and
its non-values path skips hyphen-adjacent words by design; so `arr-resolution` / `arr-decision` inside
`pg.evaluate("()=>window.__go('…')")` (and one JS array inside a Python string) stayed in five rule files: `actions.py`,
`attrs.py`, `bugs.py`, `decision.py`, `hiding.py` — seven occurrences.

**Ruled A.** Those seven move by an exact substitution of the QUOTED form only (single and double quotes), said out loud
in the commit, and the proof lives outside the tool: (1) the count before on `main` (`frontend/maquette`: 15
`arr-resolution`, 11 `arr-decision`, no other id sharing those prefixes) and ZERO after on the whole repository, every
occurrence kept as history listed by `file:line` with its reason; (2) both quote forms searched; (3) a mutation putting
one old id back into one of the five rules, which must make that rule FALL by name. **B** — a tool arm reaching a state
id inside an evaluate string — goes to the documentation pull request's register as a candidate, not built here.

## 2 — `acq-card-rungs` holds the rungs real rows reach (steward, 2026-09-26; phase 5, STOP D)

**The STOP.** « Eight cards, one on each rung » (DESIGN § 4 row 3) cannot be built from real rows: the queue's families
reach six rungs — notFound « cherché », takeable « attrapé », in-flight « téléchargement » / « arrivé » / « identifié »,
blocked « identifié », doneToday « vérifié dans Plex » — and no row stands at « demandé » or « rangé ».

**Ruled (proposal A).** `acq-card-rungs` is the loaded « En cours » with every family on its ladder: six rungs reached by
real rows, said in the state's label and in R207's docstring. The eight rungs are held whole on `sheet-journey` (« rangé »
opened into its three steps), where R207's order, agreement and one-source holds read them. No derived row: a row nobody
lived is not seeded to fill a picture (§ 13).

## 3 — Acquisition's tabs at a finger's size (steward, 2026-09-26; phase 8, STOP D)

**The STOP.** R206's « every target meets the touch minimum » hold fell on `main` for a reason the design did not
measure: the existing tabs are 99×34 px and the « ⋮ » 40×40 px, and `segmentTab` is shared with the library's lens
segment. No written directive names a touch floor; the harness holds 44 px locally (`add_footer.py`).

**Ruled (proposal A).** Acquisition's bar alone is lifted — its four tabs and its « ⋮ » at 44 px — inside the states
phase 8 already declares on `acquisition/tabs`; the library's segment does not move. B (hold at 34 px) would prove
nothing; C (the shared primitive) crosses the phase's declaration. One register row files the library segment at
34 px (B-552, owner none). Carried out as two floors in Acquisition's own catalogue (`fingerTab`, `fingerMore`,
worn beside the primitives) because `ui/variants/controls.ts` stands at 397 of its 400 lines.

## 4 — the light theme's contrast ratchet does not rise (auditor, 2026-09-26 20:0x; phase 8 gate)

**The STOP.** Phase 8's `--a11y` read the light-theme ratchet at 234 against its ceiling of 147: phases 5 to 7 had
drawn more cards and not run the tier (a cadence fault, said in the RESUME), adding 93 findings — 61 `waiting`-tone
rung chips, 32 plain card feet — every one an instance of a pair already in the ledger.

**Ruled.** A: a `waiting` rung's chip takes `neutral`. B (raising the ceiling) REFUSED: this ratchet may fall and may not
rise. The feet are repaired at the card-foot variant with an existing token that passes on light (`text-primary-text`),
which lowers the feet already counted too; the ledger is re-taken at the value read (98). A repair only a
`theme.css` token could make would have been a STOP to the steward. From here to the pull request, `--a11y` runs on
every phase gate that draws.

## 5 — the tunnel-error card is a derivation from Top Chef's real row (steward, 2026-09-26; phase 9, STOP D)

**The STOP.** The « tunnel error » section of « À traiter » has no real row: the ten real runs hold no errored step
(`pipeline-runs.json`, `errorCount` summed → 0).

**Ruled (proposal a).** « Top Chef Le Concours Parallèle (2026) » is the tunnel-error card — a DERIVATION from its real
stuck row, shown as one: its reason is a step that cannot finish (no episode data, the files cannot be named), and no
pending decision names it. The seed carries the step it stopped at; the layer files a stuck row that carries one and that
no pending decision names under the tunnel error; its reason is drawn in full as the seed words it; its feet are
« Relancer » and, from phase 11, « Abandonner ». Guard: it never reads as resolvable by an identity pick — no « Résoudre »
foot. (b), a section drawn on nothing, refused (§ 13).

## 6 — the Plex-match card is a derivation from Star Trek's real settled row (steward, 2026-09-26; phase 10, STOP D)

**The STOP.** No seed names a Plex match (`git grep -w -i -c plex` over the contract and the mocks → no match).

**Ruled (proposal a), the shape of ruling 5.** « Star Trek: Strange New Worlds (2022) » becomes the « match Plex à
confirmer » card — a DERIVATION from its real settled row, shown as one (`x-seeded-from`): the Plex side names the
identity the pipeline holds, a confirmation to give and not an invented wrong match. « Confirmer » answers demand E and
the card leaves « À traiter »; « Corriger » answers demand E with `outcome: correct` and opens the candidates screen.
(b) draws on nothing (§ 13); (c) would re-create a lived incident as fixture data, which the memory of it does not
license.

## 7 — a closed dialog's box is inherited by later states (steward, 2026-09-26; phase 11, STOP A)

**The STOP.** Phase 11's gate diverged on 63 states it did not name, all on `shell/dialog` alone and all to one box: the
region measures the CLOSED `#dlg`, which keeps the last descriptor's box, and the new `acq-abandon-confirm` became the
last dialog opened before them in the run order (they had inherited the library's `lib-delete-multiple`).

**Ruled (proposal A).** The 63 are accepted by name on `shell/dialog` only, after a script checked that each differs on
that region and on no other; B-554 files the artifact, owner none. Reordering the states would hide it; repairing the
driver's reset would be new apparatus.

## 8 — R175 reads « Suivis » (steward, 2026-09-26; phase 13, STOP)

**The STOP.** R175 (`scroll_keeps_place.py`, B-490) read Lucky's blocked card on « En cours »; phase 9 moved every
blocked card to « À traiter », and phase 9's gate did not run R175. Re-aimed onto « À traiter », its « return from the
resolution » holds fall: four cards leave no poster loading on the return.

**Ruled C.** Neither « En cours » (phase 14-bis reduces it to « En vol » alone, PR #615) nor a tuned « À traiter »: R175
reads « Suivis », the page's long list after L22 and the default tab — `?tab=follows`, loaded scenario, its return path
opening a follow's screen from a card (the one « Suivis » cards open) then Back. B-490's words stay in the docstring and
the re-aim is said out loud: its subject was moved by phases 9 and 14-bis, and B-490's own list no longer exists in its
first form.

## 9 — 14-bis over the ceiling: re-ordered so every gate is green (steward, 2026-09-27; phase 14-bis, STOP D)

**The STOP.** The removal of « À récupérer », « Rangé aujourd'hui » and « Cherché, rien trouvé » felled twelve rules
(the section readers, the card states anchored on those rows, and the take path clicking `[data-take]` on « En cours »):
≈ 20 points against a ceiling of 15.

**Ruled — neither A (a red gate between sub-phases is not admitted) nor B (above the ceiling).** The cut the plan
already uses for Arrivées — readers re-aimed BEFORE the death: (1) **14-ter first**, « Récupérer maintenant » and its
sentence on the follow's sheet (R225), the take path (busy.py, actions.py, page_host.py) re-aimed onto the sheet while
« À récupérer » is still drawn; (2) **14-bis-a**, the readers that do not need the removal re-anchored first
(one_ladder.py / `acq-card-rungs` per ruling 2 re-read, requester_line.py, release_candidates.py, R47's cropped Star
Trek poster understood); (3) **14-bis-b**, the move + R224 + the section readers (cards R41, content, todo_holds,
audit2 R16/R12, seeds_at_rest R128), measured at its opening — above 15 is a STOP again. The move is kept as a patch
file meanwhile, never a stash. Accepted: `acq-now-idle` has nothing in flight in the real world, so it reads « rien en
cours »; `acq-card-waiting` diverges by name with the same « En cours » body.

## 10 — two feet on one line in « À traiter » (steward, 2026-09-27; phase 14-bis-a, STOP A)

**The STOP.** R47 (`cards.py`) fell on the tree before any removal: the « match Plex à confirmer » card (Star Trek:
Strange New Worlds) carries its reason and two stacked feet, grows taller than its 2:3 poster can follow, and the
poster loses 51 % of its artwork against a bound of 40 %. Phase 10's defect, never read: `cards.py` ran in no gate
since the midpoint.

**Ruled (proposal a), extended for coherence.** EVERY card of « À traiter » that carries two feet lays them side by
side on one line — the Plex-match card (« Confirmer » / « Corriger ») and the tunnel-error card (« Relancer » /
« Abandonner ») — one variant of the foot in Acquisition's catalogue, each foot keeping its 44 px floor. Phase 10's
repair, landed in its own `fix` commit; (b) rewrites a ruled sentence, (c) re-opens R47's own defect. `cards.py`
joins every gate that touches a card from now on.

## 11 — 14-bis-b re-cut: the readers first, then the removal (steward, 2026-09-27; phase 14-bis-b, STOP D)

**The STOP.** 14-bis-b measured ≈ 19 at its opening (the move 12, « rien en cours » 1, R224 3, six readers at ½).

**Ruled (the implementer's proposal).** **14-bis-b1** re-aims the readers that do not need the removal, each green
BEFORE and AFTER it (measured with the removal's patch applied, then removed, as for R207): `cards.py` R41,
`todo_holds.py`, `seeds_at_rest.py` R128, `paths_to_sheets.py`, and `content.py` where its hold can move first.
**14-bis-b2** is the move, R224 and audit2's R16 and R12, the diverging states accepted by name. `paths_to_sheets.py`
was green on the wrong subject — it read the « En cours » cards under the add screen: its repair is a FINDING, not a
re-aim, said so in its commit, proved by a mutation emptying the add screen's result rows, and filed as B-555, owner
this lot, fixed in the same commit. R12 « context measured by nothing » is understood before b2's move; not caused by
the removal, it is a STOP with the reading.

## 12 — every foot of « À traiter » is also a panel action (steward, 2026-09-27; phase 14-bis-b1, STOP)

**The STOP.** R43 (`cards.py`), once it read « À traiter »'s cards, fell before any removal: the Plex-match card's
inline « Confirmer » is offered by no action of its panel (« Voir la fiche », « Voir le parcours »). Phase 10's
gap, and phase 11's beside it: R43 read only a card's first foot and never a folder's card.

**Ruled (a), extended by R43's own principle** (« one card, one behaviour — and one panel per medium », README): the
Plex-match card's panel offers « Confirmer » and « Corriger » (the same verbs), and the tunnel-error card's panel
offers « Relancer » and « Abandonner » — every inline foot of « À traiter » is also a panel action. Phases 10 and 11's
repair in its own `fix` commit, R43 green, one mutation per card (the panel action removed → R43 falls by name).
(b), dropping the state from R41's list and filing the gap, would leave a shipped broken promise — refused.

## 30 — the ladder's figure keeps one meaning; a Plex match waits on its current rung (steward, 2026-09-27; round one, A6)

**The question.** The round's brief asked Star Trek's card to read « 7 sur 8 »; the figure is the current rung's
position on every card, so « 7 » would have given the figure a second meaning (rungs passed) or moved every card.

**Ruled.** Neither. The figure KEEPS its one meaning, the current rung's position, for every card — the operator's
ruling 4 reads the tunnel's state ON THE CURRENT RUNG — and no card moves. The brief's « 7 sur 8 » is withdrawn.
Star Trek's current rung is « vérifié dans Plex », PENDING on his answer: the card reads « 8 sur 8 », the rung drawn in
its waiting tone, its word saying it waits for him (« vérifié dans Plex — à confirmer », the shape a blocked rung
already uses), never a done-looking « vérifié »; the panel's episode facts are aligned with the card. Hold in
`plex_match.py`: the current rung of the Plex card is NOT done.

## 31 — R107 races on every boot: its READ is repaired, not the product (auditor, 2026-09-27; round one, A3 STOP)

**The STOP.** The reader measured R107 (`outbox.py`) 3/5 on the branch, 0/5 on main, and order 48 called it a
regression. Measured again, same method, same session: head 3/5, 822a4c1f4 (before the « Suivis » landing) 2/8, and
main 46806a88d **2/8**, the same hold, the same text (« 1 left in the store, 0 → 1 follows »). The hold read the store
the instant the reloaded page reported itself ready; the boot starts the drain at module evaluation and
`__loadingDone` is not its end, so the rule read an envelope that had departed and was not yet forgotten — on any boot.

**Ruled.** Repair R107's READ: after the reload it waits, bounded at 3 s, for the boot's departure to answer (the
follow applied, the store empty), and a new hold reads the envelope's key arriving ONCE. Two mutations make the
proof — the outbox never departs (the wait ends in a named FAIL, never a pass); the departure doubled (the rule falls
on « once »). Red first on main (2/8 with the old read); then green in series on the branch AND on main, at least ten
runs each side. #619's body corrected with the figures. Order 48 amended accordingly.
