"""Tests for kanbanmate.app.onboard — path confinement + dir listing."""

from pathlib import Path

import pytest

import kanbanmate.app.onboard as onboard


def test_path_confined_true_under_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "dev" / "Proj").mkdir(parents=True)
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    assert onboard.path_is_confined(str(tmp_path / "dev" / "Proj")) is True


def test_path_confined_false_outside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "dev").mkdir()
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    assert onboard.path_is_confined("/etc") is False


def test_list_dir_outside_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "dev").mkdir()
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(tmp_path / "dev"),))
    with pytest.raises(PermissionError):
        onboard.list_dir("/etc")


def test_list_dir_lists_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "dev"
    (base / "ProjA").mkdir(parents=True)
    (base / "file.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(base),))
    out = onboard.list_dir(str(base))
    entries = out["entries"]
    assert isinstance(entries, list)
    names = {e["name"]: e["is_dir"] for e in entries}
    assert names["ProjA"] is True and names["file.txt"] is False
