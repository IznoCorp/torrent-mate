"""Regression test for scripts/pre-push running pytest at every core (B-385).

``pytest -n auto`` asks pytest-xdist for one worker per core — eight on this
8-core host — beside whatever gate a wave is already running under
``scripts/heavy.sh`` and outside that lock. The office's arithmetic
(``docs/reference/frontend-steward.md`` § Instrument hygiene) caps a parallel
test run at three workers here, and that cap used to live only in briefs: every
wave was told to export ``PYTEST_XDIST_AUTO_NUM_WORKERS`` by hand.

The hook now applies the cap itself, and says which number it applied. This test
runs the real hook with a stub ``python`` — so no check actually spends minutes
— and reads, in both directions, what reached the checks:

* the variable absent from the environment  -> every check sees ``3``;
* the variable present                      -> its value survives untouched.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRE_PUSH = ROOT / "scripts" / "pre-push"

_WORKER_VARIABLE = "PYTEST_XDIST_AUTO_NUM_WORKERS"


def _fake_python(tmp_path: Path, dump_file: Path) -> Path:
    """Create a stub ``python`` that records the worker variable and exits 0.

    Args:
        tmp_path: Directory to place the stub executable in (prepended to PATH).
        dump_file: File the stub appends one reading to per invocation.

    Returns:
        Path to the stub script.
    """
    script = tmp_path / "python"
    script.write_text(
        f'#!/usr/bin/env bash\necho "{_WORKER_VARIABLE}=${{{_WORKER_VARIABLE}:-UNSET}}" >> "{dump_file}"\nexit 0\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _run_hook(tmp_path: Path, worker_count: str | None) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run the real pre-push hook with a stub ``python`` and return its readings.

    Args:
        tmp_path: Scratch directory holding the stub and the dump file.
        worker_count: Value to export as the worker variable, or None to unset it.

    Returns:
        The completed process, and the concatenated readings the stub recorded.
    """
    dump_file = tmp_path / "workers.txt"
    _fake_python(tmp_path, dump_file)

    environment = os.environ.copy()
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment['PATH']}"
    if worker_count is None:
        environment.pop(_WORKER_VARIABLE, None)
    else:
        environment[_WORKER_VARIABLE] = worker_count

    result = subprocess.run(
        [str(PRE_PUSH)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, dump_file.read_text(encoding="utf-8")


def test_pre_push_caps_pytest_workers_when_the_environment_is_silent(tmp_path: Path) -> None:
    """With the variable unset, every check must see the three-worker cap."""
    result, dump = _run_hook(tmp_path, None)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert f"{_WORKER_VARIABLE}=UNSET" not in dump, f"the cap never reached a check:\n{dump}"
    assert dump.strip().splitlines() == [f"{_WORKER_VARIABLE}=3"] * 5, dump
    assert "pytest workers 3 (capped" in result.stdout, result.stdout


def test_pre_push_honours_a_worker_count_the_environment_already_names(tmp_path: Path) -> None:
    """A number already in the environment is honoured, and said out loud."""
    result, dump = _run_hook(tmp_path, "7")

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert dump.strip().splitlines() == [f"{_WORKER_VARIABLE}=7"] * 5, dump
    assert "pytest workers 7 (from the environment)" in result.stdout, result.stdout
