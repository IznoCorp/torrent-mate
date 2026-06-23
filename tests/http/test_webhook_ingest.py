"""Tests for the webhook external-move ingestion (keel step 5 B).

Covers the pure payload parsers (item id + Status name extraction with the Status-field
discriminator) and the :func:`ingest_external_move` orchestrator: a genuine external drag adopts
into ``board.json``; a self-echo (the incoming Status equals the current native placement — our own
mirror write) is DROPPED; a non-native project is a no-op; an unmappable Status / missing item id /
no Status change is a no-op; a first sighting (unplaced item) adopts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board
from kanbanmate.cli.init import ProjectEntry
from kanbanmate.http.webhook_ingest import (
    IngestOutcome,
    extract_item_id,
    extract_status_name,
    ingest_external_move,
)

_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: InProgress
    name: In Progress
"""

_STATUS_FIELD = "PVTSSF_status"


def _payload(
    *,
    project_id: str = "PVT_A",
    item_id: str | None = "PVTI_1",
    field_node_id: str | None = _STATUS_FIELD,
    field_type: str = "single_select",
    to_name: str | None = "In Progress",
) -> dict[str, Any]:
    """Build a ``projects_v2_item.edited`` payload with a single-select field-value change."""
    item: dict[str, Any] = {"project_node_id": project_id}
    if item_id is not None:
        item["node_id"] = item_id
    payload: dict[str, Any] = {"action": "edited", "projects_v2_item": item}
    if to_name is not None or field_node_id is not None:
        field_value: dict[str, Any] = {"field_type": field_type}
        if field_node_id is not None:
            field_value["field_node_id"] = field_node_id
        field_value["to"] = {"name": to_name} if to_name is not None else None
        payload["changes"] = {"field_value": field_value}
    return payload


def _entry(clone: Path, *, backend: str = "native") -> ProjectEntry:
    return ProjectEntry(
        repo="o/r",
        clone=str(clone),
        project_id="PVT_A",
        status_field_node_id=_STATUS_FIELD,
        board_backend=backend,
    )


def _setup_clone(tmp_path: Path) -> Path:
    """Write a clone with a ``.claude/kanban/columns.yml`` so name→key resolves."""
    clone = tmp_path / "clone"
    cols = clone / ".claude" / "kanban"
    cols.mkdir(parents=True)
    (cols / "columns.yml").write_text(_COLUMNS_YAML, encoding="utf-8")
    return clone


def _register_single(root: Path, entry: ProjectEntry) -> None:
    """Write a single-project projects.json (N=1 → flat store layout)."""
    from kanbanmate.cli.init import _projects_path, _upsert_project

    _upsert_project(_projects_path(root), entry.project_id, entry)


# ── pure parsers ──────────────────────────────────────────────────────────


def test_extract_item_id_present() -> None:
    assert extract_item_id(_payload(item_id="PVTI_9")) == "PVTI_9"


def test_extract_item_id_absent() -> None:
    assert extract_item_id({"projects_v2_item": {}}) is None
    assert extract_item_id({}) is None


def test_extract_status_name_matches_field_id() -> None:
    assert extract_status_name(_payload(to_name="In Progress"), _STATUS_FIELD) == "In Progress"


def test_extract_status_name_wrong_field_id_ignored() -> None:
    # A single-select edit on a DIFFERENT field (e.g. a custom chip) is not a Status move.
    p = _payload(field_node_id="PVTSSF_other", to_name="In Progress")
    assert extract_status_name(p, _STATUS_FIELD) is None


def test_extract_status_name_single_select_fallback_when_no_field_id() -> None:
    # Old-shaped entry with no recorded status field id → accept any single_select change.
    p = _payload(field_node_id=None, field_type="single_select", to_name="Backlog")
    assert extract_status_name(p, "") == "Backlog"


def test_extract_status_name_non_single_select_ignored_in_fallback() -> None:
    p = _payload(field_node_id=None, field_type="text", to_name="whatever")
    assert extract_status_name(p, "") is None


def test_extract_status_name_cleared_value_none() -> None:
    p = _payload(to_name=None)  # to: null (cleared single-select)
    assert extract_status_name(p, _STATUS_FIELD) is None


def test_extract_status_name_no_changes_none() -> None:
    assert extract_status_name({"projects_v2_item": {}}, _STATUS_FIELD) is None


# ── ingest_external_move ──────────────────────────────────────────────────


def test_ingest_external_move_adopts_and_writes_board(tmp_path: Path) -> None:
    """A genuine external drag (differs from native placement) is written into board.json."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    _register_single(tmp_path, entry)
    # Native currently places the card in Backlog; GitHub drag moves it to In Progress.
    store = FsBoardStateStore(tmp_path)
    seed_board(store, ["Backlog", "InProgress"], {"PVTI_1": "Backlog"}, {"Backlog": ["PVTI_1"]})

    outcome = ingest_external_move(tmp_path, entry, _payload(to_name="In Progress"))

    assert outcome is IngestOutcome.ADOPTED
    assert store.load()["placement"]["PVTI_1"] == "InProgress"


def test_ingest_self_echo_dropped(tmp_path: Path) -> None:
    """An incoming Status equal to the current native placement (our own mirror echo) is DROPPED."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    _register_single(tmp_path, entry)
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store, ["Backlog", "InProgress"], {"PVTI_1": "InProgress"}, {"InProgress": ["PVTI_1"]}
    )
    version_before = store.load()["version"]

    # GitHub reports In Progress — but native already sits there (we mirrored it). Self-echo.
    outcome = ingest_external_move(tmp_path, entry, _payload(to_name="In Progress"))

    assert outcome is IngestOutcome.ECHO_DROPPED
    # No write: placement unchanged AND version not bumped (no false adoption, no probe churn).
    after = store.load()
    assert after["placement"]["PVTI_1"] == "InProgress"
    assert after["version"] == version_before


def test_ingest_first_sighting_adopts(tmp_path: Path) -> None:
    """An unplaced item's first external Status is adopted (placement was None)."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    _register_single(tmp_path, entry)
    # board.json must know its columns before place_card; seed an empty placement.
    store = FsBoardStateStore(tmp_path)
    seed_board(store, ["Backlog", "InProgress"], {}, {})

    outcome = ingest_external_move(tmp_path, entry, _payload(to_name="Backlog"))

    assert outcome is IngestOutcome.ADOPTED
    assert store.load()["placement"]["PVTI_1"] == "Backlog"


def test_ingest_non_native_project_noop(tmp_path: Path) -> None:
    """A github-backed project has no native store to ingest into → NOT_NATIVE no-op."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone, backend="github")
    _register_single(tmp_path, entry)

    outcome = ingest_external_move(tmp_path, entry, _payload(to_name="In Progress"))

    assert outcome is IngestOutcome.NOT_NATIVE
    # No board.json was created (nothing written).
    assert not (tmp_path / "board.json").exists()


def test_ingest_no_status_change_noop(tmp_path: Path) -> None:
    """A payload with no Status field change → NO_STATUS no-op (e.g. an item added / other field)."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    _register_single(tmp_path, entry)

    outcome = ingest_external_move(tmp_path, entry, {"projects_v2_item": {"node_id": "PVTI_1"}})

    assert outcome is IngestOutcome.NO_STATUS


def test_ingest_unmappable_status_noop(tmp_path: Path) -> None:
    """A Status name with no matching native column (columns.yml drift) → NO_STATUS, no write."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    _register_single(tmp_path, entry)
    store = FsBoardStateStore(tmp_path)
    seed_board(store, ["Backlog", "InProgress"], {"PVTI_1": "Backlog"}, {"Backlog": ["PVTI_1"]})

    outcome = ingest_external_move(tmp_path, entry, _payload(to_name="Nonexistent Column"))

    assert outcome is IngestOutcome.NO_STATUS
    # Placement untouched (no false placement under an unknown column).
    assert store.load()["placement"]["PVTI_1"] == "Backlog"


def test_ingest_missing_item_id_noop(tmp_path: Path) -> None:
    """A Status change with no item node id → NO_STATUS no-op (nothing to key the placement)."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    _register_single(tmp_path, entry)

    outcome = ingest_external_move(tmp_path, entry, _payload(item_id=None, to_name="Backlog"))

    assert outcome is IngestOutcome.NO_STATUS


def test_ingest_multi_project_uses_per_project_subroot(tmp_path: Path) -> None:
    """In a MULTI-project root the ingest writes the per-project board.json sub-root (not the flat root).

    Mirrors the daemon wiring: N>1 → ``<root>/projects/<safe(pid)>/board.json``. Pins that the
    webhook writes the SAME board.json the daemon reads under the multi-project layout.
    """
    from kanbanmate.cli.init import _projects_path, _upsert_project
    from kanbanmate.core.registry_resolve import safe_project_id

    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    # Register TWO enabled projects → multi-project layout.
    _upsert_project(_projects_path(tmp_path), "PVT_A", entry)
    _upsert_project(
        _projects_path(tmp_path),
        "PVT_B",
        ProjectEntry(
            repo="o/r2",
            clone=str(clone),
            project_id="PVT_B",
            status_field_node_id="PVTSSF_other",
            board_backend="native",
        ),
    )
    sub_root = tmp_path / "projects" / safe_project_id("PVT_A")
    sub_root.mkdir(parents=True)
    store = FsBoardStateStore(sub_root)
    seed_board(store, ["Backlog", "InProgress"], {"PVTI_1": "Backlog"}, {"Backlog": ["PVTI_1"]})

    outcome = ingest_external_move(tmp_path, entry, _payload(to_name="In Progress"))

    assert outcome is IngestOutcome.ADOPTED
    assert store.load()["placement"]["PVTI_1"] == "InProgress"
    # The flat-root board.json must NOT have been written (the per-project sub-root is authoritative).
    assert not (tmp_path / "board.json").exists()


def test_ingest_roundtrips_via_serve_json_payload(tmp_path: Path) -> None:
    """A realistic JSON-decoded payload (the exact shape `kanban serve` decodes) adopts correctly."""
    clone = _setup_clone(tmp_path)
    entry = _entry(clone)
    _register_single(tmp_path, entry)
    store = FsBoardStateStore(tmp_path)
    seed_board(store, ["Backlog", "InProgress"], {"PVTI_1": "Backlog"}, {"Backlog": ["PVTI_1"]})

    raw = json.dumps(
        {
            "action": "edited",
            "projects_v2_item": {"project_node_id": "PVT_A", "node_id": "PVTI_1"},
            "changes": {
                "field_value": {
                    "field_node_id": _STATUS_FIELD,
                    "field_type": "single_select",
                    "from": {"name": "Backlog"},
                    "to": {"name": "In Progress"},
                }
            },
        }
    ).encode()
    payload = json.loads(raw)

    outcome = ingest_external_move(tmp_path, entry, payload)

    assert outcome is IngestOutcome.ADOPTED
    assert store.load()["placement"]["PVTI_1"] == "InProgress"
