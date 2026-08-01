"""Golden tests for the additive JSON5 deep-merge sync engine."""

from pathlib import Path

import json5
import pytest

from personalscraper.conf.overlay import ConfigLoadError
from personalscraper.conf.sync import _deep_merge_additive, sync_config_dir

# ── Golden: deep-merge additive ──


def test_deep_merge_adds_missing_top_level_key():
    """A key present in example but absent from target is added."""
    example = {"paths": {"staging_dir": "/s"}, "disks": [{"id": "d1"}]}
    target = {"paths": {"staging_dir": "/s"}}
    merged, report = _deep_merge_additive(example, target)
    assert "disks" in merged
    assert merged["disks"] == [{"id": "d1"}]
    assert len(report) == 1
    assert any("disks" in r for r in report)


def test_deep_merge_adds_missing_nested_key():
    """A nested key in example but absent from target is added."""
    example = {"paths": {"staging_dir": "/s", "data_dir": "/d"}}
    target = {"paths": {"staging_dir": "/s"}}
    merged, report = _deep_merge_additive(example, target)
    assert merged["paths"]["data_dir"] == "/d"
    assert merged["paths"]["staging_dir"] == "/s"  # existing preserved


def test_deep_merge_preserves_existing_values():
    """Existing target values are NEVER modified."""
    example = {"paths": {"staging_dir": "/new"}}
    target = {"paths": {"staging_dir": "/old"}}
    merged, report = _deep_merge_additive(example, target)
    assert merged["paths"]["staging_dir"] == "/old"  # preserved
    assert len(report) == 0


def test_deep_merge_preserves_target_extra_keys():
    """Keys in target but NOT in example are preserved."""
    example = {"paths": {"staging_dir": "/s"}}
    target = {"paths": {"staging_dir": "/s", "custom_key": "val"}}
    merged, report = _deep_merge_additive(example, target)
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
    merged, report = _deep_merge_additive(example, target)
    assert merged["a"]["b"]["c"] == 0  # preserved
    assert merged["a"]["b"]["d"] == 2  # added
    assert len(report) == 1
    assert any("b.d" in r for r in report)


# ── F-E: Type-conflict reporting ──


def test_deep_merge_reports_dict_vs_scalar_conflict():
    """Example dict vs target scalar → conflict reported, target kept."""
    example = {"paths": {"staging_dir": "/s"}}
    target = {"paths": "scalar_not_a_dict"}
    merged, report = _deep_merge_additive(example, target)
    assert merged["paths"] == "scalar_not_a_dict"  # preserved
    conflicts = [r for r in report if r.startswith("conflict")]
    assert len(conflicts) == 1
    assert "paths" in conflicts[0]
    assert "dict" in conflicts[0].lower() and "str" in conflicts[0].lower()


def test_deep_merge_reports_list_vs_scalar_conflict():
    """Example list vs target scalar → conflict reported, target kept."""
    example = {"disks": [{"id": "d1"}]}
    target = {"disks": "scalar"}
    merged, report = _deep_merge_additive(example, target)
    assert merged["disks"] == "scalar"
    conflicts = [r for r in report if r.startswith("conflict")]
    assert len(conflicts) == 1
    assert "disks" in conflicts[0]


def test_deep_merge_reports_scalar_vs_dict_conflict():
    """Example scalar vs target dict → conflict reported, target kept."""
    example = {"settings": "scalar"}
    target = {"settings": {"nested": "dict"}}
    merged, report = _deep_merge_additive(example, target)
    assert merged["settings"] == {"nested": "dict"}  # preserved
    conflicts = [r for r in report if r.startswith("conflict")]
    assert len(conflicts) == 1
    assert "settings" in conflicts[0]


def test_deep_merge_silent_on_same_non_dict_types():
    """Same non-dict types (e.g. both str) → no conflict (user customised)."""
    example = {"paths": {"staging_dir": "/new"}}
    target = {"paths": {"staging_dir": "/old"}}
    merged, report = _deep_merge_additive(example, target)
    assert len(report) == 0  # same-type scalar → silent
    # Re-verify: conflicts prefix should NOT appear.
    assert not any(r.startswith("conflict") for r in report)


def test_conflict_entries_do_not_count_as_additions():
    """Conflict lines are prefixed 'conflict' — separate from 'add key'."""
    example = {"a": {"nested": 1}, "b": "new"}
    target = {"a": "scalar"}
    merged, report = _deep_merge_additive(example, target)
    additions = [r for r in report if not r.startswith("conflict")]
    conflicts = [r for r in report if r.startswith("conflict")]
    assert len(additions) == 1  # "b" added
    assert len(conflicts) == 1  # "a" conflict
    assert merged["a"] == "scalar"
    assert merged["b"] == "new"


# ── Golden: sync_config_dir ──


def test_sync_on_empty_target_copies_all_files(tmp_path: Path):
    """Syncing onto an empty target copies every config.example file."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)
    result = sync_config_dir(example, target, dry_run=False)
    assert len(result) > 0
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
    assert result2 == []


def test_sync_up_to_date_reports_empty_list(tmp_path: Path):
    """Explicit assertion: up-to-date target returns exactly []."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)
    result2 = sync_config_dir(example, target, dry_run=False)
    assert result2 == [], f"Expected [], got {result2}"


def test_sync_untouched_file_not_rewritten(tmp_path: Path):
    """A file needing NO additions is NOT rewritten (mtime + bytes unchanged)."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    _make_minimal_example(example)
    sync_config_dir(example, target, dry_run=False)

    # Snapshot mtime and content for every file.
    snapshots: dict[str, tuple[float, int]] = {}
    for f in target.iterdir():
        stat = f.stat()
        snapshots[f.name] = (stat.st_mtime, stat.st_size)

    # Sync again — no changes to example.
    sync_config_dir(example, target, dry_run=False)

    # Every file's mtime and size must be unchanged.
    for f in target.iterdir():
        before = snapshots[f.name]
        after_mtime = f.stat().st_mtime
        after_size = f.stat().st_size
        assert after_mtime == before[0], f"{f.name} mtime changed ({before[0]} → {after_mtime})"
        assert after_size == before[1], f"{f.name} size changed ({before[1]} → {after_size})"


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
    assert list(target.iterdir()) == []


def test_dry_run_does_not_create_target_dir(tmp_path: Path):
    """--dry-run must NOT create the target directory when it does not exist."""
    example = tmp_path / "example"
    target = tmp_path / "absent"
    example.mkdir()
    _make_minimal_example(example)
    result = sync_config_dir(example, target, dry_run=True)
    assert len(result) > 0
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


# ── F-C: Malformed JSON5 → ConfigLoadError ──


def test_malformed_example_json5_raises_config_load_error(tmp_path: Path):
    """Malformed JSON5 in an example file raises ConfigLoadError naming the file."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    (example / "config.json5").write_text("{valid: true}")
    (example / "paths.json5").write_text("{paths: {staging: /s}}")
    (example / "broken.json5").write_text("not valid { json ~~~")

    with pytest.raises(ConfigLoadError) as exc_info:
        sync_config_dir(example, target, dry_run=False)
    assert "broken.json5" in str(exc_info.value)


def test_malformed_target_json5_raises_config_load_error(tmp_path: Path):
    """Malformed JSON5 in an existing target file raises ConfigLoadError naming the file."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()
    # Example has a valid file that also exists (as broken) in target → merge path.
    (example / "bad.json5").write_text("{key: 1}")
    (target / "bad.json5").write_text("not valid { json ~~~")

    with pytest.raises(ConfigLoadError) as exc_info:
        sync_config_dir(example, target, dry_run=False)
    assert "bad.json5" in str(exc_info.value)


# ── F-D: Overlay registration ──


def test_copy_new_overlay_registers_in_master(tmp_path: Path):
    """Copying a NEW overlay file appends it to the target master overlays list."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()

    # Example: config.json5 with 2 overlays + matching files.
    (example / "config.json5").write_text(
        json5.dumps({"config_version": 1, "overlays": ["paths.json5", "disks.json5"]}, indent=2)
    )
    (example / "paths.json5").write_text(json5.dumps({"paths": {"staging_dir": "/s"}}, indent=2))
    (example / "disks.json5").write_text(json5.dumps({"disks": []}, indent=2))

    # First sync — target gets everything.
    result1 = sync_config_dir(example, target, dry_run=False)
    assert len(result1) >= 3

    # Now add a NEW overlay file to example that doesn't exist in target.
    (example / "categories.json5").write_text(json5.dumps({"categories": {}}, indent=2))
    # Also update example's overlays to include it.
    (example / "config.json5").write_text(
        json5.dumps(
            {"config_version": 1, "overlays": ["paths.json5", "disks.json5", "categories.json5"]},
            indent=2,
        )
    )

    result2 = sync_config_dir(example, target, dry_run=False)
    assert any("copy new file: categories.json5" in r for r in result2)
    assert any("register overlay: categories.json5" in r for r in result2)

    # Verify target's config.json5 overlays list now includes categories.json5.
    tgt_master = json5.loads((target / "config.json5").read_text())
    assert "categories.json5" in tgt_master["overlays"]


def test_target_customized_overlays_preserved(tmp_path: Path):
    """Target overlays with custom entries → new overlays appended, existing preserved."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()

    (example / "config.json5").write_text(
        json5.dumps({"config_version": 1, "overlays": ["paths.json5", "disks.json5"]}, indent=2)
    )
    (example / "paths.json5").write_text(json5.dumps({"paths": {"staging_dir": "/s"}}, indent=2))
    (example / "disks.json5").write_text(json5.dumps({"disks": []}, indent=2))

    sync_config_dir(example, target, dry_run=False)

    # User customises target's overlays: adds a custom overlay + reorders.
    tgt_master_data = json5.loads((target / "config.json5").read_text())
    tgt_master_data["overlays"] = ["disks.json5", "paths.json5", "custom_local.json5"]
    (target / "config.json5").write_text(json5.dumps(tgt_master_data, indent=2))

    # Now example gets a new overlay.
    (example / "categories.json5").write_text(json5.dumps({"categories": {}}, indent=2))
    (example / "config.json5").write_text(
        json5.dumps(
            {"config_version": 1, "overlays": ["paths.json5", "disks.json5", "categories.json5"]},
            indent=2,
        )
    )

    result = sync_config_dir(example, target, dry_run=False)
    assert any("register overlay: categories.json5" in r for r in result)

    final_master = json5.loads((target / "config.json5").read_text())
    # Custom order preserved: "custom_local.json5" is still there and after the originals.
    assert "custom_local.json5" in final_master["overlays"]
    # "categories.json5" appended (respects example ordering among new entries).
    assert "categories.json5" in final_master["overlays"]
    # The custom order of existing entries is preserved.
    idx_custom = final_master["overlays"].index("custom_local.json5")
    idx_cats = final_master["overlays"].index("categories.json5")
    assert idx_cats > idx_custom  # new overlay appended after custom entries


def test_overlay_registration_skips_when_already_registered(tmp_path: Path):
    """Overlay already in target's list → not re-registered, no duplicate."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()

    (example / "config.json5").write_text(
        json5.dumps({"config_version": 1, "overlays": ["paths.json5", "disks.json5"]}, indent=2)
    )
    (example / "paths.json5").write_text(json5.dumps({"paths": {"staging_dir": "/s"}}, indent=2))
    (example / "disks.json5").write_text(json5.dumps({"disks": []}, indent=2))

    sync_config_dir(example, target, dry_run=False)

    # Sync again — nothing should be re-registered.
    result = sync_config_dir(example, target, dry_run=False)
    assert not any("register overlay" in r for r in result)
    assert result == []


def test_overlay_registration_respects_example_order(tmp_path: Path):
    """Multiple new overlays are appended in example's declared order."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()

    (example / "config.json5").write_text(json5.dumps({"config_version": 1, "overlays": ["paths.json5"]}, indent=2))
    (example / "paths.json5").write_text(json5.dumps({"paths": {"staging_dir": "/s"}}, indent=2))

    sync_config_dir(example, target, dry_run=False)

    # Add two new overlays.
    (example / "disks.json5").write_text(json5.dumps({"disks": []}, indent=2))
    (example / "categories.json5").write_text(json5.dumps({"categories": {}}, indent=2))
    (example / "config.json5").write_text(
        json5.dumps(
            {"config_version": 1, "overlays": ["paths.json5", "disks.json5", "categories.json5"]},
            indent=2,
        )
    )

    sync_config_dir(example, target, dry_run=False)
    final_master = json5.loads((target / "config.json5").read_text())
    # New entries appended in example order: disks before categories.
    idx_disks = final_master["overlays"].index("disks.json5")
    idx_cats = final_master["overlays"].index("categories.json5")
    assert idx_disks < idx_cats, "disks.json5 should precede categories.json5 (example order)"


def test_overlay_registration_skips_when_no_config_master(tmp_path: Path):
    """When config.json5 doesn't exist in example → no registration (nothing to register)."""
    example = tmp_path / "example"
    target = tmp_path / "target"
    example.mkdir()
    target.mkdir()

    # Example has NO config.json5 — just a standalone overlay file.
    (example / "paths.json5").write_text(json5.dumps({"paths": {"staging_dir": "/s"}}, indent=2))

    result = sync_config_dir(example, target, dry_run=False)
    # File is copied but there's no master to register it in.
    assert any("copy new file: paths.json5" in r for r in result)
    assert not any("register overlay" in r for r in result)


# ── Helpers ──


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
