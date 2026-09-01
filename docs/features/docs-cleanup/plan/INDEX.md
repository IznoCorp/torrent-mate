# docs-cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply `docs/reference/documentation-model.md` once: the present moves to
`docs/production/`, history leaves the tree and is cited by commit, the frame's model and survey
become reference documents, and a three-arm guard holds all of it.

**Architecture:** One branch, `chore/docs-cleanup`, six phases, each a green commit. The guard's
arms are written test-first in phase 1 and WIRED only in the phase that makes them true (arm 3 with
the production move, arm 2 with the departure of history), so no commit on the branch is red.
Every path rewrite is grep-enumerated at the window rather than trusted from this plan's counts,
then re-read in the diff.

**Tech Stack:** git (`mv`, `rm -r`, `cat-file -e`, `rev-parse --verify`), Python 3.12 stdlib for
the guard, pytest for its tests, macOS `sed -i ''`, the repository's own guards as proofs.

**Spec:** `docs/features/docs-cleanup/DESIGN.md` — the plan argues from it; read § 2 (the
classification) and § 3 (every end) before any phase.

## Global Constraints

- **The window**: L12's pull request merged AND its post-merge gesture done (its design under
  `docs/archive/features/maquette-l12/`, its `IMPLEMENTATION.md` row moved). L13 not launched.
  Phase 0 checks this and refuses to start otherwise.
- **Where**: the steward's worktree `/Users/izno/dev/PersonalScraper-steward`, branch
  `chore/docs-cleanup` (spec commit `54a824e7` on it), with `origin/main` merged in first — never
  the shared checkout `/Users/izno/dev/PersonalScraper`.
- **One harness at a time per machine**: announce by `SendMessage` before `run.sh`, the oracle or
  the hold-count compare; L12's agent must be done.
- **`docs/` is ignored by the operator's global `.gitignore`**: a NEW file under `docs/` is added
  with `git add -f <exact path>`, never `git add -f docs/`. `git mv` and `git rm` work on tracked
  files without it.
- **Commit messages**: Conventional Commits, scope `docs-cleanup`, no version prefix, no AI
  attribution trailer of any kind — `hooks/commit-msg` refuses `Claude-Session:` too.
- **Pushing**: the pre-push hook runs the test suite (minutes); push with `--no-verify` and let CI
  be the gate, as the spec commit was.
- **Never edit a file while a harness run's cheap-guard phase reads the tree.**
- **English only** in everything written; French only in « guillemets » quoting the operator.
- **Names in full** (`docs/reference/code-naming.md`): no `cfg`, `msg`, `dir` as a bare word.
- **The scratch directory**: every shell in every phase starts with
  `SCRATCH=/private/tmp/claude-501/-Users-izno-dev-PersonalScraper/b5f0d053-c6b6-4635-9e16-446a78dab9f7/scratchpad`
  then `SHA=$(cat "$SCRATCH/sha.txt")` — shells do not persist between steps.
- **The `@sha`**: one value for the whole wave, `SHA=$(git rev-parse --short=8 origin/main)` taken in
  phase 0 after the merge of `origin/main`, exported in every shell that rewrites a citation.
- **Version**: patch bump in phase 5 (`personalscraper/__init__.py`), and the `no-version-bump`
  label REMOVED from PR #539 in phase 6 — a guard changes.

## Phases

| Phase | File                            | Lands                                                                                                                                         | Green proof                                              |
| ----- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 0     | `phase-00-the-window.md`        | the branch merged with `origin/main`, `SHA` fixed, counts refreshed                                                                           | `git status` clean, guards green before anything moves   |
| 1     | `phase-01-the-guard.md`         | `@sha` citations resolved by arm 1; arms 2 and 3 written and tested, not wired                                                                | `pytest tests/scripts/test_check_docs_cited_paths.py`    |
| 2     | `phase-02-the-present-moves.md` | 23 files into `docs/production/`, every code-side end, the manifest, arm 3 wired                                                              | `make check` (design-gaps pair, cli-coverage, the guard) |
| 3     | `phase-03-the-frame-model.md`   | `frame-model.md`, `frame-survey.md` in `docs/reference/`, citations follow                                                                    | the guard, `check-intent-map.py`                         |
| 4     | `phase-04-history-leaves.md`    | `docs/archive/`, `docs/superpowers/`, `docs/analysis/`, L10-ter's residue, `tech-debt-2` deleted; citations `@sha`; arm 2 wired               | the guard, `git ls-files` counts                         |
| 5     | `phase-05-the-directives.md`    | `CLAUDE.md`, the plan's § 5, the lifecycle, `IMPLEMENTATION.md`, the office, `README.md`, `.gitignore`, CI filters, the register, the version | `make check`, `run.sh --contracts`                       |
| 6     | `phase-06-the-proofs.md`        | three mutations, three `git show`, the diff re-read, the pull request ready                                                                   | CI green, PR body carries the evidence                   |

Phases run in this order; 2 before 4 because the archived `api-unify` design must be MOVED out of
`docs/archive/` before the tree is removed, and 3 before 4 because `MODEL.md` and `SURVEY.md` leave
`docs/features/maquette-l10-ter/` before the rest of that folder is deleted.
