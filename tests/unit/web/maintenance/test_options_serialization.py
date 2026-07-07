"""Tests for :func:`canonical_options_json` — the deterministic JSON serializer.

The canonical form produced by this function is what
``POST /api/maintenance/run`` stores in the ``options_json`` column of
``pipeline_run`` and what the 428 precondition compares by string equality.
Any change to the serialization format would break pre-existing precondition
comparisons, so these tests are a guardrail against accidental drift.
"""

from __future__ import annotations

from personalscraper.web.maintenance.registry import canonical_options_json


class TestCanonicalOptionsJson:
    """Unit tests for the canonical JSON options serializer."""

    def test_sorts_keys_alphabetically(self) -> None:
        """Keys are sorted, not insertion-order."""
        result = canonical_options_json({"b": 1, "a": 2})
        assert result == '{"a":2,"b":1}'

    def test_empty_dict(self) -> None:
        """Empty dict serializes to empty JSON object."""
        assert canonical_options_json({}) == "{}"

    def test_nested_dicts_sort_recursively(self) -> None:
        """Nested dict keys are also sorted."""
        result = canonical_options_json({"z": {"c": 3, "b": 2, "a": 1}, "a": 1})
        assert result == '{"a":1,"z":{"a":1,"b":2,"c":3}}'

    def test_deterministic_across_calls(self) -> None:
        """Two calls with the same logical dict produce identical strings."""
        d = {"mode": "full", "disk": "Disk1", "budget": 60}
        first = canonical_options_json(d)
        second = canonical_options_json(dict(d))  # fresh dict, same content
        assert first == second
        # Explicitly verify it's not just identity — it's re-serialized.
        assert first is not second  # different string objects

    def test_deterministic_across_insertion_order(self) -> None:
        """Insertion order does not affect output."""
        a = canonical_options_json({"x": 1, "y": 2})
        b = canonical_options_json({"y": 2, "x": 1})
        assert a == b

    def test_nested_list_values_preserved(self) -> None:
        """List values inside the dict are preserved as JSON arrays."""
        result = canonical_options_json({"tags": ["b", "a", "c"]})
        assert result == '{"tags":["b","a","c"]}'

    def test_bool_int_str_types(self) -> None:
        """Common option types serialize correctly."""
        result = canonical_options_json({"dry_run": True, "limit": 50, "disk": "Disk1"})
        assert result == '{"disk":"Disk1","dry_run":true,"limit":50}'

    def test_none_value(self) -> None:
        """None serializes to null."""
        assert canonical_options_json({"disk": None}) == '{"disk":null}'
