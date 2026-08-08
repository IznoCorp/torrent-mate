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
