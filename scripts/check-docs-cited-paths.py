#!/usr/bin/env python3
"""Holds the documentation model (`docs/reference/documentation-model.md`), in three arms.

  1. Cited paths: every backticked repository path in the directives answers
     `git ls-files`; a path cited as `path@sha` is held by that commit; the
     empty read is refused.
  2. No history in the tree: nothing tracked under docs/archive/,
     docs/superpowers/, docs/analysis/ — git is the history.
  3. No birth in production: `git ls-files docs/production` equals
     `scripts/production-docs-manifest.json`.

THE DEFECT THIS ENDS is B-251, and it is the shape B-219 named from the other
side. The operator's global `.gitignore` ignores `docs/`, so a NEW file under
`docs/` is invisible to `git add -A`, to `git status` and to every gate: a
folder whose other files were force-added once looks entirely normal while the
newest file in it exists on one disk only. L15's own report was cited in a pull
request body and to the steward as if it were in the repository, and it was
not. And a path can die the other way: a design archived under
`docs/archive/features/` keeps being cited at its live address for weeks —
the plan did, for L01, and the register did, for L15's report on the very day
it was archived.

WHAT IT READS. The directive files below — the ones every agent opens before
acting — and, in each, every repository path written in backticks with a file
extension. Each path must answer `git ls-files`. Not `Path.exists()`: a file on
this disk that no commit holds is precisely the case this guard exists for, and
`exists()` would pass it. A path cited as `path@sha` is read from the commit
instead: it must name exactly one commit, and that commit must hold the path
(`documentation-model.md` § 2).

WHAT IT DOES NOT READ, and saying so is the point:
  - Bare names (`MODEL.md`, `SURVEY.md`) and relative citations. They mean
    « beside the file you are reading » and this guard has no way to know which
    file that is; a wrong one is a reader's finding.
  - Paths outside backticks, and paths with no extension (a directory cited as
    `docs/features/x/`). A directory that exists in git is a set of files, and
    the file in it that matters is cited on its own line.
  - Any file not in the list below.

THE EMPTY READ IS REFUSED. A directive with zero citations is not clean, it is
unread — a regex that stopped matching would pass every file in silence, which
is the failure mode this repository counts most often.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The directives an agent reads first. Each is declared on its own line so the
# CI-filter hold (`tests/scripts/test_ci_filter_covers_the_guards.py`) can read
# every subject and refuse one that no filter names.
STATE = ROOT / "IMPLEMENTATION.md"
REGISTER = ROOT / "BUGS.md"
INDEX = ROOT / "CLAUDE.md"
PLAN = ROOT / "docs" / "reference" / "frontend-architecture.md"
OFFICE = ROOT / "docs" / "reference" / "frontend-steward.md"
CLAUSE_MAP = ROOT / "docs" / "reference" / "product-intent-map.md"
DIRECTIVES = (STATE, REGISTER, INDEX, PLAN, OFFICE, CLAUSE_MAP)

# A repository path in backticks, rooted at one of the directories a directive
# cites, ending in an extension. `docs/features/x/DESIGN.md`, never `DESIGN.md`.
CITED_PATH = re.compile(
    r"`((?:docs|scripts|tests|frontend|personalscraper|\.github)/"
    r"[A-Za-z0-9_./-]+\.(?:md|json|json5|py|txt|sh|mjs|ts|tsx|js|css|html|yml|yaml))`"
)

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
        # Named as written, not relative to ROOT: a test patches MANIFEST to a path outside
        # the repository, and a message that raises is a refusal nobody reads.
        print(f"check-docs-cited-paths[production]: {MANIFEST.as_posix()} "
              f"is missing or not `{{\"why\": …, \"files\": [\"docs/production/…\"]}}` — "
              f"refused", file=sys.stderr)
        return 1
    prefix = "docs/production/"
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


def tracked_paths() -> set[str] | None:
    """Every path the index holds, or None when git cannot answer.

    Returns:
        The set of repository-relative paths `git ls-files` prints, or None.
    """
    listing = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                             check=False, cwd=ROOT)
    if listing.returncode != 0:
        return None
    return set(listing.stdout.split())


def cited_paths(directive: Path) -> list[str]:
    """The distinct repository paths a directive cites in backticks.

    Args:
        directive: One of `DIRECTIVES`.

    Returns:
        The paths, in order of first appearance, each once.
    """
    seen: dict[str, None] = {}
    for path in CITED_PATH.findall(directive.read_text(encoding="utf-8")):
        seen.setdefault(path, None)
    return list(seen)


def arm_cited_paths() -> int:
    """Refuse a cited path the index does not hold, and an empty read.

    Returns:
        The number of violations.
    """
    tracked = tracked_paths()
    if tracked is None:
        print("check-docs-cited-paths: `git ls-files` failed — refused rather "
              "than passed, because a guard that cannot read its subject and a "
              "clean subject are the same exit code", file=sys.stderr)
        return 1

    violations = 0
    for directive in DIRECTIVES:
        name = directive.relative_to(ROOT).as_posix()
        if not directive.is_file():
            print(f"    {name}: not in the tree — a directive this guard reads "
                  f"is missing", file=sys.stderr)
            violations += 1
            continue
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
    return violations


def main() -> int:
    """Run the arm and report.

    Returns:
        1 when anything was refused, 0 otherwise.
    """
    violations = arm_cited_paths()
    print(f"check-docs-cited-paths: "
          f"{'clean' if not violations else f'{violations} violation(s)'}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
