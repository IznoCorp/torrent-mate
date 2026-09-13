# L13a — resume brief for the successor

Written by the fourth L13a implementer when it stood down at the a·7 boundary (gauge past 50 %, the steward's call). Read it
after `docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything; this file only records state, rulings and
traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 `123816c93`, a·2 `383c67549`, a·3 `40fc7b785`, a·4 `ad4d3096a` + `4918abe65`, then:
  - **a·5** `504ce4897` `refactor(maquette-l13a): the dead screen layer and the code nobody reaches are deleted`
  - **a·6** `f353eea14` `refactor(maquette-l13a): the list schemas declare the provider identity and the poster`
  - **a·7** `8fba453c5` `refactor(maquette-l13a): the open screen, the section, the notes, the skeleton and the surface error are variants`
  - a docs commit after a·7: `docs(maquette-l13a): the operator's rulings on Q2 and D-L13-1 in the plan`, then this file.
- Gates, each on its own head, under the shared mutex:
  - a·5: `run.sh --contracts` 19 rules + 27 guards, no violation; `--oracle` 2 958 measurements, no divergence; the twelve
    re-aimed rules replayed alone (`harness-hold-counts.py --compare --only … --jobs 1`): 0 changed hold count.
    Mocks-off build boots to `/acquisition`, 0 page errors, `#shell` last child of `#device`.
  - a·6: contracts and oracle as above; `check-mock-seeds.py` clean on every arm; `compare-contracts.py --check` exit 0.
  - a·7: contracts and oracle as above; `residue.py` alone: 14 holds, no violation (19 before — the five pairs removed).
  - Beside each: `tsc -b` 0, vitest 7 files / 112 tests, the 27 cheap guards of `run.sh` exit 0.
- Records: `engine/legacy.js` **29 916** non-blank (ledger re-recorded); `legacy-css-residue.json` ceiling
  **218/138/882**; R80 `PAIRS_FLOOR` **10**. `hold-counts-baseline.json` is NOT re-recorded: at a·19's `--compare`, R80
  (`residue.py`) reads 14 against the baseline's 19, and that movement is a·7's, named in its commit body.
- `--compare` over the whole suite, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·8** (`plan/phase-a08-actions-chips-facts.md`), then a·9 … a·18, **a·18-bis** (the ≡ panel dies, see ruling 29),
  a·19.
- Version not bumped. No pull request.

## Rulings — not to be reopened

1–21: see the a·4 RESUME (in git: `git show 58d24cfc4:docs/features/maquette-l13/RESUME.md`), carried over unchanged.

From a·5 (the steward's rulings on STOP D, 2026-09-13):

22. **Q4 is about what a selector DENOTES, not a text substitution.** In a root ladder whose `#screen` rung is identically
    false and whose generic `[data-part="screen"][data-open][data-key]` rung is already present, the dead rung is REMOVED
    (`audit.py` ×3, `audit2.py` ×4, `dest.py`, `states.py`); a FIELD is re-aimed (`back.py`, `ident.py`); `bridge.py`'s
    vacuous « the media sheet is gone » now reads `[data-key^="mediaSheet:"]`; `scroll.py`'s default port re-aimed.
23. `window.__close`'s three readers use `window.__panel.close()` and
    `document.querySelector('[data-part="screen"][data-open]') && window.__bridge.back()`.
24. `openDetailSheet` went with the generic `sheet` branch; `__seamsInstalledProbe` has no product side and `boot_order.py`
    stays intact.

From a·6 (four rulings, written into `phase-a06`'s dated amendment):

25. The join is `sheetFor`'s four tiers in `build-mock-seeds.py`; `join` is declared per family in
    `fixture-projections.json`; `ids`/`poster` required and nullable on the list schemas, `Follow.ids` required non-null,
    `MediaSheet.title` required; `createFollow` takes the body's provider identity, otherwise the joined search result or
    suggestion; `beginFollow` the joined incomplete show.
26. **B-497** filed, open: `build-mock-seeds.py --check` reports the 23 converted seeds as orphans. Owner: a·10 or a·11
    (they kill `LIBRARY` and `INCOMPLETE`), or the next wave that touches the generator.

From the operator, 2026-09-13:

27. **The cut is B**: L13a → L13b → L13c, three pull requests, each with its reader round and Mac walk. L13a's STOP C is
    its own pull request at a·19.
28. **D-L13-1 = A**, ratified as written; written on INDEX's STOP E line. Nothing changes in L13a.
29. **Q2 = B: the ≡ harness panel dies** in ONE commit, **a·18-bis**, before a·19's full gate — `harness/panel.ts`, its
    five verbs, the « ≡ » button's markup, the harness.css rules and i18n keys only it used. Its readers go in the same
    commit: the panel holds of `hiding.py`, `message_above_harness.py` and `chrome.py` (named with their counts), and the
    exclusions in `audit.py` and `dest.py`. Written in `phase-a01`'s amendment and INDEX's row.

From a·7:

30. The four bare `sec` of `library-list.tsx` and `add-screen.tsx:324`'s were repaired inside a·7 and accepted as a
    conversion (named in its commit body as the 45 divergences they caused).

## Method — where the logs go (steward, 2026-09-13)

Every log of the wave goes under ONE directory, `/private/tmp/tm-l13a/`, as
`> /private/tmp/tm-l13a/<phase>-<step>.log 2>&1`. The gate logs (`<phase>-contracts`, `<phase>-oracle`) are kept
until the merge; every other log is deleted at the implementer's stand-down, and the deletion is proved by `ls`.

## Traps met — each cost a run

**THE RULE FOR EVERY PHASE (steward, 2026-09-13) still holds, WIDENED by the wave's audit the same day**: before a
gate, search every removed name everywhere a reader can live, not only in `frontend/maquette/harness/*.py` —
`rg -n -g '*.py' -g '*.mjs' -g '*.txt' -g '*.json' NAME frontend/maquette/harness scripts tests` — in its
`window.NAME`, bare `NAME(` and `=>NAME(` forms, and replay each reader alone.
New in a·5 to a·7:

- **Before deleting a class rule, scan for the class in EVERY quote position**, not only after `class=`/`className=`:
  `grep -rnE "([\"'\` ])sec([\"'\` ])"` found `grid ? "gallery" : "sec"`, which a class-attribute scan missed. The oracle
  measures some regions only — the add screen's bare `sec` was invisible to it.
- **A descendant rule (`.empty b`, `.surferr button`) has emitters in JSX as well as in strings.** Reproduce it on the
  variant with `[&_b]:…` / `[&_button]:…` utilities rather than chasing every element.
- **Read the cascade ORDER, not only the declarations**: `.sk` followed `.skcard` in the sheet, so a skeleton card's
  radius was `.sk`'s.
- **`scripts/markup_anchors.py`'s `GENRE_SITES` is keyed by LINE**: a docstring added to `audit.py`/`audit2.py` moved
  three exemptions. Re-key them in the same commit.
- **`check-markup-contracts.py` refuses a style-class anchor (`.screen.open`) and an escaped quote in a harness
  selector**: select by `data-part`, and write the JavaScript in a triple-quoted Python string.
- **`check-legacy-css-residue.py --record` rewrites the JSON and drops `$comment`**: restore the file from `HEAD` with only
  the three figures changed.
- **Removing an engine constant the fixture register lists** needs the entry gone AND `$counts` re-tallied
  (`check-mock-seeds.py` classification arm).
- **`check-mock-seeds.py`'s handlers arm refuses a string literal inside an indexed type** (`["follows"]`); name the
  contract instead (`type Schemas = components["schemas"]`, then `Schemas["Follow"]["ids"]`).
- **`run.sh`'s guard list has no `python3` prefix**: a loop over it must add it.
- **`cd` persists in the Bash tool even from a parallel call**: use absolute paths everywhere.
- **Converting an HTML-string emitter to JSX can change escaping**: the follows' filter title is escaped twice today;
  `emptyNoteMarkup` keeps a string and the engine's escaper so it stays so.
