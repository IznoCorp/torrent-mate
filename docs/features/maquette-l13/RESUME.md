# L13a — resume brief for the successor

Written by the eighth L13a implementer when it stood down at the a·12 boundary (the steward's ruling: a·12 was this
session's last unit whatever the gauge read, because a·13 — Média artwork and cast, plus the death of `POSTERS` that
ruling 45 hands it — is a whole session's unit). Read it after `docs/features/maquette-l13/BRIEF-L13a.md`, which still
governs everything. This file only records state, rulings and traps, and it dies with the wave's folder at the
post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 `123816c93`, a·2 `383c67549`, a·3 `40fc7b785`, a·4 `ad4d3096a` + `4918abe65`, a·5 `504ce4897`, a·6 `f353eea14`,
  a·7 `8fba453c5`, a·8 `b2f5f2335` (+ `097558d46`), a·9 `0cb5ce960`, a·10 `c96358876` (+ STOP D `c8995c858`), then:
  - `f7e1a82a7` `docs(maquette-l13a): the page_host.py ceiling trap the auditor ordered into the resume brief`
  - **a·11** `a6c91fc57` `refactor(maquette-l13a): acquisition draws its cards through components and lists carry their poster`
  - **a·11 follow-up** `1e34b9660` `fix(maquette-l13a): the seed builder joins a list item's poster through its base title`
  - **a·12: no commit** — its scan found no subject (below); the empty reading is recorded in the commit that adds
    this file.
- Gates:
  - a·5 to a·10: see the a·10 RESUME (`git show bc7cf8e0c:docs/features/maquette-l13/RESUME.md`).
  - a·11, on `1e34b9660` (committed 12:33:31):
    - `run.sh --contracts`: 19 rules + 27 guards, no violation — `/private/tmp/tm-l13a/a11-final-contracts.log`
      (12:38:01).
    - `--oracle`: 87 states x 34 regions, 2 958 measurements, no divergence — `a11-final-oracle.log` (12:38:38).
    - On `a6c91fc57`'s tree: `tsc -b` 0; vitest 7 files / 112 tests; `check-no-french`, `check-frontend-boundaries`,
      `check-markup-contracts`, `check-poster-box`, `check-compositor-css`, `check-css-tokens`,
      `check-legacy-css-residue`, `check-mock-seeds`, `check-frame-domain`, `check-module-size` (bare and
      `--root frontend`) exit 0; pytest `test_check_maquette_comments` 36 passed under the tests lock.
    - R77's re-aim (ruling 46) mutation-tested with `scripts/mutate.sh` on `discover-feed.ts` (the poster mode wrote
      `"grid"`): the hold fell naming `{'mode': 'poster', 'grid': 'grid', 'tiles': 30}`, restored.
  - a·12, on the head that adds this file: `a12-contracts.log` and `a12-oracle.log` under `/private/tmp/tm-l13a/`,
    and the comment-record test alone; their figures are in the stand-down report.
- a·12's scan, `python3 /private/tmp/tm-l13a/a12-residue-scan.py` (every literal of `releases-screen.tsx` and
  `quality-screen.tsx` against the 54 classes `legacy.css` still selects): `releases-screen.tsx` nothing;
  `quality-screen.tsx` `panel` ×2, both `factsPanel()`, whose identity class a variant already carries (DESIGN § 2.6)
  and whose `.panel` rule waits for a·18 with R80's pair. **No class is styled only by `legacy.css`: no subject, no
  commit** (phase-a12 « If the scan lists nothing »).
- Records:
  - `engine/legacy.js`: **29 579** non-blank (ledger 29744 → 29579).
  - `legacy-css-residue.json` ceiling: **83/54/301** (rules/classes/declarations).
  - R80 `PAIRS_FLOOR`: **4** (`.flux`, `.panel`, `.scrim.open`, `.sheet.open`).
  - `check-poster-box` floor: **4** (`ui/variants/card.ts` ×1, `surfaces.ts` ×2, `tile.ts` ×1).
  - `csstokens_ranks.py` `LOCAL_DETAILS`: **5**.
  - `comment-references-baseline.json`: read **413**, `legacy.css` references **56**.
  - `fixture-register.json`: `STRIP_LABELS` and `plages.out` converted; **`POSTERS` NOT converted** (ruling 45).
  - `hold-counts-baseline.json` is NOT re-recorded. At a·19's `--compare`, R80 (`residue.py`) reads **8** against the
    baseline's 19: a·7's −5, a·9's +15, a·10's +5, a·11's −26, each named in its commit body. R77 (`page_host.py`)
    keeps its hold count (re-aimed twice, never added).
- `--compare` over the whole suite, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·13** (`plan/phase-a13-media-artwork.md`, with its 2026-09-13 amendment), then a·14 … a·17, **a·17-bis**
  (the ≡ panel dies, rulings 29 and 31), a·18, a·19.
- Version not bumped. No pull request. Pushed at this boundary (the stand-down report carries `git ls-remote`).

## Rulings — not to be reopened

1–40: see the a·9 RESUME (`git show 4e09fa8d0:docs/features/maquette-l13/RESUME.md`); 41–44: see the a·10 RESUME
(`git show bc7cf8e0c:docs/features/maquette-l13/RESUME.md`). In short, the ones a·13 leans on:
- **32**: R80 floor moves to the MEASURED count, every pair added and removed named.
- **36**: every log goes under `/private/tmp/tm-l13a/`.
- **38**: a card's domain composition stays in its feature; features never import each other.
- **41**: `LIBRARY`, `INCOMPLETE` and `knownMedium` are b·10-bis's.
- **42**: string-composed surfaces get a MARKUP spelling in `ui/` (`tileMarkup`, `swipeRowMarkup`,
  `selectionRowMarkup`, and now `cardMarkup`).
- **43**: `page_host.py` R77 reads identities, never a class-string equality.

From a·11 (the steward accepted a·11 on the reading of its final-head logs):

45. **`POSTERS` does not leave the engine at a·11** (STOP D: three readers have no `poster` field). a·11 did everything
    else as written — `cardHTML`, `posterBox`, `stripHTML` died; every list reads `poster`; `posterArtworkFor()` keeps
    the by-title form ONLY for `features/arrivals/resolution-cards.tsx:100` and `:161` — and the table and its
    publication stay, `POSTERS` not marked converted. **Its death is a·13's, in the steward's words:** « a·13 adds
    `poster` to DecisionCandidate (types.d.ts:1229) and DecisionChoice (:1240) as an a·6-type contract declaration
    (types, seeds, demands regenerated), then deletes the table and its window export, re-taking the harness readers
    with the widened grep. » a·13 also already owns `features/media/media-screen.tsx:48-50` (`sheet.poster`).
    Dated amendments: phase-a11 and phase-a13, in `a6c91fc57`.
46. **An in-place re-aim at ZERO net lines is neither the compaction the auditor refuses nor the extraction it owes.**
    `page_host.py` R77's suggestion-mode hold reads `identities([suggestions["grid"]]) == ["gallery"]`, the identity
    token variants put first, and the comment above `identities()` names that convention. **page_host.py at 999/1000:
    a compaction is REFUSED; an edit at zero net lines is allowed and says so in its commit body; the first edit that
    ADDS a line extracts a module (a·12, a·15 or a·16 name it as a reader).** a·12 did not touch it; the extraction is
    still owed.
47. **A served field that differs from the engine's observable answer is a JOIN miss, repaired in the data, never a
    third by-title reader nor a register entry.** The seed builder's `poster` join gained the base-title fallback the
    engine's `POSTERS[t] ?? POSTERS[baseTitle(t)]` had; only `settled.json` moved (« Star Trek: Strange New Worlds
    (2022) »). The offline comparison `python3 /private/tmp/tm-l13a/compare-seed-posters.py` reads 17 families,
    0 differences.

## Method — unchanged from a·10, plus what a·11 added

- **After every phase's commit and before ANY push**: the comment-record test alone,
  `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder sh scripts/heavy.sh --class test l13a python3 -m pytest tests/scripts/test_check_maquette_comments.py -q`;
  a phase that adds a maquette file re-records `python3 scripts/check-maquette-comments.py --record` in its own
  commit.
- **Every baseline a phase moves** is re-recorded in the phase's own commit, its numbers in the body.
- **Count R80's pairs offline before setting the floor**:
  `cd frontend/maquette/harness && python3 -c "import residue as r; f=r.read_factories()[0]; c=r.pair_up(r.read_residue()[0], f)[0]; print(len(c)); [print(x['selector'], x['factory']) for x in c]"`.
- **Run by hand, before the contracts tier**: `python3 scripts/check-module-size.py --root frontend`.
- **Search every harness hold for a class-string equality** on a class the phase turns into a variant:
  `rg -n -g '*.py' "className" frontend/maquette/harness`; re-aim through `identities()` or a `data-part`.
- **NEW: compare the served data with the engine's answer OFFLINE** whenever a phase switches a reader from an engine
  table to a contract field: the oracle measures geometry, and a picture swapped for its fallback inside a declared
  box is invisible to it (ruling 47). `compare-seed-posters.py` is the shape to copy.
- **NEW: delete `legacy.css` rules with a parser, never by line numbers.** a·11's took every rule whose selectors were
  ALL in the phase's kill set (and `@container` blocks whose inner rules all were), and the comments directly above
  them; it printed every dropped comment's first line for review.

## What a·13 inherits — measured at the a·12 boundary (re-take before trusting)

**`POSTERS` readers** (ruling 45): `features/arrivals/resolution-cards.tsx:100` (`posterArtworkFor(reference, title,
opts.k, opts.exact)`), `:161` (`decision.choice.t`), `features/media/media-screen.tsx:48-50` (`artworkFor`, with
`HERO_IMAGES`); `lib/engine-drawing.ts`'s `POSTERS` member and `posterArtworkFor()`; the engine's table
(`legacy.js` ~371), its `__referentiel` member and its window export. No harness or script reads `POSTERS` by name
(`rg -g '*.py' -g '*.mjs' "POSTERS"` finds `poster.py`'s comment and `build-mock-seeds.py`'s join source); re-take
with the widened grep (`window.POSTERS`, `POSTERS[`, `reference.POSTERS`).

**Stays in the engine past a·13**: `dateFR` and its `__referentiel` member (`harness/pop.py:50`,
`harness/season_family.py:169` read it beside `sheetFor`; both re-aim at a·14); `baseTitle` (the engine's own verbs
call it; `harness/followed_sheet_act.py:88` reads it). The features read `lib/titles.ts`, `features/media/format.ts`
and `features/acquisition/rich-text.ts` instead.

**`legacy.css` selects 54 classes**: `acquiring`, `announced`, `armed`, `brandbig`, `ed`, `en`, `ep`, `epdot`, `eprow`,
`eps`, `et`, `field`, `flux`, `hpanel`, `in_library`, `legend`, `linkbtn`, `loading`, `logincard`, `loginerr`,
`loginfield`, `loginscreen`, `loginsub`, `loginsubmit`, `logintitle`, `miss`, `missing`, `mk`, `noinfo`, `open`,
`panel`, `pending`, `ptr`, `readonly`, `row`, `rulenote`, `scrim`, `season`, `sfr`, `sheet`, `spin`, `splash`,
`splashbar`, `splashmsg`, `states`, `sw-info`, `sw-muted`, `sw-success`, `sw-upcoming`, `sw-waiting`, `sw-warning`,
`to_grab`, `unverified`, `wm`. a·13's own: `noinfo` on the hero and the cast (kept while `season-list.tsx` emits it,
a·14).

## Traps met — each cost a run

**THE RULE FOR EVERY PHASE (steward, 2026-09-13)**: before a gate, search every removed name everywhere a reader can
live — `rg -n -g '*.py' -g '*.mjs' -g '*.txt' -g '*.json' NAME frontend/maquette/harness scripts tests` — in its
`window.NAME`, bare `NAME(` and `=>NAME(` forms, and replay each reader alone.

From a·5 to a·10: see the a·10 RESUME. The recurring ones:
- `check-legacy-css-residue.py --record` drops the long `$comment`: restore it with only the figures changed.
- zsh: `echo ==` errors and kills the rest of a compound command; `grep -r --include=*.py` errors « no matches
  found » — use `rg -g`.
- The Bash tool's working directory follows a `cd` made in ANY call: start every command with an absolute `cd`. In
  a·11 a relative `rg` after a `cd` searched nothing and printed nothing, which reads exactly like « no reader ».
- `run.sh --contracts` prints a failing guard's detail only in its « cheap guards » section.
- `check-module-size.py --root frontend` is not the bare run.
- A one-letter anchor may already be claimed; duplicate anchors are counted, not refused.
- `heavy.sh --class browser` holds off until 4 096 MB are free.

New in a·11:
- **`scripts/build-mock-seeds.py --write` REMOVES every seed no family claims** — 22 converted seeds. Never run it to
  regenerate one seed: `--check` names the drift (it reads 23 drifted at the a·11 head, all « no family claims it »,
  which is the baseline), and the joined value is written into the one seed by hand.
- **A group rule's descendant selector can be the only thing sizing an element**: `.poster img, .tile .p img, .pfall`
  sized the tile's `<img>` (its box carries `p`). Deleting the group left a 240px picture in a 114px box — clipped,
  so the oracle stayed at zero, and `scen.py`'s « spills » caught it. Before deleting a group, list every element each
  of its selectors matches, not only the class the phase converts.
- **`legacy.css` carries extraction MARKERS in comments**: `/* login:splashstyle:end */` sat right above the dying
  `.cfoot` banner and a comment-pruning pass took it. `serve.py` extracts up to it (a·17's subject).
- **`cva` here has no tailwind-merge**: two utilities for one property resolve by CSS order, not by class order. Put
  colours and backgrounds in the variant BRANCHES, never base plus branch; carry a class the engine writes as a
  class-qualified utility (`[&.dragging]:`, `[&.gone]:`, `[&.out]:`), and outrank another factory's padding the same
  way (`deckBody()`'s `[&.deckbody]:pb-5` over `body()`'s `pb-8`).
- **`--spacing: initial`** (theme.css): `h-0` computes to an invalid value, not 0 — write `[height:0]`.
- **`check-frontend-boundaries.py` fan-in**: `i18n/fr.json` may be imported by four features at most; read a list
  through `i18next.t(key, { returnObjects: true })` instead of importing the file.
- **The duplicate-import arm resolves paths**: `"../../features/acquisition/variants"` and `"./variants"` are one
  module.
- **`scripts/code-vocabulary.txt`** lacked `initials`, `ranges`, `rating` (added); `months`, `short`, `picture`,
  `lead` are not words there.
- **The stage labels, the month names and the fresh tag** are `surfaces.card.stages`, `common.monthsShort` and
  `surfaces.card.freshTag` in `fr.json`.
