# L13 — The engine's residue · DESIGN

Contract: `docs/reference/frontend-architecture.md` § 4, entry `#### L13 — The engine's residue`
(four clauses, two inheritances, four « Carried here by … » blocks — not restated). Brief:
`docs/features/maquette-l13/BRIEF.md`. Starting inventory: `docs/features/maquette-l13/INVENTORY.md`
(taken at `5eafd3cfc`; **every figure below was re-taken at `a37bde528`**, which is `origin/main`
`a155b54fb` — #588 merged — plus this branch's two documents). The plan is `plan/INDEX.md`; it
cites this file and repeats no figure.

**What this lot is.** Not a surface. The largest architecture decision left: a file of 31 786
lines, the sheet that styles it, the table that drives it, and everything that reads any of them.
This design turns the contract's clauses into decided HOMES, a measured ORDER and a CUT, so the
implementer executes and the operator rules on ten minutes of reading.

**A reader with no context reads § 1 (the cut), § 3 (the homes table) and § 9 (what the plan gets
wrong).** Everything else is the evidence under them.

---

## 0. What L13 owes, said once

| Clause (contract) | Measured today | Where it is discharged |
| --- | --- | --- |
| `legacy.js` no longer exists | 31 786 lines, 31 444 non-blank | L13b phase 11 |
| no PRODUCT code reads a `window.__` seam | 27 names, 211 lines (§ 2.4) | L13a phase 2 (the shell's 19 names), phases 3–4 (the engine's 6), L13b phase 11 (the last) |
| the driving seams live in a harness module, dying at switchover with `harness.css` | `__go`/`__states` in `legacy.js`; `__queries`/`__relay` in `shell.tsx`; `__mocks` in `mocks/index.ts` | L13a phase 1 (`design/src/harness/`) |
| the suite green at unchanged hold counts; the oracle green | baseline 119 rules, 2 600 holds, `failed` 0 | every conversion phase; each behaviour phase names its movement |
| Inheritance 1 — the nine fixture families | 9 declarations, 26 377 lines | L13a phases 9–16, surface by surface |
| Inheritance 2 — the five surface-opening verbs; `grep -cE …` reads 0 | 13 lines | L13b phases 2–4 |
| L12 — B-290, one ladder shape, a rule COUNTS pops | open | L13b phase 9 |
| L12 — B-275, Back reopens the panel; `panel-down`'s reverse written with its rule | open | L13b phase 10 |
| L09 — the fixture families die with the producers that read them | discharged by inheritance 1's measurement (L19) | — |
| L07 — `refonte.html` gone, R72 renegotiated, the ledger's home | 120 lines, 14 path readers | L13a phase 19 |

---

## 1. The cut — an arbitration for the operator

Sent to the steward on 2026-09-13 (message « L13 CUT ARBITRATION »). **RULED B by the operator on 2026-09-13** (three sub-lots; reading A refused as mixing conversion and behaviour in one review); **Q2 ruled (ii) the same day — the ≡ harness panel died at L13a a·17-bis** (ruling 31: `harness/bar` and `#notesBtn` stay). **The folder `docs/features/maquette-l13/` is the LOT's** (ruling 58): it dies at L13c's post-merge gesture; each sub-lot's gesture deletes only its own brief and resume, cited by commit. If the ruling is A, `plan/INDEX.md`
merges its three phase tables into one and no phase file changes.

**(A) One wave.** One branch, one squash, 39 phases chained, one reader round at the end. Cost: a
pull request deleting some 34 000 lines and converting 37 feature files, read once; a branch merging
`main` under it for weeks; one Mac walk. **And it breaks a binding rule**: `frontend-architecture.md`
§ 0 — « One kind of change per wave … Never both in one wave » — and the office's review rule 1
(`docs/reference/frontend-steward.md` § « What a review costs », rule 1). L13 carries both kinds by
construction.

**(B) Sub-lots, each a wave with its own squash, reader round and Mac walk.** Cost: three merges and
post-merge gestures instead of one, the register's rows re-owned per sub-lot, and § 0's selection rule
reading « L13 » as three entries. Gain: every reader round reads ONE kind of change, and a conversion
round is cheap — the oracle proves it at zero divergence (L14's conversion half was clean at round
one and stayed clean; every later round was its behaviour half).

**Recommended: B, in THREE sub-lots — the smallest number that keeps one kind per wave and the
dependencies true.**

| Sub-lot | Kind | What it lands | Phases |
| --- | --- | --- | --- |
| **L13a — What moves unchanged** | CONVERSION | the harness module; the seams become imports; the ladder handler and the boot out of the engine; what nobody reaches; the contract's identity fields; the drawing, the fixture families and `legacy.css`, surface by surface; `refonte.html` and R72 | 19 |
| **L13b — The engine's verbs and the ladder's shape** | BEHAVIOUR | the 62 delegation names by feature; the engine's gesture listeners; B-290 + B-397 + the 240/260 ms timers; B-275; `legacy.js` deleted | 11 |
| **L13c — What the engine was blocking** | BEHAVIOUR | B-312, B-340, B-339, B-336, B-331, B-327, B-366, B-345 (library half); the close | 9 |

**The order, and its reason.** L13a first: every later phase is proved through `__go`, and the
handler must be ONE module before its behaviour changes (a behaviour change on code that is also
moving is the edit hidden inside a move § 0 forbids). L13b second: a verb does not care who emits
its `data-*`, so it can leave after the drawing converts, and the file dies only when its last
listener has. L13c last: its repairs sit on components L13a creates and seeds L13a introduces.
**A four-way variant** (L13a split into « the harness and the frame » and « the drawing ») buys a
smaller first round for one more merge; not recommended — the frame half is five phases and would
be a wave that deletes almost nothing.

**Questions batched with the cut, and their state.**

| # | Question | State |
| --- | --- | --- |
| Q1 | The harness module's home | **Settled by the steward**: `design/src/harness/`, excluded like `harness.css` (§ 4.1). The contradiction with L20's plan is § 9.3 |
| Q2 | The ≡ harness panel (`openHarness`: the named-state list and three dials) | **The operator's; relayed.** Reading (i) — it becomes a harness-module component — is the one this plan executes. Reading (ii) — it dies, the dials reachable through `__go` only — deletes L13a phase 1's component half and nothing else. No rule taps it (`grep -l "hscen\|hphase\|htmdb\|hgo\|harness/panel" frontend/maquette/harness/*.py` → none) |
| Q3 | The fixture families' shape | **Settled**: plain JSON seeds under `mocks/seeds/`; POSTERS is `posters.json` (exists, 22 272 bytes). No product code imports a seed — lists carry the field (§ 5) |
| Q4 | `.screen.open` in `screens.py`/`bridge.py` | **Settled**: re-aimed to `[data-part="screen"][data-open]`, count unchanged, said in the rule's docstring |

---

## 2. The weight, measured

Every figure once, with its command. `E` = `frontend/maquette/design/src/engine/legacy.js`.

### 2.1 The files

| What | Figure | Command |
| --- | --- | --- |
| `legacy.js` | 31 786 lines · 31 444 non-blank | `wc -l E` · `grep -cve '^[[:space:]]*$' E` |
| of which the nine families | 26 377 lines (83 %) | D5's bracket-match (spans in § 5.1) |
| `states.js` | 793 lines · 786 non-blank · 87 states · 77 `applyState` calls | `python3 -c "import re;print(len(re.findall(r'^\s*\[\s*\n?\s*[\"\x27]([a-zA-Z0-9_-]+)[\"\x27]\s*,', open('frontend/maquette/design/src/engine/states.js').read(), re.M)))"` · `grep -c applyState …/states.js` minus the import line |
| `legacy.css` | 2 207 lines · 148 classes · 956 declarations · 238 rules | `python3 scripts/check-legacy-css-residue.py` |
| `refonte.html` | 120 lines, 0 declarations | `wc -l frontend/maquette/design/refonte.html` |
| size ledger | `engine/legacy.js` 31 444, `engine/states.js` 786 | `sed -n 94,97p scripts/frontend_size_ledger.py` |

### 2.2 The engine's code, by region (non-fixture)

`grep -nE "^  (async )?function [A-Za-z0-9_]+|^  (const|let) [A-Za-z0-9_]+ = (\(|async|function)|^  window\.__[A-Za-z0-9_]+ = " E` (136 declarations outside the family spans).

| Region | Lines (`E`) | Home |
| --- | --- | --- |
| drawing helpers (`posterBox`, `cardHTML`, `tileHTML`, `libRowHTML`, `swipeHTML`, `secHTML`, `factRowsHTML`, skeletons, `surfErr*`, `chipHTML`, `stripHTML`, `richText`, format helpers) | 88–280, 5174–5720, 7677–7790, 30435–30581 | L13a phases 7–16 |
| simulated behaviours (`actionTake`, `actionLeave`, `actionResolve`, `actionDelete`, `seedWorld`, `__reset`) | 5443–5613 | forwarders die with their verbs (L13b); `__reset` → harness (L13a ph. 1); `seedWorld` dies with `world` (L13a ph. 4) |
| settings surface (`resetSettings`, `allSettings`, `changeSetting`, …) | 7253–7376 | L13a ph. 16 (reads) + L13b ph. 1 (verbs) |
| `render`, `__referentiel` | 7400–7676 | dies across L13a (`render` → nothing; `__referentiel` → per-feature imports) |
| ladder: `hideLayers` 7983–7996 · `unwindLayer` 8016–8025 · `__derouler`/`__navigationState`/`__announcePops` 8031–8070 · `closeScreen` 8125–8153 · `navigationState`/`recordPath`/`replacePath` 8253–8325 · `switchPage` 8353–8404 · `switchPageFromLayer` 8431–8464 · `onEngineBack` 8480–8642 · `__closeLayers` 8648–8652 | ~560 | L13a ph. 3 |
| driving: `__recordStates` 8681, `applyState` 8686, entry forwarders 8716–8731, `__go` 8733–8757, `__states`/`__etatsDetailles`/`__pages`/`__blocked`/`__measure` 8758–8790, `openHarness`/`closeHarness` 8802–8840 | ~160 | L13a ph. 1 |
| delegation | 8851–9528 (678) | L13b ph. 1–7 |
| `mediaNamedBy`, `openDeleteDialog` | 9534–9700 | L13a ph. 10 (reads) + L13b ph. 6 (verb) |
| identity (`SHEETS_IDX`, `titleForProviderId`, `addressIdsFor`, `sheetFor`, `seasonsOf`, `ownedFor`, `sheetSeasonsHTML`, `epState`) | 30435–30775 | L13a ph. 5 (dead), 13–14 |
| popover, `knownMedium`, `window.__close` | 30776–30895 | L13a ph. 5, 14 |
| gestures (swipe rows, suggestion card, deck, drag guard, `__reposPTR`) | 30896–31270 | L13b ph. 8 |
| addressed panels (`REOPEN`, `reopenAddressedPanel`) | 31278–31384 | L13a ph. 3 |
| boot (`__startEngine`) | 31390–31652 (263) | L13a ph. 4 |
| exports (`export {…}` 31667; `Object.assign(window, {…})` 31713–31757, 153 names; `defineProperties` 31759–31786, 16 getters) | ~120 | shrink with each phase; gone with the file |

### 2.3 The delegation

One `document` click listener, bubble phase, `E:8851–9528` (brace-matched). **113 reads over 62
names** (`grep -o 'closest\.dataset\.' E | wc -l` → 113, all inside the span; distinct:
`grep -o "closest\.dataset\.[A-Za-z0-9_]*" E | sed 's/.*\.//' | sort -u | wc -l` → 62). The brief's
116/64 was 5eafd3cfc less #588's `topic` and `maintopic`. Three names are DATA (`index`, `ep`,
`selectedTitle`). Two more branches test CLASSES (`.cfoot` 9499–9507, `.act` 9507–9527). **Four
branches are dead**: `dismiss` and `sug` (no emitter anywhere), the generic `sheet` →
`openDetailSheet` (only `plus` and `utilisateur` are emitted), the second `resolve` (9492, the first
answers every `data-resolve`). Timers inside the span: `grep -c ', 260)'` → 6, `grep -c ', 240)'` → 4.
Surface-opening verbs: `grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)" E`
→ 13.

**The registry already wins.** `lib/verbs.ts`' listener is on `document` in CAPTURE; the delegation
is in bubble; a registered verb calls `stopPropagation` and the engine branch never runs. 17 names
are registered, none of them among the 62 (`grep -rn 'registerVerb(' frontend/maquette/design/src --include=*.ts --include=*.tsx`).
**So a verb leaves the engine by being registered, and its branch is then unreachable and deleted in
the same commit** — no mechanism to invent.

### 2.4 The seams

- **The harness reads 97 `window.__` names** (`grep -ohE 'window\.__[A-Za-z0-9_]+' frontend/maquette/harness/*.py | sort -u | wc -l`).
- **Product code outside `engine/` reads 27 of them on 211 lines.** Method: a Python pass over
  `design/src/**/*.{js,ts,tsx}`, `engine/` and `*.test.*` excluded, comments stripped, `window.__x =`
  excluded. 19 are published by the shell itself (153 lines), 6 by the engine (56 lines),
  `__mocks` by the mock layer, `__servedIdentity` by the host.
- **The engine publishes 153 bare names and 16 getters on `window`**, and rules read them inside
  evaluate strings: `render()` 23 lines / 10 files, `applyState(` 11 / 6, `SETTINGS_STATE` 13,
  `SETTINGS` 12, `closeSheet` 7, `sheetFor(` 7, `window.armedExit` 25, `window.SEASONS` 16 / 8 files,
  `state.` in 26 files. Method: `(?<![\w.'"-])NAME[(.[]` and `window\.NAME` over `harness/*.py`,
  `#` lines excluded; short words are noisy and each re-aim reads the file.

### 2.5 The drawing React still borrows

`lib/engine-drawing.ts` types **61 members; 18 are called** from features, through
`window.__referentiel`: `icons` 27 sites, `render` 15, `baseTitle` 7, `cardHTML` 6, `skelCardsInner` 6,
`svgIcon` 5, `emptyInner` 4, `tileHTML` 3, `posterBox` 3, `factRowsHTML` 3, `dateFR` 3,
`escapeHtml` 2, `secInner` 2, `chipHTML`, `swipeHTML`, `plages`, `initials`, `state` 1 each (plus
`libRowHTML` from `library/reference.ts`). They render through 7 `dangerouslySetInnerHTML` sites
(`grep -rn dangerouslySetInnerHTML --include='*.tsx' frontend/maquette/design/src | grep -v /engine/ | wc -l`).
Method for the member counts: a scan of `features/`, `app/`, `ui/` for `(reference|referentiel|ref|drawing|engine)?.NAME` and destructuring from `use*Reference()`.

### 2.6 `legacy.css` — it styles React, not only the engine

Each of the 148 classes, by who emits it (method: the whole token inside a class context — `cva()`,
`cn()`, `className=`, `class="…"`, `classList` — tests excluded, short tokens checked by hand,
data-built classes read from the markup):

| Category | Classes | Meaning |
| --- | ---: | --- |
| a component emits it and ONLY `legacy.css` styles it | **92** | deleting the sheet changes rendering — each needs its variant first |
| `index.html` shell markup (login gate, splash) | 13 | `loginscreen`, `logincard`, `loginfield`, `loginerr`, `loginsub`, `loginsubmit`, `logintitle`, `splash`, `splashbar`, `splashmsg`, `brandbig`, `mk`, `wm` |
| engine helpers still called by features | 33 | die when the helper's callers are redrawn |
| engine-internal | 6 | `hpanel`, `states` (harness panel), `ptr`, `armed`, `loading`, `spin` (pull indicator) |
| a variant already carries it | 3 | `panel`, `scrim`, `linkbtn` |
| dead | 1 | `quota` |

**The single most dangerous one: `.screen.open`.** The `screen()` variant is
`translateX(100%) invisible` with no open branch; `legacy.css` is what makes the five route screens
visible. It converts FIRST among the styles (L13a phase 7).

**R80** (`harness/residue.py`) holds `PAIRS_FLOOR = 15` over 15 pairs, not the sixteen `regions.json`
and D10 say (`grep -n PAIRS_FLOOR frontend/maquette/harness/residue.py`). **R80 is the one rule whose
hold count MUST move in a conversion phase**: it holds one pair per residue rule sharing an anchor
with a variant, and a conversion deletes residue rules. Each phase that removes a pair lowers the
floor by exactly the pairs it removes, NAMES them in the commit body, and the hold-count comparison
reads R80's movement as that figure and nothing else. `.panel`, `.scrim.open` and `.sheet.open` stay
until a·18, so R80 measures something until the phase that deletes it.

**A class rule is deleted with its LAST emitter**, not with the first surface that stops using it:
`cardHTML` emits the card classes and calls `posterBox` until Acquisition converts (a·11), so a
primitive phase converts the variant and leaves the rule while an engine helper still draws it.

---

## 3. The homes — one row per thing that dies or moves

| Thing | Today | Home, or death | Sub-lot · phase | Proof |
| --- | --- | --- | --- | --- |
| `__go`, `__states`, `__etatsDetailles`, `STATES`, `__recordStates` | `E:8681–8760` | `design/src/harness/drive.ts`; `__recordStates` dies | a·1 | `states.py` drives 87; hold counts; oracle zero |
| `states.js` (87 states) | `engine/`, grandfathered 786 | `design/src/harness/states/<surface>.ts`, each under 400; the ledger entry removed | a·1 | same; B-352 closes |
| `__reset`, `__measure`, `__blocked`, `__pages`, `__navEchec`'s reset | `E:5543`, 8772, 8777, 8766, 8271 | `harness/drive.ts` (`__pages` over the navigation table's ids, read by `drawer.py:108`, `page_host.py`) | a·1 | the 13 / 28 / 2 / 5 rule reads unchanged |
| `applyState`, `render`, `state`/`world` getters read by rules | engine exports | `harness/drive.ts` publishes `applyState` (layers hidden · store written · port reset) and `state`; `render()` in a rule becomes `__store.touch()` in the phase that kills it | a·1, then per surface | the 11 + 23 rule lines re-read |
| the ≡ harness panel, `#notesBtn`, `#scenBtn` handlers, the hint dismissal | `E:8655, 8802–8840, 31629–31649` | a harness-module component (Q2 reading i); its 5 `h*` verbs registered there | a·1 | no rule taps it; the operator's hand |
| the 19 shell-published seams read by product (153 lines) | `window.__store` 42, `__toast` 32, `__bridge` 18, `__panel` 18, … | imports of the module that owns each; **publication for the harness moves to `harness/publish.ts`** | a·2 | hold counts; `grep` for `window.__` in product → the engine's six only |
| `__servedIdentity` | host inline script read by `lib/served-identity.ts:92` | a `<script type="application/json" id="served-identity">` the host writes and the module reads | a·2 | `identity.py` re-aimed, count unchanged |
| `__mocks` read by `app/outbox-wiring.ts:85` | window | an import under `__MOCKS_BUILT_IN__` | a·2 | `outbox.py` unchanged |
| the ladder's handler: `onEngineBack`, `unwindLayer` + latch, `hideLayers`, `__closeLayers`, `__derouler`, `__announcePops` | engine | **`app/layers.ts`** — ranked registrations (dialog > drawer > sheet), the back handler, `closeLayers`, `hideLayers`, the unwind latch; `layer-registry.ts` folds in; the SHEET registers as a rung | a·3 | R59, R65, R69, R82, R94 counts unchanged; oracle zero |
| `navigationState`, `recordPath`, `replacePath`, `switchPage`, `switchPageFromLayer`, floor flags, exit guard | engine | **`app/page-switch.ts`** (§ 9.2: one file cannot hold both halves under 400) | a·3 | R69, `pop.py`, `url_state.py` unchanged |
| `REOPEN`, `reopenAddressedPanel`, `knownMedium` | engine | **`app/addressed-panels.ts`**; `knownMedium` asks the cache | a·3 | `url_state.py`, `panel.py` unchanged |
| `__startEngine` (263), `world`/`seedWorld`/`adoptWorld`, `INITIAL_STATE`, `__releasePage` | engine, `page-host.tsx:89` | **`app/arrival.ts`** (arrival address, entry replace, guard entry, `__loadingDone`, addressed reopen); `world` and `__releasePage` die | a·4 | `boot_order.py` BOOT_STEPS row and `bridge.py` (f′) re-aimed, counts unchanged |
| `#screen`, `closeScreen`, `screenStack`, `window.__close`, the mount-node placement (`shell.tsx:278–306`) | dead | die; `#shell` is placed into `#device` before the node that followed `#screen` | a·5 | eight harness readers re-aimed (§ 4.5) |
| dead code: `dismiss`, `sug`, generic `sheet`, second `resolve` branches; `sheetSeasonsHTML`, `epState`, `seasonsOf`; `__seamsInstalledProbe`; `quota` | engine, css | die | a·5 | oracle zero; nothing reads them |
| identity for lists: title → provider ids, poster | only `MediaSheet.ids` | contract fields `ids` + `poster` on 7 list schemas, `title` on `MediaSheet` (§ 5.2) | a·6 | `compare-contracts.py --check`; oracle zero |
| drawing helpers (§ 2.5) | engine HTML strings | `ui/` components (section, skeleton, facts, chip, poster, card, tile, swipe row) and pure functions beside their feature | a·7–16 | oracle zero per surface; hold counts |
| `toEngineShape` / `engine/engine-shape.ts` (+ test) | reverse projection so React reads engine field names | dies when the last surface reads contract names | a·16 | the same surface's oracle |
| nine fixture families | 26 377 lines | § 5.1 — seven die, MAINT_ACTIONS dead, POSTERS → `posters.json` behind `poster` | a·10–16 | D5's bracket-match reads 0 declarations over 100 lines |
| `app/engine-data.ts`, `app/engine-redraw.ts` | engine support | die | a·16 | oracle zero |
| `legacy.css` 92 component classes | residue | variants, in the surface phase that owns the markup | a·7–16 | oracle zero; R80's pairs fall silent by construction |
| `legacy.css` 13 shell classes | residue; `serve.py:452` builds the host's own sign-in page from raw extracts of the residue's `style` and `splashstyle` blocks (`grep -n "legacy_source" frontend/maquette/serve.py`) | a delimited `entry` block of `styles/base.css` — the document's own markup, served before any module and on a page with no bundle, which is D3's base layer — that `serve.py` extracts instead; `serve.py:416`'s `.logincard` rewrite re-aimed | a·17 | `logout.py`, `startup.py`, oracle `signin*`/`startup` |
| `legacy.css` itself, its import (`shell.tsx:26`), `check-legacy-css-residue.py`, `legacy-css-residue.json`, R80 + `test_residue.py` + its `run.sh`/`regions.json` entries, the `comment-references-baseline.json:47` row, `check-poster-box.py`'s floor, `markup_dressing.py`'s five lines, `csstokens_login.py`'s binding | live | all die or re-aim in ONE commit | a·18 | `make check` exit 0; oracle zero |
| `refonte.html`, R72 hold (a), 14 path readers | live | deleted; R72 keeps (b)+(c) mutation-tested; the ledger read from history (§ 7) | a·19 | R72 two holds, each seen to fall |
| 62 delegation names | engine | registered verbs in the owning feature (§ 6) | b·1–7 | each move lands with the rule that held it; a verb held by none gets its rule first, red on the engine branch |
| gesture listeners (swipe, suggestion card, deck, drag guard, `__reposPTR`) | `E:30896–31270` | `lib/` for the arbitration shape, the feature for which surface uses it | b·8 | R55, R98, R112, `deck.py`, `drag.py`, `press.py`; B-337's one-tap hold |
| the 240/260 ms close-then-wait timers | 10 sites | die with B-290's one shape | b·9 | `exits.py`'s inventory refuses them |
| `legacy.js`, `engine/seams.ts`, the extractor's `ENGINE`, the seed builder's and `check-mock-seeds.py`'s three parser arms, `check-state-ownership.py` `ENGINE_SOURCES`, `check-no-french.py`'s allowed set + `check_unread_javascript` allow-list, `nofrench_lexicon.py` `DEBT_FILE`, `code-vocabulary.txt`'s FRENCH DEBT section (1260–1300, 24 words), the ledger entry, `harness/mocks.py`'s `TODAY` read, `said_and_done.py`'s engine read, `page_host.py:951`, `navigation.py:149`, `frontend/maquette/resync.py` | live | deleted or re-aimed in ONE commit | b·11 | `make check` exit 0; size arm lists no GRANDFATHERED; the contract's `grep -cE` reads 0 by construction |

---

## 4. The frame half (L13a phases 1–5)

### 4.1 The harness module — `design/src/harness/`

**Why a directory under `src/` and not beside `harness.css`.** `styles/` holds sheets; code under it
would be a KIND of file in a folder for another kind (the tree rule). `harness/` is a top-level bucket
beside `mocks/`, `contract/`, `i18n/` — the shape the tree has for an artefact that belongs to no
feature — and the name says what it is.

**What it holds.** `drive.ts` (`__go`, `__states`, `__etatsDetailles`, `__reset`, `__measure`,
`__blocked`, the `__navEchec` reset, the published `applyState` and `state`); `states/<surface>.ts`
(the 87 states, split by the surface each drives — acquisition, arrivals, library, media, settings,
system, maintenance, entry, relay — each under 400 non-blank lines); `publish.ts` (every seam a rule
reads that the product owns, § 3); `panel.tsx` (the ≡ panel, Q2 reading i); `index.ts` (one
`installHarness(store, queryClient)`).

**How the engine's private latch crosses.** `__go` sets `pilotage` so a driven state writes no
history. The latch is read by `recordPath`, `replacePath` and `switchPageFromLayer`, which phase 3
moves to `app/page-switch.ts`. Phase 1 exports a verb from the engine (`drivenWithoutHistory(run)`,
three lines inside a phase that subtracts ~160); phase 3 moves the verb with its readers. **No
product module reads harness state**: the harness CALLS a product verb.

**How the switchover excludes it.** The import sits behind the build constant the mock layer already
uses (`if (__MOCKS_BUILT_IN__) installHarness(…)` — a harness without mocks cannot drive: `__go`
resets them). The bundler drops the branch when the constant is false (L08's lift-out, measured on
demand: 2 807 428 bytes built in, 1 571 705 off). **No guard is added** (the operator's first measure
of 2026-09-12): the proof is that same measurement, re-taken once in phase 1 with the harness's own
strings searched in the off build. `switchover.py` lists nothing (§ 9.8); what dies at switchover is
written in the plan's D3 paragraph beside `harness.css` by the steward.

**Where the import line goes.** `app/shell.tsx` stands at 398 of 400 non-blank lines. Phase 1
replaces `import "../engine/states.js"` (one line) with the harness import, and the install call takes
the line the `states.js` side effect needed none of — the file does not grow.

### 4.2 The seams become imports

**The rule (frame-model Part 11, and the contract): a seam is read by a rule, never by a component.**
So the product's 19 self-published names become IMPORTS of their owning module (`store` from a boot
singleton in `app/store.ts`, `toast` from `app/toast-host.ts`, `bridge`/`screens` from
`app/history-bridge.ts`, `panel` from `app/panel-host.ts`, the query client from `lib/query-client.ts`,
…), and the WINDOW publications move to `harness/publish.ts`.

**Three consequences, decided here so no phase improvises them.**
- **A read that crosses two features composes in the route.** `features/media/media-screen.tsx:74`
  reads `window.__followActions`, which `features/acquisition/queries.ts` publishes; an import would
  break invariant 7. The route that mounts the media screen (`routes/`) passes the follow actions in
  as a property — invariant 7's own words, « they compose in the route ».
- **`harness/publish.ts` publishes only what a RULE reads.** Everything the ENGINE reads off `window`
  (`__address`, `__navigation`, `__layers`, `__toast`, `__store`, …) becomes an import through
  `engine/seams.ts` in the same phase. Otherwise a build with `__MOCKS_BUILT_IN__` off would start
  an engine reading publications that no longer exist.
- **A small fixture a rule reads directly** (`window.SEASONS`, nine rule files — `grep -lE "SEASONS"
  frontend/maquette/harness/*.py`; `window.LIBRARY` in `said_and_done.py`) is re-aimed to the seed the
  mock layer serves (`window.__mocks` exposes the seeds it answers from) in the phase that kills the
  constant. Constants under 100 lines die with their last reader like the families do. After phase 2, `grep -rn "window\.__"`
over product code outside `engine/` lists only the engine's six (§ 2.4); after phase 4, none but the
engine's own reads of what the engine still publishes; after L13b phase 11, none.

### 4.3 The ladder's handler

Target, from `docs/reference/frame-model.md` § 2 Part 4 — « the ranking is frame; the move is
behaviour ». **Verified**: the drawer and the dialog registered in L15 (`app/drawer.tsx:87`,
`app/dialog-host.ts:69`); `onEngineBack` asks the registry for both (`E:8503`, `E:8511`) and still asks
`#screen` by class and the sheet through `panel.isOpen()`.

Phase 3 moves, **unchanged in behaviour**: the handler and its rungs to `app/layers.ts` (the sheet
registers as a rung from `app/panel-host.ts`, the `#screen` rung stays until phase 5 deletes it); the
page-switch half to `app/page-switch.ts`; the addressed-panel table to `app/addressed-panels.ts`.
The engine's delegation keeps calling `switchPage`/`switchPageFromLayer` — by import — until L13b.
**B-229 is closed** (`fixed #528`); B-290, B-397 and B-275 are NOT touched here.

### 4.4 The boot

`__startEngine`'s work is the arrival, not the engine: adopt the initial state, register the back
handler, parse the arrival address, write the entry, call `__loadingDone`, push the guard entry,
reopen an addressed panel. It becomes `installArrival(store)` in `app/arrival.ts`, called where
`start({ store })` stands (`shell.tsx:275–276`). `world` holds `{ lib: [], removedLib }` and nothing
in product reads it (`grep -rnE "\bworld\b" … | grep -v /engine/` → comments and the store's type) —
it dies with `adoptWorld`. **The rules**: `boot_order.py`'s `BOOT_STEPS` row `^const start =
window\.__startEngine;` becomes `^installArrival\(`; `bridge.py` hold (f′) keeps its one hold and
reads « the startup screen is hidden before any harness call » without `typeof __startEngine`.

### 4.5 What nobody reaches

`#screen` is opened by nothing: both `setOpen(select("#screen"), …)` pass `false` (`E:7987`,
`E:8150`), `screenStack.push` does not exist. Phase 5 deletes the node (`index.html:520`), its engine
readers, `window.__close`, and the mount-node placement, which becomes `device.insertBefore(mountNode,
<the node after #screen>)` so document order — and the paint order `bridge.py` relies on — is
unchanged. **Eight harness files dereference it, not three** (§ 9.6): `bridge.py:278`, `audit.py:63,303`,
`audit2.py:50`, `back.py:61`, `ident.py:36`, `dest.py:35`, `states.py:31` would throw on a missing
node; `scroll.py:20` and `audit2.py:262,305,334` are selector-only. Each is re-aimed to
`[data-part="screen"][data-open]` (Q4) with its count unchanged. `bridge.py:278`'s « the legacy
mediaSheet is gone » hold passes trivially today — its re-aim says so rather than keeping a vacuous
hold green. **The `.screen.open` CSS rule is NOT dead** (§ 2.6): it styles the React screens and
converts in phase 7.

---

## 5. The data half

### 5.1 The nine families

Spans by a bracket matcher that skips strings and comments, declarations over 100 lines; key counts
checked against the seeds (`POSTERS` 401 literal keys → 399 entries: two duplicates, « The Hawk »,
« The Hack »). **`node scripts/extract-maquette-fixtures.mjs` needs a TypeScript install; the
byte-level arms of `check-mock-seeds.py` were not run by this design** — the implementer runs them in
the phase that converts each family.

| Family | Lines (`E`) | Last live reader | Served already? | Verdict | Phase |
| --- | --- | --- | --- | --- | --- |
| `SHEETS_RAW` | 9873–30411 (20 539) | `sheetFor` (`cardHTML`'s has-a-sheet, `panel-seasons.tsx:92`, `popover-episode.ts:40`, `follow-facts.ts:120`, `media-screen.tsx:93`, `media/queries.ts:66`); `titleForProviderId` (`media-screen.tsx:62`); `addressIdsFor` (`history-bridge.ts:204`, `media-verbs.ts:71`) | `media-sheets.json` (1 612 727 bytes) + `readMediaSheet`/`readMediaSeasons`, fields 1:1 through the rename map | **dies** once lists carry `ids` (§ 5.2) | a·14 |
| `POSTERS` | 395–809 (415) | `posterBox` via `cardHTML`/`tileHTML`/`libRowHTML`; `ui/panel/index.tsx:73`; `media-screen.tsx:48` | `posters.json`, composed only into the sheet | **stays a seed**, served as `poster` on lists | a·11 |
| `HERO_IMAGES` | 826–1153 (328) | `media-screen.tsx:44` | `hero-images.json` + `MediaSheet.hero`, unread | dies; the screen reads `sheet.hero` | a·13 |
| `trailerIds` | 1160–2474 (1 315) | `media-screen.tsx:229`, a fallback | `trailers.json` + `trailerVideo`, read first | dies | a·13 |
| `OWNED` | 2481–3863 (1 383) | `ownedFor` → `season-list.tsx:109`, `panel-seasons.tsx:72` | `owned-episodes.json` + `readMediaSeasons.owned` | dies | a·14 |
| `LIBRARY` | 3938–4464 (527) | `mediaNamedBy`, `knownMedium`, `follow-facts.ts:103` | `library-items.json` + `readLibraryItems`; **the engine copy already ignores mock deletes** | dies; the three readers ask an EXACT membership read the contract gains (amended 2026-09-13, ruling 41: the paged listing narrows all three, so it is a behaviour change, not a·10's) | b·10-bis |
| `MAINT_ACTIONS` | 4641–4876 (236) | none in product; `page_host.py:248`, `url_state.py`, one type in `maintenance/reference.ts` | `maintenance-actions.json` | **dead data** | a·15 |
| `SETTINGS` | 5756–7217 (1 462) | `allSettings` (the engine's field verbs, `settings/page.tsx:163,243`), `states.js:707` | `settings.json` + `readSettings` | dies; `allSettings` = `flattenSettings(cache)` — the engine's field branches read it through the same function until L13b ph. 1 | a·16 |
| `CAST` | 9701–9872 (172) | `media-cast.tsx:91` | `cast-portraits.json` + `castPortraits`, unread | dies | a·13 |

**What loses its subject with the last family**: `check-mock-seeds.py`'s `classification`, `lossless`
and `correspondence` arms and `build-mock-seeds.py` parse `legacy.js` through the extractor. Each
family converted in L13a is marked `converted` in `fixture-register.json` (32 are already), so
`correspondence` compares fewer; the parser arms themselves go in L13b phase 11, with the file they
parse — or take the « the engine is gone → no subject » branch `arm_reference_slice` already has
(`scripts/check-frontend-boundaries.py:959`). `schema`, `provenance`, `generated`, `handlers` survive.

### 5.2 The identity demand (D7) — L13a phase 6

**The gap.** Every list card is keyed by TITLE; only `MediaSheet` carries `ids` (a scan of
`components.schemas` for `ids|provider|providerId|tmdbId`: `MediaSheet.ids`, and `provider` on two
decision schemas). Without an identity on the list item, the poster button of every card, the
`screens.mediaSheet(title)` crossing, the rescrape verb and B-366's ruling have nowhere to go once
`SHEETS_RAW` dies.

**The demand, in the register's form** — the register is COMPUTED from the contract
(`python3 scripts/compare-contracts.py --write`), so the demand is written as the contract change
and appears in `docs/reference/frontend-backend-demands.md` § 2 on regeneration:

| Operation | Schema | The interface adds |
| --- | --- | --- |
| `GET /api/acquisition/to-handle` (`readAcquisitionQueue`), `GET /api/staging/media` (`readStaging`) | `QueueCard` | `ids`, `poster` |
| `GET /api/library/items` (`readLibraryItems`) | `LibraryItem` | `ids`, `poster` |
| `GET /api/library/recent` (`readLibraryRecent`) | `LibraryRow` | `ids`, `poster` |
| `GET /api/library/incomplete` (`readLibraryIncomplete`) | `IncompleteShow` | `ids`, `poster` |
| `GET /api/acquisition/followed` (`readFollows`) | `Follow` | `ids` **required**, `poster` |
| `GET /api/acquisition/search` (`searchProviders`) | `SearchResult` | `ids`, `poster` |
| `GET /api/acquisition/suggestions` (`readSuggestions`) | `Suggestion` | `ids`, `poster` |
| `GET /api/media/{provider}/{providerId}` (`readMediaSheet`) | `MediaSheet` | `title` |

`ids` is the existing `ProviderIds` (an object of provider → integer or string); nullable everywhere
but `Follow`, where the operator's B-366 ruling makes a sheetless follow unrepresentable (« le suivi
sans fiche n'est pas un état possible »). `poster` is a URL or null. **The seeds are projected by
title join** from `media-sheets.json` and `posters.json` in `build-mock-seeds.py`; the handlers pass
the fields through. Nothing reads them in phase 6 — the oracle reads zero — and each surface phase
switches its readers.

---

## 6. The verbs (L13b phases 1–7)

Batches by owning feature. Method: each branch brace-matched inside the span of § 2.3; emitters by
`grep` of `data-<name>` and `dataset.<name>` over `design/src` outside `engine/` plus `index.html`,
every hit read; rule taps by the same `grep` over `harness/*.py`. Each phase re-takes its own rows
before it moves them:

| Phase | Feature | Names | Branch lines | Rule files / taps |
| --- | --- | --- | --- | --- |
| b·1 | settings | `setting`, `secret`, `field`+`to`, `deletefield`+`index`, `addfield`, `cancelsetting`, `save`, `reloadsettings`, `restart`, `confirmrestart`, `qsettings` | 84 | 7 / 46 |
| b·2 | account · maintenance · releases | `signout`, `sheet=utilisateur` · `maintact` · `releases`, `profile` (the last two surface-openers) | 54 | 7 / 15 |
| b·3 | media | `mediasheet`, `ep` | 11 | 16 / 34 |
| b·4 | arrivals | `pipe`, `manual`, `resolve`, `leave`, `next`, `act=resolve`, `.cfoot` | 80 | 9 / 39 |
| b·5 | acquisition | `acqtab`, `pill`, `fmode`, `sugmode`, `sheetprim`, `complete`, `standby`, `tmdb`, `act=add:N`+`confirmadd`, `journey`, `sheet=plus` | 168 | 16 / 46 |
| b·6 | library | `lens`, `cat`, `lmode`, `sort`, `setsort`+`reversed`, `clearq`, `selmode`, `delsel`, `tile`+`selectedTitle`, `del`, `.act` | 98 | 21 / 75 |
| b·7 | frame | `page`, `go`, `navgo`, `drawer`, `toast`, `phase`, `panel` → `app/` | 97 | 36 / 167 |

**Order**: settings first (five of its thirteen are forwarders to `__settingsVerbs` — the cheapest
proof the move is mechanical); the frame last (167 taps, and `page`/`go`/`navgo` are
`switchPage`'s callers, which it takes out of the engine's reach). The surface-openers leave in b·2
(`releases`, `profile`), b·3 (`mediasheet`), b·4 (`resolve`) and b·5 (`journey`); the contract's
`grep -cE` reads 0 after b·5. **A move keeps its timer**; the timers die together in b·9.

**One name, one owner — decided here so no phase improvises it.** The registry maps ONE dataset key
to ONE handler (`lib/verbs.ts`, `actions.set(keyForAttribute(name), act)`), and invariant 7 forbids one
feature answering for another. Three engine names are VALUE-dispatched across owners: `sheet`
(`utilisateur` is the account's, `plus` acquisition's), `act` (`add:N` acquisition's, `resolve`
arrivals'), `clearq` (`lib` the library's, `foll` acquisition's). Each is SPLIT into one English name
per owner in the phase of its first owner, with `scripts/rename-identifiers.py` across its three ends
(the markup, the reader, the rules — `CLAUDE.md` § Code Conventions), the rules re-aimed with their
counts unchanged, and the diff re-read after the tool. **The two CLASS-dispatched branches take no
new name**: `.cfoot`'s « Récupérer » and « Résoudre » become the card foot emitting `data-take` and
`data-resolve`, which are already registered verbs (L21, b·4), and `.act`'s swipe actions emit
`data-pause`/`data-remove` (already registered, L21) on a follow and `data-del` (b·6) on a library row.

**The sixteen `window` getters** (§ 2.2) leave with what they read, never as a block: `STATES`,
`pilotage`, `state` in a·1; `unwinding`, `unwindInProgress`, `armedExit`, `currentRender` in a·3;
`store`, `world` in a·4; `cardDrag`, `openCard`, `openCardDx`, `clickAfterDrag`, `swallowClick`,
`deckDrag`, `sugDrag` in b·8. Each one a rule reads (`armedExit` 25 lines, `swallowClick`) is
published from its new module by `harness/publish.ts` in that phase.

**Each move is a behaviour move** (L19's definition). The rule that held it runs green before and
after with its count unchanged. A name held by no rule — measured: `to`, `deletefield`, `addfield`,
`next`, `sheetprim`, `releases`, `standby`, `complete`, `tmdb`, `signout`, `selectedTitle` tap 0 rule
files — gets its hold written FIRST, red against the engine branch deleted on purpose, before the
branch moves.

**Amended 2026-09-13 (§ 7.1, rulings 73–74):** `.cfoot`'s « Résoudre » does NOT become `data-resolve` — that name means « pick this candidate » (`resolution-cards.tsx:90`, B-474); the arbitration opener is the arrivals feature's `data-resolution`, and « Récupérer » emits `data-take`. `pipe` is not a move: it converts at b·10-ter.

---

## 7. `refonte.html`, R72 and the ledger's home (L13a phase 19)

The file is a comment ledger in an empty `@layer block2 { … }`. **Its home is history**
(`docs/reference/documentation-model.md` § 2): the post-merge gesture of L13a cites it as
`frontend/maquette/design/refonte.html@<L13a's squash parent>` from the plan's L07 entry, which the
steward amends. No document is created for it — a copy in the tree is the archive the model removed.

**R72 renegotiated.** Hold (a) — the fragment injected verbatim once — has no subject and is retired
in `regions.json` with the reason. (b) one module script tag and (c) the bundle under `dist/vite/`
stay, each mutation-tested in the phase (remove the script tag → (b) alone falls; delete the bundle
→ (c) alone falls).

**Sixteen readers, not fourteen**: INVENTORY § 6's list misses `tests/scripts/test_build_identity.py:35`
(the identity hash's inputs — it drops the path with `build-identity.mjs`) and
`frontend/maquette/design/src/i18n/fr.json:14` (a sentence naming the file — rewritten to name the
tokens and the catalogue). **The fourteen INVENTORY names, and what each does instead**: `vite.config.mjs:38` (the injection goes);
`build-identity.mjs:26` (drops it from the hash inputs); `serve.py:112` (the « missing » page goes);
`harness/shell.py:49` (R72, above); `harness/common.py:152`, `harness/palette.py:30` (an unused path,
deleted); `harness/switchover.py:61,222` (R73: the copied input and the « edited source is rebuilt »
probe move to `index.html`); `harness/rename.mjs:25` (drops it); `scripts/check-css-tokens.py:80`
(fails on absence today — the input goes); `scripts/csstokens_login.py:33`,
`scripts/csstokens_ranks.py:61`, `scripts/nofrench_lexicon.py:51`,
`scripts/check-tailwind-confinement.py:92`, `scripts/check-compositor-css.py:115` (each drops the
path from its inputs).

---

## 8. The ladder's shape (L13b phases 9–10) — RATIFIED by the operator on 2026-09-13 (Q3 = A)

**B-290's arbitration, written out.** Today a layer left for an arrival has two shapes: « Voir la
fiche » closes the panel inside the navigation's commit and KEEPS its entry (Back crosses two:
`history.state.__TSR_index` 3 → 1); its siblings (`releases`, `profile`, `take`) POP the entry and
push 240/260 ms later. B-397 is a third: a panel re-produced after an edit pushes another entry.

**Decision D-L13-1 (ratified 2026-09-13): a layer left for an arrival KEEPS its entry, and Back onto it REOPENS
it.** § 16 rule 1 read literally: opening a panel is an arrival, so the panel is on the stack, and
Back from the screen it opened returns to it — which is B-275's own wording (« Back should reopen it
over the list »). The entry records what reopens it — `{ layer: "sheet", kind, subject }`, written
by `app/panel-host.ts`, which already holds `openKind`/`openSubject` — so a transient panel reopens
as surely as an addressed one. The handler tells the two entries a Back can land on apart by that
record: an entry left by an ARRIVAL reopens; the leftover a tab-bar tap buries (`E:8530–8570`'s
paragraph) carries the same record and is stepped over only when the page under it differs from the
page it was opened on. **Every sibling takes the same shape**, so the ten timers have no subject and
go (`exits.py` refuses the gap instead of printing it — R103's promised reversal). **B-397** is the
same decision seen from inside: re-producing on the entry that already records the panel REPLACES
(D1b rule 1 — a redraw is an adjustment).

**What it makes void**: the close-then-wait pattern; `openOnCurrentEntry`'s special case in
`producePanel`'s deferred path becomes the general path; B-398's counting in `switchPageFromLayer`
stays (it is the page switch, not the arrival).

**The rejected reading, so it is not re-proposed**: every sibling pops first (the entry removed,
Back returns to the list). It keeps « one entry per gesture » true and makes B-275 unanswerable —
the panel is gone from the stack, so Back cannot return to it.

**The rules (labels bound to numbers when the phase runs):**
- **R-L13-a — the pops are counted.** For each of the five openers from an open panel: forward
  `history.length` +1; Back ×1 lands on the panel, OPEN; Back ×2 lands on the list, closed.
  Red on the engine as it stands for the siblings (Back ×1 lands on the list) and for « Voir la
  fiche » (Back ×1 lands on the list with the panel shut). Mutation: the arrival pops the entry first.
- **R-L13-b — a redraw does not stack.** Edit a setting three times in its panel; one Back closes it.
  Red today (B-397). Mutation: `redraw` pushes.
- **R-L13-c — the return is drawn.** Back from a media screen reopens the panel under
  `::view-transition-new(leaving-panel)` running `panel-down` in reverse; under `reduce`, no animation.
  Red today (no subject). Mutation: the reverse keyframes removed.

---

## 9. What the plan gets wrong, measured

Recorded for the steward, who amends; **no file outside `docs/features/maquette-l13/` is edited.**

1. **`IMPLEMENTATION.md`'s « Next » row reads L20.**
   `grep -o "| \*\*Next\*\*[^|]*| [^.]\{0,60\}" IMPLEMENTATION.md` → « L20 — The global levers and the
   history ». The re-order is on the steward's `docs/steward-lot-close`, not yet on `main` (steward's
   answer to the handshake).
2. **« one `app/layers.ts` » cannot hold the page-switch and addressed-panel halves under the
   ceiling.** The handler with its rungs, `closeLayers`, `hideLayers` and the latch is ~260 lines; with
   `navigationState`/`recordPath`/`replacePath`/`switchPage`/`switchPageFromLayer` (~200) and
   `REOPEN`/`reopenAddressedPanel` (~110) it is ~570 against invariant 6's 400. Spans in § 2.2. The
   design keeps « one `app/layers.ts` » for what frame-model Part 4 names and adds two siblings.
3. **L20's plan phase 2 creates `design/src/states/system.ts`** (`grep -n "states/system.ts"
   docs/features/maquette-l20/plan/phase-02-named-states.md`). With L13 before L20, that phase loses its
   subject: B-352 closes in L13a phase 1 and a new state is added to
   `design/src/harness/states/system.ts` under the ceiling. The steward re-targets L20's phase 2.
4. **The L13 entry's « Twelve live readers name the path »** (refonte.html) reads 16 (§ 7).
5. **The L13 entry's « `legacy.css` and its guard » and D10's « it dies with L13 »** describe a sheet
   the engine alone needs. **92 of its 148 classes style React components that have no variant**
   (§ 2.6), `.screen.open` among them. `legacy.css` dies with the DRAWING's conversion, surface by
   surface — which is a conversion wave's worth of work, not a deletion.
6. **B-232's and the survey's « three readers » of `#screen`** are three in the ENGINE; the harness
   has eight more (§ 4.5).
7. **D5's « 156 top-level declarations republished on `window` »** reads 153 plus 16 getters (§ 2.2);
   frame-model Part 11's « 43 distinct names across `design/src` » and « the seams that exist because
   the engine needs them (`__address`, `__bridge`, `__panel`, `__screens`, `__store`) die with it » —
   those five are the SHELL's, 28 product seams are read by rules and survive as harness publications
   (§ 4.2).
8. **The brief's « `switchover.py` already lists what moves »**: it is R73 (the host serves the build)
   and lists nothing (`grep -n "DRIVING\|exclude" frontend/maquette/harness/switchover.py` → none).
9. **R80's `regions.json` entry and D10 say sixteen pairs**; the floor is 15
   (`grep -n PAIRS_FLOOR frontend/maquette/harness/residue.py`).
10. **Three open register rows whose subject has left**: B-220 (the drawer and tab bar —
    `app/drawer.tsx`, `app/tab-bar.tsx` exist since L15, #528), B-236 (`grep -c "panel\.open(" E` → 0
    since L19, #558), B-071 (the notes toggle « reports success for a class nothing reads » —
    `harness.css:145` reads `:root.notes .note` since B-081). The steward closes them with those
    readings; L13a phase 1 moves the toggle into the harness module as it stands.
11. **The brief counts 24 open rows naming L13; #588 fixed seven** (B-332, B-334, B-335, B-341,
    B-342, B-343, B-361) and B-397 joined: 18 (method: every `open` index row whose row or body
    matches `\bL13\b`).
12. **INVENTORY § 3's 116 reads over 64 names** read 113 over 62 on `main` (§ 2.3).
13. **The README's « 54 » named states** reads 87 (L13c phase 9 corrects it).

---

## 10. The register, assigned

| Row | Sub-lot · phase | Why there |
| --- | --- | --- |
| B-071 | stale (§ 9.10); the toggle moves in a·1 | its premise was repaired by B-081 |
| B-220, B-236 | stale (§ 9.10) | L15 / L19 discharged them |
| B-232 | a·5 | the dead layer |
| B-352 | a·1 | the table leaves the grandfathered file |
| B-465 | b·6 | the comment sits in the `tile` branch that moves |
| B-337 | b·8 | the swipe listener moves; its rule taps once with a real touch |
| B-290, B-397 | b·9 | § 8 |
| B-275 | b·10 | § 8 |
| B-312 | c·1 | behaviour on the library selection, once the `lens` verb is the feature's (b·6) |
| B-340 | c·2 | the add screen's `addQ`/`addMode`/`added` leave the store's legacy shape |
| B-339 | c·3 | the disabled drawing on `ui/panel`'s action variant (a·8 converted `.sact`) |
| B-336 | c·4 | the kind chips' strip, converted in a·10 |
| B-331 | c·5 | the pull indicator, whose block moves in b·8 |
| B-327 | c·6 | `SETTINGS` is a seed after a·16, so the seventh scheduler is one seed row |
| B-366 | c·7 | `Follow.ids` required since a·6; the tile's guard branch goes. The entry asks for « a guard that refuses one »; § 11 adds no guard, so the refusal is the contract's required field plus the mock refusing to build a follow without one, and R156 stays the gate it already is — said to the operator as the reading of his ruling |
| B-345 (library half) | c·8 | the fixture clause's hand-reachable states. The entry's ruling reads « L13: the library and the rest »; what « the rest » covers beyond the library is not measured here and is reported to the steward in c·8 rather than guessed |

---

## 11. What this design does NOT do

- No rule, mock, seed or line of code. No redrawing: every conversion draws the SAME thing (§ 15 —
  what is in the maquette is validated), proved by the oracle.
- No new guard (the operator's first measure of 2026-09-12); guards that lose their subject die in
  the phase that kills what they read.
- It does not decide Q2 or the cut — the operator does — nor D-L13-1 (§ 8), which the operator reads
  as an architecture decision before L13b opens.
- It does not re-litigate a home the plan decided; where a decided home does not fit (§ 9.2), it keeps
  the decision's name and says what was added beside it.
