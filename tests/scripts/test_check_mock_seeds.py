"""Tests for the mock-seed guard's decision about whether it can run at all.

WHAT IS HELD HERE, and why it is not the arms. The seven arms are exercised by
`frontend/maquette/harness/run.sh` on a tree that has the fixtures; what has no
cover anywhere is the branch this guard takes when the TypeScript parser it
needs is ABSENT — and that branch decides whether a missing install is reported
as a skip, as a violation, or not at all. Every wrong answer there is silent.

THE FAILURE THAT MADE THESE NECESSARY: a first version collapsed every non-zero
exit from the extractor into « no TypeScript install », so a syntax error in the
extractor — the very file the guard's arms parse — made the whole guard exit 0
while announcing a confident wrong reason.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "check-mock-seeds.py"
EXTRACTOR = ROOT / "scripts" / "extract-maquette-fixtures.mjs"


def run_guard(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Runs the guard from the repository root and returns its result."""
    return subprocess.run(
        [sys.executable, str(GUARD), *arguments],
        cwd=ROOT, capture_output=True, text=True, check=False)


def test_the_extractor_answers_where_it_can_run() -> None:
    """`--typescript-install` prints a real, existing file and exits zero."""
    answer = subprocess.run(
        ["node", str(EXTRACTOR), "--typescript-install"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    if answer.returncode == 3:
        return  # no install on this machine; the absence branch is tested below
    assert answer.returncode == 0, answer.stderr
    # A PATH, not the specifier the list holds: a caller running from anywhere
    # but `scripts/` would resolve a relative specifier against its own
    # directory and reach nothing.
    resolved = Path(answer.stdout.strip())
    assert resolved.is_absolute()
    assert resolved.exists()


def test_an_unknown_flag_is_not_read_as_a_missing_install() -> None:
    """Only exit 3 means « no install »; anything else must not be mistaken for it."""
    answer = subprocess.run(
        ["node", str(EXTRACTOR), "--a-flag-that-does-not-exist"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert answer.returncode not in (0, 3)


def test_a_broken_extractor_fails_loudly_rather_than_skipping(tmp_path: Path) -> None:
    """A syntax error in the extractor exits non-zero and names what broke.

    The guard's arms parse that file. Reporting « no TypeScript install » about
    an extractor that is merely broken is a confident wrong reason returning
    success, which is worse than failing.
    """
    broken = tmp_path / "broken.mjs"
    broken.write_text("const nothing = ;\n", encoding="utf-8")
    original = EXTRACTOR.read_text(encoding="utf-8")
    EXTRACTOR.write_text(original + "\nconst nothing = ;\n", encoding="utf-8")
    try:
        answer = run_guard()
    finally:
        EXTRACTOR.write_text(original, encoding="utf-8")
    assert answer.returncode != 0
    assert "check-mock-seeds:" in answer.stderr
    assert "no TypeScript install" not in answer.stderr


def test_the_skip_names_only_the_arms_that_need_the_parser() -> None:
    """The message names three arms, not seven, and says the others ran.

    Read from the guard's source rather than by removing the machine's node
    install: four arms read JSON and text only, and two written exemptions
    elsewhere in the repository rest on one of them running wherever the guards
    do. A skip covering all seven would leave those resting on nothing.
    """
    source = GUARD.read_text(encoding="utf-8")
    assert 'NEEDS_THE_PARSER = ("classification", "lossless", "correspondence")' in source
    # The four that must keep running are the ones no arm may skip.
    for arm in ("schema", "provenance", "generated", "handlers"):
        assert f'"{arm}"' in source


def test_the_inventory_is_readable_without_the_parser() -> None:
    """`--list` answers, because it reads the register and nothing else."""
    answer = run_guard("--list")
    assert answer.returncode == 0
    assert "family(ies)" in answer.stdout
