# maquette-conformity — RESUME

## State block (rewritten at every boundary)

- **Branch** `feat/maquette-conformity` (worktree `/Users/izno/dev/worktrees/maquette-conformity`), merged with
  `origin/main` at `9234341fc` (#645). **Orchestrator**: `Orch : TM frontend [077751]`.
- **Design** `/Users/izno/dev/review-archive/conformity-80/REPORT.md` § B, § D; the operator's rulings
  `/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md`. **Plan** `plan/INDEX.md` — 13 phases, one per
  surface (orders 98, 99): read its correspondence table and each page before a phase.
- **DONE: phases 1–10.** 1 the responsive rule · 2 its WebKit pass · 3 components I · 4 components II · 5 Système ·
  6 Réglages and Maintenance · 7 Acquisition · 8 Médiathèque (+ B-578) · 9 the media sheet · 10 the frame. **MIDPOINT DONE** (no real fall to repair). **NEXT: phase 11, Découvrir and Trackers**, **12 the harness
  consolidation** (order 52, budget ≤ 0.60), **13 the close**.
- **The phase gate (order 99)**: static guards on the files touched; each new rule read RED on the old code first
  (`scripts/mutate.sh` with a targeted expression — an old file that no longer compiles cannot be restored whole);
  the oracle ALONE, then `oracle.py --accept` through `/Users/izno/dev/review-archive/conformity-train/accept-oracle.sh`
  (outside the repository: build, publish, host, accept — run it under `scripts/heavy.sh --class browser`),
  and a script proving ONLY the declared states' keys moved; `run.sh --rules` on the touched surfaces' rules;
  R-conformity-a with `TM_RESPONSIVE_STATES` built BY SCRIPT from `harness/states/<surface>.ts` (mind the
  `.map`-built ids: `settings-field-<type>`). Every browser run names `TM_HARNESS_JOBS=2`; pytest `-n 2`.
- **Traps paid for**: the virtual window's pitch is the SHORTEST row drawn and lines are measured only once the
  geometry is the drawing's (a first row that wraps flipped the estimate; stale lanes resized tiles as lines); zsh
  does not split `$VAR` — pass a rule list as `${=VAR}`; the markup arm reads only LITERAL `data-part="…"` — a part passed as a prop or built by
  `FactRows` is invisible to it (emit it literally on a wrapper, or let the component take the prop under the
  attribute's own name, `data-region="…"`, as `Tabs` does); `check-frame-domain` refuses a domain word in
  `ui/`; a new maquette file needs `check-maquette-comments.py --record` in its commit; a merge of `main` moves the
  corpus floor too; the git index lock is taken by another process now and then — retry the commit.
- **Rules born** (letter → file): a `responsive.py` · b `one_tab_bar.py` · c `one_switch.py` · e `on_off.py` ·
  f `state_words.py` · h `empty_place.py` · j `back_control.py` · o `segmented_choice.py` · p `primary_action.py` ·
  s `lens_filters.py` · d `state_chips.py` · g `fact_state.py` · l `legends.py` · k `one_badge.py`. **Owed list** (`OWED` in `responsive.py`): the menu's WebKit « unseen » → the defects fast lane,
  alone.
- **To confirm by the operator** (choices said in the commits): « joignable » the one word of the reachable code;
  the pause « actif » when engaged; the stopped processing in danger.

## Ledger (append-only)

- 2026-09-29 — phase 0: the plan, the train's entry in `docs/reference/frontend-architecture.md` § 4 and
  `IMPLEMENTATION.md`'s « In flight », on the brief's own amendment of the office's « not a lot's to edit ».
- 2026-09-29 — phase 0 amended nine times on the operator's rulings (OPEN 1–4, 8–10, Q20) and the orchestrator's
  ownership of the rule's reds; the plan grew from 14 to 29 phases.
- 2026-09-29 — phase 1: R-conformity-a read RED first on `runs-list` (bevel · runs/row, R1). First full pass 254 s
  (run.sh printed 12 of the falls — the rule now writes `TM_RESPONSIVE_REPORT`). Mutations, each falling by name:
  bevel · shell/header, cut · flux/name, cut · flux, outside · shell/header @1280; the overflow arm is proved only by
  its preformatted branch (run/log). Found: `card/requester` drawn at zero width at every width (phase 5).
- 2026-09-30 — phase 2: the WebKit pass read contrasts wrong until colours went through a canvas (WebKit answers
  `oklch(…)`); its first full sweep read 28 states « unseen » that a pushed screen, the startup or sign-in screen or
  an `inert` page covered on purpose — skipped by name. Its one real red: the menu icon drawn 0 × 0 in WebKit, light
  and dark. Mutation: the bottom bar's ink = its background → unseen · bottom-bar, both schemes.
- 2026-09-30 — phase 3 (components I): `controls.ts` and `frame.ts` at their ceilings, so the tab variants moved to
  `ui/variants/tabs.ts` and the badge to `ui/variants/badge.ts`. Gate: guards green, 8 rules green (responsive on 45
  touched states, owed only), oracle 19 states moved — all the library page's, by the floor — accepted by name,
  proved by script (no other key moved). Orchestrator succession: `Orch : TM frontend [077751]`.
- 2026-09-30 — phase 4 (components II): the notice's variant to `ui/variants/notice.ts`, the legend to
  `ui/variants/legend.ts`, `--color-upcoming-text` declared in both themes, `SurfaceError` takes a tone and its
  words, `ui/topic-row.tsx`. Gate: guards green (two reds of mine repaired first: a stale build for the new token,
  a double import), oracle « no divergence », 5 rules green incl. responsive on 9 states.
- 2026-09-30 — phase 5 (Système): runs list → FactRows + outcome chip (B-576), one outcome map, the raw log wraps,
  the watcher renamed « Traitement automatique des téléchargements » as one levers row with « actif / inactif », the
  locks' row gone, the pause on the same pair, the seeds carry state codes (`Fact.state`, the demands doc rewritten
  by `compare-contracts.py --write`), runs empty → the empty note, the veille's dot drawn, `TopicRow`. Red first on
  the old code: on_off (e), state_words (f), empty_place (h), raw_log's re-aimed hold. The markup arm refused
  computed parts twice (FactRows `parts`, the watcher's part on its row): the readers re-aimed to `[data-run]`, the
  watcher's part emitted literally on its list. Gate: 13 rules green (machine.py re-aimed after its first fall on
  the seeds' tones), oracle 27 Système states moved, accepted by name, proved by script. Vocabulary choices to
  confirm: « joignable » for the reachable code; the pause reads « actif » when engaged.
- 2026-09-30 — phase 6 (Réglages and Maintenance): the settings field draws `toggleSwitch` (L16-bis DESIGN § 1.7
  corrected, dated), « actif / inactif » at the field and at « à blanc », five TopicRows, the back controls' icon,
  « ← » out of the copy, the banners as notices wrapped in `settings/notice`, the save as `actionButton` submit,
  12/16 px margins to steps. Red first: one_switch (c), back_control (j). Gate: 9 rules green; my first state list
  took the `.map` type names for ids (an instrument error, rebuilt); oracle 14 settings states moved, accepted by
  name, proved by script. Stood down at 72 % context before phase 7 (≈ 12 points would pass the 80 % gate).
- 2026-09-30 — phase 7 (Acquisition): the requester's zero width READ in the browser — `actionButton`'s `w-full` made
  `flex-none` in `originRow` took the whole row — repaired (foot `w-auto`, the line wraps), B-583, out of `OWED`.
  `Tabs` on Acquisition; `viewSwitch` text on the add screen; the pick = `actionButton` panelAction primary
  (`candidatePick` → `pickPlace` by the rename tool, which needs `frontend/node_modules`: a temporary symlink to the
  main checkout's, removed after); notice info, Disclosure, muted → neutral, `sectionInnerMarkup`, inline → steps.
  Red first on the old code: o, p. b had no red to read — Acquisition's bar already was the component's drawing and
  Médiathèque's and Trackers' read right since phase 3 — so no `OWED`, proved by mutation (trackersTab 52 px).
  Gate: guards green (B-238 aside), 19 rules green, responsive 46 states × 9 passes 0 fall, oracle « no divergence »
  (region roots only) — nothing to accept. Pre-push wanted `check-maquette-comments.py --record` for the 3 new rules.
- 2026-09-30 — MIDPOINT: `run.sh --contracts` — the 24 contract rules green; 26 of 27 guards green, the one red
  `check-implementation-state.py` (B-238: the In-flight row names no PR yet — owed to the PR's opening). The full
  responsive sweep, 161 states × 9 passes (7 Chromium widths, WebKit light and dark at 390): 0 fall outside `OWED`;
  owed: tab-bar 159, segment/count 23, segment 12, tile/title 44, card/title 47, card/subtitle 5, cast 54,
  connection-notice bevel 18, menu unseen 214. The orchestrator added phase 12 (harness consolidation, order 52,
  its definition ruled) and moved B-578 into phase 8.
- 2026-09-30 — phase 8 (Médiathèque + B-578): titles, sub-lines, tile titles and cast wrap (B-584); the virtual window
  measures every drawn line (resizeItem), its spacers read the virtualiser's measurements, its estimated pitch is the
  shortest row; `segmentTab` wraps. `Tabs` on Médiathèque; the category pills on « Récents » and « Incomplets »
  (`IncompleteShow.category` in the contract and seed, `incompleteIn`), states `lib-recent-movies`,
  `lib-incomplete-movies` (« movies » joins the vocabulary); the count line's `sectionCount`, `linkbtn` and 12 px
  gone. B-578 (orchestrator's ruling A): the candidate's poster carries its identity, the mock composes its sheet,
  Retour comes back. Red first on the old code: s (no pills), resolution_card h11/h12 (the poster PICKED). Re-aimed
  out loud: resolution_card, decision, audit R1, resolution_window, cards R50, lens_filters (no skeleton). Gate: 74
  rules green (81 named with the lenses, the resolution and the sheets), responsive 163 states × 9 passes 0 fall, the
  oracle 16 states accepted by name, proved by script (exactly those keys moved).
- 2026-09-30 — phase 9 (the media sheet): facts as chips (« actif / inactif » for the follow), NoInfo = the empty
  note under the `no-info` part (skeleton places stay), the season fold is `Disclosure` kind season (it now takes
  `data-part` by the attribute's name), the season marks and the trailer's source are chips, the air date text,
  episode dots are `statusDot`, `*-text` tokens on the cells, one `EpisodeLegend` over both drawings with
  `data-state` on episodes and entries, inline spacing → steps. season-list.tsx 382/400. Red first on the old code:
  d, g, l (for l, by the absent legend AND the absent `data-state`), h. The plan's named re-aims needed none;
  screen_addresses.py re-aimed (the place is a block). Gate: 47 rules green, responsive 163 × 9 passes 0 fall, the
  oracle 6 media sheets accepted by name (their body alone), proved by script.
- 2026-09-30 — phase 10 (the frame): the bar's tab button resets the browser's inline padding (a label had 68 of its
  80 px; B-585); the connection notice's action is `connectionNoticeAction`, no bevel; the drawer's Appearance is
  `viewSwitch` text, `app/` imports no feature variant, `segmentSmall` dies; the badges already were one (phase 3).
  Red first on the old code: o (drawer + import) and a (tab-bar, bevel); k green on the old code, proved by mutation
  (the drawer's badge recoloured). Gate: 45 rules green, responsive 163 states 0 fall, `OWED` = the menu alone; the
  oracle moved relay-lost and relay-refused only (STOP A raised, the orchestrator ruled A: accepted by name as item
  2's consequence), proved by script.
