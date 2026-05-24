"""Tests for io_utils atomic write helpers."""

import json
import os
from pathlib import Path

import pytest

from personalscraper.io_utils import (
    _atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
)


def test_atomic_write_text_writes_content(tmp_path: Path) -> None:
    """Round-trip: written content is readable back."""
    path = tmp_path / "test.txt"
    atomic_write_text(path, "hello world")
    assert path.read_text() == "hello world"


def test_atomic_write_text_fsyncs_file_and_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both the file fd and the parent dir fd receive fsync."""
    calls: list[int] = []
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))
    path = tmp_path / "test.txt"
    atomic_write_text(path, "hello")
    assert len(calls) >= 2, f"expected >= 2 fsync calls, got {len(calls)}"


def test_atomic_write_text_creates_parent_dir(tmp_path: Path) -> None:
    """Parent directories are created automatically."""
    path = tmp_path / "nested" / "dir" / "test.txt"
    atomic_write_text(path, "content")
    assert path.read_text() == "content"


def test_atomic_write_text_overwrites_existing(tmp_path: Path) -> None:
    """Overwriting an existing file works and leaves no .tmp residue."""
    path = tmp_path / "test.txt"
    atomic_write_text(path, "first")
    assert path.read_text() == "first"
    atomic_write_text(path, "second")
    assert path.read_text() == "second"
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_atomic_write_text_custom_encoding(tmp_path: Path) -> None:
    """Non-UTF-8 encoding round-trips correctly."""
    path = tmp_path / "test.txt"
    content = "café"
    atomic_write_text(path, content, encoding="latin-1")
    assert path.read_bytes().decode("latin-1") == content


def test_atomic_write_json_still_works_after_refactor(tmp_path: Path) -> None:
    """Regression: atomic_write_json still produces correct JSON.

    Internal refactor to _atomic_write_bytes should not change behaviour.
    """
    path = tmp_path / "data.json"
    data = {"key": "value", "nested": {"a": 1}, "unicode": "café"}
    atomic_write_json(path, data)
    assert json.loads(path.read_text()) == data


def test_atomic_write_json_indent_still_works(tmp_path: Path) -> None:
    """Regression: indent parameter of atomic_write_json still honoured."""
    path = tmp_path / "data.json"
    atomic_write_json(path, {"a": 1}, indent=4)
    raw = path.read_text()
    assert "    " in raw
    assert json.loads(raw) == {"a": 1}


def test_atomic_write_bytes_direct(tmp_path: Path) -> None:
    """_atomic_write_bytes can be called directly."""
    path = tmp_path / "test.bin"
    _atomic_write_bytes(path, b"\x00\x01\x02")
    assert path.read_bytes() == b"\x00\x01\x02"
