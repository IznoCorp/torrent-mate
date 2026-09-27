# L22b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l22/BRIEF-L22b.md` (governs) and `RULINGS.md` (the lot's own; L22a wrote 1–12,
L22b appends from 13).

## STATE

- Branch `feat/maquette-l22b`, worktree `/Users/izno/dev/worktrees/wave-l22b`, cut from L22a's PR head `6f0c987a3`
  (#619); on L22a's squash onto `main` (the steward names it) merge `origin/main` in at the next unit boundary — its
  repair round touches staging.ts, arrival-slots.ts, requester_line.py, the oracle. Steward: `Orch : TM frontend`.
- Head: `git log -1`; pushed: `git ls-remote origin refs/heads/feat/maquette-l22b` (not pushed since 0d86834fe).
- DONE: 15a, 16, 17, 18, 19, 19-bis-a, 19-bis-b. NEXT: the ONE docs commit of the coherence triage (§ B of
  `/Users/izno/dev/review-archive/coherence-2026-09-27-triage.md`: F4, F50 — minus frontend-architecture, docs/reference
  is the steward's — F51 integer renumbering, F58 L22 part, porting Q16/Q17/Q19/Q20/round 8, C8; texts in
  `coherence-2026-09-27.md`) → 18-ter `--color-waiting-text` (operator 11:0x, light oklch(0.48 0.14 345), dark =
  waiting; phase 18's state `acq-follows-film-at-plex-check` back) → 15b (real delete naming copied / moved — ingest
  COPIES a seeding torrent and MOVES any other, `ingest.py:549-561`; a new operation + demand; two states; Q2 both;
  F40; R227) → 18-bis paused follows fold (R233) → F3 (a new phase) → 20 HELD (F1+C2 at its opening) → [MIDPOINT] →
  F5 → F6+F42 → 21 (F7, F54) → 22 (F41) … 27. Each re-measured at its opening; > 15 → cut, one message.
  Orchestrator now `Orch : TM frontend [ac1af8]`.
- Rules: L22 a..u = R202–R222, R223 #616, R224–R225 L22a. L22b: i R226 set_aside_is_later · (15b) R227 · j R228
  not_a_media · l R229 follow_offered · m R230 film_follow_ends · q R231 bar_places · s R232 bar_shares · (18-bis)
  R233 · R234 discover_page · next free R235. RULINGS: L22b writes 13–29 (13–20 used); L22a's repair round from 30.
- AUDITOR ORDER 48: a fall set aside as « load » needs the SAME rule 10× here and 10× on `main` at comparable load;
  any gap is a regression. outbox.py R107 is a race in the rule's own read, on `main` too (L22a's repair) — say so.
- LOGS `~/Library/Logs/tm-l22b/`; mutex `sh scripts/heavy.sh --held`. GATE: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh
  --class browser l22b frontend/maquette/harness/run.sh --contracts --oracle <rule paths>`; `--a11y` on every gate
  that draws (light ledger 98, may only fall).
- ORACLE ACCEPT inside one invocation (`bash -c 'run.sh --oracle; python3 frontend/maquette/oracle.py --accept'`),
  then a script proves only the named states moved; bump `tests/scripts/test_oracle.py`'s pin in the same commit.
- MUTATIONS `sh scripts/mutate.sh <path> "<expr>" <rule>` on a CLEAN tree — never edit anything while a gate with
  mutations runs (refused twice here). PUSH `sh scripts/heavy.sh --class test l22b git push -u origin
  feat/maquette-l22b`, its own command; a refusal = STOP with its exact text.
- Traps: `--accept` rewrites the whole reference; a closed `#dlg` / `#sheet` keeps the last box (B-554, RULINGS 7,
  13); `go()` commits through a view transition that closes a panel opened with it (a state opening a screen and a
  panel races — `acq-resolution-not-media` opens its choice alone, BACKDROP ≠ product); the staging list is not read
  on « À traiter » until a screen asks; a rule reading an attribute by PRESENCE makes the markup guard treat it as a
  boolean (read `data-follow` by value); the entry page's tab rewinds the stack; new data-*/identifier words need
  `scripts/code-vocabulary.txt`; a live rule may only name an event the backend emits (check-live-relay).

## LEDGER (append-only)

- 2026-09-27 phase 15 opened: re-measured ≈ 29 (ruling 16's four acts) → CUT 15a / 15b (steward accepted; 15b waits
  for Q1). 15a: R226 red (`15a-red.log`, 5 holds + markup guard), move, readers re-aimed out loud (R57 leave half,
  actions.py, two_picks.py t6 — the latter now moves the list by the queue's `resolve`: no finger act takes a dense
  staging folder out today); 15a ≈ 16 by its end (two readers found beyond the opening's re-runs, and the candidates
  screen's guidance sentence) — said here. Commits c19ed60d3 (feat), 2918d4d19 (oracle accepts acq-card-set-aside
  by name, pin 122 → 123). Gate `15a-gate.log` 32 rules + 26 guards 0 failed, oracle 0; `15a-a11y.log` 0 + light
  98/98; mutation `15a-mutation.log`: EXPRESSION removes staging.ts's `if (… === LEFT_AS_IT_IS) return { ok:
  setAside(asked) };` → R226 FAIL « and it is still set aside after both reads are asked again » (and four more).
  Vocabulary gained « aside » (the contract's own token).
- 2026-09-27 phase 16: re-measured ≈ 14; the « Annuler » calls the declared inverse (DESIGN § 3.4), dated line in
  the phase file. R228 red (`16-red.log`), move, STOP A → RULINGS 13 (42 states on shell/sheet-content only, the
  closed #sheet — B-554 extended), audit2's CancelledError repaired (a cancelled read opens nothing), producers.py
  grown by `not-media` out loud. Commits e14a2f15c (feat), 61b09ac99 (oracle, script proof in the body, pin 124).
  Gate `16-gate.log` 31 rules + 26 guards 0 failed, oracle 0; `16-a11y.log` 0 + light 98/98; mutation
  `16-mutation.log`: EXPRESSION replaces the verb's `await send("POST", path, { destination })` by `undefined` → R228
  FAIL « the reclassification is answered, and the message says the destination » (and « the card is in neither »).
  Vocabulary gained « reclassify ».
- 2026-09-27 phase 17: re-measured ≈ 10; the one real subject is « Les Zinzins de l'Espace » (dense « En vol »,
  TVDB-identified, no follow); states declared at the opening: acq-now-loaded, acq-card-rungs, acq-card-waiting.
  R229 red (`17-red.log`; its first draft read `[data-follow]` by presence, which made the markup guard treat
  `data-follow` as a boolean — re-read by VALUE). Commits c67a904e9 (feat), d612e9323 (oracle, 3 states, script
  proof). Mutations (`17-mutation-{1,2,3}.log`): arrivals create follows (staging.ts arrivalsOf pushes a follow) →
  FAIL « a tap changes the follows list by exactly one » (14 → 26: the follows cache re-reads only at the tap);
  `|| ids[SERIES_PROVIDER] == null` removed → FAIL « no film and no followed series carries it »; follows-tab rows
  given a requester → FAIL « « Suivis » draws no card born of an arrival ». The gate then caught phase 16's state
  measured mid-fade: fix 9f61747fd (the choice opened alone over « À traiter », BACKDROP ≠ product, steward
  accepted) + 658c9b96b (oracle accepts its screen-resolution/body by name; a second pass read no divergence).
  Final gate on 658c9b96b (`17-final.log`): 32 rules + 26 guards 0 failed, oracle 0; `17-final-a11y.log` 0 + light 98/98.
- 2026-09-27 phase 18: STOP D → RULINGS 14 (a derivation from Wicker's real row; the event is the last rung done,
  carried on `ItemProgressed` — the live-relay guard refuses an event the backend does not emit; the engine's timing a
  demand owed, DESIGN § 6.2). R230 red (`18-red.log`), commits e70c41f20 (feat), 5dce183de (oracle). The drawing gate
  raised the light ledger 98 → 103 (the state redrew « Suivis »'s `waiting` chip) → RULINGS 15 (repair the variant,
  never re-tone) → 16 (no existing token passes, 2.98:1; the state leaves, `--color-waiting-text` goes to the operator
  through the auditor). Fix ccf142e3b (state removed, reference and pin back to 124). Gate `18-gate2.log` 30 rules + 26
  guards 0 failed, oracle 0; `18-a11y2.log` 0 + light 98/98. Mutations: `isVerifiedInPlex` reads the rung before the
  last → FAIL « while its last rung is pending, « Wicker » is in « Suivis » » (`18-mutation2-1.log`); the film-only
  filter dropped → FAIL « a followed series confirmed in Plex … is still there » (`18-mutation2-2.log`). The first
  mutation run was refused on a dirty tree (I had edited the resume during the gate) — never again.
- 2026-09-27 phase 19: re-measured ≈ 11 (RULINGS 17: no copied states; journey.py a sixth reader). R231 red
  (`19-red.log`, « Système is not in the bar »); R232 written green. Commit 7a7a697c8 (amended twice, unpushed: the
  first gate fell on four readers my grep missed or I re-aimed wrong — persistence.py counted four buttons,
  scroll_memory.py left by Système, and locks.py / queued_by_hand.py clicked the menu's SVG; the entry page's tab
  rewinds the stack, so scroll_memory.py leaves by a tab read off the bar). Mutations (`19-mutation-{1..4}.log`, on
  087794d96, the mutated files unchanged since): `sys` inBar back → R231 FAIL « Système is not in the bar »;
  `basis-1/4` → R232 FAIL « each button is 1/3 of the bar »; `flex-1` dropped → same; every row inBar → FAIL « the
  table gives the bar between 1 and 4 places ». The first mutation run was refused AGAIN on a dirty tree (I edited
  readers while it ran). Gate `19-gate2.log` on 7a7a697c8: 32 rules + 26 guards 0 failed, oracle 0; `19-a11y.log`
  light 98/98. The oracle warns its reference's base 5de78a1e is not an ancestor (my amended fix) — metadata only,
  the steward re-records at the merge.
- 2026-09-27 phase 19-bis: ≈ 20 → cut (RULINGS 18). 19-bis-a: R234 red (`19bisa-red.log`) — CONTAMINATED in part: I
  edited sources after the build, and the two assertions reading source (« the table marks « Découvrir » a page of the
  bar », « the address model declares its address ») were not red on that build; the three carrying the claim (no
  button, no page, `/discover` cold → not found) were. Commits a639bec28 (feat; frame ceiling 132 → 141, RULINGS 19),
  24906af99 (oracle: 39th region discover/body; 8 declared states; 3 pinned by RULINGS 20; script proof in the body).
  STOP A → RULINGS 20 (acq-add-empty, acq-add-results, drawer-navigation inherited `acqTab` — pinned; B-554 gains a
  line). My earlier `--record` had blessed 2 lot/date references in bar_shares.py — removed, baseline back to 0.
  Gate `19bisa-gate.log` 34 rules + 26 guards 0 failed, oracle 0; `19bisa-a11y.log` 0 + light 98/98. Mutation
  (`19bisa-mutation.log`): the discover row `inBar: false` → R234 FAIL « the table marks « Découvrir » a page of the
  bar » and « the bar carries its button, and a tap lands on its address ».
- 2026-09-27 phase 19-bis-b: R206 (three tabs) and R202's « discover » fallback red (`19bisb-red.log`). Commits
  fa0610743 (feat: the tab dies; six ids renamed by `rename-identifiers.py --values --whole` — discover-full, -posters,
  -deck, -degraded, -exhausted, -loading — the oracle and three a11y ledgers re-keyed, light still 98; RULINGS 1's exact
  substitution for five `__go('…')` strings and one backticked comment: 6; zero left under frontend/maquette; history
  left in BUGS.md, the lot's docs, and `docs/reference/product-intent-map.md:49` — not mine to edit), 12dab6588 (fix:
  the Découvrir page observes suggestionsQuery — R223 fell on discover-full, a pull re-read nothing on the page
  19-bis-a created). The oracle read no divergence; an accept run rewrote 847 lines of noise — reverted. Gate
  `19bisb-gate.log` 42 rules (21 named) + 26 guards 0 failed, oracle 0; `19bisb-a11y.log` 0 + light 98/98. Mutations:
  a « discover » tab put back → R206 FAIL « the three tabs read … »; « discover » kept in TABS → R202 FAIL « « Découvrir »
  remembered … opens « Suivis » »; `acq-discover-degraded` put back in panel.py → RULE CRASHED naming it (« état inconnu :
  acq-discover-degraded ») — RULINGS 1's reading.
