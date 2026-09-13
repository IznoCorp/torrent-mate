# L13a — resume brief for the successor

Written by the tenth L13a implementer when it stood down at the a·14.2 boundary (a·14.2 was this session's last
unit). Read it after `docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything. This file only
records state, rulings and traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 … a·13 and a·14.1: see `git show 379279643:docs/features/maquette-l13/RESUME.md` and the briefs it points to.
  Then this session:
  - **a·14.2** `932b62e7c` `refactor(maquette-l13a): every media crossing reads the provider identity and the engine's sheet table dies`
  - `1e8db81e1` `chore(maquette-l13a): the comment corpus counts the three modules the identity crossing added`
  - the commit that adds this file (`4ced4b26d`).
  - `6c6180c9a` `test(maquette-l13a): the genre-site fixture follows audit.py's assertion to line 110` — the
    pre-push suite read 1 failed (`tests/scripts/test_check_markup_contracts.py`, the site moved 105 → 110).
- Gates on `932b62e7c`, every log under `/private/tmp/tm-l13a/` (pruned 2026-09-13 by the eleventh implementer on
  the steward's order: the gate logs, `oracle-check.py`, the three cited scripts and `earlier-phases/` stay; the
  `a142-alone-*` and `a142-mutation-*` working logs cited below are gone, their figures are the ones written here):
  - `a142-gate-contracts.log`: 19 rules + 27 guards, no violation (starts 15:23:40, 5 491 MB free).
  - `a142-gate-oracle.log`: 87 x 34, 2 958 measurements, no divergence.
  - Alone (`a142-alone-*.log`, equal to `hold-counts-baseline.json`): follow_has_sheet 3, followed_sheet_act 12, pop 17,
    audit 13/13, audit2 13/13, season_family 48, season_grab_unfollowed 63, panel 51, url_state 99, screen_addresses 51,
    journey 70, transition 39, priming 40, cards 70, paths_to_sheets 13, said_and_done 17 (priming and transition
    re-run on the committed head, `a142-gate-alone.log`).
  - Mutations through `scripts/mutate.sh` (`a142-mutation-*.log`, script `a142-mutations.sh`):
    placeholder → transition (1) and priming (4) FELL; popover catalogue → pop (4) FELL; acquisition card « has a
    sheet » → paths_to_sheets (4) FELL (cards.py does NOT read it); season list owned → audit2 (12) FELL; carried
    identity in `mediaSheet` → followed_sheet_act (1) FELL; `__sheetOf` → follow_has_sheet (1) FELL; the cache scan
    `heldIdentity` → transition (10) FELL (paths_to_sheets does not reach it); re-scrape identity → said_and_done (4)
    FELL. **Two reads no rule fells**: the follow panel matrix's owned numbers (`panel-seasons.tsx` `ownedSeason`;
    tried against the oracle, surfaces.py — the oracle measures regions, not a cell's state) and the follow facts'
    `hasSheet` (`follow-facts.ts`; tried against panel.py, surfaces.py). Named for the reader round; L13a writes no rule.
  - `tsc -b` 0, vitest 114, the cheap guards 0, the comment-record test 36 passed after each commit.
- Records:
  - `engine/legacy.js`: **5 295** non-blank (ledger 27 320 → 5 295).
  - `fixture-register.json`: `SHEETS_RAW`, `OWNED` converted, `SHEETS_OLD` removed ($counts 79 → 78).
    `build-mock-seeds.py --check` reads **29** « no family claims it » (27 + media-sheets.json, owned-episodes.json).
  - `markup_anchors.py` keyed lines: audit.py 110 and 176, audit2.py 176. `code-vocabulary.txt` gains `seeds`.
  - `comment-references-baseline.json` read 416. `legacy-css-residue.json` untouched (38/29/157).
  - `hold-counts-baseline.json` NOT re-recorded.
- `--compare`, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·15**, then a·16, a·17, **a·17-bis**, a·18, a·19.
- Version not bumped. No pull request. Pushed at this boundary (the stand-down report carries `git ls-remote`).

## Rulings — not to be reopened

1–52: see `git show 379279643:docs/features/maquette-l13/RESUME.md`. Ruling 52 is amended by 53.

53. **`SEASONS` stays until b·10-bis.** Read literally, ruling 52 was a behaviour change: the follow panel's season
    triples served by identity differ on 6 of the 10 panels that draw one (Silo gains a fourth season), and on 0 when
    only the owned numbers and the episodes are served (`python3 /private/tmp/tm-l13a/a142-compare-seasons.py` — keep
    it for the reader). `SEASONS`, its read in `followFacts`, the nine `window.SEASONS` harness readers and the seasons
    half of the seed accessor are b·10-bis's (INDEX row amended).
54. **The ONE `window.__mocks` seed accessor lands, sheets only** (`mocks/mock-seeds.ts`), read by the harness alone:
    `harness/drive.ts` publishes `__carriedFor`, `__addressOf`, `__sheetOf`. `screens.mediaSheet(title, carried?)`
    takes the identity when a state or rule knows it and asks the query cache otherwise (`lib/held-identity.ts`).
55. **Reading (A): a tap primes title and poster only.** Reading (B) (the entry also carries year and kind) failed its
    precondition: 3 of the 7 list schemas carry both (Follow, SearchResult, Suggestion), 4 do not (QueueCard,
    LibraryItem, LibraryRow, IncompleteShow). The entry carries `title`, `poster`, `ids` — a vitest test holds the
    writer. D8-named on every tap: year, genre, synopsis and cast are skeletons in flight; after a failed read title
    and poster remain. R119 (d), (e), (b-i) and R115 re-aimed (phase-a14's last amendment).
56. **`screens.media.synopsisUnread` reads « Synopsis non lu. »** — the failure text (A) made reachable asserted
    « inconnu » where its key and siblings say « non lu ».

## Owed — carried to a·19 and the steward's brief (verbatim, reading A)

- **The a·19 reader line**: « A tap on any card opens the media sheet with its title and poster at once; year, genre,
  synopsis and cast are skeletons until the read lands, and after a failed read only the title and the poster remain.
  A typed `/media/<provider>/<id>` shows its ids at once and a skeleton title until the read lands. Walk restore and
  Back on a typed address. »
- **The FIRST step of the operator's Mac walk**: « Tap a card: the sheet opens with its title and poster at once, year,
  genre, synopsis and cast a skeleton for an instant. Then type /media/<provider>/<id> directly: ids at once, the
  title a skeleton for an instant, then the sheet. »
- The two reads no rule fells (above), for the reader round.

## Method — unchanged, plus what this session added

- Everything in the earlier RESUMEs' « Method ».
- **Compare engine and served answers OFFLINE before switching a reader** — `a142-compare-seasons.py` imports
  `build-mock-seeds.py`'s resolver copy and the seeds; it is what turned ruling 52 into 53 before any code moved.
- **The oracle can be a mutation's rule** through a wrapper that calls `oracle.py --check`
  (`/private/tmp/tm-l13a/oracle-check.py`); `mutate.sh` runs `python3 <rule>` with no argument, and `oracle.py`
  without `--check` is not a check.
- **A rule opens a sheet by title with `window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)`**
  — `__reset` clears the query cache, so the cache scan finds nothing right after a driven state.

## Traps met — each cost a run

- **The boot REPLACES the arriving entry's state** (`app/arrival.ts`): an entry seeded before boot does not survive a
  cold load, so R119's walks open the screen by a harness tap (`__openCarrying`), not by `goto(address)`.
- **The product primes only from an entry about its own address** (`carriedSheet` checks `ids[provider]`), so a
  thinned entry must carry `ids` — and then the identifiers row is content, which moved R119's exact count to 13.
- **`mocks/index.ts` sits at 399 non-blank lines**: anything added there goes in a module of its own and is spread in.
- **A maquette comment may not name a lot, a phase or a date** — « RE-AIMED AT L13a a·14.2 » in fourteen docstrings
  fell `check-maquette-comments.py`; « RE-AIMED, said out loud » passes.
- **Three new files move `comment-references-baseline.json`'s `read`**: the comment-record test falls until
  `check-maquette-comments.py --record`, and `mutate.sh` refuses the dirty tree it leaves — commit it first.
- **`cards.py` does not read the acquisition card's folder switch, `paths_to_sheets.py` does not reach the cache scan**:
  pick a mutation's rule by what it taps, and read « NO RULE FELL » as a finding before trying another rule.
- **A line-keyed test fixture follows a moved anchor**: `tests/scripts/test_check_markup_contracts.py` writes its
  fixture at the line `scripts/markup_anchors.py` declares, so a docstring that grows a harness rule moves both. Only
  the pre-push suite finds it — replay that test file alone after any anchor move, before the push.
- **zsh does not split `$spec` in a loop**, and a parallel tool call that `cd`s moves the shell for the next one:
  prefix every call with `cd /Users/izno/dev/worktrees/wave-l13a &&`.
