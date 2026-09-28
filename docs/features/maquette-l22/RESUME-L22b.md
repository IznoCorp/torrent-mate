# L22b — resume brief (STATE BLOCK ≤ 40 lines, rewritten at every boundary; ledger below, append-only)

Read after `docs/features/maquette-l22/BRIEF-L22b.md` (governs) and `RULINGS.md` (the lot's own; L22a wrote 1–12,
L22b appends from 13).

## STATE

- Branch `feat/maquette-l22b`, worktree `/Users/izno/dev/worktrees/wave-l22b`. #619 (L22a) merged in at 7ca978d5e;
  origin/main 665788a90 (#624) is an ancestor (8a9500c43) — nothing to merge until main moves again. Steward `Orch : TM
  frontend [84baa3]` since the reboot of 2026-09-28 05:00.
- Head: `git log -1`; pushed: `git ls-remote origin refs/heads/feat/maquette-l22b`.
- DONE: 15a–43 (the ledger says each; the MIDPOINT after 30). NEXT: **44** (NEW, steward (A) at 43's opening; INDEX's
  dated line): « doc_fr_2026_final » out of `stuck-loaded.json` — no video file, and `personalscraper/sorter/file_type.py:
  178–200` types an archive-only folder a film only if its NAME carries a video-release signal, so it is OTHER (ruling 1);
  its readers re-aimed OUT LOUD: two_picks.py (THIRD_FOLDER), cards.py (42's dense mutation subject), paths_to_sheets.py
  (« three others wear data-nonmedia »), actions/ident (first nonmedia « Résoudre »), the dense states' oracle; measured
  ≈ 5–6 — RE-MEASURE at the opening. Then (the steward's correction, 2026-09-28 — the list had LOST the readers phase;
  REBUILD it from `ls plan/` at every cut, never from memory): 45 readers, identity and launch bar (file phase-40, ≈ 15,
  OPEN 6 = A, nothing done; its own cut rule: journey.py + common.py apart) → 46 the live rule Système was borrowing
  (phase-41; system/live.ts:95–98's exemptions → check-live-relay.py at its gate) → 47 the death of Arrivées (phase-42,
  F8; R239 reads `navigation.pages.arr` in fr.json at no_sentence_to_arrivals.py:58; page_host.py's 7 « arr » lines) →
  48 the records of a dead page (phase-43) + engine-data.ts's removal (the follows' prefetch declared by its feature,
  drive.ts's `refillEngineData` door re-pointed; R207 named at its gate — the boot re-read may change) + the dead
  `acq-follows-pause-empty` in the a11y ledgers → 49 the close (phase-44; F8, F52, F67, C9; product-intent-map.md:49).
  Phase 44 has no file (INDEX's dated line and RULINGS 33 are its spec).
  Each re-measured at its opening; > 15 → cut.
- Rules: L22 a..u = R202–R222, R223 #616, R224–R225 L22a. L22b: i R226 set_aside_is_later · (21) R227 · j R228
  not_a_media · l R229 follow_offered · m R230 film_follow_ends · q R231 bar_places · s R232 bar_shares · (22) R233 ·
  R234 discover_page · R235 pull_on_a_card · (28) R236 badges_observed (R-L22-c whole) · (32) R237 follow_search · (35) R238 one_card_per_medium · (38) R239 no_sentence_to_arrivals · next free R240. Oracle pin 136. RULINGS: L22b wrote 13–29 and 33, L22a's round 30–32; a new one takes 34.
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
- ORDER (steward [84baa3], 2026-09-28): no heavy gate while the 1-min load (`uptime`) is 6 or above; read it before
  every heavy run.
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
- 2026-09-27 MIDPOINT (the steward told before). Full suite on 9c5db252b (`midpoint-suite.log`, 171 rules, 3 at a time):
  ONE fall, R207 one_ladder.py « the sheet's current rung is the card's » ×4; re-read ALONE on a quiet machine (load
  4): same fall (`midpoint-one_ladder-alone.log`) → charged to the CODE, mine. Bisected: with BadgeReads unmounted it
  still fell (`midpoint-bisect-observers.log`); with phase 28's engine-data.ts it PASSED (`midpoint-bisect-29.log`);
  a read-order diagnostic (a temporary rule, deleted) showed why — R207 collects cards in two states and opened every
  sheet in the second state's world; it agreed only because the boot list re-read the queue under the PREVIOUS state's
  scenario at each reset. Not a product defect: R207 RE-AIMED OUT LOUD (each sheet opened in its card's state), and
  BadgeReads redraws on cache moves (an observer kept a removed query after a reset's clear). Commit 76b54a3ec; gate
  `midpoint-repair-gate.log` 69 rules (56 named) + 26 guards 0 failed, no divergence. The bisect on pre-27 staging.ts
  did not build (`midpoint-bisect-27.log`, nothing measured). audit2.py ×10 in the steward's load shape (3 contract
  partners, host from run.sh, never by hand): 0/10 fell, each draw « 0 violations · 13/13 », WHOLE output kept in
  `midpoint-audit2/audit2-{1..10}.out` (main read 0/10) — the R11 fall of `20-green.log` is not reproduced.
- 2026-09-27 phase 31 opened (F5): R212 extended, red `31-red.log` — and STOP D: « Les Zinzins de l'Espace », a direct
  add, is DOWNLOADING. RULINGS 25: (b) on the operator's texts (a direct add is a card only once finished); no new
  surface in L22b (« Système › téléchargements » does not exist), so Zinzins's card stays in « En vol » until L16
  phase 5 (named gap; its removal and R229's re-aim go to L16's plan, by the steward); 31 keeps condition 3 alone. The
  R212 extension parked on local `wip/l22b-31-r212`.
- 2026-09-27 phase 32 (F6): re-measured ≈ 16 → CUT 32 (search) / 33 (F42 grab), the rest +1 (34–42). R237 red
  (`32-red.log`: no search sent). Commit e71618e71: the tap sends `searchForFollow`, says « aucun torrent trouvé » or
  the count; `searchStarted` retired; panel.py RE-AIMED OUT LOUD. Gate `32-gate.log` 35 rules (15 named) + 26 guards 0
  failed, no divergence. Mutations: toast without sending → FAIL « … sends its own search, once » (`32-mutation-toast.log`);
  zero sentence dropped → FAIL « … says « aucun torrent trouvé » … — said « … : 0 torrent trouvé. » » (`32-mutation-zero.log`).
- 2026-09-28 phase 31 (condition 3 of RULINGS 25): R212 extension cherry-picked from wip/l22b-31-r212 and scoped to
  ARRIVED direct adds; red `31-red2.log` (The Alabama Solution, Conclave). Commit 165a7e094: cell state `skipped`
  (contract enum, strip variants — a hollow dot —, card tone, sheet pip), the mock lays a direct add's four rungs before
  « arrivé » skipped with no time once arrived; DESIGN § 3.2 dated line (template times noted, § 13). Gate 1
  (`31-gate.log`) fell on R207 alone (its own current-rung copy took `skipped` for active) → 2a7b2c9cf RE-AIMED OUT
  LOUD. Gate 2 `31-gate2.log` 66 rules (50 named) + 26 guards 0 failed, no divergence; `31-a11y.log` 0 + light 88/88.
  Mutation `31-mutation.log`: the four laid done again → R212 FAIL « … lived no rung before « arrivé » » ×2 and
  « its sheet gives those rungs no time, none passed » ×2. wip/l22b-31-r212 is spent (local, never pushed).
- 2026-09-28 phase 33 (F42): R225 RE-AIMED OUT LOUD onto `grabForFollow` at the follow's address, red `33-red.log` (it
  counted `takeQueued`). Commit 8c727d8e5: the sheet's act, the release picker and the takeable card send the
  per-follow grab (202, `runUid`, optional `releaseName` — the picker's chosen release, a demand filed in DESIGN § 6.2:
  the register compares no request body); `takeQueued` retired from contract and mock; register regenerated; the
  replay pair gains `/api/acquisition/followed`. Gate 1 (`33-gate.log`) fell on my two misses → 4c0778ce2
  (declared_codes.py asks the grab's 202; lib/ ceiling 28 → 29, measured 28 without / 29 with). Gate 2 `33-gate2.log`
  47 rules (29 named) + 26 guards 0 failed, no divergence. Mutation `33-mutation.log`: the take path back → R225 FAIL
  « the tap sends that follow's grab — 0 → 0 » (and the sheet still waits for the next pass).
- 2026-09-28 phase 34 (M1): STOP D (the one seeded tunnel error, Top Chef, has no follow) → RULINGS 26 (a): the error
  POSED on « Furious » (`poseTunnelError`, state acq-card-follow-error). R222 gained four holds, red `34-red.log`.
  Commit eff6c46a0: on a follow's card the quarantine records the release as tried (the release read no longer offers
  it), the medium is back in « En vol » on « cherché », the follow goes on, the confirmation says « une autre release
  sera cherchée »; door and branch in mocks/handlers/follow-errors.ts, the release read in the leaf releases-of.ts (no
  cycle; staging.ts at 399); DESIGN § 6.2 files the demand and round 10 Q6 = C (unbuilt). Gate 1 fell: Furious is also
  a card of the queue's flight and laid the ladder first, running (`34-diagnostic.log`, a temporary rule, removed) →
  fix: the pose takes it out of flight. Gate 2 `34-gate2.log` 45 rules (25 named) + 26 guards 0 failed; 13 divergences
  = the new state only; accepted (`34-accept.log`, script proof) 982c71877, pin 132. `34-a11y.log` 0 + light 88/88.
  Mutations, each FAIL by name: tried release not recorded → « … no longer offered … »; not put back in flight → « …
  back in « En vol », on « cherché » — None »; the follow removed → « and the follow goes on » (`34-mutation-*.log`).
- 2026-09-28 phase 35: re-measured ≈ 16 → CUT 35 (Q1) / 36 (Q2), the rest +1 (37–43). STOP D (no hand-added arrival
  matches a follow) → RULINGS 27 (a): the real half — « President Curtis » and « Furious », the SAME episode as the
  queue's card in flight and as a staging arrival (read on the seeds at the auditor's condition). R238 red
  (`35-red.log`: the queue's answer names both twice). Commit 44ff14143: the queue composes arrivals first and drops
  from the flight the same ITEM (shared provider id + same episode, `mocks/handlers/same-item.ts`; the episode off
  `secondaryLine`, fragile, a demand for the field); the hand-added half a demand held by no rule. NOTE: the interface
  already joined the two in the DRAWING (`inFlightCards`); the visible defect was the ladder, laid per title by the
  flight first. Gate `35-gate.log` 80 rules (64 named) + 26 guards 0 failed; 2 divergences, acq-card-waiting on
  acquisition/body + shell/page (+58 px: the follows now WAIT behind maintenance with their reason) → ba0c29ebc,
  accepted by name, script proof. `35-a11y.log` 0 + light 88/88. Mutations: the join removed → FAIL « the queue's
  answer names every medium once »; series-only matching → FAIL « … another episode is another card ».
- 2026-09-28 phase 36 (round 10 Q2): re-measured ≈ 16 → CUT 36 / 37 (the offer), the rest +1 (38–44). R158 RE-AIMED
  OUT LOUD (red `36-red.log`: « the act moved the world — a one-off … queued: False », « NO follow is born — status
  after: 'acquiring' », the NewlyFollowed sentence). Commit 5fd094907: `Requester.via` gains `request` (« demandé par …,
  pour cette saison »), the season grab queues a one-off card and begins no follow, `newlyFollowed` and its four
  sentences retire, register regenerated. Gate 1 fell on R158 hold 5 (the surface pressed no longer changes) → STOP →
  RULINGS 28: dedupe (a second tap queues no second card) + hold 5 set aside TEMPORARILY, given back in 37 on
  « demandée ». Fix 34ecc6cb8. Gate 2 `36-gate2.log` 99 rules (84 named) + 26 guards 0 failed, no divergence.
  Mutations: the verb begins a follow again → FAIL « NO follow is born of it » (`36-mutation-follow.log`); dedupe
  removed → FAIL « a second tap queues no second card — 2 one-off card(s) » (`36-mutation-twice.log`).
- 2026-09-28 stood down after phase 36: the context hook's gate (60 %). Next unit: phase 37, for a fresh session.
- 2026-09-28 phase 37 (successor « Agent : l22b 4 »): re-measured ≈ 13 → one phase. Red `37-red.log`: R158 ×8 (« the
  surface pressed reads differently afterwards » GIVEN BACK OUT LOUD, and « the season's row says « Demandée » and offers
  the act no more »), R229's new leg red on the panel only — the one-off card's foot in « En vol » was ALREADY offered
  (the flight's offer reads any requester), said in the commit. Commit 31df61609: `features/media/asked-seasons.ts`
  derives the seasons asked once from the queue (`via` = `request`, season off `secondaryLine`, fragile), both season
  surfaces draw « Demandée » (`season/asked`, `data-asked-season`) in the act's place, the ask re-reads the queue;
  follow-facts offers « Suivre » on the one-off card's panel. Gate `37-gate.log` 84 rules (73 named) + 26 guards 0
  failed, no divergence; `37-a11y.log` 0 + light 88/88. Mutations: no season read as asked → R158 FAIL « Demandée »
  ×4 and « reads differently » on the sheet ×2 (`37-mutation-asked.log`; on the PANEL « reads differently » stays green
  under it — the panel also gains « Suivre » and the one-off's actions, a second visible fact); the panel reads
  arrivals only → R229 FAIL « and its panel offers « Suivre » » (`37-mutation-offer.log`).
- 2026-09-28 stood down after phase 37: the reboot at 05:00 (nothing opens after 37 tonight). Next unit: phase 38.
- 2026-09-28 (successor « Agent : l22b 5 », steward [84baa3] since the reboot) phase 38 opened: re-measured ≈ 17 → CUT
  38 / 39 (F7 needs a landing on a NAMED tab; steward accepted; the rest +1, 40–45). R239 red (`38-red.log`: Système,
  run-detail, acq-now-loaded, the maintenance toast and screen-profile — F54 — named Arrivées or promised « cherché, rien
  trouvé »). Commit b0d9dcd2e: five sentences rewritten, the rule note names the follow and « aucun torrent trouvé »,
  « En cours »'s cross-reference dies with its eight keys and `crossReferenceStrong`, Système's two cross-references
  land on Acquisition (remembered tab); `toArrivals*` rewritten under new keys `toAcquisition*` (the rename tool reaches
  no JSON key). Gate 1 (`38-gate.log`) fell on MY read: from a run's screen the landing rewinds to the entry « / », the
  home page's address — R239 now reads `state.page` and the address leaving /system (amended before any push). STOP A:
  13 states diverged, 4 unnamed in my announcement — relay-* / pwa-* / startup draw « En cours » under a layer (RULINGS
  23: my announcement should have named them), signin / signin-error pin no page and inherit the state before (RULINGS
  20 / 23's precedent) → steward (A): accepted by name. Gate 2 `38-gate2.log` 57 rules (48 named) + 26 guards 0 failed;
  25 divergences = 12 states × {acquisition/body, shell/page} −94.2 px + screen-profile/body +17.4 px, accepted in the
  same invocation, script proof `38-accept-proof.log`, a8a8ea558 (pin unchanged). `38-a11y.log` 0 + light 88/88.
  Mutations: run-screen's `data-go` back to `arr` → R239 FAIL « run-detail: its cross-reference 1 lands on Acquisition,
  and leaves Système — {'page': 'arr', 'path': '/arrivals'} » (`38-mutation-run.log`); the F54 note back → FAIL
  « screen-profile: no sentence promises « cherché, rien trouvé » » (`38-mutation-note.log`).
- 2026-09-28 phase 39 (F7), re-measured ≈ 8. R239 extended, red `39-red.log` (the landing opened « Suivis », no tab in
  the address). Commit 24465a071: a control names the dial it lands on (`data-dial`; « dial » already in the
  vocabulary), `go` passes it unread through the landing door, `landingTab(asked)` opens it without remembering it; both
  Système cross-references name « todo »; DESIGN § 3.7 amended. Gate 2 (`39-gate2.log`) fell on run-detail, and the
  finger walks (`39-walk.log`, `39-before-fix.log`) showed a DEFECT OF MY PHASE 38, invisible to R239 there because it
  read the named state `run-detail`, which lays Système with no entry a finger pushes: walked by finger, the run
  screen's cross-reference stepped back onto Système, and from Système the landing lost its tab. Causes and repair
  (steward approved each step, fix a separate commit 1f6272b8a): `switchPage` stepped home by an UNANNOUNCED `back()`,
  so the floor re-read its own address over the landed tab → `rewind(1 + stackedSurfaces())` + `replacePath`, the
  gesture `switchPageFromLayer` makes (the count justified in place: a rubric counts 0 at the replay); the run screen
  pushed an entry nothing knew of, and `giveTheEntryBackFirst` could not serve it (its replayed tap lands on a control
  the pop unmounted) → `countTheEntry(isOpen)`, new in `lib/stacked-surface.ts`, no capture listener. The branch
  changed REVERSES « home re-reads the floor's address »; its readers: the bottom bar, the drawer, Back from a page, a
  reload (the floor now carries the page's own address). R239 holds, all on finger walks with taps bounded at 5 s:
  Système and a run → « À traiter » with `tab=todo`, the landing standing ON THE FLOOR (`__TSR_index`, § 16 rule 2);
  the bar → home on a floor at « En cours » with « À traiter » remembered, back on « En cours » — GREEN BEFORE AND
  AFTER by design (the bar's behaviour must not change; the steward's « red first » for it was withdrawn: what tells the
  two readings apart is the back() mutation); a run's address loaded cold → the landing inside the application. The
  steward's condition (a), the bar tapped over a run's screen, was WITHDRAWN on a measure: the tap at 5 s falls, the
  screen covers the bar — no finger makes that walk (page-switch.ts's own comment on layers). entry.py was dropped from
  the named rules (steward accepted): it reads the DEPLOYED host tm-design, not this copy, and I had added it by hand
  (Page.goto timeouts at 30 s in `39-gate2.log`, `39-walk.log`). Gate 5 `39-gate5.log` on a7d9c3dec: 71 rules (60
  named) + 26 guards 0 failed, no divergence; `39-floor.log` on 1f6272b8a (the floor hold added, no code moved) 0
  failed, no divergence; `39-a11y.log` 0 + light 88/88. Mutations, each FAIL by name: `back()` put back → « system,
  walked: … drawn follows » and « run-detail, walked: … page sys » (`39-mutation-back.log`); the screen undeclared and
  `rewind(1)` → « run-detail, walked: the landing stands on the floor … floor 1, landed on 2 »
  (`39-mutation-undeclared.log`, `39-mutation-count.log`) — both passed GREEN before the floor hold existed: the landing
  looked right while leaving an entry underneath. One heavy run went unannounced (`39-diagnose.log`); every run is
  announced from now on, a diagnostic included.
- 2026-09-28 phase 40 opened (the readers of the page's states): re-measured ≈ 30 → CUT 40 (F41) / 41 (the twelve
  other readers + three code sites) / 42 (F53); the rest +2 (43–47); steward approved. `acq-todo-loading`: the steward
  ruled (A) BUILD it (DESIGN § 4 row 11 names it; its own three-card skeleton, measured by the oracle) — phase 13's use
  of it, « no tab selected while the count is unread », died with round 7's default-tab rule. R90 (state_surfaces.py)
  RE-AIMED OUT LOUD, arr-error → acq-todo-error, its subject read from fr.json: red `40-red.log` (« acq-todo-error names
  its own subject — looked for « ce qui attend votre main » »: the tab said « En cours »'s `errorNow`). Commit 7c9597cf6:
  `errorTodo`, the two states, pin 132 → 134. Gate `40-gate.log` 38 rules (17 named) + 26 guards 0 failed; 26
  divergences = the two new states only (proof `40-accept-proof.log`), accepted 5406a8db8. `40-a11y.log` 0 + light
  88/88 (134 states). Mutation `40-mutation.log`: `errorTodo` → `errorNow` → R90 FAIL « acq-todo-error names its own
  subject ». B-515 READ on acq-todo-error (triage F41): the tab's SurfaceError has no `onRetry`, so « Réessayer » is the
  delegated `data-retry` → `refetchQueries({ type: "active" })`, no pending or busy sign; the named state's error is the
  harness dial `phase: "error"`, which no answered read can clear — the same traits as on arr-error: honest, no product
  defect; B-515 stays open with its surface now acq-todo-error (owner L13c), for the closing docs pull request to record.
- 2026-09-28 phase 41 (the twelve readers + three code sites): the gate on 5f52976c9 (`41-gate.log`) fell ×5 → STOP D:
  `arr-loaded` (the dense world) had NO successor — `acq-todo-loaded` is the real world, whose staging folders are Top
  Chef (« Relancer ») and the Spider-Man game F53 removes → RULINGS 29 (a): `acq-todo-dense`, « À traiter » in the dense
  world. Measured with a TEMPORARY probe (`41-measure.log`, deleted, never committed): actions, add_screen_opens_fresh,
  audit, ident, resolution_window green there (actions and ident tap the « Résoudre » of a `data-nonmedia` card, the
  folder nobody identified — the tab also holds the queue's tie); R122 (paths_to_sheets) reads ONE identified row there
  — the steward's floor of 2 → its `arr-loaded` entry takes no successor, said in the file; the identified arrival is a
  card of « En cours », read by acq-now-loaded. R139 (panel_label_once): 0 of 25 panels on five surfaces lead to the
  journey, yet the branch LIVES in the source (`follow-actions.ts:75–83`, `primaryAction`'s last fallback: an arrival in
  flight the sort has not identified) → its B-313 hold is SET ASIDE (`BRANCH_SET_ASIDE`), given back in phase 42 on a
  posed case (the file names no phase: check-maquette-comments refuses one in a maquette comment). audit's R10: « Relancer »
  on the real world's tunnel error SENDS and changes no dial — the snapshot counts answered calls, and R10 walks « À
  traiter » in both worlds (6301f4cbb) so the count is exercised. Commits e2751fc7d (test), 4b3cd1819 (oracle: 34
  divergences = acq-todo-dense new + acq-identify / acq-resolution-none / -tie on six regions each, « À traiter » now
  under their screen; proof `41-accept-proof.log`; pin 135), 6301f4cbb, 2ccc6d6e2 (fix: acq-todo-dense's comment moved
  above its entry — the no-French arm could not parse the state; the gate before the accept could not see it). Gate
  `41-gate2.log` 42 rules (24 named) + 26 guards 0 failed. Mutation `41-mutation-r10.log`: « Relancer »'s send removed →
  R10 « acq-todo-loaded : « Relancer » changes nothing » (it did NOT fall while audit read acq-todo-dense alone, where no
  « Relancer » is — hence 6301f4cbb). `41-compare.log` (--only the 14 re-aimed, baseline 5e5ecd05): failed none;
  panel_label_once 3 → 2 and paths_to_sheets 13 → 11 are THIS phase's, said above; cards 68 → 77 and fanout 150 → 152
  are not attributable against a baseline that old (none of this phase's edits adds a hold there — cards lost two states).
  actions.py and ident.py print prose, compared on exit only. `41-a11y.log` 0 + light 88/88 (135 states).
- 2026-09-28 cards / fanout ATTRIBUTED (the steward's demand, before phase 42): a fresh base on cdb19a7c4 (just before
  41), taken by `git checkout cdb19a7c4 -- frontend/maquette` in this tree (no file added since:
  `git diff --name-only --diff-filter=A cdb19a7c4 HEAD -- frontend/maquette` empty; the served copy rebuilt by run.sh;
  restored, `git status` empty; the tool dates the record at HEAD since it reads HEAD — scratchpad only):
  `42-baseline-cdb.log` cards 75, fanout 152. fanout: unchanged by 41. cards: 77 after 41, a net +2 HIDING A FALL OF
  MINE — CARD_STATES lost arr-idle AND arr-loaded (R41/R42, cards.py:165–187, 3 holds per state plus its inline items)
  and only the first had a successor already read; the dense world's cards were read by no card state. Repaired
  1639f7d61 (acq-todo-dense in CARD_STATES, out loud): `42-cards-compare.log` cards 84 (+7: the state's 3 + 4 inline
  items), fanout 152. Mutation `42-mutation-dense.log`, the dense-only folder « doc_fr_2026_final »'s body without
  `data-panel` → cards FAIL « R46 acq-todo-dense « doc_fr_2026_final »: a folder addresses no panel ».
- 2026-09-28 phase 42 (R139's B-313 hold given back), re-measured ≈ 7. Red `42-red.log` with the hold active on the
  current surfaces (« and it reached a panel whose PRIMARY act leads to the journey … 0 such panel(s) »). Commit
  e8a856dac: `mocks/handlers/posed-identity.ts` — `poseUnknownIdentity`, a DERIVATION shown as one (RULINGS 22/24/26's
  precedent): a real dense-world arrival in flight, « Conclave » (not in the library, so no held identity finds its
  sheet; « The Alabama Solution » is in the library), loses its identifiers (`ids: null`, the contract's « no sheet
  identifies it yet »), its strip stands on the identifying step, its chip goes rather than carry a word no row says;
  named state `acq-card-identity-unknown` says it is posed and names the backend read that replaces it (the « identifié »
  rung in progress); R139 reads it. Gate `42-gate.log` 33 rules (11 named) + 26 guards 0 failed; 13 divergences = the
  new state only (proof `42-accept-proof.log`), accepted 1eeb6378f, pin 136. Mutation `42-mutation.log`: the door keeps
  the identity (`ids: null, ` removed) → R139 FAIL « and it reached a panel whose PRIMARY act leads to the journey ».
  `42-a11y.log` 0 + light 88/88 (136 states).
- 2026-09-28 stood down after phase 42 (the context hook's gate is 60 %: 50.5 measured + phase 43's ≈ 10 would cross
  it; the steward's order). Next unit: phase 43 (F53), for a fresh session; its measure is in the STATE.
- 2026-09-28 (successor « Agent : l22b 6 ») phase 43 (F53), re-measured ≈ 13; STOP D at the opening: « check
  doc_fr_2026_final the same way » found the same case → steward (A), verified in the engine (file_type.py:178–200):
  a NEW phase 44 for it, the rest 45–49 (INDEX dated line). Red `43-red.log`: R208 re-aimed OUT LOUD onto Backrooms (dense
  world) FAIL ×7, among them the new hold « acq-todo-loaded: « À traiter » draws no folder the sort filed as no medium —
  ['Marvels.Spider-Man…'] » (the non-media destinations' staging folders, `{id:03d}-{NAME}` of staging-destinations.json);
  R228 re-aimed OUT LOUD onto Backrooms, GREEN before the move (its subject changed, not its verdict — the steward asked
  for a named mutation, below). Commit f425ecb10 (seed row out; acq-card-no-identity and acq-resolution-not-media draw the
  dense world). Gate 1 `43-gate.log` fell ×3, readers of the game folder → 7a99a4c8f, re-aimed OUT LOUD: page_host.py's
  « arr » floor 140 → 130 (measured 135; steward accepted); R207 one_ladder.py and R212 requester_line.py required ≥ 2
  folders dropped by hand → ≥ 1 — A WEAKENING, said so (steward's reserve): the plurality protected a defect seen only
  from a second card — the « arrivé » start not being an accident of ONE strip (the game's [1, blocked] and Top Chef's
  [1, 1, blocked] stood at different strip positions) nor of the first card laid. MEASURED: no surface shows two folders
  dropped by hand any more — stuck.json holds Top Chef alone, stuck-loaded.json doc_fr_2026_final alone (read by neither
  rule's states) and it leaves at 44; after 44 Top Chef is the only one in every seed. The limit is NAMED: the plurality
  cannot be read on the operator's data. STOP A: 32 divergences = 16 states × 2 regions, one cause — the real world's
  « À traiter » and the Arrivées page lose the game's card; arr-idle / arr-queued / arr-running were NOT in my
  announcement (same cause) → steward (A). Gate 2 `43-gate2.log` 55 rules (38 named) + 26 guards 0 failed; `oracle.py
  --accept` takes no names — the whole-file accept ran in the run's invocation (`43-accept.log`), then a script proved
  exactly the 16 moved and wrote HEAD's reference with them (`43-accept-proof.log`) → 0c6ff1369, pin 136 unchanged.
  `43-final.log` no divergence; `43-a11y.log` 0 + light 88/88 (136 states). Mutations, each FAIL by name: the
  reclassification skips the dense list → R228 « the card is in neither « À traiter » nor « En cours » » (`43-mutation.log`;
  on the game it would not have fallen); the game row put back → R208 « acq-todo-loaded: « À traiter » draws no folder the
  sort filed as no medium » (`43-mutation-r208.log`). DESIGN §§ 2.2 item 2 and « Ce n'est pas un média » on real data,
  phases 6 and 16: one dated line each.
