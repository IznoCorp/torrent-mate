"""Integration test: init-config --sync on a tmp canonical dir — end-to-end.

exercise of the additive merge, idempotence, value preservation, and --dry-run
non-write guarantees (DESIGN §6).
"""

from __future__ import annotations

from pathlib import Path

import json5
import pytest

from personalscraper.commands.init_config import init_config_sync
from personalscraper.conf.sync import sync_config_dir


def test_sync_end_to_end_additive_and_idempotent(tmp_path: Path) -> None:
    """Full cycle: sync onto empty target → sync again (idempotent).

    Modify target → add new key to example → sync again → values preserved.
    """
    example = tmp_path / "config.example"
    target = tmp_path / "canonical"
    example.mkdir()
    target.mkdir()

    # Build a realistic example
    (example / "config.json5").write_text(
        json5.dumps(
            {
                "config_version": 1,
                "overlays": ["paths.json5", "disks.json5", "categories.json5"],
            },
            indent=2,
        )
    )
    (example / "paths.json5").write_text(
        json5.dumps(
            {
                "paths": {
                    "staging_dir": "/example/staging",
                    "torrent_complete_dir": "/example/torrents",
                },
            },
            indent=2,
        )
    )
    (example / "disks.json5").write_text(
        json5.dumps(
            {
                "disks": [{"id": "disk1", "path": "/Volumes/disk1", "categories": ["movies"]}],
            },
            indent=2,
        )
    )
    (example / "categories.json5").write_text(
        json5.dumps(
            {
                "categories": {"movies": {"label": "Movies", "icon": "🎬"}},
            },
            indent=2,
        )
    )

    # Step 1: first sync copies all files
    result1 = sync_config_dir(example, target, dry_run=False)
    assert len(result1) >= 3  # at least 3 files copied
    for name in ["config.json5", "paths.json5", "disks.json5", "categories.json5"]:
        assert (target / name).exists()

    # Step 2: second sync is idempotent
    result2 = sync_config_dir(example, target, dry_run=False)
    assert len(result2) == 0  # nothing to add

    # Step 3: user edits a value in target, then a new key is added to example
    paths_file = target / "paths.json5"
    paths_data = json5.loads(paths_file.read_text())
    paths_data["paths"]["staging_dir"] = "/operator/custom/staging"
    paths_data["paths"]["custom_operator_key"] = "keep_me"
    paths_file.write_text(json5.dumps(paths_data, indent=2))

    # Add new key to example
    ex_paths = json5.loads((example / "paths.json5").read_text())
    ex_paths["paths"]["data_dir"] = "/example/.data"
    (example / "paths.json5").write_text(json5.dumps(ex_paths, indent=2))

    # Step 4: sync again — user edits preserved, new key added
    result3 = sync_config_dir(example, target, dry_run=False)
    final = json5.loads((target / "paths.json5").read_text())
    assert final["paths"]["staging_dir"] == "/operator/custom/staging"  # preserved
    assert final["paths"]["custom_operator_key"] == "keep_me"  # preserved
    assert final["paths"]["data_dir"] == "/example/.data"  # added
    assert any("data_dir" in r for r in result3)


def test_init_config_sync_dry_run_does_not_write(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """init_config_sync --dry-run reports additions but writes nothing.

    Uses pytest's built-in capsys fixture instead of a manual sys.stdout
    swap — typer.echo writes to sys.stdout which capsys captures reliably.
    """
    example = tmp_path / "config.example"
    target = tmp_path / "canonical"
    example.mkdir()
    target.mkdir()
    (example / "config.json5").write_text('{"key": "val"}')

    init_config_sync(example, target, dry_run=True)

    captured = capsys.readouterr()
    assert "[DRY-RUN]" in captured.out, "init_config_sync should echo the dry-run banner"
    assert "Would add" in captured.out, "init_config_sync should report would-be additions"

    # Nothing written
    assert not list(target.iterdir()), "dry-run must not write any files to target"
