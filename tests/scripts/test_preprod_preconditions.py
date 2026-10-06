"""Tests for `scripts/preprod_preconditions.py`, the gate before the preprod's jobs start.

A staging deploy starts the preprod's scheduled jobs (follow, search, grab, seed sweep and
purge on the shared torrent client) only when the preprod is really set up: its overlay,
its secrets file, a data directory marked ``staging`` and every root marked as the
preprod's. Each test removes one precondition from an otherwise complete preprod built in
``tmp_path`` and expects that one named.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf import sandbox_guard
from tests.fixtures.config import CANONICAL_STAGING_DIRS

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "preprod_preconditions.py"
STREAM_KEY = "personalscraper:events:staging"


def _load() -> ModuleType:
    """Import the script as a module.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("preprod_preconditions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def preprod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Build a complete preprod in ``tmp_path``: overlay, secrets, marked data dir and roots.

    The roots live on the system disk, which the mount check refuses; the check is patched
    to accept them, so only the markers decide.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The overlay dir, secrets file, data dir and the roots, by name.
    """
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda _path: True)
    config_dir = tmp_path / "config-staging"
    config_dir.mkdir()
    data_dir = tmp_path / "data-staging"
    data_dir.mkdir()
    (data_dir / ".tm-environment").write_text("staging\n", encoding="utf-8")
    disk = tmp_path / "disk3" / "tm-preprod"
    staging_dir = tmp_path / "torrents" / "tm-preprod" / "staging"
    for root in (disk, staging_dir):
        root.mkdir(parents=True)
        (root / ".tm-preprod-root").write_text("preprod root\n", encoding="utf-8")
    master = {
        "paths": {
            "torrent_complete_dir": str(tmp_path / "torrents" / "tm-preprod" / "complete"),
            "staging_dir": str(staging_dir),
            "data_dir": str(data_dir),
        },
        "disks": [{"id": "disk_3", "path": str(disk), "categories": list(CID.BUILTIN_CATEGORY_IDS)}],
        "staging_dirs": [entry.model_dump(mode="json") for entry in CANONICAL_STAGING_DIRS],
        "web": {"stream_key": STREAM_KEY},
    }
    (config_dir / "config.json5").write_text(json.dumps(master), encoding="utf-8")
    env_file = tmp_path / ".env-staging"
    env_file.write_text("QBIT_USERNAME=preprod\n", encoding="utf-8")
    return {"config": config_dir, "env_file": env_file, "data": data_dir, "disk": disk, "staging": staging_dir}


def test_a_complete_preprod_misses_nothing(preprod: dict[str, Path]) -> None:
    """Every precondition holds: nothing is missing, the jobs may start."""
    assert _load().missing_preconditions(preprod["config"], preprod["env_file"]) == []


def test_a_missing_overlay_is_named(preprod: dict[str, Path], tmp_path: Path) -> None:
    """No preprod overlay directory: named, and nothing else is judged."""
    absent = tmp_path / "nowhere"
    missing = _load().missing_preconditions(absent, preprod["env_file"])
    assert len(missing) == 1
    assert str(absent) in missing[0]


def test_a_missing_secrets_file_is_named(preprod: dict[str, Path]) -> None:
    """No preprod secrets file: named."""
    preprod["env_file"].unlink()
    missing = _load().missing_preconditions(preprod["config"], preprod["env_file"])
    assert len(missing) == 1
    assert str(preprod["env_file"]) in missing[0]


def test_an_unmarked_data_dir_is_named(preprod: dict[str, Path]) -> None:
    """A data directory with no ``.tm-environment``: the overlay does not load in staging."""
    (preprod["data"] / ".tm-environment").unlink()
    missing = _load().missing_preconditions(preprod["config"], preprod["env_file"])
    assert len(missing) == 1
    assert ".tm-environment" in missing[0]


def test_a_data_dir_marked_for_another_environment_is_named(preprod: dict[str, Path]) -> None:
    """A data directory marked ``dev``: refused, the marker named."""
    (preprod["data"] / ".tm-environment").write_text("dev\n", encoding="utf-8")
    missing = _load().missing_preconditions(preprod["config"], preprod["env_file"])
    assert len(missing) == 1
    assert ".tm-environment" in missing[0]


@pytest.mark.parametrize("root", ["disk", "staging"])
def test_an_unmarked_root_is_named(preprod: dict[str, Path], root: str) -> None:
    """A preprod root without its ``.tm-preprod-root`` marker: that root named.

    Args:
        preprod: The complete preprod.
        root: Which root loses its marker.
    """
    (preprod[root] / ".tm-preprod-root").unlink()
    missing = _load().missing_preconditions(preprod["config"], preprod["env_file"])
    assert len(missing) == 1
    assert str(preprod[root]) in missing[0]
    assert ".tm-preprod-root" in missing[0]


def test_main_prints_every_missing_precondition_and_fails(
    preprod: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The command line exits 1 and prints one line per missing precondition."""
    preprod["env_file"].unlink()
    (preprod["disk"] / ".tm-preprod-root").unlink()
    code = _load().main([str(preprod["config"]), str(preprod["env_file"])])
    lines = capsys.readouterr().out.splitlines()
    assert code == 1
    assert len(lines) == 2


def test_main_is_silent_and_succeeds_on_a_complete_preprod(
    preprod: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The command line exits 0 and prints nothing when every precondition holds."""
    code = _load().main([str(preprod["config"]), str(preprod["env_file"])])
    assert code == 0
    assert capsys.readouterr().out == ""
