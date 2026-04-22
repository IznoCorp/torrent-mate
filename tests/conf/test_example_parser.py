"""Tests for personalscraper.conf.example_parser.

Sub-phase 3.2: smoke tests — module structure and Prompt dataclass.
Sub-phase 3.3: full parser tests with multiple fixture files.
Sub-phase 3.4: integration tests against config.example.json5 (added in 3.4).
"""

from pathlib import Path

import pytest

from personalscraper.conf.example_parser import Prompt, parse_example

# ---------------------------------------------------------------------------
# Fixtures directory helper
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# 3.2 — Smoke tests: module structure + Prompt dataclass
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

    def test_parse_example_returns_list_type(self, tmp_path: Path) -> None:
        """parse_example always returns a list."""
        dummy = tmp_path / "empty.json5"
        dummy.write_text("{}\n")
        result = parse_example(dummy)
        assert isinstance(result, list)

    def test_parse_example_empty_object_no_prompts(self, tmp_path: Path) -> None:
        """An empty JSON5 object produces no prompts."""
        dummy = tmp_path / "empty.json5"
        dummy.write_text("{}\n")
        result = parse_example(dummy)
        assert result == []


# ---------------------------------------------------------------------------
# 3.3 — Full parser tests
# ---------------------------------------------------------------------------


class TestParserSimple:
    """Tests against example_simple.json5 (1 key, 1 comment)."""

    def test_simple_one_prompt(self) -> None:
        """Single key with comment produces exactly one Prompt."""
        path = FIXTURES_DIR / "example_simple.json5"
        prompts = parse_example(path)
        assert len(prompts) == 1

    def test_simple_key_path(self) -> None:
        """Top-level key has plain key_path (no dot prefix)."""
        prompts = parse_example(FIXTURES_DIR / "example_simple.json5")
        assert prompts[0].key_path == "api_key"

    def test_simple_comment(self) -> None:
        """Comment preceding the key is captured correctly."""
        prompts = parse_example(FIXTURES_DIR / "example_simple.json5")
        assert prompts[0].comment == "The API key for authentication"

    def test_simple_default_value(self) -> None:
        """Default value is the raw JSON5 string literal."""
        prompts = parse_example(FIXTURES_DIR / "example_simple.json5")
        assert prompts[0].default_value == '"my-secret-key"'


class TestParserNested:
    """Tests against example_nested.json5 (nested objects)."""

    def test_nested_produces_four_prompts(self) -> None:
        """Two levels of nesting produce 4 leaf prompts total."""
        prompts = parse_example(FIXTURES_DIR / "example_nested.json5")
        assert len(prompts) == 4

    def test_nested_dotted_key_paths(self) -> None:
        """Nested keys use dotted notation."""
        prompts = parse_example(FIXTURES_DIR / "example_nested.json5")
        paths = [p.key_path for p in prompts]
        assert "paths.torrent_complete_dir" in paths
        assert "paths.staging_dir" in paths
        assert "library.video.preferred_codec" in paths
        assert "library.video.max_size_movie_gb" in paths

    def test_nested_comments_attached(self) -> None:
        """Comments are attached to the correct nested key."""
        prompts = parse_example(FIXTURES_DIR / "example_nested.json5")
        by_path = {p.key_path: p for p in prompts}
        assert by_path["paths.torrent_complete_dir"].comment == ("Directory where completed torrents land")
        assert by_path["library.video.preferred_codec"].comment == ("Target codec for encoding recommendations")

    def test_nested_default_values(self) -> None:
        """Default values are parsed correctly for nested scalar keys."""
        prompts = parse_example(FIXTURES_DIR / "example_nested.json5")
        by_path = {p.key_path: p for p in prompts}
        assert by_path["paths.torrent_complete_dir"].default_value == ('"/torrents/complete"')
        assert by_path["library.video.max_size_movie_gb"].default_value == "4.0"


class TestParserArrays:
    """Tests against example_arrays.json5 (inline arrays + object arrays)."""

    def test_arrays_total_prompts(self) -> None:
        """Inline array + 2 object-in-array elements = 7 prompts total."""
        prompts = parse_example(FIXTURES_DIR / "example_arrays.json5")
        # fallback_codecs (1) + disks[0].id, path, categories (3) + disks[1].id, path, categories (3)
        assert len(prompts) == 7

    def test_inline_array_as_single_prompt(self) -> None:
        """An inline array value (key: [...]) emits one Prompt with the full literal."""
        prompts = parse_example(FIXTURES_DIR / "example_arrays.json5")
        by_path = {p.key_path: p for p in prompts}
        assert "fallback_codecs" in by_path
        assert by_path["fallback_codecs"].default_value == '["av1", "h264"]'
        assert by_path["fallback_codecs"].comment == ("Accepted fallback codecs when preferred is unavailable")

    def test_object_array_first_element_indexed(self) -> None:
        """First object in array uses [0] index."""
        prompts = parse_example(FIXTURES_DIR / "example_arrays.json5")
        by_path = {p.key_path: p for p in prompts}
        assert "disks[0].id" in by_path
        assert by_path["disks[0].id"].default_value == '"drive_a"'
        assert by_path["disks[0].id"].comment == "Disk identifier used in CLI and logs"

    def test_object_array_second_element_indexed(self) -> None:
        """Second object in array uses [1] index."""
        prompts = parse_example(FIXTURES_DIR / "example_arrays.json5")
        by_path = {p.key_path: p for p in prompts}
        assert "disks[1].id" in by_path
        assert by_path["disks[1].id"].default_value == '"drive_b"'

    def test_object_array_nested_fields(self) -> None:
        """Each field in array object gets correct dotted path."""
        prompts = parse_example(FIXTURES_DIR / "example_arrays.json5")
        by_path = {p.key_path: p for p in prompts}
        assert "disks[0].path" in by_path
        assert "disks[0].categories" in by_path
        assert "disks[1].path" in by_path
        assert "disks[1].categories" in by_path


class TestParserComments:
    """Tests against example_comments.json5 (comment styles and reset logic)."""

    def test_block_comment_before_key(self) -> None:
        """A /* */ block comment on a single line is captured."""
        prompts = parse_example(FIXTURES_DIR / "example_comments.json5")
        by_path = {p.key_path: p for p in prompts}
        assert "block_key" in by_path
        assert by_path["block_key"].comment == "Block comment before a key"

    def test_multiline_block_comment(self) -> None:
        """A /* */ block comment spanning multiple lines is joined correctly."""
        prompts = parse_example(FIXTURES_DIR / "example_comments.json5")
        by_path = {p.key_path: p for p in prompts}
        assert "multiline_key" in by_path
        # The two content lines should both appear in the comment
        assert "Multi-line block comment" in by_path["multiline_key"].comment
        assert "spanning several lines" in by_path["multiline_key"].comment

    def test_single_line_comment(self) -> None:
        """A // comment is attached to the following key."""
        prompts = parse_example(FIXTURES_DIR / "example_comments.json5")
        by_path = {p.key_path: p for p in prompts}
        assert by_path["single_key"].comment == "Single line comment"

    def test_comment_without_key_resets_buffer(self) -> None:
        """A blank line after a comment resets the buffer — no spurious prompt."""
        prompts = parse_example(FIXTURES_DIR / "example_comments.json5")
        by_path = {p.key_path: p for p in prompts}
        # orphan_reset_key follows a blank line, so its comment should be empty
        assert "orphan_reset_key" in by_path
        assert by_path["orphan_reset_key"].comment == ""

    def test_two_consecutive_comments_joined(self) -> None:
        """Two consecutive // lines are accumulated into one comment."""
        prompts = parse_example(FIXTURES_DIR / "example_comments.json5")
        by_path = {p.key_path: p for p in prompts}
        comment = by_path["two_line_key"].comment
        assert "Comment followed immediately by next comment" in comment
        assert "Second line of comment" in comment

    def test_no_spurious_prompts_from_comments(self) -> None:
        """Comments not followed by a key do not produce extra prompts."""
        prompts = parse_example(FIXTURES_DIR / "example_comments.json5")
        paths = [p.key_path for p in prompts]
        # Only the 5 real keys should appear
        assert len(paths) == 5
        assert sorted(paths) == sorted(["block_key", "multiline_key", "single_key", "orphan_reset_key", "two_line_key"])


class TestParserFull:
    """Tests against example_full.json5 (copy of config.example.json5)."""

    def test_full_parses_without_error(self) -> None:
        """Parsing the full example file raises no exception."""
        prompts = parse_example(FIXTURES_DIR / "example_full.json5")
        assert isinstance(prompts, list)

    def test_full_produces_sensible_number_of_prompts(self) -> None:
        """Full example produces at least 20 prompts (all leaf keys)."""
        prompts = parse_example(FIXTURES_DIR / "example_full.json5")
        assert len(prompts) >= 20

    def test_full_key_paths_are_nonempty(self) -> None:
        """All prompts have non-empty key_path."""
        prompts = parse_example(FIXTURES_DIR / "example_full.json5")
        for p in prompts:
            assert p.key_path, f"Empty key_path in prompt: {p}"

    def test_full_contains_expected_top_level_keys(self) -> None:
        """Key paths from the top-level config fields are present."""
        prompts = parse_example(FIXTURES_DIR / "example_full.json5")
        paths = {p.key_path for p in prompts}
        assert "config_version" in paths
        assert "paths.torrent_complete_dir" in paths
        assert "paths.staging_dir" in paths
        assert "paths.data_dir" in paths

    def test_full_contains_disk_array_fields(self) -> None:
        """Disk array elements are parsed with correct indexed paths."""
        prompts = parse_example(FIXTURES_DIR / "example_full.json5")
        paths = {p.key_path for p in prompts}
        assert "disks[0].id" in paths
        assert "disks[0].path" in paths
        assert "disks[0].categories" in paths

    def test_full_contains_library_nested_fields(self) -> None:
        """Deep nested library fields are parsed correctly."""
        prompts = parse_example(FIXTURES_DIR / "example_full.json5")
        paths = {p.key_path for p in prompts}
        assert "library.video.preferred_codec" in paths
        assert "library.audio.profile_priority" in paths
        assert "library.subtitles.required_languages" in paths

    def test_full_default_values_are_nonempty(self) -> None:
        """All prompts have non-empty default_value."""
        prompts = parse_example(FIXTURES_DIR / "example_full.json5")
        for p in prompts:
            assert p.default_value, f"Empty default_value in prompt: {p}"


# ---------------------------------------------------------------------------
# 3.4 — Integration tests: parse_example(config.example.json5) validation
# ---------------------------------------------------------------------------


class TestIntegrationConfigExample:
    """Integration tests against config.example.json5 (read-only, never modified).

    These tests validate:
    1. parse_example returns a Prompt per leaf key.
    2. Each Prompt has a non-empty key_path.
    3. Documented keys have non-empty comments (majority — not every key in
       example.json5 has an inline comment; categories without individual
       comments and some shared-comment genre_mapping keys produce empty
       comments, which is correct parser behaviour, not a bug).
    4. Each default_value is a valid JSON5 literal (round-trips via json5.loads).
    """

    _EXAMPLE_PATH = Path(__file__).parent.parent.parent / "config.example.json5"

    def test_parses_config_example_without_error(self) -> None:
        """parse_example(config.example.json5) raises no exception."""
        prompts = parse_example(self._EXAMPLE_PATH)
        assert isinstance(prompts, list)
        assert len(prompts) > 0

    def test_produces_prompt_per_leaf_key(self) -> None:
        """At least one Prompt per top-level section of config.example.json5."""
        prompts = parse_example(self._EXAMPLE_PATH)
        paths = {p.key_path for p in prompts}
        # All top-level leaf keys and representative nested keys must be present
        required = {
            "config_version",
            "paths.torrent_complete_dir",
            "paths.staging_dir",
            "paths.data_dir",
            "custom_categories",
            "disks[0].id",
            "disks[0].path",
            "disks[0].categories",
            "anime_rule.enabled",
            "anime_rule.requires_genre_id",
            "anime_rule.maps_to",
            "genre_mapping.default_movies_category",
            "genre_mapping.default_tv_category",
            "library.video.preferred_codec",
            "library.audio.profile_priority",
            "library.subtitles.required_languages",
            "library.encoding_rules",
        }
        missing = required - paths
        assert not missing, f"Missing key_paths: {sorted(missing)}"

    def test_all_key_paths_are_nonempty_strings(self) -> None:
        """Every Prompt has a non-empty key_path string."""
        prompts = parse_example(self._EXAMPLE_PATH)
        for p in prompts:
            assert isinstance(p.key_path, str), f"key_path not str: {p}"
            assert p.key_path, f"Empty key_path: {p}"

    def test_majority_of_prompts_have_comments(self) -> None:
        """Most keys in config.example.json5 are documented.

        At least 70% of prompts should have a non-empty comment. This reflects
        that the example file documents all user-facing fields. Some keys (e.g.
        category folder_name entries, genre_mapping sibling keys sharing one
        comment) legitimately produce empty comments due to parser reset logic.
        """
        prompts = parse_example(self._EXAMPLE_PATH)
        with_comment = sum(1 for p in prompts if p.comment)
        ratio = with_comment / len(prompts)
        assert ratio >= 0.7, f"Only {with_comment}/{len(prompts)} prompts have comments ({ratio:.0%} < 70%)"

    def test_critical_prompts_have_comments(self) -> None:
        """Critical user-facing fields must have non-empty comments."""
        prompts = parse_example(self._EXAMPLE_PATH)
        by_path = {p.key_path: p for p in prompts}
        critical = [
            "paths.torrent_complete_dir",
            "paths.staging_dir",
            "paths.data_dir",
            "disks[0].id",
            "disks[0].path",
            "disks[0].categories",
            "anime_rule.requires_genre_id",
            "anime_rule.maps_to",
            "library.video.preferred_codec",
            "library.audio.profile_priority",
        ]
        for key in critical:
            assert key in by_path, f"Key not found: {key!r}"
            assert by_path[key].comment, f"Missing comment for critical key: {key!r}"

    def test_all_default_values_are_valid_json5_literals(self) -> None:
        """Every default_value can be parsed as a JSON5 literal.

        Validated by wrapping in ``{"x": <value>}`` and calling json5.loads.
        """
        import json5

        prompts = parse_example(self._EXAMPLE_PATH)
        invalid: list[tuple[str, str, str]] = []
        for p in prompts:
            try:
                json5.loads('{"x": ' + p.default_value + "}")
            except Exception as exc:
                invalid.append((p.key_path, p.default_value, str(exc)))

        assert not invalid, f"{len(invalid)} prompts have invalid JSON5 default_value:\n" + "\n".join(
            f"  {kp!r}: {dv!r} → {err}" for kp, dv, err in invalid
        )

    def test_genre_mapping_numeric_key_paths(self) -> None:
        """Genre mapping keys use quoted numeric keys in the key_path."""
        prompts = parse_example(self._EXAMPLE_PATH)
        paths = {p.key_path for p in prompts}
        # Check a few specific genre_mapping entries
        assert "genre_mapping.tmdb_movies.16" in paths
        assert "genre_mapping.tmdb_movies.99" in paths
        assert "genre_mapping.tvdb.27" in paths

    def test_library_codec_lists_are_inline_array_prompts(self) -> None:
        """Inline array values in library.video are emitted as single Prompts."""
        prompts = parse_example(self._EXAMPLE_PATH)
        by_path = {p.key_path: p for p in prompts}
        # These are inline: fallback_codecs: ["av1"],
        assert "library.video.fallback_codecs" in by_path
        assert "library.video.rejected_codecs" in by_path
        # Default values should be array literals
        assert by_path["library.video.fallback_codecs"].default_value.startswith("[")
        assert by_path["library.video.rejected_codecs"].default_value.startswith("[")
