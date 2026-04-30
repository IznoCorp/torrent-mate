"""Tests for personalscraper.conf.overlay.merge_overlays."""

from pathlib import Path

import pytest

from personalscraper.conf.overlay import ConfigConflictError, merge_overlays


class TestMergeOverlays:
    """Tests for the merge_overlays helper."""

    def test_happy_path_non_conflicting_overlays(self) -> None:
        """Two non-conflicting overlays must merge cleanly into a single dict.

        The base dict and both overlays own distinct top-level keys, so no
        ConfigConflictError should be raised and the result must contain all keys.
        """
        base = {"key_a": "value_a"}
        overlay_b = {"key_b": "value_b", "__source__": Path("/cfg/overlay_b.json5")}
        overlay_c = {"key_c": "value_c", "__source__": Path("/cfg/overlay_c.json5")}

        result = merge_overlays(base, overlay_b, overlay_c)

        assert result["key_a"] == "value_a"
        assert result["key_b"] == "value_b"
        assert result["key_c"] == "value_c"
        # Internal sentinel must not leak into the result.
        assert "__source__" not in result

    def test_conflicting_key_raises_config_conflict_error(self) -> None:
        """Two non-local overlays defining the same top-level key must raise ConfigConflictError.

        Merging is unambiguous only when each non-local overlay owns distinct keys.
        Duplicate ownership must be rejected with a clear error message.
        """
        base: dict = {}
        overlay_1 = {"disks": ["disk_a"], "__source__": Path("/cfg/disks.json5")}
        overlay_2 = {"disks": ["disk_b"], "__source__": Path("/cfg/extra.json5")}

        with pytest.raises(ConfigConflictError, match="disks"):
            merge_overlays(base, overlay_1, overlay_2)

    def test_local_json5_wins_without_raising(self) -> None:
        """A local.json5-sourced overlay must override any key without raising ConfigConflictError.

        local.json5 is the designated machine-specific override file; it must be
        allowed to re-define any key already claimed by a non-local overlay.
        """
        base: dict = {}
        overlay_non_local = {"paths": "/original", "__source__": Path("/cfg/paths.json5")}
        # Source ends with 'local.json5' — triggers the last-wins branch.
        overlay_local = {"paths": "/machine-specific", "__source__": Path("/cfg/local.json5")}

        # Must not raise, and the local value must win.
        result = merge_overlays(base, overlay_non_local, overlay_local)

        assert result["paths"] == "/machine-specific"
        assert "__source__" not in result
