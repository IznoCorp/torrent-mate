"""Tests for the per-card Health field state mixin (:mod:`kanbanmate.adapters.store.fs_health_state`).

Exercises the mixin via :class:`~kanbanmate.adapters.store.fs_store.FsStateStore` against a
``tmp_path`` root so tests never touch the real ``~/.kanban/``.
"""

from __future__ import annotations

from pathlib import Path

from kanbanmate.adapters.store.fs_store import FsStateStore


def _store(tmp_path: Path) -> FsStateStore:
    """Build a store rooted at ``tmp_path`` (the ``health/`` dirs are created in __init__)."""
    return FsStateStore(tmp_path)


def test_health_dirs_created(tmp_path: Path) -> None:
    """The ``health/`` + ``health/last/`` directories exist after construction."""
    _store(tmp_path)
    assert (tmp_path / "health").is_dir()
    assert (tmp_path / "health" / "last").is_dir()


def test_field_id_round_trip(tmp_path: Path) -> None:
    """Field-id get/set round-trips; absent → None; clear → None."""
    store = _store(tmp_path)
    assert store.get_health_field_id() is None
    store.set_health_field_id("PVTSSF_HEALTH")
    assert store.get_health_field_id() == "PVTSSF_HEALTH"
    store.set_health_field_id(None)
    assert store.get_health_field_id() is None


def test_options_round_trip_and_absent(tmp_path: Path) -> None:
    """Options get/set round-trips; absent → empty dict."""
    store = _store(tmp_path)
    assert store.get_health_options() == {}
    store.set_health_options({"ACTIVE": "opt_a", "BLOCKED": "opt_b"})
    assert store.get_health_options() == {"ACTIVE": "opt_a", "BLOCKED": "opt_b"}


def test_project_id_round_trip(tmp_path: Path) -> None:
    """Project-id (rebind marker) get/set round-trips; absent → None."""
    store = _store(tmp_path)
    assert store.get_health_project_id() is None
    store.set_health_project_id("PVT_PROJECT")
    assert store.get_health_project_id() == "PVT_PROJECT"


def test_per_item_value_round_trip(tmp_path: Path) -> None:
    """Per-card last-written value get/set round-trips; absent → None; clear → None."""
    store = _store(tmp_path)
    assert store.get_item_health("PVTI_1") is None
    store.set_item_health("PVTI_1", "ACTIVE")
    assert store.get_item_health("PVTI_1") == "ACTIVE"
    store.set_item_health("PVTI_1", None)
    assert store.get_item_health("PVTI_1") is None


def test_per_item_values_are_independent(tmp_path: Path) -> None:
    """Distinct cards keep independent last-written values."""
    store = _store(tmp_path)
    store.set_item_health("PVTI_1", "ACTIVE")
    store.set_item_health("PVTI_2", "BLOCKED")
    assert store.get_item_health("PVTI_1") == "ACTIVE"
    assert store.get_item_health("PVTI_2") == "BLOCKED"


def test_clear_markers_removes_field_options_and_items_but_keeps_project_id(
    tmp_path: Path,
) -> None:
    """``clear_health_markers`` drops field/options + every per-card value, keeps project_id."""
    store = _store(tmp_path)
    store.set_health_project_id("PVT_PROJECT")
    store.set_health_field_id("PVTSSF_HEALTH")
    store.set_health_options({"ACTIVE": "opt_a"})
    store.set_item_health("PVTI_1", "ACTIVE")
    store.set_item_health("PVTI_2", "BLOCKED")

    store.clear_health_markers()

    assert store.get_health_field_id() is None
    assert store.get_health_options() == {}
    assert store.get_item_health("PVTI_1") is None
    assert store.get_item_health("PVTI_2") is None
    # The project_id binding is left for the caller to re-bind, NOT cleared here.
    assert store.get_health_project_id() == "PVT_PROJECT"


def test_poison_options_file_degrades_to_empty(tmp_path: Path) -> None:
    """A corrupt options.json degrades to {} (no raise)."""
    store = _store(tmp_path)
    (tmp_path / "health" / "options.json").write_text("{not json")
    assert store.get_health_options() == {}


def test_poison_options_non_object_degrades_to_empty(tmp_path: Path) -> None:
    """A valid-JSON-but-not-an-object options.json degrades to {} (no raise)."""
    store = _store(tmp_path)
    (tmp_path / "health" / "options.json").write_text('["a", "b"]')
    assert store.get_health_options() == {}


def test_item_id_sanitisation_confines_to_last_dir(tmp_path: Path) -> None:
    """A pathological item id is sanitised so it cannot escape health/last/."""
    store = _store(tmp_path)
    store.set_item_health("../../escape", "ACTIVE")
    # Nothing was written outside health/last/.
    assert not (tmp_path.parent / "escape").exists()
    # The value round-trips under the SAME (sanitised) key.
    assert store.get_item_health("../../escape") == "ACTIVE"
    # The sanitised marker lives under health/last/.
    markers = list((tmp_path / "health" / "last").iterdir())
    assert markers, "expected a sanitised marker under health/last/"


def test_atomic_write_leaves_no_temp_file(tmp_path: Path) -> None:
    """An atomic write leaves the final marker and no .tmp residue."""
    store = _store(tmp_path)
    store.set_item_health("PVTI_1", "WAITING")
    last_dir = tmp_path / "health" / "last"
    names = [p.name for p in last_dir.iterdir()]
    assert all(not n.endswith(".tmp") for n in names)
