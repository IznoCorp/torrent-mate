"""Tests for the ``kanban-update-main`` agent helper (:mod:`kanbanmate.bin.kanban_update_main`).

The contract (DESIGN §10 — merge is human-only): the base clone is always ``git fetch``-ed; the
optional dev clone is fast-forwarded ONLY when clean AND on ``main`` (else a best-effort skip,
exit ``0``). The only mutating git call is ``pull --ff-only`` — never a merge, force, or rewrite.
``git`` is stubbed so no real repository is touched.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from kanbanmate.bin.kanban_update_main import _resolve_from_registry, main


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Build a fake :class:`subprocess.CompletedProcess` for a stubbed git call."""
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class _GitRecorder:
    """Records every ``git`` invocation and replays scripted results by sub-command."""

    def __init__(self, results: dict[str, subprocess.CompletedProcess[str]]) -> None:
        """Seed scripted results keyed by the git sub-command (argv[3], e.g. ``fetch``)."""
        self.results = results
        self.calls: list[list[str]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Record the argv and return the scripted result for its sub-command (default: ok)."""
        argv = list(args[0])
        self.calls.append(argv)
        # argv == ["git", "-C", <cwd>, <subcmd>, ...]; key on the sub-command.
        subcmd = argv[3] if len(argv) > 3 else ""
        # A multi-word key (e.g. "diff --cached") lets a test script that exact variant.
        joined = " ".join(argv[3:5]) if len(argv) > 4 else subcmd
        return self.results.get(joined, self.results.get(subcmd, _completed()))


def _install(monkeypatch: pytest.MonkeyPatch, recorder: _GitRecorder) -> None:
    """Route the git subprocess through the recorder (no real git).

    The git work was relocated from the bin into the ``base_sync`` workspace adapter (conduit
    §11.2), so the ``subprocess.run`` seam now lives there — the bin delegates to it. Patching the
    adapter's ``subprocess.run`` keeps the recorder seeing the EXACT same ``git -C <cwd> <subcmd>``
    argv the bin produced before the relocation (behaviour-preserving).
    """
    # String-target form avoids reaching through the module's re-exported ``subprocess``
    # attribute (which mypy treats as not explicitly exported).
    monkeypatch.setattr("kanbanmate.adapters.workspace.base_sync.subprocess.run", recorder)


def _no_force_or_merge(recorder: _GitRecorder) -> bool:
    """Assert no recorded git call requested a force, a merge, or a history rewrite."""
    banned = {"--force", "-f", "merge", "rebase", "reset", "push"}
    return not any(banned & set(argv) for argv in recorder.calls)


def test_base_only_fetches_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """With only a base clone, the base is fetched and the run exits 0."""
    rec = _GitRecorder({"fetch origin": _completed()})
    _install(monkeypatch, rec)

    assert main(["/base"]) == 0
    assert rec.calls == [["git", "-C", "/base", "fetch", "origin", "main"]]
    assert _no_force_or_merge(rec)


def test_missing_base_arg_with_no_registry_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """No base arg AND no resolvable single-project registry fails fast (exit 1), runs no git."""
    rec = _GitRecorder({})
    _install(monkeypatch, rec)
    # No single registered project → the registry resolution returns None → usage error.
    monkeypatch.setattr("kanbanmate.bin.kanban_update_main._resolve_from_registry", lambda: None)

    assert main([]) == 1
    assert rec.calls == []


def test_no_args_resolves_base_and_dev_from_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no args, the base clone + dev clone are resolved from the registry (defect 12).

    The single registered project's ``clone`` becomes the base clone (always fetched) and its
    ``dev_repo_path`` the dev clone (fast-forwarded when clean + on main).
    """
    rec = _GitRecorder(
        {
            "fetch origin": _completed(),
            "rev-parse --abbrev-ref": _completed(stdout="main\n"),
        }
    )
    _install(monkeypatch, rec)
    monkeypatch.setattr(
        "kanbanmate.bin.kanban_update_main._resolve_from_registry",
        lambda: ("/registry/base", "/registry/dev"),
    )

    assert main([]) == 0
    # The base clone resolved from the registry was fetched, and the dev clone was ff'd on main.
    assert ["git", "-C", "/registry/base", "fetch", "origin", "main"] in rec.calls
    assert ["git", "-C", "/registry/dev", "pull", "--ff-only"] in rec.calls
    assert _no_force_or_merge(rec)


def test_base_fetch_failure_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed base fetch is fatal (exit 1)."""
    rec = _GitRecorder({"fetch origin": _completed(returncode=1, stderr="boom")})
    _install(monkeypatch, rec)

    assert main(["/base"]) == 1


def test_dev_clean_on_main_fast_forwards(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean dev clone on main is fast-forwarded with ``pull --ff-only`` (no merge/force)."""
    rec = _GitRecorder(
        {
            "fetch origin": _completed(),
            "diff --quiet": _completed(returncode=0),  # clean tracked
            "diff --cached": _completed(returncode=0),  # clean staged
            "status --porcelain": _completed(stdout=""),  # no untracked
            "rev-parse --abbrev-ref": _completed(stdout="main\n"),
            "pull --ff-only": _completed(),
        }
    )
    _install(monkeypatch, rec)

    assert main(["/base", "/dev"]) == 0
    assert ["git", "-C", "/dev", "pull", "--ff-only"] in rec.calls
    assert _no_force_or_merge(rec)


def test_dev_dirty_skips_with_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dirty dev clone is skipped (exit 0) and is NEVER pulled."""
    rec = _GitRecorder(
        {
            "fetch origin": _completed(),
            "diff --quiet": _completed(returncode=1),  # dirty tracked changes
        }
    )
    _install(monkeypatch, rec)

    assert main(["/base", "/dev"]) == 0
    assert not any("pull" in argv for argv in rec.calls)
    assert _no_force_or_merge(rec)


# ---------------------------------------------------------------------------
# FIX 1 — multi-root registry resolution ($KANBAN_ROOT, km-worktree-helper-root fix)
# ---------------------------------------------------------------------------


def _write_one_project_registry(root: Path, *, clone: str, dev_repo_path: str) -> None:
    """Write a single-project ``projects.json`` under *root* carrying ``clone``/``dev_repo_path``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects.json").write_text(
        json.dumps(
            {
                "PVT_PROJECT": {
                    "repo": "IznoCorp/demo",
                    "clone": clone,
                    "project_id": "PVT_PROJECT",
                    "status_field_node_id": "PVTSSF",
                    "dev_repo_path": dev_repo_path,
                }
            }
        ),
        encoding="utf-8",
    )


def test_no_args_resolves_base_and_dev_from_kanban_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no args, the base/dev clones resolve from the ``$KANBAN_ROOT`` registry (FIX 1).

    Proves the km-root fix end to end: a single-project registry under a tmp ``$KANBAN_ROOT`` is
    read, so the base clone fetched and the dev clone ff'd are the registry's — never resolved
    from the hardcoded ~/.kanban. The base ``git fetch`` is the only real-ish op (stubbed).
    """
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    _write_one_project_registry(tmp_path, clone="/km/base", dev_repo_path="/km/dev")
    rec = _GitRecorder(
        {
            "fetch origin": _completed(),
            "rev-parse --abbrev-ref": _completed(stdout="main\n"),
        }
    )
    _install(monkeypatch, rec)

    assert main([]) == 0
    assert ["git", "-C", "/km/base", "fetch", "origin", "main"] in rec.calls
    assert ["git", "-C", "/km/dev", "pull", "--ff-only"] in rec.calls
    assert _no_force_or_merge(rec)


def test_resolve_from_registry_reads_kanban_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_resolve_from_registry`` reads the registry from ``$KANBAN_ROOT`` directly (FIX 1)."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    _write_one_project_registry(tmp_path, clone="/km/base", dev_repo_path="/km/dev")

    assert _resolve_from_registry() == ("/km/base", "/km/dev")


def test_resolve_from_registry_unset_falls_back_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``$KANBAN_ROOT`` unset, ``_resolve_from_registry`` falls back to the default root.

    ``DEFAULT_KANBAN_ROOT`` (the import-time-frozen ~/.kanban) is patched to a tmp dir so the
    fallback resolves under tmp; a single-project registry there resolves, proving the unset-env
    fallback is preserved (matching ``kanban_move``/``kanban_done`` contract).
    """
    monkeypatch.delenv("KANBAN_ROOT", raising=False)
    default_root = tmp_path / "default-kanban"
    monkeypatch.setattr("kanbanmate.cli.init.DEFAULT_KANBAN_ROOT", default_root)
    _write_one_project_registry(default_root, clone="/default/base", dev_repo_path="")

    assert _resolve_from_registry() == ("/default/base", "")


def test_dev_off_main_skips_with_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean dev clone NOT on main is skipped (exit 0) and never pulled."""
    rec = _GitRecorder(
        {
            "fetch origin": _completed(),
            "diff --quiet": _completed(returncode=0),
            "diff --cached": _completed(returncode=0),
            "status --porcelain": _completed(stdout=""),
            "rev-parse --abbrev-ref": _completed(stdout="feat/x\n"),
        }
    )
    _install(monkeypatch, rec)

    assert main(["/base", "/dev"]) == 0
    assert not any("pull" in argv for argv in rec.calls)
    assert _no_force_or_merge(rec)
