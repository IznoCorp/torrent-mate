"""Golden tests for the additive JSON5 deep-merge sync engine."""

from pathlib import Path

import json5

from personalscraper.conf.sync import _deep_merge_additive, sync_config_dir

# ── Golden: deep-merge additive ──


def test_deep_merge_adds_missing_top_level_key():
    """A key present in example but absent from target is added."""
    example = {"paths": {"staging_dir": "/s"}, "disks": [{"id": "d1"}]}
    target = {"paths": {"staging_dir": "/s"}}
    merged, additions = _deep_merge_additive(example, target)
    assert "disks" in merged
    assert merged["disks"] == [{"id": "d1"}]
    assert len(additions) == 1
    assert "disks" in additions[0]


def test_deep_merge_adds_missing_nested_key():
    """A nested key in example but absent from target is added."""
    example = {"paths": {"staging_dir": "/s", "data_dir": "/d"}}
    target = {"paths": {"staging_dir": "/s"}}
    merged, additions = _deep_merge_additive(example, target)
    assert merged["paths"]["data_dir"] == "/d"
    assert merged["paths"]["staging_dir"] == "/s"  # existing preserved


def test_deep_merge_preserves_existing_values():
    """Existing target values are NEVER modified."""
    example = {"paths": {"staging_dir": "/new"}}
    target = {"paths": {"staging_dir": "/old"}}
    merged, additions = _deep_merge_additive(example, target)
    assert merged["paths"]["staging_dir"] == "/old"  # preserved
    assert len(additions) == 0


def test_deep_merge_preserves_target_extra_keys():
    """Keys in target but NOT in example are preserved."""
    example = {"paths": {"staging_dir": "/s"}}
    target = {"paths": {"staging_dir": "/s", "custom_key": "val"}}
    merged, additions = _deep_merge_additive(example, target)
    assert merged["paths"]["custom_key"] == "val"


def test_deep_merge_handles_list_values():
    """List-type values from example are added as whole units when the key is missing."""
    example = {"disks": [{"id": "d1"}]}
    target = {}
    merged, _ = _deep_merge_additive(example, target)
    assert merged["disks"] == [{"id": "d1"}]


def test_deep_merge_nested_dicts_merge_recursively():
    """Nested dicts are merged recursively, not replaced."""
    example = {"a": {"b": {"c": 1, "d": 2}}}
    target = {"a": {"b": {"c": 0}}}  # c exists, d missing
    merged, additions = _deep_merge_additive(example, target)
    assert merged["a"]["b"]["c"] == 0  # preserved
    assert merged["a"]["b"]["d"] == 2  # added
    assert len(additions) == 1
    assert "a.b.d" in additions[0] or "d" in additions[0]


# ── Golden: sync_config_dir idempotence + dry-run ──


def test_sync_on_empty_target_copies_all_files(tmp_path: Path):
    """Syncing onto an empty target copies every config.example file."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)  # helper below
    result = sync_config_dir(example, target, dry_run=False)
    assert len(result) > 0
    # Every example file exists in target
    for f in example.iterdir():
        assert (target / f.name).exists()


def test_sync_second_run_is_idempotent(tmp_path: Path):
    """A second sync with no example changes produces zero additions."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)
    result2 = sync_config_dir(example, target, dry_run=False)
    assert len(result2) == 0


def test_sync_preserves_user_edits_in_target(tmp_path: Path):
    """After sync, a user-edited value in target remains unchanged."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)
    # Simulate user edit
    paths_file = target / "paths.json5"
    paths_data = json5.loads(paths_file.read_text())
    paths_data["paths"]["staging_dir"] = "/user/custom/path"
    paths_file.write_text(json5.dumps(paths_data, indent=2))
    # Add a new key to example
    ex_paths = json5.loads((example / "paths.json5").read_text())
    ex_paths["paths"]["data_dir"] = "/new/data"
    (example / "paths.json5").write_text(json5.dumps(ex_paths, indent=2))
    # Sync again
    result = sync_config_dir(example, target, dry_run=False)
    assert len(result) > 0
    # User edit preserved, new key added
    final = json5.loads((target / "paths.json5").read_text())
    assert final["paths"]["staging_dir"] == "/user/custom/path"
    assert final["paths"]["data_dir"] == "/new/data"


def test_dry_run_reports_but_does_not_write(tmp_path: Path):
    """--dry-run reports additions but touches no files."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)
    result = sync_config_dir(example, target, dry_run=True)
    assert len(result) > 0
    # No files written
    assert list(target.iterdir()) == []


def test_dry_run_does_not_create_target_dir(tmp_path: Path):
    """--dry-run must NOT create the target directory when it does not exist."""
    example = tmp_path / "example"
    target = tmp_path / "absent"
    example.mkdir()
    _make_minimal_example(example)
    result = sync_config_dir(example, target, dry_run=True)
    assert len(result) > 0
    # Target directory must NOT have been created.
    assert not target.exists(), f"dry-run must not create {target}"


def test_sync_never_removes_target_key(tmp_path: Path):
    """A key present in target but absent in example is NEVER removed."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)
    # Add a key to target that example doesn't have
    paths_file = target / "paths.json5"
    data = json5.loads(paths_file.read_text())
    data["paths"]["operator_only_key"] = "keep_me"
    paths_file.write_text(json5.dumps(data, indent=2))
    # Remove that key from example
    ex_data = json5.loads((example / "paths.json5").read_text())
    if "operator_only_key" in ex_data.get("paths", {}):
        del ex_data["paths"]["operator_only_key"]
    (example / "paths.json5").write_text(json5.dumps(ex_data, indent=2))
    # Sync again
    sync_config_dir(example, target, dry_run=False)
    final = json5.loads((target / "paths.json5").read_text())
    assert final["paths"]["operator_only_key"] == "keep_me"


def _make_minimal_example(d: Path) -> None:
    """Create a minimal config.example structure for testing."""
    (d / "config.json5").write_text(
        json5.dumps(
            {
                "config_version": 1,
                "overlays": ["paths.json5", "disks.json5"],
            },
            indent=2,
        )
    )
    (d / "paths.json5").write_text(
        json5.dumps(
            {
                "paths": {
                    "staging_dir": "/tmp/staging",
                    "torrent_complete_dir": "/tmp/torrents",
                },
            },
            indent=2,
        )
    )
    (d / "disks.json5").write_text(
        json5.dumps(
            {
                "disks": [{"id": "disk1", "path": "/Volumes/disk1", "categories": ["movies"]}],
            },
            indent=2,
        )
    )
