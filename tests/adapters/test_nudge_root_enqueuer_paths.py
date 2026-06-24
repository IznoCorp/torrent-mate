"""tug FIX 2: every enqueuer construction path bumps the TOP-LEVEL daemon nudge sentinel.

The daemon's interruptible sleep watches exactly one file — ``<runtime_root>/intents/.nudge`` — so an
enqueuer whose store targets a per-project sub-root (``<runtime_root>/projects/<safe(pid)>``) must
still bump the RUNTIME-ROOT sentinel, never a frozen per-project ``<sub-root>/intents/.nudge`` the
daemon never reads. These tests exercise the THREE store-construction paths an operator action flows
through — the http config-API nudge (``http/board_routes._nudge`` + ``http/monitor_routes``), the
agent/CLI helper path (``bin/_pin.helper_store_root``), and the daemon/CLI wiring
(``app/wiring.build_deps``) — and assert each wakes the top-level sentinel for an N>1 layout while
keeping the N=1 single-sentinel path byte-identical.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from kanbanmate.adapters.store.fs_store import FsStateStore


def _nudge_sentinel(root: Path) -> Path:
    """The daemon-watched nudge sentinel path under ``root`` (``<root>/intents/.nudge``)."""
    return root / "intents" / ".nudge"


# ---------------------------------------------------------------------------
# http config-API nudge path (board_routes._nudge / monitor_routes nudges)
# ---------------------------------------------------------------------------


def test_http_nudge_bumps_runtime_root_even_with_n_gt_1_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The http ``_nudge`` builds ``FsStateStore(_kanban_root())`` → the RUNTIME-ROOT sentinel.

    Even when N>1 (per-project sub-roots exist), the http nudge targets the runtime root (its store is
    constructed at ``_kanban_root()``, whose ``nudge_root`` defaults to that runtime root). Assert the
    top-level ``intents/.nudge`` is created and NO per-project ``<sub-root>/intents/.nudge`` is touched.
    """
    from kanbanmate.http import board_routes, config_api

    # Point the config-API runtime root at the tmp runtime root (the N>1 sub-roots live under it).
    # monkeypatch.setattr auto-restores app.state so this never leaks into another test.
    monkeypatch.setattr(config_api.app.state, "kanban_root", tmp_path, raising=False)
    sub_root = tmp_path / "projects" / "PVT_A-deadbeef"
    sub_root.mkdir(parents=True)

    board_routes._nudge()

    assert _nudge_sentinel(tmp_path).exists(), "http nudge must bump the runtime-root sentinel"
    assert not _nudge_sentinel(sub_root).exists(), (
        "http nudge must NOT write the per-project sentinel"
    )


# ---------------------------------------------------------------------------
# agent/CLI helper path (bin/_pin.helper_store_root)
# ---------------------------------------------------------------------------


def test_helper_store_n_gt_1_nudges_runtime_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project-pinned helper store (N>1) bumps the RUNTIME-ROOT sentinel, not its sub-root one.

    ``helper_store_root`` resolves ``(sub_root, runtime_root)`` for a pinned project; the built store
    enqueues per-project but nudges the runtime root. Drives the pin via ``$KANBAN_ROOT`` +
    ``$KANBAN_PROJECT_ID`` (the launch exports) and asserts the top-level sentinel is the one bumped.
    """
    from kanbanmate.bin._pin import helper_store
    from kanbanmate.core.registry_resolve import safe_project_id

    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    monkeypatch.setenv("KANBAN_PROJECT_ID", "PVT_A")
    store = cast(FsStateStore, helper_store())  # helper_store types its return as object
    store.nudge_daemon()

    sub_root = tmp_path / "projects" / safe_project_id("PVT_A")
    assert _nudge_sentinel(tmp_path).exists(), "helper nudge must bump the runtime-root sentinel"
    assert not _nudge_sentinel(sub_root).exists(), (
        "helper nudge must NOT write the sub-root sentinel"
    )


def test_helper_store_n1_uses_single_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N=1 (no project pin): the helper store nudges its own root — the single legacy sentinel."""
    from kanbanmate.bin._pin import helper_store

    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    # No KANBAN_PROJECT_ID → unpinned (N=1) → single-positional store, nudge defaults to its root.
    monkeypatch.delenv("KANBAN_PROJECT_ID", raising=False)
    store = cast(FsStateStore, helper_store())  # helper_store types its return as object
    store.nudge_daemon()

    assert _nudge_sentinel(tmp_path).exists(), "N=1 helper nudge writes the single runtime sentinel"


# ---------------------------------------------------------------------------
# daemon/CLI wiring path (app/wiring.build_deps)
# ---------------------------------------------------------------------------


def test_build_deps_n_gt_1_store_nudges_runtime_root(tmp_path: Path) -> None:
    """``build_deps`` with a ``state_root`` (N>1) wires the store nudge to the RUNTIME root."""
    from kanbanmate.app.wiring import WiringConfig, build_deps

    sub_root = tmp_path / "projects" / "PVT_A-deadbeef"
    config = WiringConfig(
        token="tok",
        project_id="PVT_A",
        repo="o/r",
        clone_dir=str(tmp_path / "clone"),
        columns_yaml="columns: []\n",
        kanban_root=str(tmp_path),
        state_root=str(sub_root),
        multi_project=True,
        board_backend="github",  # avoid the native board store construction in this wiring unit test
    )
    deps = build_deps(config)
    deps.store.nudge_daemon()

    assert _nudge_sentinel(tmp_path).exists(), "build_deps N>1 store must nudge the runtime root"
    assert not _nudge_sentinel(sub_root).exists(), (
        "build_deps N>1 store must NOT nudge the sub-root"
    )


def test_build_deps_n1_store_uses_single_sentinel(tmp_path: Path) -> None:
    """``build_deps`` with NO ``state_root`` (N=1) nudges the bare runtime root — byte-identical."""
    from kanbanmate.app.wiring import WiringConfig, build_deps

    config = WiringConfig(
        token="tok",
        project_id="PVT_A",
        repo="o/r",
        clone_dir=str(tmp_path / "clone"),
        columns_yaml="columns: []\n",
        kanban_root=str(tmp_path),
        state_root="",  # N=1 flat layout
        multi_project=False,
        board_backend="github",
    )
    deps = build_deps(config)
    deps.store.nudge_daemon()

    assert _nudge_sentinel(tmp_path).exists(), (
        "build_deps N=1 store nudges the single runtime sentinel"
    )


def test_direct_substore_without_nudge_root_would_freeze_the_wrong_sentinel(tmp_path: Path) -> None:
    """Regression guard: a sub-root store built WITHOUT nudge_root writes a sentinel the daemon ignores.

    This documents the footgun the enqueuer paths avoid — constructing ``FsStateStore(sub_root)``
    WITHOUT ``nudge_root`` bumps ``<sub-root>/intents/.nudge`` (the frozen artifact), NOT the
    runtime-root sentinel. The enqueuer paths above all pass ``nudge_root`` (or build at the runtime
    root) precisely so this never happens in production.
    """
    sub_root = tmp_path / "projects" / "PVT_A-deadbeef"
    wrong = FsStateStore(sub_root)  # no nudge_root → defaults to the sub-root (the footgun)
    wrong.nudge_daemon()

    assert _nudge_sentinel(sub_root).exists(), (
        "the sub-root fallback writes the per-project sentinel"
    )
    assert not _nudge_sentinel(tmp_path).exists(), "and it does NOT wake the runtime-root sentinel"
