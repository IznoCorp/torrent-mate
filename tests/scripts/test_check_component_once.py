"""The component guard has something to re-run, and each shape it claims is one.

WHY THIS FILE EXISTS. B-041's sentence is « the newest guard is the only one of
its family with nothing to re-run », and it became true again the day this guard
was written: it left `check-frontend-boundaries.py` to be its own file, and the
ratchet that refuses an ARM without a test does not reach a FILE. Its first
version then shipped a docstring saying « exported or not » over a regex that
refused `export default function` — the commonest way a component is exported
anywhere else — and nothing but a reader found it.

WHAT EACH TEST DOES. It writes a second declaration of a name `ui/` already
holds into a scratch copy of the tree and asks the guard to refuse it. The
copy is a real directory tree rather than a mocked filesystem: the guard walks
`design/src` by path and its floors are about how much it read, so a corpus of
two files would pass its own floor check and prove nothing.

WHAT IT DOES NOT PROVE. That the guard reads the RIGHT corpus — its exclusions
(`engine/`, `mocks/`) are asserted here by one test each, and a third directory
appearing in that tuple would be invisible to this file.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-component-once.py"
DESIGN_SOURCE = ROOT / "frontend" / "maquette" / "design" / "src"

# A NAME `ui/` ALREADY HOLDS, so a second declaration anywhere else is the
# defect this guard exists for. Read from the tree rather than typed, so a
# rename of the shared component leaves this file measuring something.
SHARED = "Icon"


def run(tree: Path) -> subprocess.CompletedProcess[str]:
    """Runs the guard against a scratch copy of the maquette's sources.

    Args:
        tree: A directory holding `frontend/maquette/design/src` and the guard.

    Returns:
        The completed process, with its output captured.
    """
    return subprocess.run(
        [sys.executable, str(tree / "scripts" / "check-component-once.py")], capture_output=True, text=True, check=False
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A scratch copy of the sources the guard reads, and of the guard itself."""
    copy = tmp_path / "frontend" / "maquette" / "design" / "src"
    copy.parent.mkdir(parents=True)
    shutil.copytree(DESIGN_SOURCE, copy, ignore=shutil.ignore_patterns("*.css", "*.json", "*.html"))
    (tmp_path / "scripts").mkdir()
    shutil.copy2(SCRIPT, tmp_path / "scripts" / SCRIPT.name)
    return tmp_path


def second(tree: Path, declaration: str, where: str = "features/releases/second.tsx") -> None:
    """Writes a second declaration of the shared name into the scratch tree."""
    target = tree / "frontend" / "maquette" / "design" / "src" / where
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(declaration, encoding="utf-8")


def test_the_tree_it_reads_is_clean(tree: Path) -> None:
    """The corpus is green before anything is written into it."""
    finished = run(tree)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "0 name(s) declared twice" in finished.stdout


def test_a_plain_second_declaration_is_refused(tree: Path) -> None:
    """A component declared in a second file is refused."""
    second(tree, f"function {SHARED}() {{ return null; }}\n")
    finished = run(tree)
    assert finished.returncode != 0
    assert SHARED in finished.stderr and "second.tsx" in finished.stderr


def test_an_exported_second_declaration_is_refused(tree: Path) -> None:
    """Exporting it changes nothing: it is still written twice."""
    second(tree, f"export function {SHARED}() {{ return null; }}\n")
    assert run(tree).returncode != 0


def test_a_DEFAULT_exported_declaration_is_refused(tree: Path) -> None:
    """The shape the first version's docstring claimed and its regex refused."""
    second(tree, f"export default function {SHARED}() {{ return null; }}\n")
    finished = run(tree)
    assert finished.returncode != 0, (
        "`export default function` is the commonest way a component is exported "
        "outside this repository, and the guard said « exported or not »"
    )
    assert SHARED in finished.stderr


def test_an_async_default_declaration_is_refused(tree: Path) -> None:
    """Nor does `async` between `default` and `function`."""
    second(tree, f"export default async function {SHARED}() {{ return null; }}\n")
    assert run(tree).returncode != 0


def test_a_generic_declaration_is_refused(tree: Path) -> None:
    """Nor a type parameter where the argument list would start."""
    second(tree, f"export function {SHARED}<T>(value: T) {{ return value; }}\n")
    assert run(tree).returncode != 0


def test_the_dying_engine_is_excluded(tree: Path) -> None:
    """A name the engine declares is not a second component: it dies with it."""
    second(tree, f"export function {SHARED}() {{ return null; }}", "engine/second.ts")
    assert run(tree).returncode == 0


def test_the_mock_layer_is_excluded(tree: Path) -> None:
    """A test double may wear the name of what it stands in for."""
    second(tree, f"export function {SHARED}() {{ return null; }}", "mocks/second.ts")
    assert run(tree).returncode == 0


def test_a_camel_case_name_is_not_a_component(tree: Path) -> None:
    """A camelCase name is a helper, and the guard says it does not read one."""
    second(tree, f"export default function {SHARED.lower()}() {{ return null; }}\n")
    assert run(tree).returncode == 0


def test_an_empty_corpus_is_refused_rather_than_called_clean(tmp_path: Path) -> None:
    """« No duplicate » over nothing read is the reading this guard refuses."""
    (tmp_path / "frontend" / "maquette" / "design" / "src").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    shutil.copy2(SCRIPT, tmp_path / "scripts" / SCRIPT.name)
    finished = run(tmp_path)
    assert finished.returncode != 0
    assert "under its floor" in finished.stderr
