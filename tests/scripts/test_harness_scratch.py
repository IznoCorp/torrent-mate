"""Where the harness writes its waste: the scratch volume, never the system disk.

WHAT IT PAID FOR. Every harness Chrome is a throw-away profile of about two
hundred files, written under the system disk's `$TMPDIR`; with several sessions
running rules, `fseventsd` sat at 75–115 % CPU and `syspolicyd` at 22 %, both
paid for files nobody reads (the audit's measurement, 2026-10-01). The operator
made an APFS volume for that waste, `/Volumes/TMScratch`, with its event log
switched off. These tests hold that the harness writes there when the volume is
mounted, falls back to `/tmp` when it is not (CI), never mistakes a bare
directory at the volume's path for the volume, and launches every Chrome with
the switches that stop it caching and fetching.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "frontend" / "maquette" / "harness"


def load(name: str):
    """Imports one harness module from its file, without running its command line.

    Args:
        name: The module's name beside `run.sh`.

    Returns:
        The imported module.
    """
    sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location(name, HARNESS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


served_copy = load("served_copy")


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    """A scratch volume the module believes mounted, in a private directory.

    Returns:
        The directory standing for the volume.
    """
    volume = tmp_path / "TMScratch"
    volume.mkdir()
    monkeypatch.setattr(served_copy, "SCRATCH_VOLUME", volume)
    real_ismount = os.path.ismount
    monkeypatch.setattr(served_copy.os.path, "ismount", lambda path: Path(path) == volume or real_ismount(path))
    return volume


def test_every_chrome_launch_neither_caches_nor_fetches(tmp_path, monkeypatch) -> None:
    """Each launch wrote a disk cache, a shader cache and component downloads.

    Those writes are the files `fseventsd` and `syspolicyd` were paying for, and
    no rule reads any of them back.
    """
    # `common` moves TMPDIR at import; without a volume it leaves this process's alone.
    monkeypatch.setenv("TM_SCRATCH_VOLUME", str(tmp_path / "absent"))
    monkeypatch.delitem(sys.modules, "served_copy", raising=False)
    common = load("common")

    arguments = common.chrome_launch_args(["--extra-for-this-rule"])

    for switch in (
        "--use-mock-keychain",
        "--disk-cache-size=1",
        "--disable-gpu-shader-disk-cache",
        "--disable-component-update",
        "--no-first-run",
        "--disable-background-networking",
    ):
        assert switch in arguments, switch
    assert arguments[-1] == "--extra-for-this-rule"


def test_without_the_volume_everything_stays_in_tmp(tmp_path, monkeypatch) -> None:
    """CI has no scratch volume: the served copy is `/tmp`'s, and TMPDIR is left alone."""
    monkeypatch.setattr(served_copy, "SCRATCH_VOLUME", tmp_path / "absent")

    assert served_copy.scratch_volume() is None
    assert served_copy.default_root() == Path("/tmp/tm-refonte")
    assert served_copy.worktree_scratch() is None
    assert served_copy.redirect_tmpdir() is None


def test_a_bare_directory_at_the_volume_s_path_is_not_the_volume(tmp_path, monkeypatch) -> None:
    """An unmounted volume can leave its mount point behind as a plain directory.

    Writing there would put the waste back on the system disk under a name that
    says it is not, which is worse than `/tmp`.
    """
    monkeypatch.setattr(served_copy, "SCRATCH_VOLUME", tmp_path)

    assert served_copy.scratch_volume() is None
    assert served_copy.default_root() == Path("/tmp/tm-refonte")


def test_the_volume_takes_the_served_copy_and_the_checkout_s_scratch(mounted) -> None:
    """The served copy is the machine's one copy; the profiles and logs are this checkout's."""
    assert served_copy.scratch_volume() == mounted
    assert served_copy.default_root() == mounted / "tm-refonte"
    assert served_copy.worktree_scratch() == mounted / ROOT.name


def test_a_rule_s_chrome_profile_is_made_on_the_volume(mounted, monkeypatch) -> None:
    """Playwright makes each profile under its driver's TMPDIR, inherited from the rule.

    So the rule's own process environment is what moves the profile: the driver
    starts after `common` is imported, and inherits it.
    """
    monkeypatch.setenv("TMPDIR", tempfile.gettempdir())
    monkeypatch.setattr(tempfile, "tempdir", None)

    moved = served_copy.redirect_tmpdir()

    assert moved == mounted / ROOT.name / "tmp"
    assert moved.is_dir()
    assert os.environ["TMPDIR"] == str(moved)
    assert Path(tempfile.gettempdir()) == moved


def test_no_harness_file_names_the_served_copy_by_a_literal_path() -> None:
    """Eight files carried `/tmp/tm-refonte` and would have read a copy nobody builds."""
    literal = re.compile(r"/tmp/tm-refonte")
    offenders = [
        path.name
        for path in sorted(HARNESS.iterdir())
        if path.suffix in {".py", ".sh"} and literal.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], offenders


def test_run_sh_takes_its_directories_from_served_copy() -> None:
    """`run.sh` asks the one module that decides, for the copy, the profiles and the logs."""
    run_sh = (HARNESS / "run.sh").read_text(encoding="utf-8")

    assert 'SERVED="$(python3 "$HERE/served_copy.py" --root)"' in run_sh
    assert 'SCRATCH="$(python3 "$HERE/served_copy.py" --scratch)"' in run_sh
    assert 'export TMPDIR="$SCRATCH/tmp"' in run_sh
