# L13a — resume brief for the successor

Written by the fifth L13a implementer when it stood down at the a·8 boundary (gauge 42 %, the steward's ruling: a·9
would cross the 60 % gate mid-phase). Read it after `docs/features/maquette-l13/BRIEF-L13a.md`, which still governs
everything; this file only records state, rulings and traps, and it dies with the wave's folder at the post-merge
gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at `60530dbd8`
  (#595, 0.98.90). Oracle reference `f1e7ac66`.
- a·1 `123816c93`, a·2 `383c67549`, a·3 `40fc7b785`, a·4 `ad4d3096a` + `4918abe65`, a·5 `504ce4897`, a·6 `f353eea14`,
  a·7 `8fba453c5`, then:
  - `9ddb1677e` `docs(maquette-l13a): the removed-name search widened, the panel's readers re-taken, the logs' directory, two stale directives`
  - `be6f2a32c` `docs(maquette-l13a): ruling 31 — the ≡ panel dies alone, as a·17-bis before a·18`
  - **a·8** `b2f5f2335` `refactor(maquette-l13a): actions, chips, status dots, fact rows and the poster box are variants`
  - then this file.
- Gates, each on its own head, under the shared mutex:
  - a·5 to a·7: see the a·7 RESUME (`git show d75205677:docs/features/maquette-l13/RESUME.md`).
  - a·8 (`b2f5f2335`): `run.sh --contracts` 19 rules + 27 guards, no violation; `--oracle` 87 states x 34 regions,
    2 958 measurements, no divergence; `residue.py` alone 14 holds, no violation. Beside it: `tsc -b` 0, vitest 7 files /
    112 tests; `check-no-french`, `check-frontend-boundaries`, `check-legacy-css-residue`, `check-poster-box`,
    `check-compositor-css`, `check-frame-domain`, `check-markup-contracts`, `check-mock-seeds`, `check-module-size` exit 0.
    The gate logs are `/private/tmp/tm-l13a/a08-contracts.log` and `a08-oracle.log`.
- Records: `engine/legacy.js` **29 824** non-blank (ledger re-recorded); `legacy-css-residue.json` ceiling
  **190/123/783** (rules/classes/declarations); R80 `PAIRS_FLOOR` **10**; `check-poster-box` **5** boxes (legacy.css x3,
  ui/variants/surfaces.ts x2). `hold-counts-baseline.json` is NOT re-recorded: at a·19's `--compare`, R80 (`residue.py`)
  reads 14 against the baseline's 19, and that movement is a·7's, named in its commit body; a·8 did not move it.
- `--compare` over the whole suite, the full suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·9** (`plan/phase-a09-arrivals.md`), then a·10 … a·17, **a·17-bis** (the ≡ panel dies, rulings 29 and 31),
  a·18, a·19.
- Version not bumped. No pull request.

## Rulings — not to be reopened

1–30: see the a·7 RESUME (`git show d75205677:docs/features/maquette-l13/RESUME.md`; 1–21 point further back to
`58d24cfc4`), carried over unchanged. The operator's three of 2026-09-13 in short: **27** the cut is B (L13a → L13b →
L13c, three pull requests; L13a's STOP C is its own pull request at a·19); **28** D-L13-1 = A, nothing changes in L13a;
**29** Q2 = B, the ≡ harness panel dies in ONE commit before a·18.

31. **(steward, 2026-09-13, on the panel's readers re-taken by grep) Ruling 29 kills the ≡ PANEL and nothing else**, and
    its commit is renumbered **a·17-bis**, BEFORE a·18 — a stylesheet cannot die while a component still needs its
    `.hpanel` rules. It goes: the panel half of `harness/panel.ts`, its five `h*` verbs, `#scenBtn`, the `.hpanel` rules
    (they are in `legacy.css`), the panel-only i18n keys, `markup_verbs.py`'s five answers, `check-markup-contracts.py`'s
    `data-hscen`/`data-hphase` contract and its two test assertions, `hscen` in `code-vocabulary.txt`. It stays:
    `harness/bar` and `#notesBtn` with its toggle. `hiding.py` and `chrome.py` do not move; `message_above_harness.py`,
    `audit.py` and `dest.py` drop only their `harness/panel` (and `#scenBtn`) reads. Written in INDEX's row and
    `phase-a01`'s amendment. `harness/panel_verbs.mjs` reads `ui/panel` action targets and is NOT a reader of the ≡.

From a·8 (the steward accepted each on the reading):

32. **R80 over a corpus that changes on both sides: the floor moves to the MEASURED count** (phase-a08 amended; a·10 and
    a·11 each carry the line). At a·8: 10 pairs before, 10 after. −7: `.pip` and its six tones ↔ `statusDot()`. +7:
    `.chip` and its five tones ↔ `chip()`, `.pfall` ↔ `posterFallback()`. The seven added fall in the phase that removes
    the LAST engine builder writing `chip`/`pfall` (`cardHTML`, `tileHTML`, `libRowHTML`, `posterBox`), each named, floor
    lowered to the measured count. One contextual pair more: `.tile .fr` ↔ `factValue()`.
33. **`.poster` is NOT paired, on purpose.** Its rule is grouped with `-webkit-touch-callout`, which Chrome does not
    compute; an anchored pair reads nothing on either side and R80 fails it (« neither side reads a value »).
    `posterFrame()` leads with a utility and the call site writes `poster` beside it.
34. **The action buttons are axes of `actionButton()`**: `kind` (`panelAction` = `sact`, `cardFoot` = `cfoot`, `add` =
    `mediaadd`, `submit` = `btnprimary`) and `tone` (`plain`, `primary`, `danger`, `solid`, `owned`, `done`), every
    colour in one `compoundVariants` entry per kind and tone. Its anchor is a utility, so no R80 pair.
    `actionButton()` with no argument is unchanged token for token (`variants.test.ts` holds it).
35. **`.btnprimary:disabled { opacity: 0.5 }` MOVED to `styles/base.css`, unlayered** beside `.addrow .btnprimary`. As a
    utility it loses to the unlayered `:where(button…):hover` rule and a disabled submit lifts to 0.85 under a cursor.
    c·3 draws the disabled state (B-339).
36. **The log directory**: every log under `/private/tmp/tm-l13a/`, `<phase>-<step>.log`; the gate logs
    (`<phase>-contracts`, `<phase>-oracle`) kept until the merge, the rest deleted at stand-down and proved by `ls`.

## What a·9 inherits, read but not acted on

Readings taken at the a·8 boundary, to re-take before trusting (they are a start, not a proof):

- `cardHTML` is still called outside Arrivées — `features/acquisition/now-tab.tsx`, `follows-tab.tsx`,
  `add-screen.tsx`, `discover-cards.ts`, `features/library/incomplete-lens.tsx` — so every card rule those still emit
  stays until a·10/a·11. Inside `features/arrivals/`, `cardHTML` is called only in `page.tsx` (the stuck section with
  `foot`/`footAct: "resolve"`, moving, settled); `resolution-cards.tsx` and `resolution-screen.tsx` already draw
  `ReleaseCard`/`DecisionCard` in JSX with bare card classes (`card`, `ctop`, `cbody`, `ctitle`, `csub`, `cmeta`, `cov`,
  `creason`).
- `cardHTML` (engine) draws: a `poster` button (`data-mediasheet`) or a `folder` button (`data-panel`,
  `data-nonmedia="dossier"`, `dlabel` « Dossier »), `ccol` > `ctop` > `cbody` button (`data-panel`) with `ctitle`,
  `csub`, `creason` (`richText`), `cov`, `cmeta` (`frac`, the chip, `crating`), `cannotations` (`caption`, `freshtag`
  « Nouveau »), then `stripHTML` (`strip` > `st` done/now/blocked > `d` + `l`) and the `cfoot` (`data-act`,
  `data-solid`, `disabled` when done). French literals in it (« Fiche de », « Actions pour le dossier », « Dossier »,
  « Nouveau ») must go through i18n when the card becomes a component.
- Harness readers of the card on these surfaces: `take.py` reads `[data-part="card/foot"]`; `arrivals.py` reads the flux
  rows by `data-part`.

## Traps met — each cost a run

**THE RULE FOR EVERY PHASE (steward, 2026-09-13, widened the same day)**: before a gate, search every removed name
everywhere a reader can live — `rg -n -g '*.py' -g '*.mjs' -g '*.txt' -g '*.json' NAME frontend/maquette/harness scripts tests`
— in its `window.NAME`, bare `NAME(` and `=>NAME(` forms, and replay each reader alone.

From a·5 to a·7 (see the a·7 RESUME for the detail): scan a deleted class in EVERY quote position; a descendant rule has
JSX emitters too; read the cascade ORDER; `GENRE_SITES` is keyed by line; `check-markup-contracts.py` refuses a
style-class anchor in a harness selector; `check-legacy-css-residue.py --record` drops `$comment` (restore it with only
the figures changed); an engine constant in the fixture register needs its entry gone AND `$counts` re-tallied;
`check-mock-seeds.py` refuses a string literal in an indexed type; `run.sh`'s guard list has no `python3` prefix; `cd`
persists in the Bash tool; converting a string emitter to JSX can change escaping.

New in a·8:

- **`residue.py` reads a variant branch as ONE string literal.** A tone written as two concatenated literals is read as
  two branches, the probe wears half the tone, and R80 fails on the half it lost (it cost a contracts run: `color`
  diverged on five chip tones while the built CSS was right). Every branch is one literal, however long.
- **Tailwind orders two utilities setting the same property by NAME**, not by where they are written: `bg-danger/20`
  sorts before `bg-muted` and loses to it. A tone's colours live in mutually exclusive branches or compound entries, or
  go through a custom property the base reads with a fallback (`chip()` does the latter).
- **R80 fails a pair whose rule declares a property Chrome does not compute** (`-webkit-touch-callout`): « neither side
  reads a value ». Check a rule's properties before anchoring a factory on its class.
- **`check-frame-domain.py` holds `ui/` at ZERO domain words** in identifiers — feature names and page aliases (`media`,
  `library`, `account`, `settings`, `system`, `acq`, `lib`…). A variant axis named `mediaAdd` in `ui/` is refused; name it
  by what it is (`add`).
- **An unlayered base.css rule beats every utility**: `:where(button…):hover`, `:active`, `.sact:has(> svg)`. A state
  rule moved from `legacy.css` to a utility can lose to one of them.
- **`markup_dressing.py`'s `BARE_ALLOWED` is keyed by FILE**: moving a bare element (the poster's `<img>`) to another
  file needs its entry re-keyed in the same commit.
- **An inner constant of an engine function is in the fixture register under a qualified name**
  (`factRowsHTML.TONS`): deleting the function takes the entry and re-tallies `$counts`.
- **Shell traps in this tool**: zsh does not word-split `set -- $spec` (use a function with arguments); `echo =====` is a
  zsh `=command` expansion and errors; `grep` is ugrep, and a `-o` pattern with `.{0,N}` bounds fails « exceeds
  complexity limits » — read built CSS with Python instead.
