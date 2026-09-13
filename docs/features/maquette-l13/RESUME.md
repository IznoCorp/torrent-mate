# L13a — resume brief for the successor

Written by the eleventh L13a implementer when it stood down at the a·17 boundary (a·17 was this session's last
unit, by the steward's order). Read it after `docs/features/maquette-l13/BRIEF-L13a.md`, which still governs
everything. This file only records state, rulings and traps, and it dies with the wave's folder at the post-merge
gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 … a·14.2: see `git show 5fb41e90e:docs/features/maquette-l13/RESUME.md` (and the RESUMEs it points to). Then
  this session:
  - `5fb41e90e` docs — the previous RESUME records `6c6180c9a` and the pruned logs.
  - **a·15** `9c083a9b7` `refactor(maquette-l13a): system, maintenance and account draw their facts as components and the dead actions table goes`
  - **a·16** `9374287dc` `refactor(maquette-l13a): settings read the served catalogue and the engine's settings table dies` (ruling 57)
  - **a·17** `9907cb34a` `refactor(maquette-l13a): the login gate and the startup screen take their styles from the base layer`
  - `198f6c554` `chore(maquette-l13a): the comment corpus counts the references the entry block's move took away`
  - the commit that adds this file.
- Gates, every log under `/private/tmp/tm-l13a/` and postdating its commit:
  - a·15 on `9c083a9b7`: `a15-gate-contracts.log` 19 rules + 27 guards, no violation; `a15-gate-oracle.log` 87 x 34,
    2 958, no divergence; alone page_host 44, url_state 99; mutations `a15-mutation-*.log`: panel title → page_host
    FELL, served catalogue emptied → url_state FELL, account fact list back to the bare class → oracle FELL.
  - a·16 on `9374287dc`: contracts 19 + 27, no violation; oracle no divergence; alone settings 65, settings_editing 15,
    seeds_at_rest 15, page_host 44, url_state 99; six mutations `a16-mutation-*.log` all FELL (heldSettings,
    the page's search, the state seeds, the readonly zero margin, a served topic missing, the served schema empty).
  - a·17 on `9907cb34a`: contracts 19 + 27 (starts 5 140 MB free), oracle no divergence (5 779 MB); alone logout 8,
    startup 28, entry 10; mutations `a17-mutation-*.log`: `.splash[hidden]` emptied → startup FELL; the entry extract
    removed → startup FELL; **the form rewrite aimed at an id nothing carries → NO RULE FELL** (below).
  - All equal to `hold-counts-baseline.json`. `tsc -b` 0 and vitest 114 after a·15 and a·16; the pytest slice
    (comments, residue, markup-contracts, boundaries arms, mock-seeds, css tokens, csstokens ranks, oracle, build
    identity, autodeploy restart) 224 passed + the comment-record test 36 passed on `198f6c554`, tests lock.
- Records:
  - `engine/legacy.js`: **3 593** non-blank (ledger 5 295 → 5 056 → 3 593).
  - `styles/legacy.css`: 248 non-blank; `legacy-css-residue.json` rules 14, classes 12, declarations 56.
  - `fixture-register.json`: `MAINT_ACTIONS`, `SETTINGS` converted. `build-mock-seeds.py --check` reads **31**
    « no family claims it » (29 + maintenance-actions.json, settings.json).
  - `residue.py` (R80) `PAIRS_FLOOR` 4 → 3 (`.flux` left). `comment-references-baseline.json` re-recorded.
  - `mocks/mock-seeds.ts` exposes `settings` beside `sheets` (harness-read, ruling 54's shape).
  - `hold-counts-baseline.json` NOT re-recorded.
- `--compare`, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·17-bis**, then a·18, a·19 (full gate, version bump, pull request).
- Version not bumped. No pull request. Pushed at this boundary (the stand-down report carries `git ls-remote`).

## Rulings — not to be reopened

1–56: see `git show 5fb41e90e:docs/features/maquette-l13/RESUME.md` (53–56 there, 1–52 in the file it points to).

57. **a·16 lands its own subject only.** The React-side support — `engine/engine-shape.ts` and its test,
    `lib/engine-drawing.ts`, `window.__referentiel` with `app/reference.d.ts` and the `*Reference` slices,
    `app/engine-data.ts`, `app/engine-redraw.ts`, the `FAN_IN_EXEMPT` / `OUTSIDE_IMPORTS_ALLOWED` engine entries and
    the reference-slice arm (its `text.index("window.__referentiel = {")` raises the day the object goes) — dies at
    **b·11** with its last publisher. Measured: 40 `toEngineShape` call sites in 13 files, 40 product files reading
    `__referentiel`. PLAN GAP for the L13b brief: homes for `icons`, `EP_LABEL`, `TODAY`, `REASON_LABEL/DETAIL/TONE`,
    `ST_TONE`, `stLabel`, `MAINT_TOPICS`, `SERVICES_PANNE`, `AUDIOS`, `RESOLUTIONS`. `phase-a16` carries the dated
    amendment; the INDEX a·16 and b·11 rows say so.

## Owed — carried to a·19 and the steward's brief (verbatim, reading A)

- **The a·19 reader line**: « A tap on any card opens the media sheet with its title and poster at once; year, genre,
  synopsis and cast are skeletons until the read lands, and after a failed read only the title and the poster remain.
  A typed `/media/<provider>/<id>` shows its ids at once and a skeleton title until the read lands. Walk restore and
  Back on a typed address. »
- **The FIRST step of the operator's Mac walk**: « Tap a card: the sheet opens with its title and poster at once, year,
  genre, synopsis and cast a skeleton for an instant. Then type /media/<provider>/<id> directly: ids at once, the
  title a skeleton for an instant, then the sheet. »
- **Reads no rule fells, for the reader round** (L13a writes no rule):
  - the follow panel matrix's owned numbers (`panel-seasons.tsx` `ownedSeason`) and the follow facts' `hasSheet`
    (`follow-facts.ts`) — from a·14.2;
  - **the host sign-in page's form `method="post" action="/login"`** (`serve.py`, the rewrite by pattern on
    `id="loginform"`): no harness rule and no test reads it — `grep -rln 'action="/login"' --include='*.py'
    frontend/maquette/harness tests scripts` is empty.

## a·17-bis — what it is (ruling 31, literal; INDEX row)

The ≡ harness panel dies in ONE commit, before a·18: the « ≡ » opener `#scenBtn` in `design/index.html`; the panel
half of `harness/panel.ts` and its five `h*` verbs (`hclose`, `hgo`, `hscen`, `hphase`, `htmdb`); the `.hpanel` rules in
`styles/legacy.css`; the i18n keys only the panel read; `closeHarnessPanel` in `harness/drive.ts` and
`__etatsDetailles`; `.hpanel` in `app/layers.ts`; the comments naming « the ≡ panel ». Outside the harness:
`scripts/markup_verbs.py`'s five answers, `scripts/check-markup-contracts.py`'s `data-hscen`/`data-hphase` contract
and its two assertions in `tests/scripts/test_check_markup_contracts.py`, `scripts/nofrench_values.py`, `hscen` in
`scripts/code-vocabulary.txt` (the other four `h*` words if no name uses them). Readers re-aimed:
`message_above_harness.py` drops `harness/panel` and `#scenBtn`, keeps `harness/bar`; `audit.py` and `dest.py` drop
`harness/panel` from their exclusions. **STAY**: `[data-part="harness/bar"]`, `#notesBtn` and its toggle;
`hiding.py` and `chrome.py` do NOT move; `harness/panel_verbs.mjs` is not a reader of the ≡. Re-take every line
number by grep — a·15, a·16 and a·17 moved several files.

## Method — unchanged, plus what this session added

- Everything in the earlier RESUMEs' « Method ».
- **Measure the phase file's list of readers before moving anything.** a·16's named three readers of
  `__referentiel`; the scan found forty. The scan that settles it: `__referentiel.X`, the aliases
  (`const reference = window.__referentiel`) and destructuring from `use*Reference()`.
- **A seed family the harness needs before a page mounts** goes through `window.__mocks` (`mocks/mock-seeds.ts`),
  because `__reset` clears the query cache; a rule that runs after the page drew reads
  `window.__queries.getQueryData([...])`; a cold subject fetches the served address.
- **`check-legacy-css-residue.py --record` rewrites the file's `$comment`** to a short default: restore the old
  comment in the same commit (a15/a16/a17 did, by a four-line Python that swaps the JSON string back).

## Traps met — each cost a run

- **A grep filter that hides the class you look for.** a·16's « no element wears `rulenote` » came from a grep whose
  exclusions dropped `ruleNote()`'s identity class; the oracle diverged on `settings-field-structure` (14 px). Grep the
  identity string bare, then filter by reading.
- **An R80 pair leaves with its residue rule**: deleting `.flux` fell `residue.py`'s floor; the floor is lowered with
  a paragraph naming what left, as the earlier paragraphs do.
- **`page_host.py` stands at 999 non-blank lines**: a re-aim there is a line replaced in place, said in the commit
  body only.
- **zsh does not split `$T`** — a pytest file list in a variable is ONE argument (exit 4). Write the paths out.
- **The comment-record test falls when a phase moves comments out of a file** (`read` or a per-file count moves
  down): `check-maquette-comments.py --record` in its own commit, then the test alone.
- **`pm2 restart torrentmate-design` is not the wave's**: tm-design serves main; `logout.py` starts its own scratch
  host from the branch's `serve.py`.
- **A line-keyed test fixture follows a moved anchor**: `tests/scripts/test_check_markup_contracts.py` writes its
  fixture at the line `scripts/markup_anchors.py` declares — replay it alone after any anchor move (a·17-bis moves
  `audit.py`).
- **zsh `===` in an echo is an expansion error**, and a parallel tool call that `cd`s moves the shell for the next
  one: prefix every call with `cd /Users/izno/dev/worktrees/wave-l13a &&`.
