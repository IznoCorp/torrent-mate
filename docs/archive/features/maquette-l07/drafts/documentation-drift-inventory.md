# The wave's documentation drift — the inventory behind B-068

Found by an adversarial doc-accuracy review over `origin/main...feat/maquette-l07`, 2026-08-25.
**This file is the evidence B-068 indexes**, kept because a list of forty small facts does not
belong in a register entry and does not survive in a pull-request body.

**What was RE-MEASURED and is correct**, said first so the list below is read as exceptions
rather than as a verdict: `2 739` measurements (33 regions × 83 states), `530` rules, `4 136`
lines, `18` compositor declarations, `30` colours, `8` shadows, `55` rules / `5` contracts /
`14` arms, `12` live readers of the fragment path, `936` bytes leaked, « five tests », and
D-L07-1's six BLOCK 1 line ranges — exact, line by line.

**What this file does NOT hold**: everything already repaired in the pull request itself —
`harness.css` « ships nowhere », ACC-18's command, §15's palette figures, `serve.py`'s superseded
paragraph, `vite.config.mjs`'s `@source` claim, `check-css-tokens.py`'s « Declare it in BLOCK 2 »,
L07's `NOT STARTED` line, the compositor guard's « six properties » and « EVERY ENTRY CARRIES ITS
REASON », `check-tailwind-confinement.py`'s « the four holds ».

---

## Counts that no longer measure what they say

| where | says | is |
| --- | --- | --- |
| `check-css-tokens.py:653,659` | « three files … these three » | four |
| `csstokens_patterns.py:2` vs `check-css-tokens.py:68` | « three patterns » vs « four » | five exports, four regexes |
| `csstokens_login.py:10,28` / `:114` / `:12` | « four files » / « its two sources » / « three times » | a five-entry table (one dead) / five / a list of five |
| `check-compositor-css.py:95` | « three stylesheets of D3 » | four |
| `base.css:8` / `:196` | « six regions » (five named) / « three hidden cases » | six / four selectors |
| `DESIGN.md:22, 26, 215, 173, 311` | 2 328 declarations · 4 `:has()` · 22 call sites · 5 keyframes + 4 `:has()` · 53 `.py` | none of six readings gives 2 328 · 3 · 29 over 12 · 3 and 3 · 56, which contradicts its own § 1 |
| `frontend-architecture.md:326` | ceiling 400 / warn 250 | `check-module-size.py` reads 1000 / 800 |
| `shell.tsx:48` + `states.js:19` | « twenty names » | 18 |
| `oracle.py:20` | « the 17 » properties | 19 — **pre-existing** |
| `regions.json` | « 82 states »; `$comment` says `probe` and `regions` were removed | 83; both present — **pre-existing** |

## Comments detached from, or contradicting, their subject

`check-css-tokens.py:236-239` an orphaned comment for a table that moved to another file ·
`:227` « when L07 lands », which it has · the module docstring, `Usage:` and the argparse
description omit `--arm motion-classes` entirely · `:965` prints the four durations where it
meant the four token NAMES · `check-tailwind-confinement.py:101` describes an exclusion its regex
does not implement · `rename-identifiers.py:399` « the property in group 1 », true for one of
three patterns · `palette.py:9` and `serve.py:530` name `--primary`, renamed to `--color-primary`
by this wave · `ui/variants.ts` a fifteen-line docblock about a `cva` factory atop a three-line
barrel, with an unused `cva` import · `base.css:13` « imported first » (`theme.css` is) · `:29`
« everything below is the BASE layer », which closes at 159 of 319 · `:127`, `:161`, `:250` three
comments detached from their subjects · `legacy.css:1601, 1925, 1933, 1942, 2039` five orphaned
comments, the last saying « Display lives here » about a rule now in `base.css:172` · `:2447`
« for the three the engine emits » directly above « All five names, not the three a first pass
thought » · `:2125` names `backControl()`, the export is `backAction` · `surfaces.ts:15` says
`pip` is on the engine's declared French-debt list; it is in neither `code-vocabulary.txt` nor
`regions.json` · `:156` a `(was: …)` diff-note shipped in a docblock · `theme.css:24-34` « the
three LOOP periods stay declared here » — all seven are · `controls.ts:20` « follows STRUCTURE »,
where three of five still need a hand-added class · `common.py:63` « TWO THINGS ARE DELIBERATELY
OUT, and neither is an oversight », while `styles/harness.css` is a third instrument file and IS
in `DESIGN_SOURCES` · `harness.css:21,32` cite `extract-maquette-css.py` and the parity probe,
both deleted 2026-08-20 and **re-committed into a living source file by this wave** ·
`README.md` § CSS-contract (`:301, 319, 339, 348, 356`) left standing under its own replacement ·
roughly fifteen stale paths and identifiers in `README.md` (`src/states.js`,
`components/panel.tsx`, `/fiche/$titre`, `panneauOuvert`, `data-go="profil"`, « 522 words »,
« arm 13 ») — **pre-existing**.

## § Language — a phase number is a session artefact

`CLAUDE.md` § Language: maquette and harness comments « carry no reference to a session, a phase
or a dated decision — they must still read years from now, out of context ». The durable half is
already stated in each of these; the phase number is what has to go.

`legacy.css` eighteen « CONVERTED (L07 phase N) » banners, plus `:2440` « the card arrived in
phase 8, the system in phase 6 » and `:2` « arbitrated by the operator on 2026-08-24 » ·
`layout.ts:52` · `settings/variants.ts:62` · `page-host.tsx:193` · `base.css:224` ·
`arrivals/variants.ts:8` · `theme.css:195` · `common.py:55,111` · `bridge.py:62` ·
`type_scale.py:102` · `palette.py:49`.

French screen names written bare rather than in « guillemets »: `arrivals/variants.ts:1`,
`surfaces.ts:49,149,153`, `legacy.css:2097`.

## Rule identifiers that collide

`R7`, `R8` and `R4` are cited in seven new comments with the meanings from `README.md`'s
trap list, which are NOT the harness registry's (`R7` = « no panel renders emptiness in silence »,
`R8` = « every layer reserves the tab bar »); `base.css:315`'s `R4` resolves under neither. The
collision is **pre-existing** and was newly propagated by this wave. Whichever way it is settled,
one of the two namespaces has to be renamed — a citation that resolves to two different rules is
worse than one that resolves to none.
