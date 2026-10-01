"""The design build on a tree that has never been built (B-318).

WHAT IT PAID FOR. `vite.config.mjs`'s two plugins read `dist/` from their
`closeBundle` hook, and rolldown calls `closeBundle` on a build that FAILED as
well: on a copy with no `dist/`, the failure was reported as `ENOENT scandir
dist/vite`, the hook's own crash, and the build's real error — a module it could
not resolve — was never printed. B-318 read that mask as a race against the
output; measured on `main` `27b304157`, a complete tree builds first time, and a
tree missing `../contract` answers `ENOENT` alone. `writeBundle` runs only once
the bundles are written.

The build is driven on a copy in `tmp_path`, outside any repository, so nothing
here writes into `frontend/maquette/design/`. It needs the design project's
installed `node_modules`; where there are none it skips and says why.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAQUETTE = ROOT / "frontend" / "maquette"
DESIGN = MAQUETTE / "design"
VITE = DESIGN / "node_modules" / "vite" / "bin" / "vite.js"

# What the build reads beside `src/`; `dist/` and `node_modules/` are never copied.
BUILD_FILES = ("index.html", "sw.js", "package.json", "vite.config.mjs", "build-identity.mjs", "tsconfig.json")


def fresh_design_copy(tmp_path: Path) -> Path:
    """Copy the design project's build inputs into a tree with no `dist/`.

    Args:
        tmp_path: The pytest scratch directory.

    Returns:
        The copy's root, its `node_modules` a link to the installed one. The
        contract it imports sits beside it, as `../contract` does in the tree.
    """
    copy = tmp_path / "maquette" / "design"
    copy.mkdir(parents=True)
    shutil.copytree(MAQUETTE / "contract", tmp_path / "maquette" / "contract")
    shutil.copytree(DESIGN / "src", copy / "src", ignore=shutil.ignore_patterns(".claude"))
    for name in BUILD_FILES:
        shutil.copy2(DESIGN / name, copy / name)
    (copy / "node_modules").symlink_to(DESIGN / "node_modules")
    return copy


def build(copy: Path) -> subprocess.CompletedProcess[str]:
    """Run the design build in a copy, skipping where it cannot be driven.

    Args:
        copy: The copy made by `fresh_design_copy`.

    Returns:
        The finished build, its output captured.
    """
    node = shutil.which("node")
    if node is None or not VITE.exists():
        pytest.skip("node or the design project's node_modules is missing — the build cannot be driven here")
    return subprocess.run(
        [node, str(VITE), "build", "--logLevel", "error"],
        cwd=copy,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_a_failed_build_reports_its_own_error(tmp_path: Path) -> None:
    """A build that cannot resolve a module names that module, never `dist/vite`."""
    copy = fresh_design_copy(tmp_path)
    shutil.rmtree(tmp_path / "maquette" / "contract")

    built = build(copy)

    assert built.returncode != 0
    assert "openapi.json" in built.stderr, built.stderr[-2000:]
    assert "dist/vite" not in built.stderr, built.stderr[-2000:]


def test_a_build_on_a_tree_never_built_precaches_its_own_bundles(tmp_path: Path) -> None:
    """A first build succeeds, and the worker precaches exactly the bundles it wrote."""
    copy = fresh_design_copy(tmp_path)

    built = build(copy)

    assert built.returncode == 0, built.stderr[-2000:]
    written = sorted(f"/vite/{path.name}" for path in (copy / "dist" / "vite").iterdir())
    worker = (copy / "dist" / "sw.js").read_text(encoding="utf-8")
    precached = sorted(set(re.findall(r'"(/vite/[^"]+)"', worker)))
    assert precached == written
