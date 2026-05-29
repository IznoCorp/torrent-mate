# Phase 7 — Feature PR + review (auto-invoked)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the full local quality gate, push `feat/multi-filesystem`, open
the GitHub PR, poll CI to green, run the PR review toolkit (max 3 fix cycles),
and squash-merge.

This phase is auto-invoked by `/implement:feature-pr` followed by
`/implement:pr-review`. It is documented here for completeness and to record
the gate checklist that must pass before the PR is opened.

**NTFS invariant:** No code changes in this phase. The invariant is verified
by the gate below.

---

## Gate (prerequisites from Phase 6)

All six prior phases complete. Every AC in `ACCEPTANCE.md` passes.

Verify the full checklist before pushing:

```bash
# 1. Full quality gate
make lint && make test && make check
# expected: exit 0

# 2. All multifs tests pass (no real disks)
pytest -m multifs -q 2>&1 | tail -1
# expected: N passed (N>=8), 0 failed, 0 errors

# 3. NTFS flags unchanged
python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"
# expected: ['-a', '--no-perms', '--no-owner', '--no-group', '--no-times', '--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store', '--exclude=._*']

# 4. No literal --no-perms in _transfer.py
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py | wc -l | tr -d ' '
# expected: 0

# 5. Single mount shell-out
rg -c "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/_fs_probe.py
# expected: 1

# 6. Old call sites clean
rg -l "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py
# expected: empty stdout (exit 1)

# 7. Version bump (VERSION is the single source of truth; pyproject uses an attr)
cat VERSION
# expected: contains 0.18.0

# 8. CHANGELOG
grep -c "0.18.0" CHANGELOG.md
# expected: >=1

# 9. Package smoke
python -c "import personalscraper; print('ok')"
# expected: ok
```

---

## Files

No new files. All production and test changes are complete in Phases 1–6.

---

## Task 1 — Run `/implement:feature-pr`

- [ ] **Step 1.1: Invoke the feature-pr skill**

```
/implement:feature-pr
```

This skill:

1. Runs the full local gate (`make lint && make test && make check`).
2. Pushes `feat/multi-filesystem` to remote with `-u`.
3. Creates the GitHub PR with generated title/body.
4. Polls CI until green (or reports failure).

- [ ] **Step 1.2: Confirm CI is green before proceeding to review**

The PR URL is returned by the skill. Open it and verify:

- All CI checks pass.
- Branch is up to date with `main`.

---

## Task 2 — Run `/implement:pr-review`

- [ ] **Step 2.1: Invoke the PR review skill**

```
/implement:pr-review
```

This skill:

1. Runs `pr-review-toolkit` on the open PR.
2. Filters review comments against `DESIGN.md` and the phase plan.
3. Applies fixes in up to 3 cycles if needed.
4. Squash-merges when approved and CI is green.

- [ ] **Step 2.2: Post-merge verification**

After squash merge, confirm on `main`:

```bash
git checkout main && git pull
python -c "import personalscraper; print('ok')"
# expected: ok

make check
# expected: exit 0
```

---

## Post-merge AC re-exercise (mandatory before closing the feature)

Per `docs/reference/feature-lifecycle.md`, every AC in `ACCEPTANCE.md` must
be re-exercised on `main` after squash merge:

```bash
# Re-run all AC commands from docs/features/multi-filesystem/ACCEPTANCE.md
# on the merged main branch. Every command must produce its documented
# expected output.

# Quick subset:
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"
# expected: ntfs_macfuse

python -c "from personalscraper.indexer._fs_capability import capability_for; print(capability_for('unknown') == capability_for('ntfs_macfuse'))"
# expected: True

pytest -m multifs -q 2>&1 | tail -1
# expected: N passed, 0 failed

make check
# expected: exit 0
```

---

## Milestone commit (not applicable — this phase ends with the squash merge)

The squash merge commit on `main` is the milestone. Its message is generated
by `/implement:pr-review` and follows the Conventional Commits format with
`(multi-filesystem)` scope.
