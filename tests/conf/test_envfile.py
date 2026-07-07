"""Tests for personalscraper.conf.envfile — write_env_keys and read_env_catalog."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from personalscraper.conf.envfile import read_env_catalog, write_env_keys

# ---------------------------------------------------------------------------
# write_env_keys
# ---------------------------------------------------------------------------


class TestWriteEnvKeysUpsert:
    """Existing keys are replaced in place; comments, blanks, and unrelated keys are preserved."""

    def test_replaces_existing_key_in_place(self, tmp_path: Path) -> None:
        """A key present in the file is replaced on its original line."""
        env_path = tmp_path / ".env"
        env_path.write_text("# a comment\nSECRET=old\nUNRELATED=keep\n")
        write_env_keys({"SECRET": "new"}, env_path)
        assert env_path.read_text() == "# a comment\nSECRET=new\nUNRELATED=keep\n"

    def test_preserves_comments_and_blanks(self, tmp_path: Path) -> None:
        """Comments and blank lines around the replaced key are preserved."""
        env_path = tmp_path / ".env"
        env_path.write_text("# top comment\n\nSECRET=old\n\n# bottom comment\n")
        write_env_keys({"SECRET": "new"}, env_path)
        assert env_path.read_text() == "# top comment\n\nSECRET=new\n\n# bottom comment\n"

    def test_preserves_unrelated_keys(self, tmp_path: Path) -> None:
        """Keys not present in the upsert dict are left untouched."""
        env_path = tmp_path / ".env"
        env_path.write_text("KEEP_ME=val\nREPLACE_ME=old\nALSO_KEEP=yes\n")
        write_env_keys({"REPLACE_ME": "new"}, env_path)
        assert env_path.read_text() == "KEEP_ME=val\nREPLACE_ME=new\nALSO_KEEP=yes\n"

    def test_preserves_key_order(self, tmp_path: Path) -> None:
        """Replaced keys stay where they were; appended keys go at the end."""
        env_path = tmp_path / ".env"
        env_path.write_text("A=1\nB=2\n")
        write_env_keys({"B": "bb", "C": "cc"}, env_path)
        assert env_path.read_text() == "A=1\nB=bb\nC=cc\n"

    def test_does_not_touch_comment_lines_starting_with_hash(self, tmp_path: Path) -> None:
        """A commented-out KEY=val line must not be matched as a key."""
        env_path = tmp_path / ".env"
        env_path.write_text("# COMM_OUT=leave\nCOMM_OUT=real\n")
        write_env_keys({"COMM_OUT": "new"}, env_path)
        assert env_path.read_text() == "# COMM_OUT=leave\nCOMM_OUT=new\n"

    def test_lstrip_matches_indented_keys(self, tmp_path: Path) -> None:
        """Keys with leading whitespace are matched after lstrip (original behaviour)."""
        env_path = tmp_path / ".env"
        env_path.write_text("  INDENTED=val\nREAL_KEY=old\n")
        write_env_keys({"INDENTED": "new", "REAL_KEY": "new2"}, env_path)
        # INDENTED is matched (lstrip removes leading whitespace), so it is
        # replaced IN PLACE — the leading whitespace is lost (line becomes
        # "INDENTED=new").  This matches the behaviour of the extracted helper.
        assert env_path.read_text() == "INDENTED=new\nREAL_KEY=new2\n"

    def test_replaces_multiple_keys_in_one_call(self, tmp_path: Path) -> None:
        """Multiple keys can be upserted in a single call."""
        env_path = tmp_path / ".env"
        env_path.write_text("A=1\nB=2\nC=3\n")
        write_env_keys({"A": "aa", "C": "cc"}, env_path)
        assert env_path.read_text() == "A=aa\nB=2\nC=cc\n"

    def test_appends_missing_keys_at_end(self, tmp_path: Path) -> None:
        """Keys not already present in the file are appended at the end."""
        env_path = tmp_path / ".env"
        env_path.write_text("EXISTING=yes\n")
        write_env_keys({"NEW_KEY": "value"}, env_path)
        assert env_path.read_text() == "EXISTING=yes\nNEW_KEY=value\n"

    def test_creates_file_when_absent(self, tmp_path: Path) -> None:
        """When the .env file does not exist, it is created."""
        env_path = tmp_path / ".env"
        assert not env_path.exists()
        write_env_keys({"SECRET": "val"}, env_path)
        assert env_path.read_text() == "SECRET=val\n"

    def test_handles_empty_existing_file(self, tmp_path: Path) -> None:
        """An empty .env file is handled correctly (new keys appended)."""
        env_path = tmp_path / ".env"
        env_path.write_text("")
        write_env_keys({"SECRET": "val"}, env_path)
        assert env_path.read_text() == "SECRET=val\n"

    def test_handles_existing_file_with_only_comments(self, tmp_path: Path) -> None:
        """A file with only comments gets the key appended after the comments."""
        env_path = tmp_path / ".env"
        env_path.write_text("# just a comment\n")
        write_env_keys({"KEY": "val"}, env_path)
        assert env_path.read_text() == "# just a comment\nKEY=val\n"


class TestWriteEnvKeysAtomicity:
    """The write uses a same-directory temp file + os.replace for atomicity."""

    def test_uses_temp_file_and_os_replace(self, tmp_path: Path) -> None:
        """The atomic write creates a .tmp file and renames it via os.replace."""
        env_path = tmp_path / ".env"
        env_path.write_text("OLD=value\n")

        real_os_replace = os.replace
        temp_files_seen: list[str] = []

        def tracking_replace(src: str, dst: str) -> None:
            temp_files_seen.append(src)
            real_os_replace(src, dst)

        with mock.patch("os.replace", side_effect=tracking_replace):
            write_env_keys({"NEW": "v"}, env_path)

        assert len(temp_files_seen) == 1
        assert temp_files_seen[0].startswith(str(tmp_path))
        assert ".env." in temp_files_seen[0]
        assert temp_files_seen[0].endswith(".tmp")
        # Verify the content actually landed.
        assert env_path.read_text() == "OLD=value\nNEW=v\n"

    def test_cleans_up_temp_file_on_error(self, tmp_path: Path) -> None:
        """If os.replace fails, the temp file is cleaned up and original is untouched."""
        env_path = tmp_path / ".env"
        env_path.write_text("KEEP=me\n")

        # After fdopen succeeds, os.replace raises — temp file must be cleaned.
        with mock.patch("os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError):
                write_env_keys({"KEY": "val"}, env_path)

        # Original file must be untouched.
        assert env_path.read_text() == "KEEP=me\n"
        # No .tmp file must be left behind.
        tmp_files = list(tmp_path.glob(".env.*.tmp"))
        assert len(tmp_files) == 0


# ---------------------------------------------------------------------------
# read_env_catalog
# ---------------------------------------------------------------------------

CATALOG_FIXTURE = """\
# ── Section One ──────────────────────────────
# This is a description for KEY_ONE.
KEY_ONE=default

# ── Section Two ──────────────────────────────
# Multi-line description
# for KEY_TWO that spans.
KEY_TWO=

# Single-line description.
KEY_THREE=some_value

# ── Section Three ────────────────────────────

KEY_FOUR=value
"""


class TestReadEnvCatalog:
    """Parse .env.example into {KEY: description}."""

    def test_parses_keys_and_descriptions(self, tmp_path: Path) -> None:
        """Keys and their comment descriptions are correctly extracted."""
        path = tmp_path / ".env.example"
        path.write_text(CATALOG_FIXTURE)
        catalog = read_env_catalog(path)
        assert catalog["KEY_ONE"] == "This is a description for KEY_ONE."
        assert catalog["KEY_TWO"] == "Multi-line description for KEY_TWO that spans."
        assert catalog["KEY_THREE"] == "Single-line description."
        assert catalog["KEY_FOUR"] == ""

    def test_excludes_section_rule_lines(self, tmp_path: Path) -> None:
        """Section-rule comments (# ──) are excluded from descriptions."""
        path = tmp_path / ".env.example"
        path.write_text("# ── Section ──\n# real comment\nS_KEY=val\n")
        catalog = read_env_catalog(path)
        assert catalog["S_KEY"] == "real comment"

    def test_key_with_no_comment_gets_empty_string(self, tmp_path: Path) -> None:
        """A key with no preceding comment gets an empty description."""
        path = tmp_path / ".env.example"
        path.write_text("NO_COMMENT=val\n")
        catalog = read_env_catalog(path)
        assert catalog["NO_COMMENT"] == ""

    def test_blank_line_breaks_comment_run(self, tmp_path: Path) -> None:
        """Comments after a blank line do not attach to the next key."""
        path = tmp_path / ".env.example"
        path.write_text("# orphan comment\n\n# attached\nAFTER_BLANK=val\n")
        catalog = read_env_catalog(path)
        # The "# orphan comment" line is separated from AFTER_BLANK by a blank
        # line — only "# attached" should be included.
        assert catalog["AFTER_BLANK"] == "attached"

    def test_section_rule_resets_comment_accumulator(self, tmp_path: Path) -> None:
        """A section rule between comments resets, so preceding comments don't bleed."""
        path = tmp_path / ".env.example"
        path.write_text("# before section\n# ── Section ──\n# after section\nKEY=val\n")
        catalog = read_env_catalog(path)
        assert catalog["KEY"] == "after section"

    def test_key_not_starting_with_uppercase_is_ignored(self, tmp_path: Path) -> None:
        """Only keys matching ^[A-Z][A-Z0-9_]*= are recognized as catalog entries."""
        path = tmp_path / ".env.example"
        path.write_text("# desc\nkey_lower=val\nVALID_KEY=val\n")
        catalog = read_env_catalog(path)
        assert "key_lower" not in catalog
        assert "VALID_KEY" in catalog

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """An empty file yields an empty catalog."""
        path = tmp_path / ".env.example"
        path.write_text("")
        catalog = read_env_catalog(path)
        assert catalog == {}

    def test_handles_only_comments_file(self, tmp_path: Path) -> None:
        """A file with only comments and no keys yields an empty catalog."""
        path = tmp_path / ".env.example"
        path.write_text("# just comments\n# no keys here\n")
        catalog = read_env_catalog(path)
        assert catalog == {}

    def test_last_key_wins_on_duplicate(self, tmp_path: Path) -> None:
        """When the same key appears twice, the last occurrence wins."""
        path = tmp_path / ".env.example"
        path.write_text("# first desc\nKEY=1\n# second desc\nKEY=2\n")
        catalog = read_env_catalog(path)
        assert catalog["KEY"] == "second desc"

    def test_real_env_example_file(self, tmp_path: Path) -> None:
        """Smoke-test against a fragment that mirrors the real .env.example."""
        path = tmp_path / ".env.example"
        path.write_text("""\
# ── qBittorrent ──────────────────────────────
# Host and port live in config/torrent.json5 (clients.qbittorrent.host / .port).
# Only credentials belong here.
QBIT_USERNAME=admin
QBIT_PASSWORD=

# ── TMDB / TVDB ──────────────────────────────
TMDB_API_KEY=
TVDB_API_KEY=

# ── TorrentMate Web UI ────────────────────────
# Password hash for web UI login (generated by `personalscraper web set-password`).
WEB_PASSWORD_HASH=
# HS256 secret key for JWT session tokens.
WEB_JWT_SECRET=
""")
        catalog = read_env_catalog(path)
        assert catalog["QBIT_USERNAME"] == (
            "Host and port live in config/torrent.json5 "
            "(clients.qbittorrent.host / .port). "
            "Only credentials belong here."
        )
        # QBIT_PASSWORD has no comment lines immediately above it — the
        # QBIT_USERNAME line (a key, not a comment) breaks the comment run.
        assert catalog["QBIT_PASSWORD"] == ""
        assert catalog["TMDB_API_KEY"] == ""
        assert catalog["TVDB_API_KEY"] == ""
        assert catalog["WEB_PASSWORD_HASH"] == (
            "Password hash for web UI login (generated by `personalscraper web set-password`)."
        )
        assert catalog["WEB_JWT_SECRET"] == "HS256 secret key for JWT session tokens."

    def test_comment_without_hash_space(self, tmp_path: Path) -> None:
        """Comments without a space after # are still parsed."""
        path = tmp_path / ".env.example"
        path.write_text("#no-space\nKEY=val\n")
        catalog = read_env_catalog(path)
        assert catalog["KEY"] == "no-space"

    def test_key_can_contain_digits(self, tmp_path: Path) -> None:
        """Keys can contain digits after the first uppercase letter."""
        path = tmp_path / ".env.example"
        path.write_text("# desc\nKEY_2_WITH_123=val\n")
        catalog = read_env_catalog(path)
        assert catalog["KEY_2_WITH_123"] == "desc"
