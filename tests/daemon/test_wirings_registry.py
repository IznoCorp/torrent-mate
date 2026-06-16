"""Tests for the multi-project wiring builder + N=1 back-compat (ingress-multiproject §3.1 / §9).

Covers ``_wirings_from_registry`` / ``_load_wirings``: N=1 yields a 1-element list with the LEGACY
FLAT store layout (no state_root, multi_project=False) — byte-identical to today; N>1 yields one
wiring per ENABLED entry with per-project sub-roots + multi_project=True; a disabled entry is
skipped; the multi-org token_ref loads from <root>/tokens/<ref>; and the OLD-shaped projects.json
(no new keys) loads unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH
from kanbanmate.core.registry_resolve import safe_project_id
from kanbanmate.daemon.loop import _load_wirings, _wirings_from_registry


def _write_clone(tmp_path: Path, name: str) -> Path:
    """Create a clone dir with a minimal columns.yml and return its path."""
    clone = tmp_path / name
    cols = clone / CLONE_COLUMNS_RELPATH
    cols.parent.mkdir(parents=True, exist_ok=True)
    cols.write_text("columns: []\n", encoding="utf-8")
    return clone


def _write_registry(root: Path, entries: dict[str, dict[str, object]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects.json").write_text(json.dumps(entries), encoding="utf-8")


def _seed_token(root: Path, name: str = "token", value: str = "tok") -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_n1_legacy_flat_layout_byte_identical(tmp_path: Path) -> None:
    """N=1: one wiring, NO state_root (flat layout), multi_project=False — back-compat."""
    clone = _write_clone(tmp_path, "clone-a")
    _write_registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "o/r1",
                "clone": str(clone),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
            }
        },
    )
    _seed_token(tmp_path)

    wirings = _wirings_from_registry(tmp_path)

    assert len(wirings) == 1
    w = wirings[0]
    assert w.state_root == ""  # flat layout — no sub-root
    assert w.multi_project is False
    assert w.token == "tok"


def test_old_shaped_registry_loads_unchanged(tmp_path: Path) -> None:
    """An OLD projects.json (no org/enabled/ingress/token_ref) loads with the defaults applied."""
    clone = _write_clone(tmp_path, "clone-a")
    # Deliberately omit the new keys — exactly what a deployed N=1 file looks like.
    _write_registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "o/r1",
                "clone": str(clone),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
                "option_map": {},
                "config_dir": "",
                "dev_repo_path": "",
            }
        },
    )
    _seed_token(tmp_path)

    wirings = _wirings_from_registry(tmp_path)
    assert len(wirings) == 1
    # ingress defaults to webhook (entry default); multi_project False for N=1.
    assert wirings[0].ingress == "webhook"
    assert wirings[0].multi_project is False


def test_n_gt_1_per_project_sub_roots(tmp_path: Path) -> None:
    """N>1: one wiring per enabled entry, each with a per-project sub-root + multi_project=True."""
    clone_a = _write_clone(tmp_path, "clone-a")
    clone_b = _write_clone(tmp_path, "clone-b")
    _write_registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "o/r1",
                "clone": str(clone_a),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
                "ingress": "polling",
            },
            "PVT_B": {
                "repo": "o/r2",
                "clone": str(clone_b),
                "project_id": "PVT_B",
                "status_field_node_id": "F",
                "ingress": "webhook",
            },
        },
    )
    _seed_token(tmp_path)

    wirings = _wirings_from_registry(tmp_path)

    assert len(wirings) == 2
    by_pid = {w.project_id: w for w in wirings}
    assert by_pid["PVT_A"].multi_project is True
    # The sub-root is keyed by the COLLISION-RESISTANT slug (#6); assert via safe_project_id so the
    # test tracks the slug format (it is the SAME function the helpers read the sub-root with).
    assert by_pid["PVT_A"].state_root == str(tmp_path / "projects" / safe_project_id("PVT_A"))
    assert by_pid["PVT_B"].state_root == str(tmp_path / "projects" / safe_project_id("PVT_B"))
    assert by_pid["PVT_A"].ingress == "polling"
    assert by_pid["PVT_B"].ingress == "webhook"


def test_disabled_entry_skipped(tmp_path: Path) -> None:
    """An enabled=false entry is not wired; one enabled + one disabled collapses to N=1 flat."""
    clone_a = _write_clone(tmp_path, "clone-a")
    clone_b = _write_clone(tmp_path, "clone-b")
    _write_registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "o/r1",
                "clone": str(clone_a),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
            },
            "PVT_B": {
                "repo": "o/r2",
                "clone": str(clone_b),
                "project_id": "PVT_B",
                "status_field_node_id": "F",
                "enabled": False,
            },
        },
    )
    _seed_token(tmp_path)

    wirings = _wirings_from_registry(tmp_path)
    assert [w.project_id for w in wirings] == ["PVT_A"]
    # Sole ENABLED entry → N=1 collapse: flat layout, single-project.
    assert wirings[0].multi_project is False
    assert wirings[0].state_root == ""


def test_token_ref_loads_per_org_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-empty token_ref loads from <root>/tokens/<ref> (the multi-org token model, §6)."""
    clone_a = _write_clone(tmp_path, "clone-a")
    clone_b = _write_clone(tmp_path, "clone-b")
    _write_registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "orgA/r1",
                "clone": str(clone_a),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
            },
            "PVT_B": {
                "repo": "orgB/r2",
                "clone": str(clone_b),
                "project_id": "PVT_B",
                "status_field_node_id": "F",
                "token_ref": "orgB",
            },
        },
    )
    _seed_token(tmp_path, "token", "shared-tok")
    _seed_token(tmp_path, "tokens/orgB", "orgB-tok")

    # $KANBAN_TOKEN must not win here (the env override path) — unset it via monkeypatch so it is
    # restored after the test (no global env leakage, #7d).
    monkeypatch.delenv("KANBAN_TOKEN", raising=False)

    wirings = _wirings_from_registry(tmp_path)
    by_pid = {w.project_id: w for w in wirings}
    assert by_pid["PVT_A"].token == "shared-tok"
    assert by_pid["PVT_B"].token == "orgB-tok"


def test_all_disabled_raises(tmp_path: Path) -> None:
    """Every project disabled → FileNotFoundError (nothing to drive)."""
    clone = _write_clone(tmp_path, "clone-a")
    _write_registry(
        tmp_path,
        {
            "PVT_A": {
                "repo": "o/r1",
                "clone": str(clone),
                "project_id": "PVT_A",
                "status_field_node_id": "F",
                "enabled": False,
            }
        },
    )
    _seed_token(tmp_path)
    with pytest.raises(FileNotFoundError):
        _wirings_from_registry(tmp_path)


def test_load_wirings_config_yml_override_single(tmp_path: Path) -> None:
    """A config.yml override yields a 1-element list (the single-project override path)."""
    import yaml

    columns = tmp_path / "columns.yml"
    columns.write_text("columns: []\n", encoding="utf-8")
    config = tmp_path / "config.yml"
    config.write_text(
        yaml.dump(
            {
                "token": "ovr-tok",
                "project_id": "PVT_OVR",
                "repo": "o/r",
                "clone_dir": str(tmp_path / "clone"),
                "columns_path": str(columns),
                "kanban_root": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )
    wirings = _load_wirings(config)
    assert len(wirings) == 1
    assert wirings[0].project_id == "PVT_OVR"
    assert wirings[0].state_root == ""  # override path keeps the flat layout
