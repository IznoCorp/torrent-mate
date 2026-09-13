# L13a — resume brief for the successor

Written by the sixth L13a implementer when it stood down at the a·9 boundary (gauge 38 %, the steward's ruling: a·9
cost 28 points and a·10 is wider, so a·10 is a whole session's unit, the a·8 precedent). Read it after
`docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything; this file only records state, rulings and
traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 `123816c93`, a·2 `383c67549`, a·3 `40fc7b785`, a·4 `ad4d3096a` + `4918abe65`, a·5 `504ce4897`, a·6 `f353eea14`,
  a·7 `8fba453c5`, a·8 `b2f5f2335` (+ `097558d46`, the pre-push suite reading a·8's comment record), then:
  - `716b8fe9b` `docs(maquette-l13a): the per-phase comment-record check, and the brief's dead reading line`
  - **a·9** `0cb5ce960` `refactor(maquette-l13a): arrivals and the resolution screen draw the card as a component`
  - then this file.
- Gates, each on its own head, under the shared mutex:
  - a·5 to a·8: see the a·8 RESUME (`git show 68381bdd0:docs/features/maquette-l13/RESUME.md`).
  - a·9 (`0cb5ce960`): `run.sh --contracts` 19 rules + 27 guards, no violation; `--oracle` 87 states x 34 regions,
    2 958 measurements, no divergence. Beside it: `tsc -b` 0, vitest 7 files / 112 tests; `check-no-french`,
    `check-frontend-boundaries`, `check-markup-contracts`, `check-poster-box`, `check-frame-domain`,
    `check-legacy-css-residue`, `check-compositor-css`, `check-mock-seeds`, `check-module-size`, `check-css-tokens`
    exit 0; pytest `test_check_maquette_comments`, `test_residue`, `test_check_css_tokens`, `test_csstokens_ranks`
    75 passed under the tests lock. The first contracts reading, on the pre-amend `126b14b46`, fell on three variant
    spellings, corrected and named in the commit body (traps below). The gate logs are
    `/private/tmp/tm-l13a/a09-contracts.log` and `a09-oracle.log`.
- Records: `engine/legacy.js` **29 824** non-blank (a·9 did not touch the engine, the ledger was not re-recorded);
  `legacy-css-residue.json` ceiling **190/123/783** (rules/classes/declarations); R80 `PAIRS_FLOOR` **25** (29 holds);
  `check-poster-box` floor **6** (legacy.css x3, ui/variants/card.ts x1, ui/variants/surfaces.ts x2);
  `csstokens_ranks.py` `LOCAL_DETAILS` **6**; `comment-references-baseline.json` read **401**, references **282**.
  `hold-counts-baseline.json` is NOT re-recorded: at a·19's `--compare`, R80 (`residue.py`) reads 29 against the
  baseline's 19 — a·7's −5 and a·9's +15, each named in its commit body.
- `--compare` over the whole suite, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·10** (`plan/phase-a10-library.md`), then a·11 … a·17,
  **a·17-bis** (the ≡ panel dies, rulings 29 and 31), a·18, a·19.
- Version not bumped. No pull request.

## Rulings — not to be reopened

1–36: see the a·8 RESUME (`git show 68381bdd0:docs/features/maquette-l13/RESUME.md`; 1–30 point further back to
`d75205677` and `58d24cfc4`), carried over unchanged. In short, the ones a·10 leans on: **27** the cut is B, L13a's
STOP C is its own pull request at a·19; **31** the ≡ panel dies alone as a·17-bis, before a·18; **32** R80 over a
corpus that changes on both sides — the floor moves to the MEASURED count, every pair added and removed named;
**33** `.poster` is not paired (`-webkit-touch-callout`); **36** every log under `/private/tmp/tm-l13a/`.

From a·9 (the steward accepted a·9 on the reading of its gate logs):

37. **The card is PARTS**: `ui/card.tsx` (`Card`, `CardContent`, `CardTop`, `CardPoster`, `CardBody`, `CardTitle`,
    `CardSubtitle`, `CardReason`, `CardOverview`, `CardMeta`, `CardCaption`, `CardFolder`, `CardStrip`), each naming
    itself with its `data-part`; its factories in `ui/variants/card.ts`, each with the card's identity class at the
    front (the delegation reads `.card`/`.ctitle`; `check-markup-contracts.py` counts a variant as declared only in a
    file named `variants.ts` or under `ui/variants/`). The strip's dot and label lead with a utility and the call site
    writes `d`/`l`, because `liveDot()` already claims the anchor `d`. The foot is `actionButton({ kind: "cardFoot" })`.
38. **The DOMAIN composition of a card stays in the feature** (invariant 10): `features/arrivals/arrival-card.tsx`
    decides poster-or-folder through `sheetFor`, writes `data-mediasheet`, `data-panel="media:…"`/`"dossier:…"` and
    `data-nonmedia="dossier"`, attribute for attribute as `cardHTML`. Features never import each other (invariant 7):
    a·11 composes acquisition's cards in acquisition, over the same `ui/card.tsx` parts.
39. **No card rule dies before `cardHTML` does.** The emit scan at a·9 found every card class still written by
    `cardHTML` (acquisition tabs, add screen, incomplete lens); they all wait for a·11, `.flux` for a·15 (phase-a09's
    dated amendment). R80 gained 15 pairs: `.card`, `.ccol`, `.ctop`, `.cbody`, `.ctitle`, `.csub`, `.creason`, `.cov`,
    `.cmeta`, `.caption`, `.folder`, `.dlabel`, `.strip`, `.st`, and `.flux` ↔ `factList()`. They fall — floor lowered
    to the measured count, each named — with `cardHTML` at a·11 (the fourteen) and the last `flux` emitter at a·15.
40. **The card's French lives in `surfaces.card.*`** (`sheetOf`, `folderActions`, `folder`, `stages`; `stages` read as
    a lookup table by importing `fr.json`, the resolution screen's precedent). The engine's own literals stay until
    its builder dies; « Nouveau » joins `surfaces.card` when a phase draws the fresh tag. `check-poster-box.py`'s floor
    and `csstokens_ranks.py`'s `LOCAL_DETAILS` are baselines like any other: re-taken in the phase's commit.

## Method — added at the a·9 opening

- **After every phase's commit and before ANY push** (the steward, 2026-09-13, measured: the pre-push suite fell on it
  at a·7 AND at a·8, ~3 min of suite each):
  `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder sh scripts/heavy.sh --class test l13a python3 -m pytest tests/scripts/test_check_maquette_comments.py -q`.
  A phase that adds or removes a maquette file or a dated comment re-records
  `python3 scripts/check-maquette-comments.py --record` INSIDE its own commit and reads the diff: only the `read` count
  and the reference count may move, and the commit body says the two numbers.
- **Every other baseline a phase moves** — the residue ceiling, the frame-domain floors, the mock seeds, R80's floor,
  the poster-box floor, `LOCAL_DETAILS` — is re-recorded in the phase's own commit, its numbers in the body.
- **Count R80's pairs offline before setting the floor**: `pair_up()` needs no browser —
  `cd frontend/maquette/harness && python3 -c "import residue as r; f=r.read_factories()[0]; c=r.pair_up(r.read_residue()[0], f)[0]; print(len(c)); [print(x['selector'], x['factory']) for x in c]"`.

## What a·10 inherits — the STOP D it raises FIRST, then its width

**Three questions the phase file leaves open; the fresh session asks the steward BEFORE moving anything** (the steward,
2026-09-13):

1. **`knownMedium`** (phase-a10 amended by a·3): the engine still defines it (`engine/legacy.js` ~29505) over
   `follows()`, `INCOMPLETE` and `LIBRARY`, handed in through `installKnownMedium`. Moving it to the cache narrows its
   answer — a title known on any page today is known then only where its listing page is cached. The phase must DECIDE,
   in its report, whether that is a behaviour change to file, or whether a·6's `ids` on every list item makes the
   predicate unnecessary. Re-take its readers first.
2. **`INCOMPLETE`** (`engine/legacy.js` ~4483): no phase of the plan names its death. Readers at the a·9 boundary:
   the engine ~8432 (a `find` by title), its `__referentiel` publication (~7292, read by
   `features/library/incomplete-lens.tsx`'s reference), and `knownMedium`. a·10 takes it or says which phase does.
3. **`LIBRARY`** (`engine/legacy.js` 3948) — three readers to the cache: `mediaNamedBy` (~8425,
   `LIBRARY.filter(row => row.t === title).length`, still the engine's until b·6), `knownMedium` (~29508), and
   `features/acquisition/follow-facts.ts:103` (`window.LIBRARY`). STOP D if one has no cache answer. Then
   `fixture-register.json`: `LIBRARY` (and `INCOMPLETE` if taken) marked `converted`, `$counts` re-tallied
   (served 41 / asset 5 / interface 29 / unserved 4 / total 79 at a·9).

**Its width, measured at the a·9 boundary** (re-take before trusting):

- `tileHTML` (`legacy.js` 7428–7457, 30 lines): selection mode off `currentState()`, a badge tone map, `data-tile`,
  `data-dismissable`, `data-panel`, `aria-pressed` + `data-selected-title` OR `data-mediasheet`, `posterBox`, the
  `sel` check (`svgIcon(icons.check, 3)`), `tilebadge` with an inline `background:var(--tone)`, `nm`, `fr`.
- `libRowHTML` (7469–7484, 16 lines): in selection mode a `selrow` button (`sel`, a `poster` span, `rowtxt` > `ctitle`
  + `csub`); otherwise `swipeHTML(cardHTML({ t, s: f, overview }), <act remove …>Supprimer</button>)` — so the library
  list's resting row IS a card inside a swipe row: a·10 draws it with a·9's `ui/card.tsx` parts.
- `swipeHTML` (5339–5343): `swipe` > `actions` > optional `side left` + `side right`, then the inner.
- Callers outside the engine: `features/library/library-list.tsx:196–197` (virtual rows), `features/library/page.tsx`
  (comments), `features/library/incomplete-lens.tsx:23,39` (`cardHTML` + `tileHTML`),
  `features/library/reference.ts:34` (type), `features/acquisition/follows-tab.tsx:145,173` (`swipeHTML`, `tileHTML`),
  `features/acquisition/discover-cards.ts:90` (`tileHTML`, a string emitter). Harness readers named by the phase:
  `library_sort.py`, `gallery.py`, the selection rules; `content.py:255` mentions `libRowHTML` on a detached node.
- `legacy.css` rules of those classes (line numbers at a·9): `.swipe/.sugwrap/.deck` group 98–111, `.swipe` 116,
  `.actions` 128–139, `.act` 142–170, `.tilebadge` 464, `.gallery` 579–598 (with media queries), `.tile` 602–672,
  `.selrow` 680–707, the long-press group 1470–1477. `.act`, `.pause`, `.remove`, `.resume`, the `.swipe, .sugwrap,
  .deck` group and the `discover-feed.ts` gallery wait for a·11 (phase-a10).
- **R80 at a·10**: `cardHTML` still writes `chip` and `pfall` until a·11, so a·10 removes the chip/pfall pairs only if
  it re-takes the emit scan and finds itself the last writer — it will not be. New tile/row factories anchored on
  residue classes ADD pairs (ruling 32); count them offline (Method).
- **The two arms notes** (the steward's dry read): a swipe row as a `ui/` component may NOT import a feature's action —
  the feature passes the action in as a prop (`check-frontend-boundaries.py` 368–369, « ui/ must know no feature »);
  and no `ui/` identifier carries `library`/`lib` (frame-domain ui ceiling 0 — name a tile's axis by what it is).

## Traps met — each cost a run

**THE RULE FOR EVERY PHASE (steward, 2026-09-13, widened the same day)**: before a gate, search every removed name
everywhere a reader can live — `rg -n -g '*.py' -g '*.mjs' -g '*.txt' -g '*.json' NAME frontend/maquette/harness scripts tests`
— in its `window.NAME`, bare `NAME(` and `=>NAME(` forms, and replay each reader alone.

From a·5 to a·8 (see the a·8 RESUME for the detail): scan a deleted class in EVERY quote position; a descendant rule has
JSX emitters too; read the cascade ORDER; `GENRE_SITES` is keyed by line; `check-markup-contracts.py` refuses a
style-class anchor in a harness selector; `check-legacy-css-residue.py --record` drops `$comment` (restore it with only
the figures changed); an engine constant in the fixture register needs its entry gone AND `$counts` re-tallied;
`check-mock-seeds.py` refuses a string literal in an indexed type; `run.sh`'s guard list has no `python3` prefix; `cd`
persists in the Bash tool; converting a string emitter to JSX can change escaping; `residue.py` reads a variant branch
as ONE string literal; Tailwind orders same-property utilities by NAME; R80 fails a pair on a property Chrome does not
compute; `check-frame-domain.py` holds `ui/` at zero domain words; an unlayered `base.css` rule beats every utility;
`markup_dressing.py`'s `BARE_ALLOWED` is keyed by file; an engine function's inner constant is registered under a
qualified name; zsh does not word-split, `echo =====` errors, ugrep refuses bounded `.{0,N}`.

New in a·9:

- **Tailwind's `self-start` and `justify-self-start` compute `flex-start`**, not `start`: a residue rule declaring
  `align-self: start` / `justify-self: start` needs `[align-self:start] [justify-self:start]`, or R80 fails the pair.
- **`bg-transparent` is not `background: transparent`**: R80 compares the computed `background` shorthand, which the
  utility serialises with `background-position: 0% 0%` against the shorthand's `0px 0px`. Where the residue writes the
  shorthand with `transparent`, write `[background:transparent]` (`bg-card` against `background: var(--color-card)`
  passed).
- **A `z-*` utility in ANY variant must be named**: in `ui/variants/frame.ts`'s ranked list if it is a frame rank, or in
  `scripts/csstokens_ranks.py`'s `LOCAL_DETAILS` if it is local to one box — `check-css-tokens.py` runs in the contracts
  tier, not in the quick guards you run by hand first.
- **`check-no-french.py`'s vocabulary arm refuses words inside library type names**: `ComponentPropsWithoutRef`
  (`Component`, `Props`) and `Column` are not in `scripts/code-vocabulary.txt`. `ButtonHTMLAttributes<HTMLElement>`
  passes; `CardContent` replaced `CardColumn`.
- **`run.sh --contracts` prints a failing guard's detail only in its « cheap guards » section**: the log's tail shows
  the guard's GREEN lines. Read from « Running the repository's cheap guards » down.
- **The Bash tool's working directory follows a `cd` made in ANY call, parallel ones included**: start every command
  from the worktree root with an absolute `cd`.
