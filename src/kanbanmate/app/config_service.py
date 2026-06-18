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

    def resolve(self, draft: PipelineDraft, from_col: str, to_col: str) -> ResolvedTransition:
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
