# Maquette parity ledger — Acquisition UI

Mission contract: `docs/superpowers/handoffs/2026-08-08-maquette-parity-handoff.md`.
Method: `docs/superpowers/specs/2026-08-08-maquette-parity-method-design.md`
(operator-approved 2026-08-08; hybrid probe/overlay/flows; headless Playwright
driver addendum). Tools live in the session scratchpad `parity/` (probe.js,
probe_diff.py, overlay_diff.py, harness.py, allowlist.json, fixtures.js);
their source is reproduced or referenced in the plan
(`docs/superpowers/plans/2026-08-08-maquette-parity-execution.md`).

Entry format — one entry per fix loop: deployed sha (+ /api/version proof),
probe result (divergence table or « 0 divergences on N selectors »), overlay
% + heatmap path, flows exercised, gate outputs. The DOM probe is the hard
gate; the allowlist is explicit and every allowed pair is justified inline
in `allowlist.json` (never silent).

---

## Entry 1 — L0 calibration (probe + differ) and the two findings

**Setup verified**: staging token re-minted (expires +24 h); maquette served
at `127.0.0.1:8801` (debug copy; prototype file untouched); two isolated
headless contexts, both `documentElement.clientWidth === 390`, DPR 2, mobile,
touch; app context authenticated (`/api/version` → `0.87.0 staging @
dd2ff60e`), service workers blocked (kills the PWA stale-bundle trap for
measurements).

**Calibration probe** (regions: `.viewtabs`, `.seg > button`, `.more`) —
first run surfaced, as designed (tool validated on supposedly-at-zero
regions):

1. **UA-default noise** (maquette has no CSS reset; the app has Tailwind
   preflight): `.more` fontSize 13.33→14, UA button paddings 1px/6px→0 —
   all on an icon-only 40×40 grid-centered button, rendering-identical.
   → documented in `allowlist.json` (7 entries + 2 zero-width-border
   entries on `.viewtabs`).
2. **REAL finding — font mismatch**: in the same browser, `line-height:
   normal` at 13 px resolved 17.55 px (maquette) vs 18 px (app): the
   maquette runs the system stack, the app runs **Geist** (brand webfont).
   Letter widths and every `normal` line box diverge structurally.
   **Operator arbitration 2026-08-08: Geist is canonical** for the
   Acquisition surface; the maquette's system stack is a prototype
   artifact. Measurement consequence: the harness injects Geist at runtime
   into MY headless maquette rendering (file untouched) so both sides
   measure under the same font.
3. **REAL finding — stale pins**: the app hard-pinned `height: 36px` +
   `line-height: 18px` (tabs) and `line-height: 18px` (`.sact`) — values
   measured under the PREVIOUS environment's system font. Under
   Geist-on-both-sides they diverge from the maquette's intrinsic boxes
   (35.5 vs 36 on `.seg > button`, cascading 61.5 vs 62 on `.viewtabs`).
   **Fix `963b2922`**: pins removed; the maquette's verbatim declarations
   (padding 9/0, font 13/600, `line-height: normal` via the parity block)
   now produce identical boxes by construction in any environment that
   loads Geist.

**Gates**: `npx tsc -b --noEmit` OK; `npx eslint src` 0 errors (1
pre-existing warning); `npx vitest run` **1274/1274**.

**Deploy**: branch pushed; staging ours-merge `16621507` pushed;
post-deploy re-probe recorded in Entry 2.

---

## Entry 2 — L0 closed: base typography fixed, all three tools calibrated at zero

**Second real finding**: after unpinning, the app measured 35 vs maquette
35.5 — the « line-height parity » block (`normal`) mis-read the maquette.
Ground truth: the maquette's `.device` declares `font: 14px/1.35
var(--sans)` and `font: inherit` propagates **1.35** everywhere
(13 × 1.35 = 17.55 — font-INDEPENDENT, which the isolated-span experiment
proved: identical 17.0 struts under literal `Geist` on both pages).
**Fix `9f328b91`**: `.mq { font-size: 14px; line-height: 1.35 }` (the
verbatim `.device` base) replaces the `normal` block. App base was
14px/1.5 (preflight) inside `.mq` before this.

**Deploy**: staging ours-merge `3afae935`; `/api/version` = `staging @
3afae935…` verified in the measuring context (service workers blocked).

**Probe (hard gate)**: calibration region (`.viewtabs`, `.seg > button`,
`.more`) → **`0 divergences on 4 selectors`**, with 8 allowlisted pairs
(UA-default noise + zero-width-border props, each justified in
`allowlist.json`).

**Overlay (net)**: `fixtures.js` mirror payloads (maquette demo data
reshaped as real API envelopes, injected via init-script into the app
context only) make the tab badge show « 4 » on both sides. Element
screenshots of `.viewtabs` → **`diff_pct=1.37`** (< 2 target), heatmap
`ov-tabs.heat.png`: glyph antialiasing + sub-pixel edges on the badge and
« ⋮ » dots, no structural hotspot.

**L0 exit state**: probe + differ + allowlist + overlay + mirror fixtures
all validated on the deployed build. Known forward notes: the mirror
fixtures already carry post-L3 fields (`season`/`episode` on to-handle,
`eta_seconds`, `last_search_at/best`) — inert until the UI reads them.

---

## Entry 3 — L1-T4: swipe panes `.act` (icons + tones) + two flow findings

**Fixes deployed** (staging `d8159fce` → `722d33fd` → `b50ade31`):

1. `b61f2418` — verbatim `.actions`/`.act` transplant (84 px column,
   11 px/700, line 1.2, 17 px SVG; grab=primary, pause=muted+`--fg`,
   remove=danger); maquette icons down/pause/trash replace `icon: null`;
   SwipeActions drops Tailwind tone classes for the maquette grammar.
   Obsolete test rule « never a class named grab » removed (the handle is
   `sheetgrab` — named that way in the maquette precisely for this).
2. `256767db` — **population finding caught by the probe** (7 expected
   `.act.pause` vs 5): the maquette's « Cherché, rien trouvé » includes
   ACTIVE `non_verifie` follows (renderNow line 823); the app filtered
   `en_attente` only. Fixed + honest sub « pas encore vérifié sur les
   trackers » (no fake search verdict); pinned by a new MaintenantPanel
   test.
3. `3fc1a3b9` + `72c9244f` — **behavior finding caught by the flow
   exercise**: mouse semantics fire a click after a drag, so a desktop
   swipe opened the detail sheet over the revealed pane (phantom sheet);
   and the first fix wrongly closed the fresh pane. Final contract =
   maquette `justSwiped`: the synthetic click is absorbed 400 ms WITHOUT
   closing; a later tap on the open card settles it first. Pinned by
   SwipeActions tests.

**Probe (hard gate)**, deployed build, mirror data, Maintenant-scoped:
`0 divergences on 16 selectors` (`.act.grab/.pause/.remove` + grab svg).
Allowlist: pane `h` ×3 — TEMPORARY (pane stretches to its card; card
sub-line content converges at L3-T16; re-check and REMOVE at L5).
Differ improvement: zero-width-border style/color pairs are skipped as
rendering-equivalent (preflight declares solid+color on every element).

**Overlay**: swiped-open first takeable card — pane side visually
identical (17 px ‖ icon, 11 px/700 label, muted tone); full-height
overlay blocked by the allowlisted card-height gap until L3-T16
(`size mismatch 164 vs 156` physical px — expected).

**Measurement-integrity hardening** after one transient live-data
screenshot: the harness now FAILS LOUD when the mirror is not active
(sentinel: first followed must be « Silo ») or when a swipe did not open
(transform assertion) — no silent live-data measurements possible.

---

## Entry 4 — L1-T5: pull-to-refresh `.ptr` + a maquette internal contradiction

**Fix deployed** (`c02741e8`, staging `20e31a20`): maquette `.ptr`
chrome (16 px spinner, height-transition grid, `armed` tone, `mq-spin`
keyframe — Tailwind owns `spin`), damped drag model in `gestures.ts`
(`pullHeight = min(80, 0.55·dy)`, `pullArmed = h ≥ 64×0.62`), commit on
the DAMPED armed height (dy ≥ ~72) instead of the old raw 64 px, 44 px
loading held until the real refetch settles. sr-only live region kept
(absolutely positioned — no layout impact). Pinned by gestures tests +
a page test walking damped/armed/loading/collapse.

**Probe**, deployed build, held synthetic touch pull (dy=120):
`0 divergences on 2 selectors` (`.ptr`, `.ptr .spin`), 1 allowlisted:

**⚠ FLAG FOR OPERATOR (T16)** — maquette internal contradiction: the
maquette DECLARES `.ptr` height 66 (style.height=66px, transition:
height) but RENDERS 21.3 px — `.ptr` lacks `flex: 0 0 auto` inside the
fixed-height pane (all its siblings have it) and gets flex-shrunk by
the demo scroller's content, so its rendered height depends on demo
content length. The app follows the DECLARED model (66/80/44 real
pixels). If you prefer the compressed feel seen on the maquette device,
it is a one-line change — say so at T16.

---

## Entry 5 — L1-T6: `.skel` shimmer + `.empty` states (staging `205d1a94`)

`de048a18`: 101 px `.skel` cards (keyframe `mq-sh` — Tailwind owns
`sh`-adjacent names) replace bare « Chargement… » paragraphs in both
panels and the shadcn Skeletons in the add screen (3 per busy container,
sr-only live text kept); `.empty` grammar (block-bold title + advice) on
panel empties, maquette copy VERBATIM for the filter-no-match case.
Pinned by SuivisPanel tests. **Probe**: `.empty`/`.empty b` on
filter-no-match, both sides → `0 divergences on 2 selectors`; `.skel`
class measured via runtime-injected nodes in BOTH contexts (composition
pinned by unit tests) → `0 divergences` once injected at the app's real
section container (the first run measured my injection point's width,
not the class — corrected).

---

## Entry 6 — L1-T7: crossref + grid tiles (staging `a020ed5d` → `f5b7fabf` → `b90ee45f`)

1. `0e4fa27c` — `.crossref` verbatim (1 px DASHED border, 12 px mutedfg,
   right-pinned primary « Contrôle → » span); `.tile.off` opacities
   .42/.55 and the paused tile's `.fr` says « en pause ».
   **Probe crossref**: `0 divergences on 2 selectors`.
2. `38f84c06` — **population finding caught by the probe** (0 `.tile.off`
   rendered): the app's « Tout » pill EXCLUDED paused follows; maquette
   FILTERS say « Tout » = everything (paused dimmed, urgency-sorted
   last), Séries/Films cut by nature only. Fixed + tests re-pinned
   (counts 9/8/1/2, paused rows close the list).
3. `9b9c5e56` — **tile-geometry findings caught by the probe**: grid gap
   12→10 px (column 114 exact), poster box `.p` transplanted (aspect
   2/3, radius 6, NO border, 20/700 initials metrics), badge back to a
   direct `.tile` child, `.nm` 11 px with INHERITED 1.35 line box
   (leading-tight was 13.2 px vs 14.85), `.fr` mono 10 px. Poster
   fallback INTERNALS stay DS-owned (maquette gradients = prototype
   stand-ins for artwork) — allowlisted `.p` backgroundColor with that
   ruling.
   **Final probe**: `0 divergences on 3 selectors` (+1 allowlisted).

---

## Entry 7 — L1-T8: maquette `.dlg` confirmation dialog (staging `b90ee45f` → `436df8f4`)

`b7c2acb8` — `MqDialog` (.dlgscrim/.dlg/.dlgacts/.dlgbtn.danger)
replaces both shadcn Dialogs: §5 replace (maquette copy VERBATIM: « Ce
film est déjà en médiathèque », « …le résultat REMPLACERA la version en
place », verb « Remplacer ») and §9 removal (meta copies — already
verbatim ACT_WORDS — and `confirmer-le-retrait` testid kept). Adjusted
vs maquette, documented in the CSS: `fixed` not `absolute` (the .device
IS the viewport), z 60/61 above the app's z-50 bottom bar. Escape
closes, initial focus lands on Annuler, `inert` while closed.
`76f85ddf` — **probe finding**: `.dlg h3` weight 400 vs 700 — the
maquette rides the UA h3 bold, the app preflight resets it; pinned in
the CSS. **Final probe** (remove dialog opened by swipe+tap on both
sides): `0 divergences on 6 selectors`, no allowlist.

---

## Entry 8 — L1-T9: unified maquette toast + FAB 54 px (staging `ccd1bce6`) — **L1 COMPLETE**

`0033acb4` — `mqtoast()` imperative API + single `MqToaster` host: the
maquette's ONE neutral tone (the message carries the outcome), bottom
82 px above the FAB, real close control, 5 s auto-hide; all 10 sonner
calls on the Acquisition surface migrated (page, watcher ×6,
obligations, cadence) — sonner remains outside Acquisition. FAB to
maquette metrics (54 px, 24 px icon, maquette shadow) — it was 48 px.
Tests: 3 new MqToast pins + Watcher/Obligations/Page test mocks
re-pinned from sonner to mqtoast (tone assertions collapse into message
assertions — maquette has no tones). 1284/1284.

**Safety-net added to the harness**: `fixtures.js` now intercepts
MUTATIONS on `/api/acquisition/*` with a synthetic 200 — no measurement
scenario can ever write to the shared library.db.

**Probes on `ccd1bce6`**: FAB `0 divergences on 2 selectors` (6
UA-noise pairs allowlisted, same family as `.more`); toast at IDENTICAL
text both sides (maquette toast DOM state reproduced — its `toast()` is
closure-scoped) `0 divergences on 2 selectors` (5 allowlisted UA pairs
on the icon-only close button). First run with different messages had
flagged only `h` — style parity held even then.

**L1 exit**: all §7 missing-CSS regions transplanted and measured at
zero on the deployed build: `.act`+icons, `.ptr`, `.skel`, `.empty`,
`.crossref`, `.tile` family + `.off`, `.dlg`, toast + FAB.

---

## Entry 9 — L2 complete (`.sugg`, add-screen sweep, sheets)

- **T10 `.sugg`** (`6f28b2c0` + `6eda31df`): honest recent-searches chips
  (§3.5c — localStorage cap 5, case-insensitive dedup vs follows, tap RUNS
  the search); probe on seeded history **0 divergences on 6 selectors**
  after the add-body double-inset fix (`px-4` removed — maquette #addbody
  never pads; children self-pad; `.rescount` transplanted).
  ⚠ One gate fault this lot: pushed with the FULL suite red (isolated file
  green); fixed in `cd10067e`, rule re-stated (full-suite summary line
  before any push).
- **T11 add-screen sweep** (`1eb2651d`, `15655783`, `ad7eb863`): by-ID
  block MOVED INSIDE the scroll body (maquette #addbody position — old app
  §7 pinned it above), `.resbtn` transplant bugs from lot 5 fixed (radius
  99→6, padding 12→13, `ml-auto` removed), « ✓ Suivi » now ALSO
  title-matches the live follows (maquette isFollowed — old « Correction
  3 » session-only rule superseded), UA margins the maquette rides
  restored (form 14, p 12), idle-empty inline paddings (32/14).
  **Probes: chrome+first-result 0 divergences on 14 selectors** (2
  allowlisted `.rp` poster-fallback pairs), **idle-empty 0/1**.
- **T12 sheets** (`05ab6c0c`, `01f39ce4`, `4061c3c1`, part of
  `b938b5d6`): the « ⋮ » sheet rebuilt in maquette grammar — title+meta
  verbatim, two REAL `.sact` summaries (watcher state + last pass;
  obligations counted via obligationStatus) each EXPANDING its full S3
  panel (function preserved one tap deep), honest `.kv` (« Dernier run
  réussi » only when served), footnote+link. The unserved maquette `.kv`
  rows (« Recherche automatique », « Prochain passage », « Ratio
  global ») are OMITTED, not faked — **flagged as candidate backend
  additions**. Portal traps fixed: `.mq` scope re-applied on the portaled
  SheetContent, sheetbody insets 16/20, `.sheetmeta` line-height 1.35
  re-pinned (shadcn text-sm leaked 1.4286 — class-level fix, all sheets
  benefit). **Probe: 0 divergences on 6 selectors.**
- **C19 conformance** (`563313c7`): first `make check` of the branch
  surfaced pre-existing debt — raw `<img>` in `.rp` → DS `MediaPoster`;
  the transplant's 9 raw colours → verbatim `--mq-*` tokens in
  `tokens/maquette.css` (same computed pixels).

---

## Entry 10 — L3 complete: the four backend additions + the elapsed sibling

- **D — episode label** (`b938b5d6`): `ToHandleItem`/`ToHandleItemModel`
  carry `season`/`episode` from the correlated ProvenanceRow (migration
  017); blocked card opens its reason with « S16E12 · » (maquette).
  Backend 12/12 + panel pins.
- **C — `last_search_at`** (`55d1e2d5`, `0eeb985f`): MAX over ALL wanted
  statuses per follow (a done row witnesses the last pass); the resting
  card reads « rien de conforme au dernier passage · il y a 3 h » instead
  of the next-check substitute; never-searched → verdict alone.
- **B — ETA** (`4c713a6d`, `db66833c`): `TorrentItem.eta_seconds` mapped
  from qBittorrent (8640000 sentinel + negatives → None) and Transmission
  (`eta` added to its explicit torrent_get arguments; −1/−2 → None,
  timedelta handled); exposed on `AcquisitionDownload`; the row shows
  « 12 min restantes » only while downloading AND known.
  ⚠ Second gate fault: `make check` exit masked by an `echo $?` in a
  shell chain — pushed red (docstring-only failure). Fixed immediately;
  gates now verified via `if make check; then`, never `$?` after a pipe.
- **A — best candidate** (`93c0928b`): migration 019 (single transaction
  + user_version bump — the first draft without the bump re-ran the ALTER
  on every store open, caught by the full suite: 74 failures),
  `record_search_outcome(best=)` persists the chosen release's facts and
  a chose-nothing pass CLEARS them; `WantedSearchBest` +
  `last_search_found` + `followed_id` on the API (fail-soft `_row_col`
  reads for pre-migration DBs); the takeable card composes « S02E05 ·
  1080p WEB-DL · 42 sources » — each segment only when known.
  NOTE: the shared acquire.db receives migration 019 at the first staging
  acquisition write (additive nullable column + `.bak` snapshot; required
  by prod at merge anyway).
- **Elapsed sibling** (`b78199d2`): `stageElapsed`/`formatSince` from
  journey timestamps — « depuis 4 min », « ~ » when `estimated_stages`
  taints precision (§13), silence without timestamps.

All lots: frontend 1302/1302, `make check` PASS before push (post-fault
protocol).

---

## Entry 11 — L3 verified on deploy + L4 desktop (staging `9af346d4`)

**L3 content verification** (mirror data, deployed build): **5/5 PASS** —
« S02E05 · 1080p WEB-DL · 42 sources » (A), « S16E12 · titre ambigu — 3
candidats proposés » (D), « il y a 3 h » (C), « 12 min restantes » (B,
after `f40b9299` folded the ETA onto the correlated card — the maquette
puts it there, the first cut only had it on uncorrelated rows), « depuis
4 min » (T17). Two mirror-fixture defects found and fixed on the way
(missing `followed_id` on wanted rows; progress on a 0–100 scale instead
of 0–1).

**L4 desktop** (`4c4f8aa2`): element metrics CONSTANT across widths
(`.seg > button` h 35.5 at 1280 and 1440 — the 390 px truth), column
672 px centered in the content area (the desktop shell adds a nav rail —
window-relative centering is not the contract), tile grid auto-fill →
5 columns, `.dlg` capped 420 px centered. Screenshots at both widths
sent to the operator.

---

## Entry 12 — L5: FULL union at zero, gesture pass, version 0.88.0 — READY FOR T16

**Probe union** (14 region maps, every scenario, one browser, deployed
build `9af346d4`): **ALL 14 PASS at `0 divergences`** — tabs(4),
swipe(16), ptr(2), empty(2), skel(1), crossref(2), tiles(3), dlg(6),
more(6), sugg(6), addidle(1), add(14), fab(2), toast(2) = 67 selector
pairs. Allowlist finalized at 24 pairs, each justified inline
(`allowlist.json`): UA-default noise on icon-only buttons, sticky-bar
background, poster-fallback DS ownership, the `.ptr` maquette
contradiction (operator flag), and the `.act` heights whose divergence
is DEMO-population, not CSS (the maquette lists Pan Am takeable AND
waiting simultaneously — unreproducible under the app's single §13
status derivation). The TEMPORARY `.act` height entries were removed
and re-checked as promised: the CSS contract measures at zero.

**Gesture pass** (deployed build, mirror data, 12 assertions, 3 GIFs
sent to the operator): view swipe both ways (aria-selected proof),
pull-to-refresh armed → loading, card swipe → pane action, card tap →
detail sheet, add round-trip (search → URL `?q=` → fiche navigation →
back RESTORES query and results → second back closes).

**Gates**: `npx tsc -b` 0, eslint 0, vitest **1302/1302**, `make
check` PASS (backend 10 4xx+ tests, C19, module size, typed API,
OpenAPI drift). **Version 0.88.0** (minor — new API fields), single
bump for the PR.

**REMAINING — the operator's T16 gate** (only they close the mission):
phone validation against the 11-point checklist
(`docs/superpowers/plans/2026-08-06-acquisition-mobile-refonte.md`
lines 2433–2456), then the PR flow. Open flags awaiting their word:
1. `.ptr` rendered-height contradiction (Entry 4) — declared model
   shipped; say the word for the compressed feel.
2. The « ⋮ » sheet's unserved maquette `.kv` rows (« Recherche
   automatique », « Prochain passage », « Ratio global ») — candidate
   backend additions if wanted.
3. The maquette demo's Pan-Am-in-two-sections quirk — the app follows
   §13 (one status, one section).

## Entry 13 — 2026-08-08 (post-L5 continuation): fresh state + strengthened probe

**Fresh state implemented and measured** (the last unmeasured card
state). Maquette grammar transplanted verbatim: `.freshtag` pill
(10px/700, primary, closes the meta row) and `.fresh` glow on the row
(primary border + 2px `color-mix` ring + `pop` 0.45s under
`prefers-reduced-motion: no-preference`). `SwipeActions` gained an
optional `className`; `SuivisPanel` applies `fresh` via the existing
`isNew()` (24h). Rendering composition pinned by unit test at REAL
render (freshtag present, LAST in meta row, container `.fresh`);
geometry measured class-level via symmetric injection (the `.skel`
precedent) — scenario `freshinject`, `regions-fresh.json`.

**Probe strengthened**: `boxShadow`, `animationDuration`,
`animationTimingFunction` added to PROPS for ALL regions.
(`animationName` deliberately excluded: keyframes are namespaced
`mq-pop` vs `pop`; duration + timing are compared instead.)

**Two real divergences caught and fixed** by the strengthened pass:
1. Suivis rows carried a year subtitle line the maquette `followRow`
   does not have (title + meta row only) — card height 81 vs 77. Year
   removed (it lives in the sheet). Commit `64a06761`.
2. The toast had NO shadow vs maquette `0 8px 26px rgba(0,0,0,.5)`;
   transition/translateY also drifted (0.22s/8px vs .28s
   cubic-bezier/14px). Fixed via `--mq-shadow-toast` token. Commit
   `4d372f51`.
Also fixed en route: freshtag ordering (app opened the meta row,
maquette closes it) — commit `3818e1fd`.

**Measurement** (deployed build `7a6667e4`, mirror fixtures): UNION
**ALL PASS — 15 regions, 0 divergences** (69 selector pairs incl. the
2 fresh ones), toast now passing with its shadow equal. Gates: tsc 0,
eslint 0, vitest **1303/1303** (fresh pin test added).

## Entry 14 — 2026-08-08: five operator-reported fixes, measured on the deployed build

All five reports from the operator's TODO list, each fixed → deployed →
verified live (staging `948310df`):

1. **Back gesture closed the tab, not the sheet.** Detail sheets were
   React state, invisible to history — Back popped `?tab=suivis` and
   landed on Maintenant. New `useBackCloses` hook: opening a layer
   pushes a same-URL marker entry (preventScrollReset), Back pops it
   and closes the layer, a UI close consumes it, « Voir la fiche »
   REPLACES it so one Back returns under the sheet. Wired on
   FollowDetailSheet (×2), JourneyDetailSheet, the « ⋮ » sheet.
   Verified live: back→sheet closed on Suivis; fiche→one back→Suivis.
2. **Suivis list slow.** API was 66 ms — the cost was FRONT: full-size
   posters (~370 KB TVDB each) + cold query per tab switch. Fixes:
   `posterThumb()` (TVDB `_t`, TMDB `w342`) on card/tile/sheet
   surfaces, prefetch of `followed(active=all)` at page mount,
   staleTime 55 s. Measured live: tab switch → first card 149 ms;
   19/19 poster responses are thumbnails (0 full-size).
3. **Pull-to-refresh dead under a real finger.** The pager carries
   `touch-pan-y`: the browser claimed vertical pans and sent
   pointercancel — the pointer-based pull only ever worked with
   synthetic events. Pull moved to non-passive TOUCH listeners with
   preventDefault at top. Verified with native CDP touch gestures:
   pull arms (`ptr armed h=80px`), release fires 10 acquisition
   refetches. Harness ptrhold scenario updated to touch accordingly.
4. **Owned series not flagged in search.** The §5 ownership pass only
   checked `kind == "movie"`. Series now go through `owned_pairs()` —
   owned as soon as ANY live episode file exists. Regression test
   (mutation-checked: fails on pre-fix code). Verified live:
   « tv Kaamelott 2005 owned=True ».
5. **Views opened mid-scroll.** `ScrollRestoration` mounted in
   RouterBridge (push → top, Back → restored) + explicit scroll-top on
   the Suivis view-mode switch. Verified live: fiche opens at
   scrollY 0; vsw switch → 0.

**Parity re-proof after all five**: UNION **ALL PASS — 15 regions, 0
divergences** on the deployed build. Gates: tsc 0, eslint 0, vitest
**1313/1313**, `make check` **10445 passed** (one
`test_locks_tmp_orphans` flake, passes alone — known isolation noise).

**Process fault logged**: one commit (`fcd4aab8`) was pushed with tsc
RED — a `; echo` masked the exit code (the exact gate-verdict fault
this mission already documented). Repaired within minutes by
`8a5ea20c`; the strict `if …; then` form is now used everywhere.

**Pre-existing quirk observed (NOT a regression, left open)**: opening
any shadcn/Radix sheet clamps `window.scrollY` to 0 (body
`overflow:hidden` scroll-lock), so the list under a sheet loses its
scroll position on close. Predates this branch; consistent with the
operator's stated top-of-view preference, flagged for their call.

## Entry 15 — 2026-08-08 (afternoon): operator batches 2-3 + the Ninja Turtles bug

**Tab inversion (operator directive, overrides the maquette pane order)**:
Suivis first and default (clean URL; ?tab=maintenant explicit; legacy +
?tab=suivis normalized; pager direction inverted); last active tab
remembered (localStorage) and restored on a plain return — deep links
win. Verified live incl. the memory round-trip via /controle.

**Mobile batch, all live-verified on `ca0ea814`**: bottom sheets close by
dragging down from the handle strip (SheetGrabHandle, CDP-touch-verified
1→0 dialogs); media fiche carries the « ‹ Retour » bar (deep-link
fallback to /acquisition); sticky top zone layer-promoted against the
iOS scroll shiver (device confirmation = operator's); end-of-list add
button removed; « ⋮ » sheet swapped its cross for « ‹ Retour » (global
back alignment: screens/panels get the bar, bottom sheets keep the
handle — their own directive); « Dernier run réussiil y a 8 h » was the
maquette `.kv` block never transplanted — rules added, row reads
« Dernier run réussi | il y a 9 h »; ALL zoom disabled
(maximum-scale=1 + user-scalable=no, also kills the input focus
auto-zoom); search result button reduced to TWO states (primary
Suivre/Ajouter, outline-success ✓ Suivi/✓ Ajouté — the outline-warning
« Suivre… » owned state is gone, operator overrides the maquette);
kebab « ··· » removed from all media cards (accidental taps).

**BUG (operator priority) — « Ninja Turtles 2014 bloqué en À récupérer
sans explication » — root-caused, reproduced, fixed:**
- Diagnosis on live data: search fine (14 candidates, best known), but
  the tr4ker download endpoint of the TOP candidate serves the WRONG
  torrent — the D5 info-hash cross-check refuses it
  (`expected 3254a0…, fetched 629061…`, reproduced deterministically).
  Classified transient → the SAME candidate re-picked every pass (4
  attempts), the healthy sibling (same film, 5 seeders) one rank below
  never tried, and the only trace went to Telegram.
- Fix 1 `d1393b7a`: grab walks the ranked candidates on
  TorrentFetchError (bounded FETCH_FALLBACK_CANDIDATES=3);
  auth/circuit stay tracker-wide. Mutation-checked.
- Fix 2 `e4216250` + `e3acf894`: migration 020 persists
  last_grab_reason/last_grab_at on the wanted row (cleared on success),
  served by the API, spoken by the card: « Récupération en échec : le
  téléchargement du torrent échoue (fichier invalide côté tracker)
  (4 tentatives) · il y a 34 min » — live screenshot sent.
- En route: `available` was MISSING from /api/acquisition/wanted's
  status filter, and the takeable-card correlation queried `pending` —
  a status takeable rows never have. The « S02E05 · 1080p · N sources »
  line now actually renders in production conditions (verified live:
  « 1080p BluRay · 14 sources » on the real card).
- Shared acquire.db migrated to v20 manually (additive, prod-tolerant);
  the observed failure recorded truthfully on row 100.
- NOTE for prod: the fallback ships at MERGE — until then the 15:20
  prod grab keeps failing (harmlessly) on the broken candidate.

**Measurement**: UNION **ALL PASS — 15 regions** on `ca0ea814` after
harness realignment (tab clicks by accessible name, default scenario
pins Maintenant, seg pairing active↔active across the inverted order,
toastshow via the sheet, mirror sentinel population-based, fixture
wanted rows on status available). Gates: `make check` PASS (backend
full suite + frontend 1322/1322).

## Entry 16 — 2026-08-08 (evening): batch 4 — the download made visible everywhere

**Ninja Turtles epilogue**: the prod 15:20 grab succeeded on its 5th
attempt (ranking shifted; a healthy candidate topped) and the pipeline
took the film all the way to DISPATCHED. What the operator watched
meanwhile exposed four visibility gaps, each fixed and live-verified on
`1246166e`:

1. **« Nom de release non enregistré » during the whole download** —
   the journey name derived only from disk paths, which do not exist
   between grab and ingest. Migration 021: `upsert_grab` persists the
   chosen candidate's title; `journey_release_name` serves it as the
   last-resort candidate (paths stay more faithful). Shared DB migrated
   v21 + the live row backfilled truthfully (hash-matched on the
   tracker: MULTI VF2 1080p BluRay HDLight x264-OLOBYHD).
2. **No poster on the in-flight card** — identity was NEVER lost
   (tmdb 98566 rides the spine); the journey card passed
   `posterUrl=null`. It now correlates to the follow's poster by
   followed_id.
3. **A live download « visible nulle part » in Pipeline** — it lives
   upstream of « Arrivée » (torrent client). FlowBoard grows an
   upstream « Téléchargement » station (only when something is inbound)
   linking to Acquisition.
4. **« Trailers en cours mais aucun média »** — the badge names the
   RUN's current step, the count names PARKED stock; when they diverge
   the drawer now explains instead of contradicting.

**PWA batch**: install banner moved ABOVE the fixed bottom bar (its
close button was underneath — the « impossible de fermer » on both
platforms), and the iOS variant walks the 3 real steps (Safari →
Partager → Sur l'écran d'accueil). Kanban ticket
**IznoCorp/torrent-mate#421** created and added to the board (Backlog)
for PWA push notifications (Android + iOS) — planning only.

**Gates**: `make check` PASS (incl. migrations chain 21), frontend
1323/1323, UNION **ALL PASS — 15 regions** post-batch.

## Entry 17 — 2026-08-08 (post-batch-4): two truth fixes + the gesture net rebuilt

**A conflated unknown, caught by measuring the render path.** Proving the
release-name fix end-to-end (a patched payload, not the parity mirror)
showed 3 of 5 in-flight cards naming the release and 2 still reading
« Nom de release non enregistré ». Root cause was not the new column: the
card rendered `journey?.release_name ?? "Nom de release non enregistré"`,
folding TWO different unknowns into one sentence — a correlated journey
whose name was never recorded, versus a download tied to NO journey at
all. « Non enregistré » asserts we consulted the record; that is only true
in the first case. Now split (« Acquisition non corrélée » for the
second). Test mutation-checked: it fails on the pre-fix code.

**« Recherche automatique » served** (`0578ca02`) — the last maquette
`.kv` row that could be filled honestly, read from the grab cron's LIVE
schedule via the scheduler registry, never hardcoded. Verified live:
« Recherche automatique | Tous les jours à 03:20 et 15:20 ».
The other two stay OMITTED with their reason recorded in the component
docstring: « Prochain passage » has no computable next-fire (the registry
mirrors the cron in prose only) and « Ratio global » has no data at all
(`ratio_state` holds zero rows — a figure there would be invented, which
is precisely §14's prohibition).

**Gesture pass rebuilt for the new channels — it had gone vacuous.** The
12-assertion pass still drove POINTER events for pull-to-refresh and
asserted tab positions by `nth-child`, both invalidated by today's work.
It was failing loudly on the pull (good) but its two swipe assertions
were passing while certifying the wrong direction (bad — a green test
that checks the old contract). Realigned to touch events + accessible
names, and EXTENDED with the two gestures shipped today: Back closes the
sheet without leaving the tab, and dragging the handle down closes it
(driven by native CDP touch, not synthetic JS). **14/14 pass**, 3 GIFs
regenerated.

**Measurement**: UNION **ALL PASS — 15 regions** on `432fac94`;
`make check` PASS; frontend **1326/1326**.

## Entry 18 — 2026-08-08: adversarial pre-PR review (22 agents) — 15 defects, all fixed

A six-lens review of the day's diff (`12bf25ba..HEAD`), each finding then
handed to an adversarial verifier instructed to REFUTE it. **15 confirmed,
1 refuted.** Every confirmed defect is fixed, with a mutation-checked test
where the behaviour is testable. The ones that mattered:

**The fallback walk blamed the wrong tracker (HIGH, mine, same day).** An
auth error raised while resolving a LOWER-ranked candidate escaped the
loop, terminally abandoned the item, and named the ranked TOP's provider
in the operator alert — sending the operator to fix credentials on a
healthy tracker. The walk now absorbs each candidate's failure, keeps
going across trackers, and concludes on the CULPRIT. Extracted to
`_resolve_walk.py` (the addition had pushed `orchestrator.py` back over
the 1000-line ceiling — 1042).

**A homonym could not be added at all (HIGH, pre-existing).** « Déjà
suivi » was decided by a lowercase TITLE match, and the button was
hard-disabled: with « Dune » (2021) followed, « Dune » (1984) was
declared already followed and could not be added. Identity is now the
provider id. The follows mock was forced to carry `media_ref` like the
real API — it had been letting tests pass against a payload production
never sends.

**A series popped the FILM replacement dialog (HIGH, mine).** Flagging
series `already_owned` (this morning's fix) reached a consumer that
treats the flag as the movie replacement trigger: following a
partially-owned show announced a replacement that will not happen. §5
confirmation is now movie-only; the informative badge stays for both.

**The download station counted finished torrents (HIGH, mine).** The
endpoint lists every grabbed row — seeding, paused, missing included —
so the new upstream station could claim « en cours » for a download
finished hours earlier. Only genuinely inbound states feed it.

**Two open layers closed each other (MEDIUM, mine).** The history marker
was a shared boolean. Giving each hook its own id exposed a deeper
defect while writing the test: opening a layer ON TOP pushes an entry,
which the old logic read as a Back and used to close the layer
underneath. The close is now gated on a POP.

Also fixed: `not_found` (a search verdict) was stamped as a grab failure;
a stale failure survived requeues (now cleared at claim); the failure line
rendered `attempts` — which counts tracker interactions, not retrievals —
as « n tentatives »; the takeable correlation read an unpaginated page 1;
drag-to-close fought a scrolled sheet; a second finger left the pull bar
armed; and the release-name production wiring had zero coverage (the
helper and the column were pinned, the one line feeding them was not).

**Measurement**: `make check` PASS, frontend **1330/1330**, UNION **ALL
PASS — 15 regions** and gesture pass **14/14** on the deployed
`84298c34`. One mirror fixture was corrected in the process: its « Silo »
search result carried a provider id matching no follow, which made the
app render « Suivre » where the maquette shows « ✓ Suivi » — the fixture
was wrong, not the app.

## Entry 19 — 2026-08-08: the spinner that never ended, and 1 MB of raw JS

Two operator reports, one measurement session, two root causes — neither
where the symptom pointed.

**« Le refresh bloque des dizaines de secondes ».** Every acquisition
endpoint was timed on staging first: 10–130 ms, search 1.3 s,
completeness 40 ms. Nothing slow. The cause was that **`fetch` carries no
timeout**: a stalled socket — a phone waking from background, a wifi/4G
handoff, a proxy that accepted the connection and went quiet — waits
FOREVER, and the pull's `invalidateQueries` waits on the slowest query it
triggered. The same rule the shell side has carried since the
omdbapi.com incident (never an unbounded network call) had simply never
reached the web client. Every request now carries a finite budget
(15 s; 45 s for paths that genuinely reach trackers or run pipeline
steps). The spinner is additionally capped at 6 s — past it the bar
collapses and the refetches finish in the background — and a failed
refresh now SAYS so instead of looking like « up to date » (§8).

**« Certains chargements sont très longs ».** Measured, not guessed: the
SPA shipped **1.05 MB of JavaScript raw** — no `content-encoding` header
at all — and **no `Cache-Control`**, so every visit re-downloaded the
whole bundle. Fixed inside the app rather than in the reverse proxy (so
it survives a proxy reconfiguration): `GZipMiddleware` above 1 KB, and
`/assets/*` — whose Vite filenames carry a content hash, hence can never
go stale — served `public, max-age=1y, immutable`. `index.html` stays
revalidated on purpose: caching it would pin the device to an old bundle
and no deploy would ever land.

**Measured on the deployed `7f05938e`**: bundle **1120 KB → 311 KB**
(−72 %) on a cold load, zero bytes on a repeat visit, and API JSON
compressed too (journeys 50 KB → 5.7 KB). Gates: `make check` PASS,
frontend **1333/1333**, UNION **ALL PASS — 15 regions**, gestures
**14/14**.

One test was caught being vacuous while writing it (it asserted on an
empty map without ever calling the code) and was replaced by a real
assertion over the exported budget table — the same defect class the
adversarial review flagged an hour earlier.

## Entry 20 — 2026-08-08: nine operator fixes, incl. the iOS shimmer's real cause

**The shimmer was mine.** Reported twice; the first attempt (compositing
layers on the sticky elements) treated a symptom. The cause: a
permanently-registered NON-PASSIVE `touchmove` listener on the pager —
added with the touch pull-to-refresh earlier the same day. It tells the
browser « I may cancel this scroll », so iOS drops that subtree from the
compositor and routes every frame through the main thread; the content
then scrolls a frame ahead of the `position: sticky` header, which is
exactly what shivers. The listener is now attached ONLY for a gesture
that can become a pull (finger down at scrollTop 0) and removed on
release — ordinary mid-list scrolling keeps the fast path. Pinned by a
test that spies on `addEventListener` and mutation-checked.

**Add screen** — four in one pass: the button moved BEFORE « Déjà en
médiathèque » (the badge appears on some rows only and made the button
dance); changing Tout/Séries/Films returns to the top of the list;
submitting from the on-screen keyboard blurs the field so the keyboard
closes (tapping « Chercher » already did); and closing RESETS the search
— the screen stays mounted, so its state used to survive « Voir mes
suivis » and reappear on the next opening.

**A film's tile badge** dropped the « 1 »: it counted nothing the tile's
own presence had not already said. A dot signals « celui-ci demande
quelque chose » without pretending to be a count.

**Removing a follow now REMOVES it.** `DELETE` called
`set_active(False)` — the exact write the pause button performs. Two
verbs, one effect: the removal never happened and the follow came back
in « En pause ». It now deletes the row and whatever was still queued
for it; rows already handed to the client are KEPT, their acquisition is
real and its provenance must stay readable. The confirmation copy stopped
promising a reactivation and points at « Mettre en pause » for that.

**Add-by-ID: two reports, one cause.** The form followed on submit,
sight unseen, with a hand-typed title — usually none, which is how a
NAMELESS follow was created (blank in the list AND in its own sheet).
New `GET /api/acquisition/lookup` resolves an id into a search result
(title, year, poster, ownership) and follows nothing; the screen renders
it as an ordinary card, so the add stays one deliberate tap. The typed
title field is gone — the provider owns the name — replaced by the
Série/Film choice the lookup actually needs. Server-side safety net for
ANY client: the enrichment now carries the provider title and the create
path uses it when the client sends none; « Sans titre » only if both are
silent. Verified live: `lookup?provider=tvdb&provider_id=255968` →
« Top Chef », 2010, poster — and the follow count unchanged by the
resolution itself.

Two modules crossed the 1000-line ceiling during this batch and were
split rather than squeezed: the resolve walk into `_resolve_walk.py`,
and the lookup engine + `_parse_search_best` out of the acquisition
router.

**Measurement** (deployed `df1fc6eb`): `make check` PASS, frontend
**1336/1336**, UNION **ALL PASS — 15 regions**, gestures **14/14**.

## Entry 21 — 2026-08-08: the iOS shimmer, third report, real cause found

Two previous fixes treated symptoms. A 5-agent audit of the actual code
(four independent hypotheses + a synthesis, each forbidden from
re-proposing the failed attempts) found what I had missed.

**The cause: a non-passive `touchmove` still covered the gestures that
matter.** Attempt #2 made the pull tracker per-gesture, gated on `atTop`
— but `atTop` is sampled ONCE, at touchstart. A gesture that STARTS at
the top keeps the scroll-blocking listener for its whole duration,
including the upward drag that scrolls the list. And the list is at the
top on arrival, after every display-mode switch, after every tab change
and after every refresh: that is the dominant case, not the rare one.
Attempt #2 removed the listener exactly where nobody was complaining.

**The fix: zero scroll-blocking listeners, anywhere.** The
`preventDefault` existed only to beat the native rubber-band, and CSS
already refuses the native pull — `overscroll-behavior-y` moved from
`contain` (stops chaining, KEEPS the bounce) to `none`, which lets the
tracker be `{ passive: true }` and permanent. iOS keeps the document on
the compositor, and the scrolling tree applies the sticky offsets itself
instead of the main thread re-resolving them a frame late. Pinned by a
test that spies on `addEventListener` and fails if ANY `touchmove` /
`wheel` is registered non-passive; mutation-checked.

**Three companions, all from the audit:**
- The sticky TopBar carried `bg-background/85 backdrop-blur-sm`. A
  blurred backdrop must be re-sampled from the moving content every
  frame. The maquette specifies no blur here (its only blur is the
  decorative poster backdrop in the media sheet) and the shell's other
  pinned bar is already opaque — so the bar became an opaque slab.
- The three ResizeObservers wrote `:root` custom properties on every
  tick. On iOS the collapsing URL bar resizes the observed elements
  CONTINUOUSLY mid-scroll, and `.filters` pins at the SUM of two of
  those vars. Writes are now quantised and skipped when unchanged —
  measured: **0 writes across 6 viewport-height changes**. Quantised
  with `ceil`, not `round`, on the audit's warning: rounding a real
  height down would seat the filter zone a fraction high and open a
  sliver of list content in the seam.
- `min-h-screen` (=100vh, the LARGE viewport on iOS) manufactured a
  toolbar-sized overflow on every page, guaranteeing the URL-bar dance
  even on a short list → `min-h-svh`.

**Reverted**: the `translateZ(0)` layer promotion from attempt #1. It
fixed nothing, and promoting a sticky element to its own layer is itself
a documented iOS jitter source. A failed fix left in place is debt.

**Harness honesty**: making the pull passive exposed TWO false
assertions in my own gesture pass — one racing the refresh it had just
triggered, and one asserting `.sheettitle`, a string that only appears
once the completeness query resolves (a request the mirror does not
intercept). It was measuring a fetch and calling it a gesture. Both now
assert what they claim.

**Measurement** (deployed `f7faa140`): `overscroll-behavior-y: none`,
`backdrop-filter: none`, no transform on the sticky bars, published
heights whole-pixel (69px / 62px), shell at `min-h-svh`. `make check`
PASS, frontend **1336/1336**, UNION **ALL PASS — 15 regions**, gestures
**14/14**. The device verdict is the operator's — it is the only iPhone.

---

## Entry 22 — 2026-08-08: thirteen operator reports — the follow that would not die, and the id search that took the screen hostage

**Reported** (batch of 13, in the operator's order): a downloaded film that
reached the library sits « en pause » then claims « pas encore acquis », and
once reactivated can be neither paused nor removed, silently (a); every action
must confirm (b); repair the blocked row (c); an acquired film must LEAVE the
follows, but only on confirmed arrival (d); a film already in the library must
be re-downloaded and REPLACE it (e); every failure must say so (f); a clear
button on the search field (g); « Voir mes suivis » broken after an add-by-id
(h); the ordinary search dead after an id search (i); the id result rendered
above its own form (j); swipe panes badly shown on an iPhone SE (k); only one
row open at a time (l); scrolling the filter pills changes VIEW on iOS (m).

**The follow that would not die** (a, c, d, e). Two distinct promises were
false at once. An acquired film was `set_active(False)` — a PAUSE, indistin-
guishable from an operator pause, which is why the card then read « pas encore
acquis » and why removing it did nothing: `DELETE` was itself a soft-delete of
an already-inactive row. Both are now real: `detect` and the post-dispatch
reconcile DELETE the follow, and the endpoint deletes rather than deactivates.
The §5 dialog's other promise — « le résultat REMPLACERA la version en place »
— never ran at all: `detect` closed the follow the moment it saw the film
owned, so the acquisition the operator had just authorised was discarded before
it started. Migration 022 carries that authorisation as `replace_owned`,
consumed as soon as the wanted row exists so the ordinary owned-closure applies
again when the NEW file lands.

**Every action reports** (b, f). Success was silent, and failures went to the
sonner stack — which on this surface sits behind full-screen sheets. One funnel
now decides: the maquette toast when its host is mounted, sonner otherwise.
Measured on staging: pausing a row answers `« American Dad! » — recherche
suspendue.`

**The id search took the screen hostage** (h, i, j). `results` preferred
`idResult` whenever it was set and nothing ever cleared it, so every later title
search rendered the id card instead. The resolved card renders at the TOP of
the body while the operator's thumb is on the accordion at the BOTTOM — it
resolved out of sight. And « Voir mes suivis » pushed `/acquisition` then popped
the add entry, landing back on `?add=1`: the screen it had just left reopened.
One replace-navigation, one reset on a new query, one fold-and-scroll on a
resolved id.

**The pills that changed view** (m). The pager declares `touch-action: pan-y`,
which per spec intersects with everything below it — so iOS never scrolled the
pill train, it handed the drag to the pager. The train now WRAPS: measured
`flex-wrap=wrap`, overflow **0 px** at 375, so no filter is out of reach and no
horizontal gesture competes for that strip at all.

**What could not be reproduced** (k). Measured with real touch events at both
375×667 and 320×568: the card settles at `translateX(-168px)` and BOTH panes
land fully inside the viewport (84 px each, `visible=84`). « Pause plus a
sliver of Retirer » is a row left MID-DRAG, not a layout — so the settle no
longer depends on which of pointerup / pointercancel / touchend iOS delivers:
the row captures the pointer and settles on the first of them to arrive, at the
window. A partial 100 px drag now measures `-168px`.

**Two stale rows, not deletable from prod yet.** `Ninja Turtles` (id 29) and
`On l'appelait Robin des Bois` (id 33) are paused follows for films confirmed
in the library (items 3296 / 3297, 2.9 GiB and 17.27 GiB of real file). They
are artifacts of the old pause-instead-of-remove behaviour. Prod still runs the
soft-delete DELETE, and staging refuses writes, so they survive until this
branch merges — then one tap on « Retirer » ends them.

**Measurement** (deployed `62f65709`, 375×667, real touch): `make check` PASS,
frontend **131 files / all green**, batch pass **10/10 PASS** — pills wrap +
view unchanged, partial swipe settles, one row open, both clear buttons, the id
card in view (`attendu='Top Chef' affiché=['Top Chef'] scrollTop=0`), title
search back in control, « Voir mes suivis » out of the add screen, action toast
shown. The device verdict stays the operator's.

---

## Entry 23 — 2026-08-08: the shimmer, fourth report — the operator read the template right

**Reported**: « Sur iOS la partie fix tremble encore quand on scroll ! le bug
n'est toujours pas corrigé !!! pourquoi les éléments scrollent-ils jusque sous
la partie fix ? peut-être que le problème est là ? Dans le template même de la
page. » — and that is exactly where it was.

**Why three fixes failed.** Attempts 1–3 all treated the header: promote it to
its own layer, stop claiming the touch, stop rewriting its height. Each
addressed a contributor; none addressed the mechanism. While the DOCUMENT
scrolls, iOS collapses and expands the URL bar throughout the gesture. Every
one of those frames changes the visual viewport AND `env(safe-area-inset-*)`,
so a `position: sticky` header must be re-placed against a scrollport that is
itself moving — on the main thread, one frame behind the content the compositor
has already scrolled. That gap is the shiver. Damping it was always going to
lose to its cause.

**The template answer.** The shell is now a FRAME: exactly one viewport tall,
`overflow: clip`, with `main` as the single scrollport (`data-scroll-root`).
The header and the desktop rail are ordinary static rows. The document has
nothing to scroll, so the URL bar never moves, so the viewport never resizes
mid-gesture, so there is nothing to re-place — and nothing passes under the
header, because the scrolling area now BEGINS below it. The acquisition tabs
pin at `top: 0` of that scrollport instead of a measured header height, and the
filter zone at the tabs' height alone: the sum that included the header — the
value iOS kept changing — is gone from the sticky math entirely.

**Measured on deployed `8eb89117`** (390×844, real touch scroll):
document scrollable **0 px**, header `position: relative`, scrollport top
**69** = header bottom **69** (nothing under it), content scrolled **0 → 295**
while the header box stayed byte-identical, and **0** `--tm-*` writes during
the gesture.

**Collateral, caught by the harness.** Making the row capture its pointer (the
mid-drag fix from entry 22) retargets the click that ends the gesture to the
capturing element — so every tap on a control INSIDE a card was swallowed and
the detail sheet stopped opening. The gesture pass caught it before deploy.
Capture now belongs to a drag that has actually locked horizontally, never to a
press; a regression test pins it.

**Trade-off, stated.** In mobile Safari the URL bar no longer auto-collapses on
scroll — a frame gives up that gesture by construction. In the installed PWA
(standalone) there is no URL bar and nothing changes.

**Still sticky, deliberately**: the view tabs and the filter zone, INSIDE the
scrollport. Their offsets are now constant and were measured stable. If the
operator still sees those two shiver, the next lever is lifting them out of the
scroller as well, leaving the list as the only scrolling element.

**Full re-measure** (`8eb89117`): `make check` PASS, frontend **131 files**
green, UNION **ALL PASS — 15 regions**, gestures **15/15**, batch **10/10**,
frame **6/6**, and every authenticated route (9) holds the frame with its
content still reachable.
