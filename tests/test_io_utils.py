"""Tests for personalscraper.io_utils — dataclass JSON serialization helpers."""

import json

from personalscraper.io_utils import read_json, serialize_to_json, write_json
from personalscraper.verify.library_checks import LibraryValidationResult


class TestJsonSerialization:
    """Tests for JSON serialization helpers (validation output)."""

    def test_roundtrip_validation_result(self) -> None:
        """Serialize and deserialize a validation result."""
        result = LibraryValidationResult(
            validated_at="2026-04-15T12:00:00",
            disk_filter=None,
            category_filter=None,
            total_items=0,
            valid_count=0,
            fixed_count=0,
            issues_count=0,
            items=[],
        )
        json_str = serialize_to_json(result)
        parsed = json.loads(json_str)
        assert parsed["validated_at"] == "2026-04-15T12:00:00"
        assert parsed["total_items"] == 0

    def test_atomic_write_and_read(self, tmp_path) -> None:
        """Write to file atomically and read back."""
        result = LibraryValidationResult(
            validated_at="2026-04-15T12:00:00",
            disk_filter="Disk1",
            category_filter=None,
            total_items=0,
            valid_count=0,
            fixed_count=0,
            issues_count=0,
            items=[],
        )
        path = tmp_path / "test.json"
        write_json(result, path)
        assert path.exists()

        data = read_json(path)
        assert data["validated_at"] == "2026-04-15T12:00:00"
        assert data["disk_filter"] == "Disk1"
