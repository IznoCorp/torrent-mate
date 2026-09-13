# L13a — resume brief for the successor

Written by the seventh L13a implementer when it stood down at the a·10 boundary (gauge 34 %, the steward's ruling:
a·10 cost 25 points and a·11 is wider, so a·11 is a whole session's unit, the a·8 and a·9 precedent). Read it after
`docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything. This file only records state, rulings and
traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 `123816c93`, a·2 `383c67549`, a·3 `40fc7b785`, a·4 `ad4d3096a` + `4918abe65`, a·5 `504ce4897`, a·6 `f353eea14`,
  a·7 `8fba453c5`, a·8 `b2f5f2335` (+ `097558d46`), a·9 `0cb5ce960`, then:
  - `c8995c858` `docs(maquette-l13a): a·10's STOP D — the library's membership read moves to b·10-bis`
  - **a·10** `c96358876` `refactor(maquette-l13a): the library draws its tiles, rows and swipe rows as components`
  - then this file.
- Gates, each on its own head, under the shared mutex:
  - a·5 to a·9: see the a·9 RESUME (`git show 4e09fa8d0:docs/features/maquette-l13/RESUME.md`).
  - a·10 (`c96358876`):
    - `run.sh --contracts`: 19 rules + 27 guards, no violation.
    - `--oracle`: 87 states x 34 regions, 2 958 measurements, no divergence.
    - Beside them: `tsc -b` 0; vitest 7 files / 112 tests; `check-no-french`, `check-frontend-boundaries`,
      `check-markup-contracts`, `check-frame-domain`, `check-mock-seeds`, `check-module-size`, `check-poster-box`,
      `check-compositor-css`, `check-css-tokens`, `check-legacy-css-residue` exit 0.
    - pytest `test_check_maquette_comments`, `test_residue`, `test_check_css_tokens`, `test_csstokens_ranks`: 75 passed
      under the tests lock.
    - The first contracts reading fell twice, both corrected and named in the commit body: R77's re-aim and the module
      ceiling (traps below).
    - The gate logs are `/private/tmp/tm-l13a/a10-contracts.log` and `a10-oracle.log`; earlier phases' logs are in
      `earlier-phases/`.
- Records:
  - `engine/legacy.js`: **29 744** non-blank (ledger re-recorded, 29824 → 29744).
  - `legacy-css-residue.json` ceiling: **168/113/691** (rules/classes/declarations).
  - R80 `PAIRS_FLOOR`: **30**.
  - `check-poster-box` floor: **6** (legacy.css x2, ui/variants/card.ts x1, ui/variants/surfaces.ts x2,
    ui/variants/tile.ts x1).
  - `csstokens_ranks.py` `LOCAL_DETAILS`: **6**.
  - `comment-references-baseline.json`: read **407**, references **281**.
  - `fixture-register.json`: untouched ($counts served 41 / asset 5 / interface 29 / unserved 4 / total 79).
  - `hold-counts-baseline.json` is NOT re-recorded. At a·19's `--compare`, R80 (`residue.py`) reads 34 against the
    baseline's 19: a·7's −5, a·9's +15 and a·10's +5, each named in its commit body. R77 (`page_host.py`) keeps its
    hold count (re-aimed, not added).
- `--compare` over the whole suite, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·11** (`plan/phase-a11-*.md`), then a·12 … a·17, **a·17-bis** (the ≡ panel dies, rulings 29 and 31), a·18,
  a·19.
- Version not bumped. No pull request.

## Rulings — not to be reopened

1–40: see the a·9 RESUME (`git show 4e09fa8d0:docs/features/maquette-l13/RESUME.md`; earlier ones point further back),
carried over unchanged. In short, the ones a·11 leans on:
- **32**: R80 floor moves to the MEASURED count, every pair added and removed named.
- **33**: a rule grouped with `-webkit-touch-callout` is not paired.
- **36**: every log goes under `/private/tmp/tm-l13a/`.
- **37**: the card is `ui/card.tsx`'s PARTS.
- **38**: a card's domain composition stays in its feature; features never import each other.
- **39**: no card rule dies before `cardHTML` does; the fourteen card pairs and `.flux` fall with their last writer.
- **40**: the card's French lives in `surfaces.card.*`; `check-poster-box` and `LOCAL_DETAILS` are re-taken in the
  phase's commit.

From a·10 (the steward accepted a·10 on the reading of its gate logs):

41. **`LIBRARY`, `INCOMPLETE` and `knownMedium` die at b·10-bis, not at a·10** (STOP D). The paged listing narrows all
    three readers (`follow-facts.ts`'s `inLibrary` on `/acquisition`, `knownMedium` for a typed address, and
    `mediaNamedBy` over pages not loaded), and a·6's `ids` make none of it moot: both « Doctor Who » rows carry the
    same ids.
    - The owner is **b·10-bis « the library's membership read »**, a BEHAVIOUR phase before b·11. The contract gains
      an exact read (title, and year where ids collide), its rule first and red against the engine. The three
      fixtures die there with their readers and the harness re-aims at the `window.__mocks` seeds (`panel.py`,
      `url_state.py`, `said_and_done.py`, `library_sort.py`, `season_grab_unfollowed.py`).
    - Dated amendments are in `c8995c858`: phase-a10, phase-b06:39 (`mediaNamedBy` reads `window.LIBRARY` until
      b·10-bis), DESIGN § 5.1, and the INDEX row. The steward writes b·10-bis's phase file.
42. **String-composed surfaces get a MARKUP spelling in `ui/`, not a React element** — `ui/tile.ts` (`tileMarkup`),
    `ui/rows.ts` (`swipeRowMarkup`, `selectionRowMarkup`), the spelling `ui/poster.tsx` already had. `VirtualRows`
    compares each row's STRING to decide a redraw, and follows/discover compose their lists as strings. Attributes go
    through `attributesMarkup` (`ui/tile.ts`); the domain attribute values (`media:…`, `data-mediasheet`, `sug:…`)
    are the feature's.
43. **R77's view-switch hold reads `#libitems`'s `data-part` (`grid`/`section`)**, re-aimed from a `className ===
    "gallery"` equality. It was said out loud and mutation-tested (the hold fell naming
    `{'mode': 'grid', 'drawn': 'section'}`). **`page_host.py` is AT ITS CEILING: 999 non-blank.** The next edit that
    adds a line there SPLITS the module on a subject; it does not compact it again.
44. **The tile badge's no-fill defect is carried, not repaired**: follow-status badges read
    `var(--neutral-signal|--waiting|--info|--warning)`, which is declared nowhere, so they have never had a fill.
    `tileBadge()` has one fill tone, `overlay`. The register entry is the steward's, at the gesture; the owner is the
    wave that next opens the tile's variants.

## Method — unchanged from a·9

- **After every phase's commit and before ANY push**:
  `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder sh scripts/heavy.sh --class test l13a python3 -m pytest tests/scripts/test_check_maquette_comments.py -q`.
  A phase that adds or removes a maquette file or a dated comment re-records
  `python3 scripts/check-maquette-comments.py --record` in its own commit; only `read` and the reference count move.
- **Every other baseline a phase moves** is re-recorded in the phase's own commit, its numbers in the body.
- **Count R80's pairs offline before setting the floor**:
  `cd frontend/maquette/harness && python3 -c "import residue as r; f=r.read_factories()[0]; c=r.pair_up(r.read_residue()[0], f)[0]; print(len(c)); [print(x['selector'], x['factory']) for x in c]"`.
- **Run by hand, before the contracts tier, the guard the tier runs with a flag**:
  `python3 scripts/check-module-size.py --root frontend` (it reads the harness; the bare run does not).
- **Search every harness hold for a CLASS-STRING equality on a class the phase turns into a variant**:
  `rg -n -g '*.py' "className" frontend/maquette/harness`. A `=== 'x'` on a variant's element falls the moment the
  class string grows utilities; re-aim to a `data-part` and say it.

## What a·11 inherits — measured at the a·10 boundary (re-take before trusting)

**`cardHTML` callers outside the engine** (all string emitters):
- `features/acquisition/now-tab.tsx:87`, `:100`, `:124`, `:130`, `:137`;
- `features/acquisition/add-screen.tsx:165`;
- `features/acquisition/discover-cards.ts:69`;
- `features/acquisition/follows-tab.tsx:149`, inside `swipeRowMarkup`;
- `features/library/incomplete-lens.tsx:57`;
- `features/library/library-rows.ts:79`, inside `swipeRowMarkup`.

The engine itself no longer calls `cardHTML` (its only `cardHTML(` is the definition). Because those surfaces are
strings, a·11 either writes a card MARKUP spelling beside `ui/card.tsx`'s parts (ruling 42's shape) or converts a
surface to JSX where its container is React-owned. `VirtualRows` stays string-based.

**R80 at a·11**:
- The fourteen card pairs (`.card`, `.ccol`, `.ctop`, `.cbody`, `.ctitle`, `.csub`, `.creason`, `.cov`, `.cmeta`,
  `.caption`, `.folder`, `.dlabel`, `.strip`, `.st`), `.chip` and its five tones, and `.pfall` all fall with
  `cardHTML`, their last bare writer. No chip/pfall emitter is left outside the engine.
- `.flux` falls at a·15.
- The `.swipe` pair (↔ `swipeRow()`) and the four `.gallery` pairs (↔ `posterGrid()`) stay while their groups live.

**The six `legacy.css` groups a·10 KEPT, and the a·11 class that holds each**:
1. `.gallery` and its three `@container port` rules — the discover feed's `box.className = "gallery"`
   (`discover-feed.ts` ~276). When it switches to `posterGrid()`, the rules die, and so do the four pairs.
2. `.act`, `.act.resume`, `.act svg`, `.act.pause`, `.act.remove` — the swipe actions written as strings in
   `follows-tab.tsx` and `library-rows.ts` (b·6 owns `.act`'s branch; the rules wait for the last bare writer).
3. `.swipe, .sugwrap, .deck` (`user-select`) — `.sugwrap` and `.deck`, from `discover-cards.ts`.
4. `.swipe img, .sugwrap img, .deck img, .tile img` (`user-drag`) — the same two, plus `.tile`, now written by
   `ui/tile.ts`. Split the selector list only with `check-compositor-css.py` read.
5. `.poster, .tile, .dcard` (long press) and `.poster img, .tile img, .dcard img` — `.poster` from `cardHTML` and
   `.dcard` from `deckCard`.
6. `.poster img, .tile .p img, .pfall` (the fallback ground) — `.poster` and `.pfall`, from `cardHTML`.

## Traps met — each cost a run

**THE RULE FOR EVERY PHASE (steward, 2026-09-13)**: before a gate, search every removed name everywhere a reader can
live — `rg -n -g '*.py' -g '*.mjs' -g '*.txt' -g '*.json' NAME frontend/maquette/harness scripts tests` — in its
`window.NAME`, bare `NAME(` and `=>NAME(` forms, and replay each reader alone.

From a·5 to a·9: see the a·9 RESUME. The recurring ones:
- `check-legacy-css-residue.py --record` drops the long `$comment`: restore it with only the figures changed.
- zsh: `echo ==` errors, and it silently kills the rest of a compound command.
- The Bash tool's working directory follows a `cd` made in ANY call: start every command with an absolute `cd`.
- `run.sh --contracts` prints a failing guard's detail only in its « cheap guards » section.

New in a·10:
- **harness/page_host.py at 999/1000: a compaction is REFUSED; an edit at zero net lines is allowed and says so in its commit body; the first edit that ADDS a line extracts a module (a·12, a·15 or a·16 name it as a reader).**
- **A harness hold compared a class STRING** (`page_host.py` R77, `className === "gallery"`), and fell the moment the
  container wore a variant. See Method for the search, ruling 43 for the re-aim.
- **`check-module-size.py --root frontend` is not the bare run**: the contracts tier runs it over the harness, and a
  re-aim's eight comment lines put `page_host.py` at 1 008.
- **R80 pairs a factory with a SHARED GROUP rule** once the class's own rule is gone. A group declaring
  `-webkit-touch-callout` cannot compare, so the factory leads with a utility and the markup writes the identity class
  (`tile ${tile()}`, the `posterFrame()` precedent). A group declaring `user-select` compares, so the factory carries
  `select-none` (`swipeRow()`).
- **A one-letter anchor may already be claimed**: `fr` was `factValue()`'s. Duplicate anchors are counted, not
  refused, and the second is silently not paired: lead with a utility and write the letter at the call site
  (`stripDot()` precedent).
- **`scripts/code-vocabulary.txt` lacks `gallery` and `listed`**: the grid factory is `posterGrid`.
- **`UiState.selected` is typed `unknown`**: cast `as Set<string>`, as `selection-bar.tsx` does.
- **`check-frontend-boundaries.py`'s duplicate-import arm counts `import type { X }` plus `import { y }` from one module
  as two imports**: merge them (`import { y, type X }`).
- **`heavy.sh --class browser` holds off until 4 096 MB are free**, so a contracts run can outlive the tool's 600 s
  timeout. The tool then backgrounds it: wait for its notification, never poll.
