# Design — docs-cleanup: the documentation model's first application

> **Status**: spec, for the operator's review — nothing is moved until the window opens.
> **Dictated**: 2026-08-31, at the close of a reflection that changed nothing before it ended.
> **Codename**: `docs-cleanup` · **Branch**: `chore/docs-cleanup` · **Bump**: patch (a guard changes).
> **Window**: between L12's post-merge gesture and L13's launch — never under a lot in flight.
> **Executed by**: the steward (`docs/reference/frontend-steward.md`), because it is directive
> work: it moves no code beyond the paths code cites.
> **The rule it applies**: `docs/reference/documentation-model.md`. This file is the move, that
> file is the model; once this wave is merged this file is read from history (model § 2).

---

## 0. The five decisions, in the operator's order

1. **No new repository now.** Whether the engine is adapted or rebuilt is the backend study's
   question, and a new project would bet on one answer. The form chosen must survive both. A new
   repository is at most the gesture of the switchover, decided then.
2. **Git is the history.** `docs/archive/` leaves the tree; what is still needed from it is cited
   by commit, never by an archive file.
3. **Three families, and the present is what moves.** The future and the knowledge stay in
   `docs/reference/`, where every guard reads them; the present goes to `docs/production/`, named
   to die, and nothing is born there.
4. **Language.** The constitution stays French, the only named exception. The present is not
   translated. Everything else that lives is English.
5. **Timing.** Between L12 and L13, one pull request, the steward's.

## 1. What the tree holds — measured 2026-08-31 at `5322c2fa`

| Where               | Files                         | Lines   | Language                                                          | Verdict                                      |
| ------------------- | ----------------------------- | ------- | ----------------------------------------------------------------- | -------------------------------------------- |
| `docs/archive/`     | 1 164                         | 224 308 | mostly French (`legacy-alpha/`, most `features/*/`)               | leaves the tree                              |
| `docs/superpowers/` | 27                            | 9 333   | mixed; three handoffs French                                      | leaves the tree                              |
| `docs/analysis/`    | 3                             | 792     | English                                                           | leaves the tree                              |
| `docs/reference/`   | 45 documents + 52 `_samples/` | 64 675  | English (constitution French)                                     | split three ways, § 2                        |
| `docs/features/`    | 23                            | 3 042   | English                                                           | L12's is the wave's; L10-ter's is split, § 2 |
| Root                | 10 markdown files             | 11 000  | four French (`README`, `MANUAL`, `INSTALLATION`, `CONFIGURATION`) | split, § 2                                   |

Code, for scale: engine 131 560 lines, tests 248 440, `frontend/src` 78 413, maquette 149 262,
harness 24 942, scripts 27 462. `docs/` holds 1 254 files; after the move it holds 53 documents and `_samples/`, plus the open
wave's folder.

**Two things measured wrong during the reflection, corrected here.** The `_samples/` files that
`wc -l` reports at zero lines are one-line JSON without a trailing newline (18 B to 38 922 B),
not empty: nothing is deleted there. And `docs/production/**` cannot be kept out of every CI
filter: the design-gaps job parses the ANCHORS of seven present documents that 72 `Design:`
markers in 29 test files contract against, so `docs/**` stays in the `docs` filter and those
seven move with their markers (§ 3).

## 2. The classification, file by file

The criterion is the model's § 1 question: « if the version in production were switched off
tomorrow, would this sentence still be true? »

### The present → `docs/production/` (23 files)

From `docs/reference/` (18): `architecture.md`, `commands.md`, `config-overlay-layout.md`,
`event-bus.md`, `external-ids-flow.md`, `grab-core.md`, `indexer-json-shapes.md`, `indexer.md`,
`insights.md`, `logging.md`, `maintenance.md`, `pipeline-internals.md`, `promises.md`,
`runbook-post-merge.md`, `scraping.md`, `storage.md`, `trailers.md`, `web-ui.md`.

From the root (4): `MANUAL.md`, `INSTALLATION.md`, `CONFIGURATION.md`, `ROADMAP.md` — the last
one dated 2026-08-16 and declaring itself superseded by `IMPLEMENTATION.md`; its open ideas
(ratio, cross-seed, LLM) are carried by the constitution's §18–§19 and the backend demands.

From the archive (1): `docs/archive/features/api-unify/DESIGN.md` → `docs/production/api-unify-design.md`.
It is the one archived file that is NOT history: six `Design:` markers in
`tests/integration/test_design_api_transport.py` and `test_design_api_activation.py` contract
against its anchors, and `tests/feature_map/api-unify.json` names it. A test contract is the
present engine's, so its design lives with the present.

**Not moved and not translated**: the model says what « frozen » allows (one-line corrections of
a false sentence, nothing added). Their citations of `docs/archive/…` are left as written — the
model's universal key (§ 2) resolves them — because rewriting a dying document is work that dies
with it.

### The future — stays in `docs/reference/` (8 + 2 moved in)

`product-intent.md` (French, the exception), `product-intent-map.md`, `frontend-architecture.md`,
`frontend-steward.md`, `backend-demands-architecture.md`, `frontend-backend-demands.md`,
`frontend-backend-demands-stream.md`, `documentation-model.md` (new, this wave). Moved in from
`docs/features/maquette-l10-ter/`: `MODEL.md` → `frame-model.md`, `SURVEY.md` →
`frame-survey.md` — the plan cites them twenty-four times and had to carve an exemption from its
archive gesture to keep them; the move dissolves the exemption.

At the root: `BUGS.md`, `BUGS-CLOSED.md` (kept — model § 1, the register's memory),
`IMPLEMENTATION.md`, `CLAUDE.md`, `README.md` (kept at the root as the landing page, one signpost
line added, not translated).

### The knowledge — stays in `docs/reference/` (17 + `_samples/`)

The twelve API references: `c411-api.md`, `ffprobe-api.md`, `healthchecks-api.md`, `omdb-api.md`,
`plex-api.md`, `qbittorrent-api.md`, `telegram-api.md`, `tmdb-api.md`, `tr4ker-api.md`,
`trakt-api.md`, `transmission-api.md`, `tvdb-api.md`, with `_samples/` (read by six unit-test
modules). The method: `feature-lifecycle.md`, `testing.md`, `code-naming.md`. Two judgment calls:
`naming.md` (how a movie or a series is named on disk — a fact of the library, not of the
engine) and `libraries.md` (rapidfuzz, tenacity, structlog, guessit traps — true wherever the
library is reused). At the root: `CHANGELOG.md`.

### Out of the tree (1 200 files)

`docs/archive/` entire — including whatever the post-merge gestures add to it before the window
(L12's design lands there under the old gesture; it leaves with the rest). `docs/superpowers/`
entire, `docs/analysis/` entire. `docs/features/maquette-l10-ter/` once `MODEL.md` and
`SURVEY.md` have moved (`BRIEF.md`, `DEFINITION.md`, `HANDOVER.md`, `QUESTIONS.md`, `REPORT.md`
are the design phase's record). `docs/features/tech-debt-2/DESIGN.md`, a May draft of an engine
tech-debt round the roadmap ranked P3 and nothing ever executed.

## 3. Every end that moves — counted, not estimated

A path is a name, and a name moves with all of its ends or the interface half-works in a way no
single file reveals. The ends, by kind, from `grep` over the tree at `5322c2fa` (the plan will
recount at the window, because L12 writes between now and then).

**Directives the guard reads** — citations rewritten to `@sha` or to the new path:
`BUGS.md` (15 to the archive, 2 to L10-ter), `IMPLEMENTATION.md` (7 archive, 4 superpowers,
2 L10-ter, 1 `BUGS-CLOSED.md` unchanged), `docs/reference/frontend-architecture.md` (7 archive,
2 superpowers, 4 L10-ter), `CLAUDE.md` (4 archive, 1 L10-ter: the reference-index rows for
`registry/DESIGN.md` §5.3 and `config-home/DESIGN.md`, the « Also check archived alpha versions »
line, the frame-model row, and the eighteen index rows that name a present document),
`docs/reference/product-intent-map.md` (1 L10-ter). The office cites none of them.

**Living documents the guard does not read** — rewritten all the same:
`docs/reference/feature-lifecycle.md` (4: § 6's banner rule dies, § 7's two pointers to the
archived skills spec become `@sha`), `docs/reference/libraries.md` (1),
`frontend/maquette/README.md` (1: the 2026-08-10 spec, now `@sha`), and L12's brief if it is still
in the tree (1 archive, 3 L10-ter — it is L12's file; if L12 has merged, it has left).

**Code that names a document** — every one a path string, moved with the file:

- 72 `Design:` markers over the seven present documents (`architecture.md` 24, `scraping.md` 20,
  `pipeline-internals.md` 13, `storage.md` 7, `indexer-json-shapes.md` 5, `trailers.md` 2,
  `indexer.md` 1) and 6 over the archived `api-unify` design, in 29 test files.
- `scripts/_codename_overrides.py`: seven keys. `tests/unit/test_update_feature_map.py`: eight
  literals that mirror them. `tests/feature_map/*.json`: eight `design` keys, regenerated by
  `scripts/update_feature_map.py` (the pre-commit hook refuses a hand edit staged beside a
  `test_design_*` change — regenerate, do not edit).
- `scripts/audit-cli-coverage.py`: `COMMANDS_DOC` and five docstring mentions of `commands.md`.
- Engine docstrings: `web-ui.md` 5, `logging.md` 2, `event-bus.md` 1, `indexer-json-shapes.md` 1.
  Test prose citing a present document: 11 lines across `tests/integration/test_design_*.py`,
  `tests/architecture/test_layering.py`, `tests/event_bus/test_pipeline_events.py`,
  `tests/integration/indexer_scenarios/__init__.py`.
- The maquette: `frontend/maquette/design/src/mocks/stream-protocol.ts` and `stream.ts` cite
  `web-ui.md` § WebSocket Protocol; `frontend/maquette/harness/arrivals.py` cites `commands.md`
  § Pipeline. Three comment lines, and the harness comment rule (no dated reference) holds.

**The guard and its wiring**: `scripts/check-docs-cited-paths.py` (three arms, model § 5),
`tests/scripts/test_check_docs_cited_paths.py` (one test per arm, each seen red first), the new
`scripts/production-docs-manifest.json`, and `.github/workflows/ci.yml`'s `maquette` filter,
which must name every path the guard declares — `docs/production/**`, the manifest,
`docs/archive/**`, `docs/superpowers/**`, `docs/analysis/**` — or
`tests/scripts/test_ci_filter_covers_the_guards.py` refuses it. Naming the three dead
directories in a filter is the point: a pull request that recreates one runs the guard that
refuses it.

**The operator's own tooling** — six files under `.claude/`, gitignored, listed and not touched:
`skills/implement:create-branch/SKILL.md` and its `references/archive-previous-protocol.md`
(`git mv docs/features/… docs/archive/features/…`), `skills/implement:archive/SKILL.md`,
`references/preflight-checks.md`, `references/deepseek-flash-dispatch-protocol.md`, and
`skills/implement:prepare-feature/references/design-generation-prompt.md`. Until they change,
arm 2 refuses what they produce, which is the correct order: the tree says no before the habit
is unlearned.

**Left as written, on purpose**: the present documents' citations of the archive (`architecture.md`
8, `web-ui.md` 4, `runbook-post-merge.md` 4, `event-bus.md` 2, `grab-core.md`,
`config-overlay-layout.md`, `logging.md` 1 each, `ROADMAP.md` 6).

## 4. The commit that holds everything

The `@sha` written in every rewritten citation is the sha of `origin/main` at the moment of
writing (model § 2). For this wave that is the commit the branch is cut from at the window — it
holds every file that leaves, L12's archive included — and it is named in the pull request
body and in the model's « universal key » paragraph as the one commit a reader needs to open any
path that a document never rewritten still cites bare. `5322c2fa` is the anchor for everything
that exists today; the window's sha supersedes it only for what L12 adds.

## 5. What was found on the way — to file at execution, numbered by `--next`

1. `IMPLEMENTATION.md` says « the L06 spec is parked, not lost —
   `docs/superpowers/roadmap/maquette-l06/specs/` », and no commit on any branch has ever held
   that directory (`git log --all -- docs/superpowers/roadmap/maquette-l06` is empty). The guard is
   blind to a directory citation by design; the sentence is rewritten to where the spec is, once
   found, or to « lost » if it is not.
2. 38 `Design:` markers in tests name `docs/features/{api-unify,torrent-fetch,watch-seed,scraper,
webui-ux,test-coverage}/…` — paths that left the tree when those features were archived — and
   `update_feature_map.py --check` and `audit_design_coverage.py --strict` pass over them in
   silence. A guard green over what it does not read; counted in `BUGS.md`'s § Guards green over
   what they do not read, left as found by this wave.
3. `.gitignore` lines 150 and 170 cite `docs/features/config-home/DESIGN.md` and
   `docs/features/provider-ids/plan/DEVIATIONS.md`, neither in the tree. Two stale lines, removed.

## 6. The phases the plan will cut

1. **The model and the guard** — `documentation-model.md` lands; the guard's `@sha` resolution,
   arm 2 and arm 3 written test-first, each test red against the guard as it stands, then green;
   the manifest starts as the exact `git ls-files docs/production` of phase 3, so arm 3 goes green
   in the same commit that fills the directory.
2. **History leaves** — `git rm -r` of the four trees in § 2; every citation in § 3's first two
   blocks rewritten; `git show` on three of them prints the file's first heading.
3. **The present moves** — `git mv` of the 23 files; the 78 markers, the overrides, the eight
   maps regenerated, `audit-cli-coverage.py`, the docstrings, the three maquette comments; the
   design-gaps pair green.
4. **The frame's model and survey** move to `docs/reference/`; twenty-four plan citations and the
   `CLAUDE.md` row follow.
5. **The directives** — `CLAUDE.md` (index rows, § Language: the exception list becomes the
   constitution alone, the « archive frozen » bullet dies, the archived-alpha line dies),
   the plan's § 5 gesture four and its L10-ter exemption paragraph, `feature-lifecycle.md` § 6
   and § 7, `IMPLEMENTATION.md`'s rows and the finding above, the office (one paragraph: the
   model is the steward's to hold), the `README.md` signpost, the register entries of § 5, the
   CI filter.
6. **The proofs and the pull request** — § 7.

## 7. Definition of done

- `git ls-files docs/archive docs/superpowers docs/analysis | wc -l` prints `0`;
  `git ls-files docs/production | wc -l` equals the manifest's length (23).
- `python3 scripts/check-docs-cited-paths.py` is clean and prints its three arms; three
  mutations, each restored: `git add -f` of a file under `docs/archive/` → arm 2 red naming it;
  a file added under `docs/production/` → arm 3 red naming it; one `@sha` citation edited to a
  sha that does not hold the path → arm 1 red naming the citation.
- `make check` green — which includes `update_feature_map.py --check` and
  `audit_design_coverage.py --strict` over the moved documents, `check-no-french.py`'s
  self-description arm over the edited `CLAUDE.md`, and `audit-cli-coverage.py` over the moved
  `commands.md`. `frontend/maquette/harness/run.sh --contracts` green, announced first: one
  harness at a time per machine. CI green on the pull request, with the `maquette`, `docs` and
  `python` filters all firing (the pull request touches all three).
- `git show <sha>:<path>` executed on three rewritten citations, output in the pull request.
- The diff re-read, not the tool's count: two corruptions in this repository were found by
  reading a diff after a tool reported success.
- `IMPLEMENTATION.md` carries the wave as a « NOT A LOT » row, like L07-bis and L10-bis, with its
  PR number and version; `check-implementation-state.py` accepts it.
- The memory of the operator's `.claude/` skills is listed in the pull request body, untouched.

## 8. What this wave does not do

It writes no documentation for the next version beyond the model: the constitution, the plan, the
frame model and the backend demands already are that documentation, and the backend brief will
write the rest when the study has answered its question. It does not translate the present. It
does not touch `frontend/src`, `personalscraper/` beyond docstring paths, or the maquette beyond
three comment lines. It does not create a repository. It does not decide which production
documents the backend brief will promote.
