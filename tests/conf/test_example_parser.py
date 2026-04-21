"""Tests for personalscraper.conf.example_parser.

Sub-phase 3.2: smoke tests — import and stub behaviour.
Sub-phase 3.3: full parser tests (added below after implementation).
Sub-phase 3.4: integration tests against config.example.json5.
"""

from pathlib import Path

import pytest

from personalscraper.conf.example_parser import Prompt, parse_example

# ---------------------------------------------------------------------------
# Fixtures directory helper
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# 3.2 — Smoke tests: import + stub returns empty list
# ---------------------------------------------------------------------------


class TestExampleParserSmoke:
    """Minimal smoke tests verifying the module structure is correct."""

    def test_prompt_dataclass_is_frozen(self) -> None:
        """Prompt is a frozen dataclass — immutable after creation."""
        p = Prompt(key_path="foo.bar", comment="a comment", default_value='"hello"')
        with pytest.raises(AttributeError):
            p.key_path = "other"  # type: ignore[misc]

    def test_prompt_fields_accessible(self) -> None:
        """Prompt exposes key_path, comment, default_value fields."""
        p = Prompt(
            key_path="paths.staging_dir",
            comment="Staging directory",
            default_value='"/path/to/staging"',
        )
        assert p.key_path == "paths.staging_dir"
        assert p.comment == "Staging directory"
        assert p.default_value == '"/path/to/staging"'

    def test_stub_returns_empty_list(self, tmp_path: Path) -> None:
        """parse_example stub returns [] (implementation pending in 3.3)."""
        dummy = tmp_path / "dummy.json5"
        dummy.write_text("{ key: 1 }\n")
        result = parse_example(dummy)
        assert result == []

    def test_parse_example_returns_list_type(self, tmp_path: Path) -> None:
        """parse_example always returns a list (even on stub)."""
        dummy = tmp_path / "empty.json5"
        dummy.write_text("{}\n")
        result = parse_example(dummy)
        assert isinstance(result, list)
