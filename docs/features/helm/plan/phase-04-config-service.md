# Phase 4 — Config service (app)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `app/config_service.py` — the path-injected service layer that the HTTP
entrypoint (Phase 5) calls. Provides `ConfigInvalid` exception, `ConfigService` with `.load()`,
`.validate()`, `.save()`, `.render()`, and `.resolve()`.

**Architecture:** `app` layer. Path-injected: `app` may NOT import `cli.init`
(the layering guard forbids `app → cli`, `tests/test_layering.py:41`). The HTTP layer (Phase 5)
resolves the absolute paths from `cli.init` and injects them into `ConfigService`. Atomic write
uses `os.replace` (same-filesystem rename — guaranteed within each file's own parent directory).

**Tech Stack:** stdlib `pathlib`, `os`, `tempfile`. All core functions from Phases 1–3.

## Global Constraints

- `app/` must NOT import from `cli/` or `daemon/` — the layering guard enforces this.
- Google-style docstrings on all new modules/classes/functions.
- Tests live in `tests/app/` — use a `tmp_path` fixture (pytest built-in) to create a real
  temporary file tree for the atomic-write tests.

---

## Task 4.1 — `app/config_service.py` + service tests

**Files:**
- Create: `src/kanbanmate/app/config_service.py`
- Create: `tests/app/test_config_service.py`

**Interfaces:**
- Consumes:
  - `PipelineDraft` from `core.config_model` (Phase 1)
  - `render_pipeline`, `RenderedPipeline` from `core.config_serialize` (Phase 2)
  - `validate`, `ValidationResult`, `ResolvedTransition` from `core.config_validate` (Phase 3)
- Produces:
  - `ConfigInvalid(Exception)` carrying `.result: ValidationResult`
  - `ConfigService(transitions_path: Path, columns_path: Path)` with:
    - `.load() -> PipelineDraft`
    - `.validate(draft: PipelineDraft) -> ValidationResult`
    - `.save(draft: PipelineDraft) -> None` — raises `ConfigInvalid` on any error finding
    - `.render(draft: PipelineDraft) -> RenderedPipeline`
    - `.resolve(draft: PipelineDraft, from_col: str, to_col: str) -> ResolvedTransition`
- Consumed by: Phase 5 (HTTP endpoints)

- [ ] **Step 4.1.1: Write the failing service tests**

```python
# tests/app/test_config_service.py
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
    ColumnDef,
    Defaults,
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
    assert len(draft.definition.columns) == 14


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
    from dataclasses import replace
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
    from dataclasses import replace
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
    assert tp.stat().st_mtime == tp_mtime_before, "transitions.yml was modified despite validation error"
    assert cp.stat().st_mtime == cp_mtime_before, "columns.yml was modified despite validation error"

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
```

- [ ] **Step 4.1.2: Run tests to verify they fail**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/app/test_config_service.py -v
```

Expected: `ImportError: cannot import name 'ConfigService' from 'kanbanmate.app.config_service'`

- [ ] **Step 4.1.3: Create `app/config_service.py`**

```python
# src/kanbanmate/app/config_service.py
"""Path-injected config service for the pipeline draft (DESIGN §12).

:class:`ConfigService` is the app-layer boundary between the HTTP/CLI entrypoints
and the pure ``core`` config functions.  It is **path-injected**: callers
(``http/config_api.py``) resolve the two absolute clone config file paths from
``cli.init`` and inject them here; this module must never import ``cli`` (the
layering guard forbids ``app → cli``, ``tests/test_layering.py:41``).

Atomic write: temp-file → ``os.replace`` within each file's own parent directory
(same filesystem, guaranteed atomic rename).  On a validation error nothing is
written.

Layering: ``app`` may import ``core`` and ``adapters`` but not ``cli`` or
``daemon``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from kanbanmate.core.config_model import PipelineDraft
from kanbanmate.core.config_serialize import RenderedPipeline, render_pipeline
from kanbanmate.core.config_validate import (
    ResolvedTransition,
    ValidationResult,
    resolve,
    validate,
)


class ConfigInvalid(Exception):
    """Raised by :meth:`ConfigService.save` when the draft has error-severity findings.

    Attributes:
        result: The :class:`~kanbanmate.core.config_validate.ValidationResult`
            that triggered the exception.
    """

    def __init__(self, result: ValidationResult) -> None:
        """Initialise with the failing ValidationResult.

        Args:
            result: The validation result carrying the error findings.
        """
        super().__init__(f"Config validation failed: {len(result.findings)} finding(s)")
        self.result = result


class ConfigService:
    """Path-injected config service (DESIGN §12).

    Provides load / validate / save / render / resolve for the pipeline draft.
    The two absolute paths to the clone config files are injected at construction
    time by the HTTP entrypoint (which resolves them via ``cli.init`` — a layer
    that ``app`` may not import directly).

    Attributes:
        transitions_path: Absolute path to the clone's ``transitions.yml``.
        columns_path: Absolute path to the clone's ``columns.yml``.
    """

    def __init__(self, transitions_path: Path, columns_path: Path) -> None:
        """Initialise the service with the resolved config file paths.

        Args:
            transitions_path: Absolute path to ``<clone>/.claude/kanban/transitions.yml``.
            columns_path: Absolute path to ``<clone>/.claude/kanban/columns.yml``.
        """
        self._transitions_path = transitions_path
        self._columns_path = columns_path

    def load(self) -> PipelineDraft:
        """Read both config files and return an editable :class:`~kanbanmate.core.config_model.PipelineDraft`.

        Returns:
            The editable draft built from the current on-disk config.

        Raises:
            ValueError: If either file is absent or structurally invalid.
            FileNotFoundError: If either config file does not exist.
        """
        transitions_yaml = self._transitions_path.read_text(encoding="utf-8")
        columns_yaml = self._columns_path.read_text(encoding="utf-8")
        return PipelineDraft.from_loaded(transitions_yaml, columns_yaml)

    def validate(self, draft: PipelineDraft) -> ValidationResult:
        """Validate the draft without writing anything.

        Passes the raw ``columns_yaml`` for V8 (defaults coherence) when the
        columns file exists; omits it otherwise (V8 is skipped).

        Args:
            draft: The draft to validate.

        Returns:
            A :class:`~kanbanmate.core.config_validate.ValidationResult`.
        """
        columns_yaml: str | None = None
        if self._columns_path.exists():
            columns_yaml = self._columns_path.read_text(encoding="utf-8")
        return validate(draft, columns_yaml=columns_yaml)

    def save(self, draft: PipelineDraft) -> None:
        """Validate and atomically write both config files (DESIGN §12).

        Validation runs first; if any ``error``-severity finding exists, raises
        :class:`ConfigInvalid` and writes NOTHING.  On success, both files are
        written atomically via temp-file → ``os.replace`` within each file's own
        parent directory (same filesystem, guaranteed atomic rename).

        Args:
            draft: The draft to persist.

        Raises:
            ConfigInvalid: When the draft has one or more ``error``-severity
                findings.
        """
        result = self.validate(draft)
        if not result.ok:
            raise ConfigInvalid(result)

        rendered = render_pipeline(draft)

        # Atomic write for transitions.yml.
        self._atomic_write(self._transitions_path, rendered.transitions)
        # Atomic write for columns.yml.
        self._atomic_write(self._columns_path, rendered.columns)

    def render(self, draft: PipelineDraft) -> RenderedPipeline:
        """Render the draft to YAML strings without writing (preview).

        Args:
            draft: The draft to render.

        Returns:
            A :class:`~kanbanmate.core.config_serialize.RenderedPipeline` with
            the ``transitions.yml`` and ``columns.yml`` content.
        """
        return render_pipeline(draft)

    def resolve(
        self, draft: PipelineDraft, from_col: str, to_col: str
    ) -> ResolvedTransition:
        """Simulate whitelist resolution for a ``(from_col, to_col)`` move (DESIGN §6).

        Args:
            draft: The pipeline draft.
            from_col: The source column key.
            to_col: The destination column key.

        Returns:
            A :class:`~kanbanmate.core.config_validate.ResolvedTransition`.
        """
        return resolve(draft, from_col, to_col)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """Write ``content`` to ``path`` atomically via a temp file and ``os.replace``.

        The temp file is created in the SAME directory as ``path`` so the rename
        is guaranteed to stay on the same filesystem (``os.replace`` requires this
        for atomicity on POSIX systems).

        Args:
            path: The destination file path.
            content: The UTF-8 content to write.
        """
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile with delete=False in the same directory as path so
        # os.replace crosses no filesystem boundary.
        fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, path)
        except Exception:
            # Clean up the temp file on failure — the destination is untouched.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
```

- [ ] **Step 4.1.4: Run all service tests**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/app/test_config_service.py -v
```

Expected: all PASS.

- [ ] **Step 4.1.5: Run layering guard to confirm app→cli is not present**

```bash
cd /Users/izno/dev/worktrees/ticket-5
python -m pytest tests/test_layering.py -v
```

Expected: PASS. `config_service.py` imports only from `core`.

- [ ] **Step 4.1.6: Phase gate**

```bash
cd /Users/izno/dev/worktrees/ticket-5
make lint
make test
make check
python -c "import kanbanmate"
```

Expected: all clean.

- [ ] **Step 4.1.7: Commit**

```bash
cd /Users/izno/dev/worktrees/ticket-5
git add src/kanbanmate/app/config_service.py tests/app/test_config_service.py
git commit -m "feat(helm): app/config_service.py — path-injected service + atomic write"
```
