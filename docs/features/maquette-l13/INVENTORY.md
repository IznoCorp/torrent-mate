# L13 — The engine's residue: measured inventory (read-only subagent, 2026-09-13, main 5eafd3cfc)

Every figure carries its command; re-run rather than trust.

## 1. legacy.js
- wc -l → 31802 (31460 non-blank; L19-close figure 31645, 185 lower today).
- Ladder handler (brace-matched): hideLayers 7984–7997 (14) · unwindLayer 8017–8026 (10) · switchPageFromLayer 8432–8465 (34) · onEngineBack 8481–8643 (163) · window.__closeLayers 8649–8653 (5) → 226 lines. Adjacent: closeScreen 8125–8152 (28), screenStack 8110.
- Boot handshake window.__startEngine: defined legacy.js:31406, span 31406–31668 (263 lines); called once from app/shell.tsx:275; typed shell.tsx:128; held by harness/boot_order.py:106 and harness/bridge.py:200-207.
- Engine-side seams are DEFINED BY THE SHELL, not the engine: __address shell.tsx:243 · __bridge history-bridge.ts:129 · __panel panel-host.ts:352 · __screens history-bridge.ts:191 · __store shell.tsx:212. The engine READS them. Reader lines outside engine/ (bare / window-qualified / files / lines inside engine): __address 7/4/4/17 · __bridge 19/14/13/22 · __panel 25/20/21/14 · __screens 12/7/8/17 · __store 44/43/16/0.
  Command: grep -rn "__<name>\b" --include='*.ts' --include='*.tsx' --include='*.js' frontend/maquette/design/src | grep -v '/engine/'

## 2. Harness driving seams
- __go legacy.js:8734 · __states legacy.js:8759 · __queries shell.tsx:227 · __relay shell.tsx:381 · __mocks mocks/index.ts:303. Two of five live in the dying file.
- Harness rule files reading each (of 125): __go 91 (278 occ) · __mocks 25 (224) · __queries 18 (44) · __states 12 (17) · __relay 6 (80).
- Product readers of __go outside engine: 7 lines in app/entry.ts, app/layer-registry.ts, app/outbox.ts, app/panel-host.ts, app/shell.tsx, features/system/page.tsx, lib/relay-condition.ts.

## 3. Delegation (document-level click)
- One delegation legacy.js:8852 → 9544 (693 lines); gate `event.target.closest("button, a[data-navgo]")` at 8855. Two other listeners (31028 drag guard, 31645 hint dismissal) dispatch no dataset.
- grep -c "closest\.dataset\." → 116 occurrences, 64 distinct names, ALL inside the block (L19 close: 133/73).
- Names: acqtab act addfield cancelsetting cat clearq complete confirmadd confirmrestart del deletefield delsel dismiss drawer ep field fmode go hclose hgo hphase hscen htmdb index journey leave lens lmode maintact maintopic manual mediasheet navgo next page panel phase pill pipe profile qsettings releases reloadsettings resolve restart reversed save secret selectedTitle selmode setsort setting sheet sheetprim signout sort standby sug sugmode tile tmdb to toast topic. Data, not verbs: index, ep, selectedTitle. Frame's own: drawer, navgo, sheet.
- Five surface-opening verbs: grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)" → 13 lines (mediasheet 9367/9371 · journey 9469/9475 · resolve 9099/9102/9508/9509 · releases 9145/9147 · profile 9151/9152/9165).
- ", 260)" → 6; "panel\.open(" → 0 (L19 discharged).

## 4. Nine fixture families (D5 bracket-match, python3 reader; declarations > 100 lines)
POSTERS 395–809 (415) · HERO_IMAGES 826–1153 (328) · trailerIds 1160–2474 (1315) · OWNED 2481–3863 (1383) · LIBRARY 3938–4464 (527) · MAINT_ACTIONS 4641–4876 (236) · SETTINGS 5757–7217 (1461) · CAST 9717–9888 (172) · SHEETS_RAW 9890–30427 (20538) → 9 families, 26 375 lines, IDENTICAL to L19's close.
Readers: posterBox legacy.js:121 (6 occ) · cardHTML 5290 (8) · tileHTML 7708 (4) · allSettings 7304 (7) · sheetFor 30501 (8) · seasonsOf 30547 (3) · ownedFor 30575 (5).
Family→reader: POSTERS 124-125 (posterBox), 7499 (__referentiel), 31739 (handshake export) · HERO_IMAGES 7498, 31735 (published only) · trailerIds 7612, 31771 · OWNED 30549 (seasonsOf), 30576 (ownedFor), 31738 · LIBRARY 9551, 30825, 31735 · MAINT_ACTIONS 7589, 31736 · SETTINGS 7304 (allSettings), 7596, 31684, 31739 · CAST 7609-7610 (get CAST() on __referentiel), 31730 · SHEETS_RAW 30460, 30481, 30503 (sheetFor), 31734.

## 5. Dead #screen layer
- Node index.html:520 `<div class="screen" id="screen" data-part="screen">` inside #device (index.html:171).
- Three live readers: onEngineBack legacy.js:8513 · hideLayers 7988 · window.__close 30854/30856. Plus closeScreen 8125–8152 (reads 8127/8139/8151), screenStack (8110; reset 5590, 8986; popped 8128; exported 31762). No screenStack.push anywhere; both setOpen(#screen, …) pass false.
- Harness: only audit.py:63,220,303 and audit2.py:50,52 select #screen by id; others select [data-part="screen"][data-open]…
- Mount-node placement shell.tsx:305–307 (device.insertBefore(mountNode, legacyScreen)), reasoning 278–302 (containment vs .device position:relative; paint order so `.screen.open` resolves first — screens.py, bridge.py rely on it).
- B-232 row: `| B-232 | Two dead layers: the page-render branch and #screen | by survey | open |` body BUGS.md:9489–9498.

## 6. refonte.html
- 120 lines, 1 <style>, 1 `{` (@layer block2 { at line 4), 1 `}` (120), 0 declarations — a comment ledger inside an envelope.
- 14 files hold a path literal (plan says twelve): vite.config.mjs:38 (build injects it) · build-identity.mjs:26 · serve.py:112 · harness/shell.py:49 (R72) · harness/common.py:152 · harness/palette.py:30 · harness/switchover.py:61,222 · harness/rename.mjs:25 · scripts/check-css-tokens.py:80 · scripts/csstokens_login.py:33 · scripts/csstokens_ranks.py:61 · scripts/nofrench_lexicon.py:51 · scripts/check-tailwind-confinement.py:92 · scripts/check-compositor-css.py:115. Plus regions.json (R72 text) and 24 prose-only files (41 total excl. dist/).
- R72 (regions.json $adversarialReview): holds (a) refonte.html verbatim exactly once in dist/index.html — THE injection hold; (b) one script tag with type="module" and src="/vite/…js"; (c) that bundle exists under dist/vite/. Mutation of record for (a): `@layer block2 {` → `@layer block2X {` in dist/index.html fells (a) alone. R72_SKIP_BUILD=1 skips the build gate.

## 7. legacy.css
- 2207 lines. Guard scripts/check-legacy-css-residue.py reads RESIDUE (legacy.css) + CEILING frontend/maquette/legacy-css-residue.json; ratchet on rules/declarations/classes (comments stripped); today classes 148, declarations 956, rules 238, exit 0, zero slack (re-taken 2026-08-31 L12).
- The ONE import: app/shell.tsx:26 `import "../styles/legacy.css"`; not in index.html nor vite.config. Tools reading it as a path: check-legacy-css-residue.py:41, harness/residue.py:81 (R80), check-css-tokens.py:113,654, csstokens_login.py:37. Baselines: legacy-css-residue.json; comment-references-baseline.json:47 ("design/src/styles/legacy.css": 61). Cited by line: harness/exits.py:37, harness/gestures.py:281, scripts/check-poster-box.py:16,70, scripts/markup_dressing.py:195–220,277. Prose in product: ui/variants/controls.ts:190, ui/variants/frame.ts (9 lines), app/drawer-gesture.ts (4 lines), features/{acquisition,arrivals,media}/variants.ts. R80 regions.json:262 « IT DIES WITH D10 ».

## 8. check-frontend-boundaries.py --arm size
exit 0; « grandfathered counts: engine/legacy.js 31460→31460, engine/states.js 786→786 »; ceiling 400, warning 250 (36 above). GRANDFATHERED in scripts/frontend_size_ledger.py:95: "engine/legacy.js": ("L13 — the engine dies by subtraction, surface by surface", 31460); states.js 786 (B-352, L13).

## 9. frame-model.md § 2 Part 4 (lines 92–111) / frame-survey.md (242 lines, measured at faee1192 2026-08-29)
- Model: app/history-bridge.ts owns the PRIMITIVES (record, replace, pushLayer, back, rewind, onBack); the engine owns the LOGIC (onEngineBack walks drawer → #screen → sheet → page → exit guard; unwindLayer; hideLayers resets for __go; __closeLayers = scrim tap). Target: ONE app/layers.ts holding ranked registrations, the back handler, closeLayers, hideLayers; the engine calls it through the seam. « The ranking is frame; the move is behaviour » — drawer/dialog register in L15; the handler moves out in L13. B-229: dialog pushes no entry.
- Survey: 19 drawing sites (13 innerHTML, 2 insertAdjacentHTML, 4 appendChild) over nine surfaces: tab bar 7802 · drawer 10000 · confirmation dialog 9064 openDlg (producers 10788, 10915) · toast 8943/8933 · selection bar 8236/8239 · episode popover 32060/32061 · Découvrir feed (8653…8845) · page view 7862 DEAD · harness panel 10074/10098 · viewport meta 49. Six frame's, one feature's (Découvrir), two scaffolding. 29 toast() + 5 toastUndo() callers. openDlg pushes no entry and onEngineBack has no #dlg branch. z-order: .dlg 48 (legacy.css:225) under #nav z-50; .selbar 51, .eppop 60, .hpanel 60, .loginscreen 60, .splash 70. __closeLayers walks three layers where the ladder walks two live ones; scrim raised by three writers.
  (Line numbers in the survey have moved: onEngineBack now 8481–8643.)

## 10. BUGS.md rows carried into L13
- Index rows: B-232 (above) · B-275 « Back from a media screen opened via « Voir la fiche » does NOT reopen the panel — §16's mirror cannot play | by L12 bench | open » (body 4722) · B-290 « A layer closed inside a navigation's commit KEEPS its history entry, so Back crosses two entries where its siblings cross one | by L12 review | open » (body 4358).
- Index rows naming L13: B-327 (open: Réglages draws SIX scheduled jobs while the machine runs seven… until SETTINGS leaves the engine; by L13) · B-350 fixed #572.
- 24 OPEN rows whose body names L13 as owner: B-071, B-220, B-232, B-236, B-275, B-290, B-312, B-327, B-331, B-332, B-334, B-335, B-336, B-337, B-339, B-340, B-341, B-342, B-343, B-345, B-352, B-361, B-366, B-465. (Settings family: 327, 331, 332, 334, 335, 341, 342, 343, 361; library engine half: 312, 336; add screen: 340; swipe: 337; tile: 366; states.js: 352; seeds: 345; dead comment: 465.)
- « frame model » rows B-242, B-271 both closed.

## 11. README « Every state has a name » (README.md:416)
__go("<id>") drives without clicking; __states() lists; ≡ panel; three dials (Data scenario real/loaded; Surface phase ready/loading/error; TMDB account). harness/states.py reads them live (states.py:21) and asserts each renders, no horizontal overflow, no JS error. README says 54 — STALE: 87 named states today (declared in engine/states.js `const STATES = [` line 41; count: python3 -c "import re;print(len(re.findall(r'^\s*\[\s*[\"\x27]([a-zA-Z0-9_-]+)[\"\x27]\s*,', open('frontend/maquette/design/src/engine/states.js').read(), re.M)))"). states.js 793 lines (786 non-blank, B-352).

## 12. Harness reads of window.__ seams (96 distinct; 91 non-driving)
By files/occurrences: __loadingDone 44/73 · __panel 28/121 · __store 27/110 · __measure 22/28 · __followActions 18/38 · __queue 15/33 · __toast 15/34 · __screens 12/22 · __referentiel 10/50 · __suggestions 7/11 · __reset 6/13 · __bridge 5/11 · __dialog 5/9 · __closeLayers 3 · __deleteLibraryItems 3 · __gestures 3/13 · __navEchec 3/8 · __settingLabels 3/7 · __close 2 · __i18n 2 · __layers 2 · __libraryNextPage 2/7 · __outbox 2/30 · __pages 2 · __queueActions 2 · __refused 2 · __reposPTR 2 · __routeur 2 · __samples 2 · __searchResults 2 · __startEngine 2/6; plus 60 seams read by one file each (probe seams mostly). __releasePage (legacy.js:7436–7438) « goes with the boot handshake at L13 ».

## Figures, once
legacy.js 31 802 (31 460 nb) · legacy.css 2 207 · refonte.html 120 · named states 87 · harness rule files 125 · delegation 116 occ / 64 names / 693 lines / 13 surface-verb lines · fixture families 9 / 26 375 lines · ladder handler 226 lines · __startEngine 263 lines · residue ceiling 148/956/238 exit 0 · size arm exit 0 (31460→31460) · refonte.html path readers 14 files · open rows owned by L13: 24 · harness non-driving seams: 91.
