"""Tests for :mod:`kanbanmate.app.config_service`.

Uses pytest's tmp_path fixture to create real clone config files so the
atomic-write and injected-path tests exercise the real filesystem.
"""

from __future__ import annotations

import importlib.resources
import shutil
from pathlib import Path

import pytest

from kanbanmate.app.config_service import ConfigInvalid, ConfigService
from kanbanmate.core.config_model import (
    Binding,
    Definition,
    PipelineDraft,
    TransitionDef,
)
from kanbanmate.core.transitions_defaults import render_transitions_yaml


def _columns_template_path() -> Path:
    """Return the path to the shipped columns.yml.tmpl asset."""
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    # importlib.resources may return a traversable — resolve to a real path.
    with importlib.resources.as_file(ref) as p:
        return p


def _make_clone_config(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal clone config dir under tmp_path and return (transitions_path, columns_path)."""
    config_dir = tmp_path / ".claude" / "kanban"
    config_dir.mkdir(parents=True)
    transitions_path = config_dir / "transitions.yml"
    columns_path = config_dir / "columns.yml"
    transitions_path.write_text(render_transitions_yaml("owner/repo"), encoding="utf-8")
    shutil.copy(_columns_template_path(), columns_path)
    return transitions_path, columns_path


def test_config_service_load_returns_draft(tmp_path: Path) -> None:
    """ConfigService.load() reads both files and returns a PipelineDraft."""
    tp, cp = _make_clone_config(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)
    draft = svc.load()
    assert isinstance(draft, PipelineDraft)
    assert len(draft.definition.columns) == 13


def test_config_service_validate_clean(tmp_path: Path) -> None:
    """ConfigService.validate() on the shipped config returns ok=True."""
    tp, cp = _make_clone_config(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)
    draft = svc.load()
    result = svc.validate(draft)
    assert result.ok is True


def test_config_service_render(tmp_path: Path) -> None:
    """ConfigService.render() returns a RenderedPipeline with non-empty YAML strings."""
    tp, cp = _make_clone_config(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)
    draft = svc.load()
    rendered = svc.render(draft)
    assert rendered.transitions
    assert rendered.columns


def test_config_service_save_atomic_write(tmp_path: Path) -> None:
    """ConfigService.save() writes both files atomically; reloading gives the same draft."""
    tp, cp = _make_clone_config(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)
    draft = svc.load()

    # Mutate the binding.project to verify the file is actually written.
    mutated = PipelineDraft(
        definition=draft.definition,
        binding=Binding(project="other/repo", option_map={}),
    )
    svc.save(mutated)

    # Both files must exist after save.
    assert tp.exists()
    assert cp.exists()

    # Reloading must give back the mutated project slug.
    svc2 = ConfigService(transitions_path=tp, columns_path=cp)
    reloaded = svc2.load()
    assert reloaded.binding.project == "other/repo"


def test_config_service_save_validation_error_writes_nothing(tmp_path: Path) -> None:
    """save() with an error-producing draft must raise ConfigInvalid and write NOTHING."""
    tp, cp = _make_clone_config(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)

    # Record mtime of both files before the attempted save.
    tp_mtime_before = tp.stat().st_mtime
    cp_mtime_before = cp.stat().st_mtime

    # Build a draft with an invalid permission_mode (V3 error — blocks save).
    bad_transition = TransitionDef(
        from_col="Backlog",
        to_col="Brainstorming",
        profile="docs",
        prompt="/implement:brainstorm {{code}}",
        advance="auto:Spec",
        permission_mode="bypassPermissions",  # banned
    )
    draft = svc.load()
    bad_draft = PipelineDraft(
        definition=Definition(
            columns=draft.definition.columns,
            transitions=[bad_transition],
            defaults=draft.definition.defaults,
        ),
        binding=draft.binding,
    )

    with pytest.raises(ConfigInvalid) as exc_info:
        svc.save(bad_draft)

    # Neither file must have been modified.
    assert tp.stat().st_mtime == tp_mtime_before, (
        "transitions.yml was modified despite validation error"
    )
    assert cp.stat().st_mtime == cp_mtime_before, (
        "columns.yml was modified despite validation error"
    )

    # The exception must carry the ValidationResult.
    assert not exc_info.value.result.ok
    errors = [f for f in exc_info.value.result.findings if f.severity == "error"]
    assert errors


def test_config_service_resolve(tmp_path: Path) -> None:
    """ConfigService.resolve() delegates to core.resolve and returns a ResolvedTransition."""
    tp, cp = _make_clone_config(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)
    draft = svc.load()
    result = svc.resolve(draft, "Backlog", "Brainstorming")
    assert result.matched is True
    assert result.would_launch is True


def test_config_service_injected_paths(tmp_path: Path) -> None:
    """ConfigService takes injected absolute paths — it must NOT import cli.init."""
    import ast
    import inspect

    import kanbanmate.app.config_service as svc_mod

    source = inspect.getsource(svc_mod)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "kanbanmate.cli" not in node.module, (
                    "config_service must not import from cli (layering guard: app→cli forbidden)"
                )


def test_save_restores_transitions_when_columns_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A2: if columns.yml's rename fails AFTER transitions.yml landed, transitions is rolled back.

    Guarantees the two config files never end up desynced (a partial write that left transitions.yml
    updated while columns.yml stayed stale was a HIGH adversarial-audit finding).
    """
    import os

    from kanbanmate.core.config_model import Defaults, Definition, PipelineDraft

    tp, cp = _make_clone_config(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)
    original_t = tp.read_text(encoding="utf-8")
    base = svc.load()
    # A valid draft that renders a DIFFERENT transitions.yml (defaults live in transitions.yml).
    changed = PipelineDraft(
        definition=Definition(
            columns=base.definition.columns,
            transitions=base.definition.transitions,
            defaults=Defaults(concurrency_cap=7, move_rate_limit_per_hour=9),
        ),
        binding=base.binding,
    )
    real_replace = os.replace

    def failing_replace(src: object, dst: object) -> None:
        if str(dst) == str(cp):  # fail ONLY the columns.yml rename (the second one)
            raise OSError("simulated columns.yml rename failure")
        real_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr("kanbanmate.app.config_service.os.replace", failing_replace)
    with pytest.raises(OSError):
        svc.save(changed)
    # transitions.yml must be RESTORED to its original content (not the half-applied concurrency_cap=7).
    assert tp.read_text(encoding="utf-8") == original_t
    # No stray temp files left in the config dir.
    assert not list(tp.parent.glob("*.tmp"))
