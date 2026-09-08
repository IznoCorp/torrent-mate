# ci-draft — CI does not run while a pull request is a draft

**Dictated by the operator, 2026-09-08:** « On va faire une PR pour ne pas exécuter la CI quand la PR
est en draft, on l'exécute qu'à la sortie de draft. Afin d'économiser du temps de CI. »

That sentence is the whole objective. What follows is what the repository already knows about its own
CI, which changes HOW it must be done — read it before touching the file.

## What you read before acting

1. `.github/workflows/ci.yml` **whole**, and in particular the comment block above `on:` and above the
   `changes` job. Both were written after real incidents and both bear on this change.
2. `tests/scripts/test_ci_filter_covers_the_guards.py` — the CI file has test coverage, and a guard
   whose subject no filter names runs in no job. Your change must keep it green and gains its own.
3. `CLAUDE.md` § Commit Convention (the version bump per PR and the `no-version-bump` label) and
   § Critical Rules.
4. `BUGS.md`'s register conventions (rule 3: an entry closes with the reading that establishes it).

## The trap, measured before this brief was written

- **`ready_for_review` is in NO trigger of this repository** (`grep -n ready_for_review
  .github/workflows/*.yml` returns nothing). The trigger's types are
  `[opened, synchronize, reopened, labeled, unlabeled]`. So a naive « skip when draft » would mean the
  pull request leaving draft dispatches NOTHING and the checks never run at all. **Adding
  `ready_for_review` to the types is half of this change, not an option.**
- **No `paths-ignore` at the trigger, deliberately**: the comment says a run that never starts leaves a
  required check « expected » for ever and the pull request stuck. The same reasoning decides the
  SHAPE of this change: gate at the JOB level with an `if`, never by removing the trigger. A skipped
  job reports a real conclusion (`skipped`, which required checks accept) and costs no runner minute,
  which is exactly the saving the operator asked for; a run that never exists reports nothing.
- **`labeled` / `unlabeled` are in the types on purpose** (#488): a label added after `opened` changes
  nothing until a new event re-dispatches. That machinery is what makes the escape hatch below work
  without any new trigger.

## Scope — what you deliver

1. **`ready_for_review` added to the trigger's types**, with a comment saying why it is not optional.
2. **Every job carries the draft condition**, at job level:
   `if: github.event.pull_request.draft == false || contains(github.event.pull_request.labels.*.name, 'run-ci-on-draft')`
   — the label is the ESCAPE HATCH, approved by the steward and told to the operator: a wave that needs
   a green reading before its merge day adds the label and the run dispatches (the `labeled` type is
   already there). Without the label a draft costs nothing. Name every job, including `changes`, and say
   in a comment that a job added later without the condition silently re-enables draft runs — which is
   what your new test refuses.
3. **A test that bites**, beside `test_ci_filter_covers_the_guards.py`: it parses `ci.yml` and asserts
   (a) every job carries the draft condition, (b) `ready_for_review` is among the trigger's types,
   (c) the label named in the condition is one single spelling. **Seen RED first**: remove the condition
   from one job, watch it name that job, restore. Show both readings in your report.
4. **The directives change in the same move, because a decision changed.** Every sentence in the
   repository that says a draft pull request is how CI is read must be corrected — start from
   `grep -rn "draft" --include='*.md' . | grep -i ci`, and expect at least `CLAUDE.md`,
   `docs/reference/frontend-steward.md`, `docs/reference/frontend-architecture.md` and
   `IMPLEMENTATION.md`'s « In flight » row, which explains that #572 opens as a draft precisely so CI
   can be read. The new sentence: **a draft runs nothing; CI is read after `ready_for_review`, or on a
   draft by adding the `run-ci-on-draft` label**. Do not rewrite history in those files; correct the
   sentence and say it changed on 2026-09-08 by the operator's decision.
5. **One register entry** recording what this closes and the escape hatch, with the readings.
6. **The version bumped to `0.98.77`** — `main` carries 0.98.74, the L21 branch 0.98.75 and the
   desktop-frame branch 0.98.76, so 0.98.77 is past all three whichever merges first. This PR touches
   `.github/workflows/`, so it is NOT a `no-version-bump` PR.

## Non-goals

- No change to what any job DOES, to the paths filter, to the concurrency group, or to
  `gitleaks-full.yml`.
- No change to the branch protection or the required-check list (the operator's, and the steward's to
  relay).
- Nothing in `personalscraper/`, `frontend/`, `scripts/` beyond the new test.
- **If you believe something outside this list is needed, STOP and ask the orchestrator first.**

## The consequence you must state in the pull request body

Two pull requests are in flight as drafts (#572 L21, #576 maquette-desktop-frame). Once this merges,
their CI stops dispatching until they leave draft or carry the label. Say so in the body, plainly,
so whoever reads a « zero check-runs » on them knows which of the two reasons it is — this repository
already learned that zero check-runs means « never started », and it now has a SECOND cause.

## How you deliver

Branch `chore/ci-draft`, worktree `/Users/izno/dev/worktrees/wave-ci-draft`, a DRAFT pull request at
your first push (and note the irony in your report: this one's own CI runs because it is opened before
its change is merged). English title and body. The gate before the pull request: `make lint`,
`make check` (0 failed, 0 errors) and your new test seen red then green. **Every push is a heavy run**
(the pre-push hook runs `pytest -n auto`): wrap it —
`PYTEST_XDIST_AUTO_NUM_WORKERS=3 HEAVY_FREE_FLOOR_MB=3072 sh scripts/heavy.sh ci-draft <command>` —
output to a file, never piped through `tail`, and a push is landed when `git ls-remote --heads origin
chore/ci-draft` shows the local sha, never when a wrapper exits 0. The harness is NOT yours and you
need none: another wave holds it. Then report to the steward; the merge word is the operator's.
