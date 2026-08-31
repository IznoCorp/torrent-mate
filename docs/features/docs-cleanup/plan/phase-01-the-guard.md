# Phase 1 — The guard

**Delivers:** `scripts/check-docs-cited-paths.py` resolves `` `path@sha` `` citations (arm 1
extended), and holds two new arms — no history tree in the index (arm 2), production equals its
manifest (arm 3) — each written test-first. Arms 2 and 3 are NOT wired into `main()` here: arm 2
would be red while `docs/archive/` is still tracked, arm 3 while `docs/production/` is empty. Phase
2 wires arm 3, phase 4 wires arm 2.

**Files:**

- Modify: `scripts/check-docs-cited-paths.py`
- Test: `tests/scripts/test_check_docs_cited_paths.py`

**Interfaces:**

- Consumes: the existing `tracked_paths() -> set[str] | None`, `cited_paths(directive) -> list[str]`,
  `arm_cited_paths() -> int`, `DIRECTIVES`, `ROOT`, `CITED_PATH`.
- Produces, for phases 2 and 4 to wire and for the tests to patch:
  - `CITED_HISTORY: re.Pattern` — matches `` `<path>@<sha>` ``.
  - `cited_history(directive: Path) -> list[tuple[str, str]]` — `(path, sha)` pairs, each once.
  - `held_by_commit(sha: str, path: str) -> bool | None` — True/False, None when `sha` is not one
    unambiguous commit.
  - `HISTORY_TREES = ("docs/archive/", "docs/superpowers/", "docs/analysis/")`.
  - `arm_no_history_in_tree() -> int`.
  - `PRODUCTION = ROOT / "docs" / "production"`, `MANIFEST = ROOT / "scripts" / "production-docs-manifest.json"`.
  - `manifest_paths() -> list[str] | None`, `arm_production_manifest() -> int`.
  - The manifest's shape: `{"why": "<one sentence>", "files": ["docs/production/…", …]}`, `files`
    sorted.

---

### Task 1.1: Arm 1 resolves `@sha` citations

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_check_docs_cited_paths.py`. The helper `_run` is extended to accept
the verdicts `held_by_commit` should return, keyed by `(sha, path)`.

```python
def _run_history(module, directive: Path, tracked: set[str] | None, verdicts: dict) -> int:
    """Like `_run`, with `held_by_commit` answering from `verdicts` — None for an unknown commit."""
    with (
        patch.object(module, "DIRECTIVES", (directive,)),
        patch.object(module, "ROOT", directive.parent),
        patch.object(module, "tracked_paths", return_value=tracked),
        patch.object(module, "held_by_commit", side_effect=lambda sha, path: verdicts.get((sha, path))),
    ):
        return module.arm_cited_paths()


def test_a_history_citation_the_commit_holds_is_clean(tmp_path: Path) -> None:
    """`docs/archive/x/DESIGN.md@5322c2fa` — the commit holds the path → 0, and the read is not empty."""
    module = _load()
    directive = _directive(tmp_path, "Design: `docs/archive/features/x/DESIGN.md@5322c2fa`.\n")
    assert module.cited_history(directive) == [("docs/archive/features/x/DESIGN.md", "5322c2fa")]
    assert module.cited_paths(directive) == []
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/features/x/DESIGN.md"): True}) == 0


def test_a_history_citation_the_commit_does_not_hold_is_refused(tmp_path: Path, capsys) -> None:
    """The sha is a commit, the path was never in it → refused, naming the citation."""
    module = _load()
    directive = _directive(tmp_path, "See `docs/archive/features/x/DESIGN.md@5322c2fa`.\n")
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/features/x/DESIGN.md"): False}) == 1
    assert "does not hold" in capsys.readouterr().err


def test_a_history_citation_with_an_unknown_commit_is_refused(tmp_path: Path, capsys) -> None:
    """A sha that is not one unambiguous commit → refused, not passed."""
    module = _load()
    directive = _directive(tmp_path, "See `docs/archive/features/x/DESIGN.md@abcdef12`.\n")
    assert _run_history(module, directive, set(), {}) == 1
    assert "not one commit" in capsys.readouterr().err


def test_history_citations_count_as_a_read(tmp_path: Path) -> None:
    """A directive whose only citations are `@sha` ones is read, not empty."""
    module = _load()
    directive = _directive(tmp_path, "Only `docs/archive/a.md@5322c2fa` here.\n")
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/a.md"): True}) == 0


def test_a_bare_citation_still_needs_the_index(tmp_path: Path) -> None:
    """The `@sha` form does not loosen the bare form: an untracked bare path is still refused."""
    module = _load()
    directive = _directive(tmp_path, "`docs/archive/a.md@5322c2fa` and `docs/x/b.md`.\n")
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/a.md"): True}) == 1
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd /Users/izno/dev/PersonalScraper-steward && python3 -m pytest tests/scripts/test_check_docs_cited_paths.py -q 2>&1 | tail -3`
Expected: 5 failed (`AttributeError: … has no attribute 'cited_history'` / `held_by_commit`), 6 passed.

- [ ] **Step 3: Implement**

In `scripts/check-docs-cited-paths.py`, after `CITED_PATH`:

```python
# The same path, cited WITH the commit that holds it: `docs/archive/x/DESIGN.md@5322c2fa`.
# `docs/reference/documentation-model.md` § 2 — git is the history, and a path that left the
# tree is cited by a commit that held it, never by an archive file.
CITED_HISTORY = re.compile(
    r"`((?:docs|scripts|tests|frontend|personalscraper|\.github)/"
    r"[A-Za-z0-9_./-]+\.(?:md|json|json5|py|txt|sh|mjs|ts|tsx|js|css|html|yml|yaml))"
    r"@([0-9a-f]{7,40})`"
)


def cited_history(directive: Path) -> list[tuple[str, str]]:
    """The distinct `(path, sha)` pairs a directive cites in the `@sha` form.

    Args:
        directive: One of `DIRECTIVES`.

    Returns:
        The pairs, in order of first appearance, each once.
    """
    seen: dict[tuple[str, str], None] = {}
    for path, sha in CITED_HISTORY.findall(directive.read_text(encoding="utf-8")):
        seen.setdefault((path, sha), None)
    return list(seen)


def held_by_commit(sha: str, path: str) -> bool | None:
    """Says whether one unambiguous commit holds a path.

    Args:
        sha: A commit, abbreviated or full.
        path: A repository-relative path.

    Returns:
        True when `git cat-file -e sha:path` succeeds, False when the commit exists and
        the path is not in it, None when `sha` does not name exactly one commit.
    """
    resolved = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],
                              capture_output=True, text=True, check=False, cwd=ROOT)
    if resolved.returncode != 0:
        return None
    probe = subprocess.run(["git", "cat-file", "-e", f"{sha}:{path}"],
                           capture_output=True, text=True, check=False, cwd=ROOT)
    return probe.returncode == 0
```

Then in `arm_cited_paths()`, replace the body of the `for directive in DIRECTIVES:` loop from
`cited = cited_paths(directive)` to the end with:

```python
        cited = cited_paths(directive)
        history = cited_history(directive)
        missing = [path for path in cited if path not in tracked]
        print(f"check-docs-cited-paths: {name} cites {len(cited)} path(s) and "
              f"{len(history)} by commit, {len(missing)} not in `git ls-files`")
        if not cited and not history:
            print(f"    {name}: zero citations read — the pattern matched "
                  f"nothing, and nothing is not clean", file=sys.stderr)
            violations += 1
        for path in missing:
            print(f"    {name}: cites `{path}`, which no commit holds — "
                  f"either the file lives on one disk only (B-251: `git add -f` "
                  f"it, `docs/` is ignored globally) or it moved and the "
                  f"citation did not", file=sys.stderr)
            violations += 1
        for path, sha in history:
            verdict = held_by_commit(sha, path)
            if verdict is None:
                print(f"    {name}: cites `{path}@{sha}`, and `{sha}` is not one "
                      f"commit of this repository — abbreviated too short, or never "
                      f"here", file=sys.stderr)
                violations += 1
            elif not verdict:
                print(f"    {name}: cites `{path}@{sha}`, and that commit does not "
                      f"hold the path — cite a commit that did (`git log --all "
                      f"--oneline -- {path}`)", file=sys.stderr)
                violations += 1
```

Update the module docstring's « WHAT IT READS » paragraph with one sentence: « A path cited as
`` `path@sha` `` is read from the commit instead: it must name exactly one commit, and that commit
must hold the path (`documentation-model.md` § 2). »

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/scripts/test_check_docs_cited_paths.py -q 2>&1 | tail -2`
Expected: 11 passed.

- [ ] **Step 5: Run the guard on the real tree**

Run: `python3 scripts/check-docs-cited-paths.py | tail -1`
Expected: `check-docs-cited-paths: clean` (no directive cites `@sha` yet; the bare arm is unchanged).

- [ ] **Step 6: Commit**

```bash
git add scripts/check-docs-cited-paths.py tests/scripts/test_check_docs_cited_paths.py
git commit -m "feat(docs-cleanup): the cited-paths guard reads a path cited with the commit that holds it"
```

### Task 1.2: Arm 2 — no history tree in the index (written, not wired)

- [ ] **Step 1: Write the failing tests**

```python
def _run_arm(module, arm: str, tracked: set[str] | None) -> int:
    with patch.object(module, "tracked_paths", return_value=tracked):
        return getattr(module, arm)()


def test_a_tracked_path_under_a_history_tree_is_refused(capsys) -> None:
    """`docs/archive/x.md` back in the index — a tool that still archives — is named and refused."""
    module = _load()
    assert _run_arm(module, "arm_no_history_in_tree", {"docs/archive/x.md", "docs/reference/a.md"}) == 1
    assert "docs/archive/x.md" in capsys.readouterr().err


def test_each_history_tree_is_held() -> None:
    module = _load()
    tracked = {"docs/archive/a.md", "docs/superpowers/b.md", "docs/analysis/c.md"}
    assert _run_arm(module, "arm_no_history_in_tree", tracked) == 3


def test_an_index_without_history_trees_is_clean() -> None:
    module = _load()
    assert _run_arm(module, "arm_no_history_in_tree", {"docs/reference/a.md", "docs/production/b.md"}) == 0


def test_history_arm_refuses_when_git_is_unreachable() -> None:
    module = _load()
    assert _run_arm(module, "arm_no_history_in_tree", None) == 1
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m pytest tests/scripts/test_check_docs_cited_paths.py -q -k history_tree 2>&1 | tail -2`
Expected: 4 failed (`AttributeError: … 'arm_no_history_in_tree'`).

- [ ] **Step 3: Implement**

After `held_by_commit` in the guard:

```python
# The trees that are history and live in git alone (`documentation-model.md` § 2). A tracked
# path under one of them is a tool that still archives — the operator's `implement:*` skills
# did — and the tree says no before the habit is unlearned.
HISTORY_TREES = ("docs/archive/", "docs/superpowers/", "docs/analysis/")


def arm_no_history_in_tree() -> int:
    """Refuse a tracked path under a history tree.

    Returns:
        The number of violations.
    """
    tracked = tracked_paths()
    if tracked is None:
        print("check-docs-cited-paths[history]: `git ls-files` failed — refused rather "
              "than passed", file=sys.stderr)
        return 1
    reborn = sorted(path for path in tracked if path.startswith(HISTORY_TREES))
    for path in reborn:
        print(f"    {path}: tracked under a history tree — history lives in git alone; "
              f"cite the commit (`path@sha`), do not re-add the file", file=sys.stderr)
    print(f"check-docs-cited-paths[history]: {len(reborn)} tracked path(s) under "
          f"{', '.join(tree.rstrip('/') for tree in HISTORY_TREES)}")
    return len(reborn)
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/scripts/test_check_docs_cited_paths.py -q 2>&1 | tail -2`
Expected: 15 passed.

- [ ] **Step 5: Commit** (the arm is not called by `main()` yet — phase 4 wires it)

```bash
git add scripts/check-docs-cited-paths.py tests/scripts/test_check_docs_cited_paths.py
git commit -m "feat(docs-cleanup): the guard's history arm — a tracked path under docs/archive is refused (unwired until history leaves)"
```

### Task 1.3: Arm 3 — production equals its manifest (written, not wired)

- [ ] **Step 1: Write the failing tests**

```python
import json


def _manifest(tmp_path: Path, files: list[str] | str) -> Path:
    path = tmp_path / "production-docs-manifest.json"
    body = files if isinstance(files, str) else json.dumps({"why": "test", "files": files})
    path.write_text(body, encoding="utf-8")
    return path


def _run_manifest(module, manifest: Path, tracked: set[str] | None) -> int:
    with (
        patch.object(module, "MANIFEST", manifest),
        patch.object(module, "tracked_paths", return_value=tracked),
    ):
        return module.arm_production_manifest()


def test_production_matching_the_manifest_is_clean(tmp_path: Path) -> None:
    module = _load()
    manifest = _manifest(tmp_path, ["docs/production/a.md", "docs/production/b.md"])
    assert _run_manifest(module, manifest, {"docs/production/a.md", "docs/production/b.md", "docs/reference/z.md"}) == 0


def test_a_birth_in_production_is_refused(tmp_path: Path, capsys) -> None:
    """A file the manifest does not name — production receives no new file."""
    module = _load()
    manifest = _manifest(tmp_path, ["docs/production/a.md"])
    assert _run_manifest(module, manifest, {"docs/production/a.md", "docs/production/new.md"}) == 1
    assert "docs/production/new.md" in capsys.readouterr().err


def test_a_manifest_entry_the_tree_lost_is_refused(tmp_path: Path, capsys) -> None:
    """A file promoted or deleted shrinks the manifest in the same change, or the manifest lies."""
    module = _load()
    manifest = _manifest(tmp_path, ["docs/production/a.md", "docs/production/gone.md"])
    assert _run_manifest(module, manifest, {"docs/production/a.md"}) == 1
    assert "docs/production/gone.md" in capsys.readouterr().err


def test_an_empty_production_is_refused(tmp_path: Path) -> None:
    """Zero files is the switchover, and the switchover deletes this arm; until then it is a misread."""
    module = _load()
    manifest = _manifest(tmp_path, [])
    assert _run_manifest(module, manifest, {"docs/reference/z.md"}) == 1


def test_an_unreadable_manifest_is_refused(tmp_path: Path) -> None:
    module = _load()
    assert _run_manifest(module, _manifest(tmp_path, "{not json"), {"docs/production/a.md"}) == 1
    assert _run_manifest(module, tmp_path / "absent.json", {"docs/production/a.md"}) == 1
    assert _run_manifest(module, _manifest(tmp_path, '{"files": "a"}'), {"docs/production/a.md"}) == 1
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m pytest tests/scripts/test_check_docs_cited_paths.py -q -k manifest 2>&1 | tail -2`
Expected: 5 failed (`AttributeError: … 'MANIFEST'`).

- [ ] **Step 3: Implement**

Add `import json` to the imports. After `arm_no_history_in_tree`:

```python
# The present — the version in production — is frozen: it receives no new file
# (`documentation-model.md` § 1). The manifest pins the directory's exact contents; a file
# added is a birth, a file missing is a manifest that lies, and both are refused. A number
# nobody compares is a number nobody reads, which is why this is a file and not a count.
PRODUCTION = ROOT / "docs" / "production"
MANIFEST = ROOT / "scripts" / "production-docs-manifest.json"


def manifest_paths() -> list[str] | None:
    """The paths the production manifest names, or None when it cannot be read.

    Returns:
        The `files` list, or None for a missing, malformed or mis-shaped manifest.
    """
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        return None
    return files


def arm_production_manifest() -> int:
    """Refuse a production directory that differs from its manifest, either way.

    Returns:
        The number of violations.
    """
    tracked = tracked_paths()
    if tracked is None:
        print("check-docs-cited-paths[production]: `git ls-files` failed — refused rather "
              "than passed", file=sys.stderr)
        return 1
    manifest = manifest_paths()
    if manifest is None:
        print(f"check-docs-cited-paths[production]: {MANIFEST.relative_to(ROOT).as_posix()} "
              f"is missing or not `{{\"why\": …, \"files\": [\"docs/production/…\"]}}` — "
              f"refused", file=sys.stderr)
        return 1
    prefix = PRODUCTION.relative_to(ROOT).as_posix() + "/"
    actual = sorted(path for path in tracked if path.startswith(prefix))
    born = sorted(set(actual) - set(manifest))
    gone = sorted(set(manifest) - set(actual))
    for path in born:
        print(f"    {path}: not in the manifest — production receives no new file; a "
              f"document about the version in production was frozen on 2026-08-31, and a "
              f"document about the next version lives in docs/reference/", file=sys.stderr)
    for path in gone:
        print(f"    {path}: named by the manifest and not tracked — shrink the manifest in "
              f"the same change that removed the file", file=sys.stderr)
    violations = len(born) + len(gone)
    if not actual:
        print("    docs/production/ holds no tracked file — the switchover deletes this arm "
              "with the directory; until then an empty read is a misread", file=sys.stderr)
        violations += 1
    print(f"check-docs-cited-paths[production]: {len(actual)} file(s), manifest names "
          f"{len(manifest)}, {len(born)} born, {len(gone)} gone")
    return violations
```

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/scripts/test_check_docs_cited_paths.py -q 2>&1 | tail -2`
Expected: 20 passed.

- [ ] **Step 5: `ruff` and `mypy` on the two files**

Run: `ruff check scripts/check-docs-cited-paths.py tests/scripts/test_check_docs_cited_paths.py && mypy scripts/check-docs-cited-paths.py | tail -1`
Expected: no error.

- [ ] **Step 6: Commit** (unwired — phase 2 wires it with the manifest)

```bash
git add scripts/check-docs-cited-paths.py tests/scripts/test_check_docs_cited_paths.py
git commit -m "feat(docs-cleanup): the guard's production arm — the directory equals its manifest, both ways (unwired until the present moves)"
```

### Task 1.4: The guard's docstring names its three arms

- [ ] **Step 1: Rewrite the module docstring's first paragraph and add an arms list**

Replace the sentence « Refuses a directive that cites a repository path the tree does not hold. »
with:

```
Holds the documentation model (`docs/reference/documentation-model.md`) — three arms:

  1. Cited paths: every backticked repository path in the directives answers
     `git ls-files`; a path cited as `path@sha` is held by that commit; the
     empty read is refused.
  2. No history in the tree: nothing tracked under docs/archive/,
     docs/superpowers/, docs/analysis/ — git is the history.
  3. No birth in production: `git ls-files docs/production` equals
     `scripts/production-docs-manifest.json`.
```

Keep every paragraph that follows (B-251, what it reads, what it does not read) — and delete
the one sentence « `docs/archive/` is frozen history and cites what existed then, on purpose »,
which has no subject once arm 2 exists.

- [ ] **Step 2: Commit**

```bash
git add scripts/check-docs-cited-paths.py
git commit -m "docs(docs-cleanup): the guard's docstring names its three arms"
```
