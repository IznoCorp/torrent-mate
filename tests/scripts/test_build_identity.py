"""The design build's identity, held to what git accounts for (B-384).

WHAT IT PAID FOR. `buildIdentity()` walked every file under `design/src/`, and
the command-logging hook writes `.claude/logs/bash-commands.log` under the
current directory of any session that shells there. Measured on 2026-09-11 by
L21's implementer: `dist/build.json` moved from `c133d97cc1ff` to `22c6c46fbb42`
between two builds of an UNCHANGED source, the two last lines of that log being
the steward's own greps. The identity the design host publishes — and the
oracle's served-copy stamp reads — followed shell commands rather than code.

WHERE THIS TEST LIVES, AND WHY IT IS PYTHON. The maquette's own vitest suite
runs nowhere in continuous integration: the `frontend` job runs `npm run test`
for `frontend/` and only `npm run typecheck` for `frontend/maquette/design`. A
hold added there would never be read. The `test` job, on the other hand, sets up
Node 22 — so a Python test driving `node` runs exactly where the gate is, and
`build-identity.mjs` imports nothing but Node's standard library so it needs no
`node_modules` at all.

Every test builds a synthetic design tree in a `tmp_path` repository: nothing
here writes into `frontend/maquette/design/`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "frontend" / "maquette" / "design" / "build-identity.mjs"

ROOT_FILES = ("index.html", "refonte.html", "sw.js", "package.json")


def git(repository: Path, *arguments: str) -> None:
    """Run a git command in the throwaway repository, with the hook leaks stripped."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")
    }
    subprocess.run(["git", *arguments], cwd=repository, check=True, env=environment)


def make_design_tree(tmp_path: Path) -> Path:
    """Build a synthetic design project inside a throwaway repository.

    Args:
        tmp_path: The pytest scratch directory.

    Returns:
        The design project's root — what `buildIdentity` is given.
    """
    design = tmp_path / "design"
    (design / "src" / "ui").mkdir(parents=True)
    (design / "src" / "ui" / "button.ts").write_text("export const button = 1;\n", encoding="utf-8")
    (design / "src" / "index.ts").write_text("export const shell = 1;\n", encoding="utf-8")
    for name in ROOT_FILES:
        (design / name).write_text(f"// {name}\n", encoding="utf-8")
    (design / ".gitignore").write_text("dist/\n.claude/\n", encoding="utf-8")

    git(design, "init", "-q")
    git(design, "config", "user.email", "tester@example.invalid")
    git(design, "config", "user.name", "tester")
    git(design, "add", "-A")
    git(design, "commit", "-qm", "init")
    return design


def identity(design: Path) -> str:
    """Read the identity `build-identity.mjs` computes for a design root."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH — the design build cannot be driven here")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            "const { buildIdentity } = await import(process.argv[1]);\n"
            "process.stdout.write(buildIdentity(process.argv[2]));",
            MODULE.as_uri(),
            str(design),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    return result.stdout.strip()


def test_a_command_log_written_under_src_does_not_move_the_identity(tmp_path: Path) -> None:
    """THE DEFECT THIS FILE WAS WRITTEN FOR: a shell's log is not source."""
    design = make_design_tree(tmp_path)
    before = identity(design)

    logs = design / "src" / ".claude" / "logs"
    logs.mkdir(parents=True)
    (logs / "bash-commands.log").write_text("grep -n PROTOTYPE common.py\n", encoding="utf-8")

    assert identity(design) == before, "the command log entered the build's identity"


def test_an_ignored_directory_under_src_does_not_move_the_identity(tmp_path: Path) -> None:
    """Nothing git refuses to account for may name the build."""
    design = make_design_tree(tmp_path)
    before = identity(design)

    output = design / "src" / "dist"
    output.mkdir()
    (output / "bundle.js").write_text("console.log(1);\n", encoding="utf-8")

    assert identity(design) == before, "an ignored file entered the build's identity"


def test_a_changed_source_moves_the_identity(tmp_path: Path) -> None:
    """THE CONTROL, and without it every test above passes over a constant.

    An identity that never moves would satisfy the two holds above perfectly and
    tell the update discipline nothing at all.
    """
    design = make_design_tree(tmp_path)
    before = identity(design)

    (design / "src" / "ui" / "button.ts").write_text("export const button = 2;\n", encoding="utf-8")

    assert identity(design) != before, "a changed source left the identity where it was"


def test_a_source_written_and_not_yet_added_moves_the_identity(tmp_path: Path) -> None:
    """Untracked is not the same as ignored: a file written a minute ago is source."""
    design = make_design_tree(tmp_path)
    before = identity(design)

    (design / "src" / "ui" / "panel.ts").write_text("export const panel = 1;\n", encoding="utf-8")

    assert identity(design) != before, "an untracked source was invisible to the identity"


def test_a_rebuild_of_an_unchanged_tree_reads_the_same_identity(tmp_path: Path) -> None:
    """« An unchanged id proves an unchanged build » is the promise being repaired."""
    design = make_design_tree(tmp_path)
    assert identity(design) == identity(design)


def test_the_root_files_are_part_of_the_identity(tmp_path: Path) -> None:
    """The shell is four files beside `src/`, and all four name the build."""
    for name in ROOT_FILES:
        design = make_design_tree(tmp_path / name)
        before = identity(design)
        (design / name).write_text(f"// {name} changed\n", encoding="utf-8")
        assert identity(design) != before, f"{name} is outside the build's identity"
