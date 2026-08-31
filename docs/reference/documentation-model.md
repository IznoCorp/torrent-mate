# The documentation model — what a document may describe

**What this file is.** The rule that says, for every document in this repository, which version
of the product it is allowed to describe, where it lives because of that, in which language it is
written, and what happens to it on the day the next version reaches production. It was dictated
by the operator on 2026-08-31, at the close of a reflection that changed nothing before it was
finished, and the move that first applied it is `docs/features/docs-cleanup/DESIGN.md` (a wave's
design; once merged it is read from history, § 2 says how).

**Why it exists.** The maquette is the NEXT version of the application and it REPLACES the shipped
one (`docs/reference/frontend-architecture.md` § 1, `docs/reference/product-intent.md` §15). The
documentation had not followed that decision: 1 254 markdown files, 302 000 lines, three quarters
of them a frozen archive, and — the part that misleads — documents describing the shipped
production and documents describing the version that replaces it sitting in the same directory
under the same name, with nothing to tell a reader which one may be taken as true. An agent opens
the repository in a fresh session knowing nothing else; a document it can read as current, and is
not, costs it a wrong directive. This file makes the distinction structural so no reader has to
make it.

---

## 1. Three families, three fates

Every document belongs to exactly one family. The family decides its home; the home is the
family's only marker — no banner, no status line, no naming convention has to be remembered.

| Family          | What it describes                                                                                                                          | Home                                                                                             | Fate                                                                                |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| **The future**  | The next version only — its intent, its plan, its model, what it asks of the backend, the register of what stands in its way               | `docs/reference/`, and at the root `BUGS.md`, `BUGS-CLOSED.md`, `IMPLEMENTATION.md`, `CLAUDE.md` | Lives. Written in English — one named exception, § 3                                |
| **Knowledge**   | What is true whatever the version: what an external API does and the traps it has cost, the method (how a feature is built, tested, named) | `docs/reference/`, its `_samples/`, and `CHANGELOG.md` at the root                               | Lives. English                                                                      |
| **The present** | The version in production, until the day it is replaced                                                                                    | `docs/production/` — and nowhere else                                                            | Frozen. Receives no new file. Deleted in the switchover commit, with `frontend/src` |

**The criterion for the present is a question, not a list**: « if the version in production were
switched off tomorrow, would this sentence still be true? » A document whose sentences are mostly
about the shipped engine's modules, its web routes, its CLI, its deploy topology or its operator
manual is the present. A document whose sentences are about TMDB's pagination or how a golden
file is regenerated is knowledge, even when it was written for the present. The first application
of the criterion, file by file, is `docs/features/docs-cleanup/DESIGN.md` § 2; a later reader who
finds a file on the wrong side moves it, under § 7.1 of the plan, and says why.

**The present is frozen, and « frozen » means this.** No file is born under `docs/production/`
— a guard holds a manifest of the directory and refuses an addition (§ 5). No section is added to
a file there. What IS allowed is the correction of a sentence that has become false, because a
document that lies is worse than a document that is stale; the correction is one line, it is
named as a correction in the pull request, and it adds nothing. The production documents are not
translated, restyled or re-indexed: the work would die with them.

**The register's memory is not the present.** `BUGS-CLOSED.md` holds the bodies of the closed
entries of `BUGS.md`, and the register's own rule reads « a closed bug whose history has been
erased is a bug that will be made again ». It belongs to the future family with the register it
serves, and `check-bug-register.py --next` reads it to take the next free number. It stays.

---

## 2. Git is the history — a path is cited with the commit that holds it

There is no archive directory. What a merged wave wrote — its design, its plan, its report — is
not moved anywhere: it is deleted from the tree at the post-merge gesture, and read from history
by anyone who needs it. The repository's history IS the archive; a second copy of it in the tree
was 224 000 lines a reader could open by mistake.

**The citation form.** A path that no longer exists in the tree is cited with the commit that
held it, the two joined by `@`:

```
`docs/archive/features/maquette-l07/DESIGN.md@5322c2fa`
```

and it is read with `git show 5322c2fa:docs/archive/features/maquette-l07/DESIGN.md`. Any commit
that holds the file is a valid anchor — the citation does not have to name the LAST one, only a
true one — so **the sha written is the sha of `origin/main` at the moment the citation is
written**, and it never needs updating. The abbreviated form is eight characters, which this
repository's history disambiguates; the guard resolves it and refuses one that has become
ambiguous.

**The universal key.** Every path that ever lived under `docs/archive/`, `docs/superpowers/` and
`docs/analysis/` existed at the commit the move was cut from, named in
`docs/features/docs-cleanup/DESIGN.md` § 4 and in the move's own pull request. A reader who meets
a bare `docs/archive/…` path in a document that was not rewritten — a production document, an old
commit message, a review comment — reads it with `git show <that sha>:<path>`, and when in doubt,
`git log --all --oneline -- <path>` lists every commit that touched it.

**What is cited by `@sha`, and what is not.** A FILE is. A directory is not — `docs/archive/`
cited as a folder names a set, and the file in it that matters is cited on its own line, as the
guard already required. A path that still exists in the tree is cited bare, as before, and the
guard refuses a bare citation the tree does not hold and an `@sha` citation the named commit does
not hold — the two halves of the same rule.

**What this changes in the method.** The plan's post-merge gesture number four
(`docs/reference/frontend-architecture.md` § 5) no longer archives: it deletes
`docs/features/<codename>/` and rewrites every citation of it to the `@sha` form in the same
step. `docs/reference/feature-lifecycle.md` § 6, which asked for a « superseded » banner on an
archived design, has no subject: a superseded design is history, and the reference document is
the only authority on the present. The two exceptions the plan had carved out of the archive
gesture — the frame's model and survey, kept live under a wave's folder — are dissolved by moving
those two files where they belonged, `docs/reference/frame-model.md` and
`docs/reference/frame-survey.md`.

---

## 3. Language

Everything that lives is written in English: the future, the knowledge, the code, the register,
the state, this file. **One exception, named**: `docs/reference/product-intent.md`, the
constitution, is French, because it is the operator's dictated word and a translation would move a
word the operator chose — « par-dessus » cost two pull requests to get right in its own language.
It stays French and is amended only by the operator.

The present is not translated; its language is the language it was written in, and it is
indifferent, because nothing is meant to read it as current. The rule that operator-facing
documents are written in French does not survive the switchover: the next version's operator
documents — its `README.md`, its manual — are born in English.

The root `README.md` is the repository's landing page and it describes the version in production.
It keeps its language and receives one line at the top saying so and pointing at the constitution
— a signpost, not a rewrite.

---

## 4. A wave's documents

`docs/features/<codename>/` is a wave's workspace: its brief, its design, its plan, its report.
It lives while the wave is open. At the post-merge gesture it is deleted, and everything that
must still be read from it is cited by `@sha`. A design that has become a durable reference — a
model, a survey, a rule — does not stay in the wave's folder as an exception: it is moved to
`docs/reference/` under a name that says what it is, in the wave's own pull request or in the
post-merge gesture, and the citations move with it.

`docs/superpowers/` — the brainstorming skill's default location for specs and plans — does not
exist in this repository. A spec is a wave's design and lives with the wave.

---

## 5. The guard, and where it runs

`scripts/check-docs-cited-paths.py` holds this model. Its arms:

1. **Cited paths** — every backticked repository path in the directives (`IMPLEMENTATION.md`,
   `BUGS.md`, `CLAUDE.md`, the plan, the office, the clause map) answers `git ls-files`; an
   `@sha` citation answers `git cat-file -e <sha>:<path>`; the empty read is refused.
2. **No history in the tree** — no tracked path under `docs/archive/`, `docs/superpowers/` or
   `docs/analysis/`. A tool that still archives (the operator's `implement:*` skills did) would
   recreate the directory in silence; this arm is what says so.
3. **No birth in production** — `git ls-files docs/production` equals the manifest
   `scripts/production-docs-manifest.json`. A file removed from production is allowed (the
   manifest shrinks); a file added is refused. The manifest is the same mechanism as the French
   exemption baseline: a number nobody compares is a number nobody reads.

It runs where the other cheap guards run: `frontend/maquette/harness/run.sh --contracts`,
`make check`, and the CI `maquette` filter. The design-gaps job keeps reading the anchors of the
production documents that tests contract against (`docs/**` stays in the `docs` filter), because a
heading renamed in a frozen document still flips a test's verdict.

---

## 6. The switchover

The day the maquette replaces `frontend/src`, the same commit deletes `docs/production/`, the
manifest and arm 3. That is the whole mechanism, and it is one sentence because everything was
ranged for it in advance.

**What the backend brief may take from production first.** Whether the engine is adapted to the
frozen interface or rebuilt from its parts is the backend study's question, not this file's
(operator, 2026-08-31). If the study keeps a part of the engine, the documents describing that
part are **promoted** out of `docs/production/` into `docs/reference/` — rewritten as knowledge of
the version that keeps them, in English, under the brief. Promotion is a move OUT of production;
it is never a birth in it, and the manifest shrinks with each one.
