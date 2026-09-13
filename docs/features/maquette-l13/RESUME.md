# L13a — resume brief for the successor

Written by the ninth L13a implementer when it stood down at the a·14.1 boundary (ruling 50: a·14.1 was this session's
last unit whatever the gauge read). Read it after `docs/features/maquette-l13/BRIEF-L13a.md`, which still governs
everything. This file only records state, rulings and traps, and it dies with the wave's folder at the post-merge
gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 `123816c93` … a·10 `c96358876` (see `git show bc7cf8e0c:docs/features/maquette-l13/RESUME.md`), a·11 `a6c91fc57`
  + `1e34b9660`, a·12 no commit (see `git show 297718341:docs/features/maquette-l13/RESUME.md`), then this session:
  - **a·13** `5e1ca3308` `refactor(maquette-l13a): the media screen reads its artwork and cast from the served sheet, and POSTERS dies`
  - `1a73ff2ea` `fix(maquette-l13a): heavy.sh counts the speculative pages macOS reclaims first` (ruling 48)
  - `4c0e1d036` `fix(maquette-l13a): mutate.sh reads a rule's exit code as a fall` (ruling 49)
  - `802ba182d` `docs(maquette-l13a): a·13's two named differences and ruling 50's cut of a·14, in the plan`
  - **a·14.1** `c65c68fbc` `refactor(maquette-l13a): the season tree draws through variants and its legacy rules die`
  - the commit that adds this file (phase-a14's amendment for rulings 51 and 52, and this brief).
- Gates, every log under `/private/tmp/tm-l13a/`:
  - a·13 on `1a73ff2ea`: `a13-contracts.log` (19 rules + 27 guards, no violation), `a13-oracle.log` (87 x 34, 2 958,
    no divergence); alone `a13-alone-*.log`: audit2 13, screen_addresses 51, transition 39, priming 40, decision 24.
    Mutations: transition R115 fell (« the fanart can be warmed »), audit2 R13 fell through the REPAIRED tool
    (`a13-mutation-audit2-repaired.log`, « FELL — the rule exited 1 … Widow's Bay (2026), Widow's Bay »).
  - a·14.1 on `c65c68fbc`: `a14-contracts.log` (19 + 27, no violation), `a14-oracle.log` (87 x 34, 2 958, no
    divergence); alone `a14-alone-*.log`: audit 13, audit2 13, surfaces exit 0, season_family 48, priming 40,
    screen_addresses 51, pop 17, season_grab 16, followed_sheet_act 12 — all equal to `hold-counts-baseline.json`.
    No re-aim, so no mutation.
  - Comment-record test 36 passed after each phase commit; `tsc -b`, vitest 112, the cheap guards exit 0.
- Records:
  - `engine/legacy.js`: **27 320** non-blank (ledger 29579 → 27320 at a·13; a·14.1 does not touch the engine).
  - `legacy-css-residue.json` ceiling: **38/29/157** (rules/classes/declarations).
  - R80 `PAIRS_FLOOR`: **4** (`.flux`, `.panel`, `.scrim.open`, `.sheet.open`). `check-poster-box` floor: **4**.
  - `comment-references-baseline.json`: `legacy.css` references **51**.
  - `fixture-register.json`: `HERO_IMAGES`, `trailerIds`, `CAST`, `POSTERS` converted. `check-mock-seeds.py`: 40 in the
    engine, 39 converted. `build-mock-seeds.py --check` reads **27** « no family claims it » (the baseline).
  - `hold-counts-baseline.json` NOT re-recorded (R80 reads 8 against 19 at a·19's `--compare`, as before).
- `--compare`, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·14.2** (below), then a·15, a·16, a·17, **a·17-bis**, a·18, a·19.
- Version not bumped. No pull request. Pushed at this boundary (the stand-down report carries `git ls-remote`).

## Rulings — not to be reopened

1–47: see the a·12 RESUME (`git show 297718341:docs/features/maquette-l13/RESUME.md`) and the ones it points to.

48. **`scripts/heavy.sh` counts « Pages speculative »** — the file cache macOS reclaims first — beside free and inactive.
    A repair of an instrument's reading with its test (`tests/scripts/test_heavy.py`), floors untouched.
49. **`scripts/mutate.sh` reads the replayed rule's exit code as a fall** beside its `FAIL`/`violation(s)` grep, and
    names the exit. `tests/scripts/test_mutate.py` holds it (a sandbox repository).
50. **a·14 lands as two commits**: a·14.1 the season tree (this session, done), a·14.2 the identity crossings
    (`Agent : l13a 10`).
51. **(a)/(b) of a·14.2, ruled by the auditor under the operator's delegation — VERBATIM:**

    > a·14.2 STAYS in L13a as reading (1): the crossing carries what the tap knew — the tapped list item's title,
    > poster URL and ids (a·6's fields) are written into the navigation ENTRY (lib/navigation-entry.ts, a·3's
    > ENTRY_DIALS), placeholderData (media/queries.ts) and the in-flight title (media-screen.tsx) read the ENTRY, R119's
    > INTERCEPT thinning seam (priming.py) moves to the entry's publisher (harness/publish.ts); SHEETS_RAW, OWNED,
    > SHEETS_IDX, sheetFor, titleForProviderId, addressIdsFor, ownedFor die with their 13 product readers and 18
    > harness files re-aimed. ONE observable difference, D8-accepted: a TYPED address shows its ids at once and a
    > skeleton title until the read lands (the end frame identical). THREE CONDITIONS: (a) that difference is a dated
    > amendment in phase-a14 AND a line of the a·19 reader brief AND one step of the operator's Mac walk (« type
    > /media/<title> directly: ids at once, the title a skeleton for an instant, then the sheet »); (b) the entry
    > carries title, poster URL and ids ONLY — no sheet body (history.state has a size ceiling in Safari); a hold or the
    > reader reads it; (c) restore/Back on a typed address is walked by the reader. Refused: moving a·14.2 to L13b
    > (ships ~20 500 engine lines alive).

    Condition (a)'s phase-a14 amendment is written (this commit); the a·19 reader-brief line and the Mac-walk step
    are still owed.
52. **`SEASONS` moves to a·14.2** (a PRODUCT reader the phase file did not list), and a·14.2 adds the ONE `window.__mocks`
    seed accessor DESIGN § 4.2 promises, so the harness readers of `window.SEASONS` read the seeds the mock layer
    answers from — the design's own line, not new apparatus.

## The a·14.2 hand-over — measured at the a·14.1 boundary (re-take before trusting)

**Engine**: `SHEETS_RAW` (`legacy.js` ~6260, ~20 500 lines, up to `SHEETS_OLD` ~26798), `SHEETS_OLD`, `SHEETS_IDX`,
`titleForProviderId`, `addressIdsFor`, `sheetFor`, `ownedFor` (~26849–26905), `OWNED` (~381), `SEASONS` (~271), their
`__referentiel` members and window exports. Re-take with `grep -nE "^  const (SHEETS_RAW|OWNED|SHEETS_IDX|SHEETS_OLD|SEASONS) =|^  function (sheetFor|ownedFor|titleForProviderId|addressIdsFor)\(" frontend/maquette/design/src/engine/legacy.js`.

**The 13 product reader sites** (`rg -n "sheetFor|ownedFor|titleForProviderId|addressIdsFor" -g '*.ts' -g '*.tsx' frontend/maquette/design/src | grep -v legacy.js`):
- the has-a-sheet question, by title: `features/acquisition/card-markup.ts:70`, `features/library/card-markup.ts:32`,
  `features/arrivals/arrival-card.tsx:82`, `features/acquisition/follow-facts.ts:120`;
- `features/media/panel-seasons.tsx:73` (`ownedFor`) and `:93` (`sheetFor`), `features/media/popover-episode.ts:41`,
  `features/media/season-list.tsx:108` (`ownedFor`);
- `features/media/media-verbs.ts:72` and `app/history-bridge.ts:197` (`addressIdsFor`);
- `features/media/media-screen.tsx:52` (`titleForProviderId`) and `:83` (the failed-read fallback);
- `features/media/queries.ts:66-68` (the placeholder — ruling 51's entry).

**`SEASONS`' product reader** (ruling 52): `features/acquisition/follow-facts.ts:33` (the `window.SEASONS` declaration)
and `:96` (the follow panel's seasons block); the same function reads `window.LIBRARY` (ruling 41, b·10-bis) and
`reference.INCOMPLETE`.

**Harness files reading the resolvers or the sheet table** (15): `audit.py`, `audit2.py`, `follow_has_sheet.py`, `followed_sheet_act.py`, `page_host.py`, `panel.py`, `pop.py`, `priming.py`, `rename.mjs`, `said_and_done.py`, `screen_addresses.py`, `season_family.py`, `season_grab_unfollowed.py`, `transition.py`, `url_state.py`.
**Harness files reading `window.SEASONS`** (8): `busy.py`, `followed_sheet_act.py`, `message_over_layers.py`, `queued_ask_mark.py`, `season_family.py`, `season_grab_unfollowed.py`, `season_grab.py`, `seeds_at_rest.py`; the phase file
also names `season_grab.py`, `seeds_at_rest.py` and `priming.py` — re-take with the widened grep before moving.

**The media types**: `features/media/reference.ts` still declares `sheetFor`, `titleForProviderId`, `addressIdsFor`,
`ownedFor`, `EP_LABEL`, `TODAY`; `features/arrivals/reference.ts:104` declares `sheetFor`.

## Method — unchanged, plus what this session added

- Everything in the a·12 RESUME's « Method ».
- **`scripts/mutate.sh` now sees a rule that exits non-zero with no FAIL line.** Before `4c0e1d036` it did not: a
  « NO RULE FELL » from a rule whose verdict is its exit code (`audit2.py`, `audit.py`) was a false green.
- **`mutate.sh` restores, REBUILDS and REPUBLISHES** the served copy on exit (`scripts/mutate.sh:152-154`): no manual
  republish is owed after it.
- **Compare the served data with the engine's answer OFFLINE** before switching a reader: `a13-compare-media.py`
  (840 identities) and `a13-compare-seed-posters.py` (a candidate read exactly) are the shapes to copy.

## Traps met — each cost a run

- **A `cva("", …)` base is UNREADABLE to R80** (`residue.py` « the variant sources are read »): the anchor is the
  first token of the base. Give every factory an identity token first, even one with no style (`legendSwatch`'s
  `swatch`).
- **`scripts/markup_anchors.py`'s exemptions are KEYED BY LINE** (`("audit2.py", 171, "note")`): an edit above the
  site moves it, and `check-markup-contracts.py` names the new line.
- **Deleting `legacy.css` comments moves `comment-references-baseline.json`** (56 → 51 here): the comment-record test
  falls until `check-maquette-comments.py --record`.
- **`check-legacy-css-residue.py --record` rewrites the long `$comment`**: restore it from a copy taken before.
- **The media screen's placeholder is the engine's sheet and carries no artwork**: in flight and after a failed read
  the banner has no picture, the trailer is its skeleton, the cast shows initials (a·13's named difference).
- **A new word in a name must be in `scripts/code-vocabulary.txt`** (`cell`, `disclosure`, `shortfall` added).
- **`build-mock-seeds.py --write` deletes every seed no family claims**: join a converted seed through the module's
  `joined()` and `canonical()`, never `--write` (a·13 did it for the decision seeds).
- **In a shell loop, `python3 "scripts/x.py --root frontend"` is one filename**: exit 2, not the guard's verdict.
- **The heavy wrapper's browser class held a gate for fourteen minutes** before ruling 48; after it, it starts at
  ~5.5 GB free on this machine.
