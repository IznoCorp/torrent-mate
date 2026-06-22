from pathlib import Path

from kanbanmate.cli.init import (
    ProjectEntry,
    _delete_project,
    _load_registry,
    _projects_path,
    _upsert_project,
)


def test_delete_existing_removes_entry(tmp_path: Path) -> None:
    path = _projects_path(tmp_path)
    entry = ProjectEntry(
        repo="O/r",
        clone=str(tmp_path / "c"),
        project_id="PVT_x",
        status_field_node_id="FLD",
    )
    _upsert_project(path, "PVT_x", entry)
    assert "PVT_x" in _load_registry(path)
    assert _delete_project(path, "PVT_x") is True
    assert "PVT_x" not in _load_registry(path)


def test_delete_absent_returns_false(tmp_path: Path) -> None:
    path = _projects_path(tmp_path)
    _upsert_project(
        path,
        "PVT_x",
        ProjectEntry(
            repo="O/r",
            clone="c",
            project_id="PVT_x",
            status_field_node_id="FLD",
        ),
    )
    assert _delete_project(path, "PVT_missing") is False
    assert "PVT_x" in _load_registry(path)  # untouched
