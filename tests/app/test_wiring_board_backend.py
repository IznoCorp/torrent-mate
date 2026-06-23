"""Tests for the board_backend switch in build_deps + back-compat (anchor §12.5, §12.6)."""

from __future__ import annotations

import pathlib


_MINIMAL_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
    class: inert
  - key: InProgress
    name: In Progress
    class: reactive
"""


def test_wiring_config_has_board_backend_default() -> None:
    from kanbanmate.app.wiring import WiringConfig

    wc = WiringConfig(
        token="t",
        project_id="pid",
        repo="o/r",
        clone_dir="/tmp/clone",
        columns_yaml="columns: []",
    )
    # keel step 5 (A): the WiringConfig default flipped to "native" (one-way native authority).
    assert wc.board_backend == "native"
    assert wc.board_mirror is True


def test_build_deps_native_backend_routes_to_native(tmp_path: pathlib.Path) -> None:
    """build_deps with board_backend='native' wires NativeBoardBackend into both slots."""
    from kanbanmate.adapters.board.native import NativeBoardBackend
    from kanbanmate.app.wiring import WiringConfig, build_deps

    clone = tmp_path / "clone"
    clone.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = WiringConfig(
        token="tok",
        project_id="pid",
        repo="o/r",
        clone_dir=str(clone),
        columns_yaml=_MINIMAL_COLUMNS_YAML,
        kanban_root=str(root),
        board_backend="native",
        board_mirror=False,
    )
    deps = build_deps(wc)
    assert isinstance(deps.board_reader, NativeBoardBackend)
    assert isinstance(deps.board_writer, NativeBoardBackend)


def test_build_deps_github_backend_still_routes_to_github(tmp_path: pathlib.Path) -> None:
    """build_deps with an EXPLICIT board_backend='github' wires GithubClient — the legacy path.

    After keel step 5 (A) the DEFAULT is native, but ``"github"`` stays a valid explicit value so a
    board pinned to the legacy forge-authority backend keeps wiring the plain GithubClient.
    """
    from kanbanmate.adapters.github.client import GithubClient
    from kanbanmate.app.wiring import WiringConfig, build_deps

    clone = tmp_path / "clone"
    clone.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = WiringConfig(
        token="tok",
        project_id="pid",
        repo="o/r",
        clone_dir=str(clone),
        columns_yaml=_MINIMAL_COLUMNS_YAML,
        kanban_root=str(root),
        board_backend="github",  # EXPLICIT legacy backend (the default is now native)
    )
    deps = build_deps(wc)
    assert isinstance(deps.board_reader, GithubClient)
    assert isinstance(deps.board_writer, GithubClient)


def test_build_deps_default_routes_to_native(tmp_path: pathlib.Path) -> None:
    """A default WiringConfig (no board_backend) now wires NativeBoardBackend (keel step 5 A)."""
    from kanbanmate.adapters.board.native import NativeBoardBackend
    from kanbanmate.app.wiring import WiringConfig, build_deps

    clone = tmp_path / "clone"
    clone.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = WiringConfig(
        token="tok",
        project_id="pid",
        repo="o/r",
        clone_dir=str(clone),
        columns_yaml=_MINIMAL_COLUMNS_YAML,
        kanban_root=str(root),
        # NO board_backend set → defaults to "native" (one-way native authority)
    )
    deps = build_deps(wc)
    assert isinstance(deps.board_reader, NativeBoardBackend)
    assert isinstance(deps.board_writer, NativeBoardBackend)
    # One-way default: not hybrid (no GitHub→native reconcile) unless explicitly hybrid.
    assert deps.board_reader._hybrid is False


def test_wiring_for_entry_threads_board_backend(tmp_path: pathlib.Path) -> None:
    """wiring_for_entry threads board_backend from the registry entry onto WiringConfig."""
    from kanbanmate.cli.init import ProjectEntry
    from kanbanmate.daemon.registry_wiring import wiring_for_entry

    clone = tmp_path / "clone"
    clone.mkdir()
    columns_path = clone / ".claude" / "kanban"
    columns_path.mkdir(parents=True)
    (columns_path / "columns.yml").write_text(_MINIMAL_COLUMNS_YAML)

    entry = ProjectEntry(
        repo="o/r",
        clone=str(clone),
        project_id="pid",
        status_field_node_id="sfid",
        board_backend="native",
    )
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = wiring_for_entry(root, entry, multi=False, kill_switch=False)
    assert wc.board_backend == "native"


def test_build_deps_hybrid_backend_sets_hybrid_flag(tmp_path: pathlib.Path) -> None:
    """build_deps with board_backend='hybrid' wires NativeBoardBackend with hybrid=True (bidirectional)."""
    from kanbanmate.adapters.board.native import NativeBoardBackend
    from kanbanmate.app.wiring import WiringConfig, build_deps

    clone = tmp_path / "clone"
    clone.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "token").write_text("tok")

    wc = WiringConfig(
        token="tok",
        project_id="pid",
        repo="o/r",
        clone_dir=str(clone),
        columns_yaml=_MINIMAL_COLUMNS_YAML,
        kanban_root=str(root),
        board_backend="hybrid",
    )
    deps = build_deps(wc)
    assert isinstance(deps.board_reader, NativeBoardBackend)
    assert deps.board_reader._hybrid is True, (
        "hybrid backend must enable the GitHub→native reconcile"
    )
