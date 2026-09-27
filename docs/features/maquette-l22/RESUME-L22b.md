# L22b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l22/BRIEF-L22b.md` (governs) and `RULINGS.md` (the lot's own; L22a wrote 1–12,
L22b appends from 13).

## STATE

- Branch `feat/maquette-l22b`, worktree `/Users/izno/dev/worktrees/wave-l22b`. #619 (L22a) merged in at 7ca978d5e
  (re-merged three ways on the real fork point 6f0c987a3: 47 conflicts → 6 unions). Steward `Orch : TM frontend
  [ac1af8]`. main has moved (#621, the references' gesture): merge `origin/main` at the next unit boundary — only the
  generated files conflict; regenerate them (oracle by an accept in one invocation + the script proof; ledgers re-read).
- Head: `git log -1`; pushed: `git ls-remote origin refs/heads/feat/maquette-l22b`.
- DONE: 15a–19-bis-b, merges of #619/#621/main(#617/#618/#622/#623/#624), the triage's docs commit, 20–30 (28 was CUT
  at its opening ≈ 30 → 28/29/30, the rest +2). NEXT: **the MIDPOINT** — [full suite + audit2.py ×10 with its WHOLE
  output kept per draw; the steward's ×10 on main read 0/10, logs ~/Library/Logs/tm-steward/o48-audit2/] → 31 direct-add card (F5) → 32 follow sheet search + grab (F6 +
  F42; likely cut) → 33 « Abandonner » on a follow's card (M1) → 34 one-off acquisitions (round 10 Q1 + Q2; likely
  cut) → 35 sentences (F7, F54, F53) → 36 readers (F41) → 37 → 38 (the dead `acq-follows-pause-empty` still sits in
  the a11y ledgers) → 39 death of Arrivées (F8) → 40 → 41 close (F8, F52, F67, C9; product-intent-map.md:49).
  Files renumbered 31–41 by `git mv`; 29 and 30 live in phase-28's file (cut). STEWARD: engine-data.ts's removal
  (the follows' prefetch declared by its feature, drive.ts's `refillEngineData` door re-pointed) is L22b's, at 40.
  Each re-measured at its opening; > 15
  → cut. **REBOOT Monday 2026-09-28 05:00: open no phase that cannot finish before 04:50.**
- Rules: L22 a..u = R202–R222, R223 #616, R224–R225 L22a. L22b: i R226 set_aside_is_later · (21) R227 · j R228
  not_a_media · l R229 follow_offered · m R230 film_follow_ends · q R231 bar_places · s R232 bar_shares · (22) R233 ·
  R234 discover_page · R235 pull_on_a_card · (28) R236 badges_observed (R-L22-c whole: bar badge + menu button, 28–30) · next free R237. RULINGS: L22b writes 13–29 (13–24 used); L22a's repair round wrote 30–32.
- AUDITOR ORDER 48 (amended): a fall set aside as « load » needs the same rule ≥ 10× here and ≥ 10× on `main` at
  comparable load; any gap is a regression.
- LOGS `~/Library/Logs/tm-l22b/`; mutex `sh scripts/heavy.sh --held`. GATE: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh
  --class browser l22b frontend/maquette/harness/run.sh --contracts --oracle <rule paths>` — NAME every rule a phase's
  change can reach, not only the ones it edits (url_state.py was missed at 19-bis-a); `--a11y` on every gate that draws
  (light ledger 98, may only fall).
- ORACLE ACCEPT inside one invocation (`bash -c 'run.sh …; python3 frontend/maquette/oracle.py --accept'`), then a
  script proves only the named keys moved and the committed file is HEAD's with those keys (never the accept's
  reformatting); bump `tests/scripts/test_oracle.py`'s pin when the state count moves.
- MUTATIONS `sh scripts/mutate.sh <path> "<expr>" <rule>` on a CLEAN tree — never edit while one runs. PUSH at EVERY
  phase end: `sh scripts/heavy.sh --class test l22b git push -u origin feat/maquette-l22b`, its own command.
- Traps: `--accept` rewrites the whole reference; a closed `#dlg` / `#sheet` keeps the last box (B-554, RULINGS 7, 13,
  20); the entry page's tab rewinds the stack; read `data-follow` by value; new data-*/identifier words need
  `scripts/code-vocabulary.txt`; a live rule may only name an event the backend emits; zsh does not word-split `$var`
  in loops; a transient `index.lock` (the status line) — retry the git write, never delete the lock.

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
- 2026-09-27 stood down at 69 % after 19-bis-b (the triage's docs commit is the next unit, for a fresh session).
- 2026-09-27 (successor « Agent : l22b 2 ») merge of #619 (5e5ecd052): git's base was the old main, so 47 files
  conflicted; re-merged three ways on L22a's head 6f0c987a3 → 40 clean, 6 unions (follow-facts, card-markup, fr.json,
  handlers/staging, handlers/acquisition, RULINGS). handlers/acquisition.ts merged at 403 non-blank lines (> 400): my
  phase-18 comment tightened, said in the body. Oracle merged key by key. Commit 7ca978d5e. Gate 1 (`merge-gate.log`)
  RED: url_state.py « every page the model declares is one this rule knows how to reach » — MY miss at 19-bis-a (the
  rule is in no --contracts tier and I never named it); RE-AIMED OUT LOUD, fix 91811f599. Gate 2 (`merge-gate2.log`):
  64 rules (48 named) + 26 guards, 0 failed; 10 oracle divergences, five states × (acquisition/body, shell/page), each
  cause named (phase 17's foot and 15a/16's cards under L22a's ruling 32), accepted in the same invocation; the script
  proved exactly those 10 keys moved; aae52da02. `merge-oracle3.log` no divergence; `merge-a11y.log` 0 + light 98/98.
  Pushed aae52da02.
- 2026-09-27 the triage's docs commit (§ B): F51 renumbering (20–27 → 24, 29–35; new 20–23, 25–28), F4 / F50 / F58 /
  C8 / round 8 Q16, Q17, Q19, Q20 / M1, M2, M3, round 10 Q1, Q2, Q6 as dated lines and DESIGN § 7.4; RULINGS 21. Not
  mine and not done: `frontend-architecture.md`'s L22 entry and `product-intent-map.md:49` (the steward's docs PR); the
  regions.json note of F58 (« the four tabs » → « the bottom bar: two to four buttons ») is left to the lot that edits
  regions.json.
- 2026-09-27 phase 20: R230 re-aimed out loud onto the named state again, hold 4 (the chip's light text is the computed
  --color-waiting-text). Red `20-red.log` (after two authoring fixes the guards caught: a class-token selector → the
  chip read by `dataset.tone`; a phase reference in a comment) + `20-red-a11y.log` light 103. Commits 662989abc (feat),
  e5411db6f (oracle by name, pin 125, light ceiling 98 → 88 by --record in the same invocation). Mutation
  `20-mutation.log`: the variant reads the tone → R230 FAIL by hold 4. `20-final.log` no divergence, light 88/88.
  audit2.py R11 fell ONCE (`20-green.log`, no detail — run.sh deletes per-rule logs), green on the three runs after;
  NOT set aside: ×10 here at the midpoint with the output kept, ×10 on main by the steward (R11 also fell on #623's CI).
- 2026-09-27 B-556 / B-557 filed (the operator's verbatim) and placed as phases 21 / 22; 21–35 → 23–37.
- 2026-09-27 phase 21 (B-556): cause read — the pull's isExcluded refused `.swipe`, the rows of « Suivis » and of the
  Médiathèque's list; R223 pulled above the cards. `.swipe` left the exclusion. R235 new (pull_on_a_card.py): red
  `21-red.log` (follows-list, lib-list), gate `21-gate.log` 41 rules (17 swipe drivers) + 26 guards 0 failed, mutation
  `21-mutation.log` (`.swipe` back → FAIL both). Commits 85790103d, bf1eb3ec0 (the comment-reference record's `read`
  514 → 515, the pre-push pytest refused the first push).
- 2026-09-27 phase 22 (B-557): R206 at 390 AND 369 px, counted tabs at « 999 » (« Suivis » draws no count — my first
  draft's premise, corrected out loud). Gate `22-gate.log` 0 failed; mutation `22-mutation.log` (tabTodo lengthened →
  FAIL at both widths). Commit 3551e8125.
- 2026-09-27 phase 23 re-measured ≈ 31 → cut into 23 / 24 / 25; the rest +2 (26–39).
- 2026-09-27 phase 23 (the deletion): deleteStagedMedia + verb + confirmation (neutral case) + the set-aside card's
  second foot and its panel action; R227 new (delete_set_aside.py). Commits c49b6562c, 8c19bd589 (R43 read no card of
  the closed fold — acq-card-set-aside joined its CARD_STATES, re-aimed out loud; mutation 23-mutation3.log).
- 2026-09-27 phase 25 (F40): notFound/doneToday out of the contract, the mock, the seeds; register → unserved. 287acb0c3.
- 2026-09-27 phase 24 (M2): STOP D → RULINGS 22 (the auditor: (a), the case POSED on Lucky, two conditions);
  readStagedMediaCopies, staged-folders.ts, three states; four mutations; STOP A (63 states on shell/dialog, B-554) →
  RULINGS 7 applied. da0ecf77f, 576e90994 (pin 128).
- 2026-09-27 phase 26 (R233): paused follows fold; three readers of the PAUSED follows re-aimed after the gate fell;
  96d37a7ad carried a whole-file --accept by accident (a background run's accept wrote after my restore) — replaced by
  the by-name form in b77bbbe22. NEVER edit while a background run has not returned its notification.
  ORDER 36 (steward): NO gate runs in the background — wait inside the call (≤ 600 s) or in a bounded loop on its log,
  editing nothing meanwhile. RULINGS 23: a state drawing a tab under a layer is named at the opening of a phase that
  touches the tab.
- 2026-09-27 phase 27 (F3): STOP D → RULINGS 24 (only a disagreement waits; POSED on Star Trek as « Star Trek:
  Discovery »; « Corriger » sends the identity held, no candidates screen; demand E = the correction verb, OPEN 9's
  fifth demand). R221 re-aimed out loud; four readers of Star Trek's card re-aimed or repaired (R47 was a real defect:
  the two-sided sentence cropped the poster to 43 % — the card's title is the held side, the sentence names Plex's);
  a guard exemption keyed by line (markup_anchors.py, audit2.py:184) kept by a shorter comment. Commits 571989427,
  2122c49f5, ddb9ce06b, f0566bda1 (pin 129). Mutations `27-mutation-{agree,correct,confirm}.log`, each FAIL by name.
- 2026-09-27 stood down after phase 27 (the context hook's 60 % gate: 63 %); the next unit is phase 28.
- 2026-09-27 (successor « Agent : l22b 3 ») merged origin/main 665788a90 (#624, docs only) clean: 8a9500c43.
- 2026-09-27 phase 28 opened: re-measured ≈ 30 → CUT 28 / 29 / 30 (steward accepted). Read at the opening, and a
  PRODUCT defect F1 covers: Acquisition's bar badge froze on any other page after a live event (a cache read observes
  nothing; only engine-data's boot prefetch filled it). 28 (F1 + C2): `NavigationRow.useBadgeReads`, acq + arr declare,
  `app/badge-reads.tsx` observes per drawn row. R236 red (`28-red.log`: « still reads 3 »). app/ domain ceiling 141 →
  145 (steward accepted). Commit 36bdd1762. Gate `28-gate.log` 66 rules (52 named) + 26 guards 0 failed, no
  divergence. Mutation `28-mutation.log`: EXPRESSION drops `useBadgeReads: useAcquisitionBadgeReads,` → R236 FAIL
  « after a live event empties « À traiter », the badge is gone from the other page — still reads 3 ».
- 2026-09-27 phase 29 (MOVE): engine-data.ts's staging + queue prefetch removed, header corrected; app/ ceiling 145 →
  143 measured. Commit 33dc70d2e. Gate `29-gate.log` 66 rules (52 named) + 26 guards 0 failed, no divergence.
  Mutation `29-mutation.log`: the same EXPRESSION now fells the COLD-LOAD hold too (« … carries the seeded count —
  None »): the declaration alone fills the badge. Steward placed engine-data.ts's removal at phase 40 (a new phase
  before the close if 40's budget does not hold it).
- 2026-09-27 phase 30 (the menu button's badge, M3's no-rights half): `features/system/badge.ts` (`systemBadge` +
  `useSystemBadgeReads`), `app/menu-badge.tsx` portalled into the static button, the drawer's count named
  `shell/drawer-count`, states menu-system-badge / menu-clear. R236 grew the menu holds, red `30-red.log` (« server 1,
  button None »). app/ ceiling 143 → 147; vocabulary + alert, faults, menu, service. Commit 567462c2e; gate 1
  (`30-gate.log`) fell on two causes → fix 56623d4ac (the drawer re-derived on server state only: « button 3, entry
  2 »; systemBadge threw on fanout/replay's pending-read marker). Gate 2 `30-gate2.log` 68 rules (55 named) + 26
  guards 0 failed; 36 divergences = the two NEW states only; accepted in one invocation (`30-accept.log`), script
  proof, f37b9c460 (pin 131). `30-a11y.log` 0 + light 88/88. Mutations `30-mutation-{wiring,constant,maintenance,
  declaration}.log`, each FAIL by name (MenuBadge unmounted → « button None »; `return 1` → « server 2, button 1 »;
  `return maintenance` → « expected 3, button 2 »; Système's declaration dropped → « server 1, button None »).
