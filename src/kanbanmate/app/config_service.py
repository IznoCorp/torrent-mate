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
    Finding,
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
                findings, OR when rendering the draft to YAML fails — both are
                client-side errors (a 422 at the HTTP boundary), never a 500.
        """
        result = self.validate(draft)
        if not result.ok:
            raise ConfigInvalid(result)

        # A render failure is a CLIENT error (the draft does not serialise), not a server fault —
        # surface it as a ConfigInvalid (→ 422 at the HTTP boundary, consistent with the validation
        # path) instead of letting the raw exception bubble out as a 500. Nothing has been written
        # yet at this point, so there is no on-disk state to roll back.
        try:
            rendered = render_pipeline(draft)
        except Exception as exc:
            raise ConfigInvalid(
                ValidationResult(
                    findings=[
                        Finding(
                            field="draft",
                            message=f"Failed to render the draft to YAML: {exc}",
                            severity="error",
                            locus="render",
                        )
                    ],
                    ok=False,
                )
            ) from exc

        # Two-file write made all-or-nothing (defense-in-depth): write BOTH temp files FIRST — a
        # render / disk-full / encoding error then happens BEFORE any rename, so neither destination
        # is touched. Only once both temps exist do we perform the two ``os.replace`` calls
        # back-to-back. If the SECOND replace fails after the first already landed, restore the first
        # file's prior content so transitions.yml and columns.yml can never end up desynced.
        tmp_transitions = self._write_temp(self._transitions_path, rendered.transitions)
        try:
            tmp_columns = self._write_temp(self._columns_path, rendered.columns)
        except Exception:
            self._cleanup_temp(tmp_transitions)
            raise

        try:
            prior_transitions = (
                self._transitions_path.read_text(encoding="utf-8")
                if self._transitions_path.exists()
                else None
            )
        except OSError:
            # Race (file unlinked / perms changed between exists() and read_text()) BEFORE any rename:
            # clean both temps so a failed prior-read can't leak orphaned .tmp files (no desync — neither
            # destination was touched yet).
            self._cleanup_temp(tmp_transitions)
            self._cleanup_temp(tmp_columns)
            raise
        os.replace(tmp_transitions, self._transitions_path)
        try:
            os.replace(tmp_columns, self._columns_path)
        except Exception:
            # columns.yml rename failed AFTER transitions.yml landed — undo the transitions write so
            # the pair never desyncs, then surface the error.
            self._cleanup_temp(tmp_columns)
            if prior_transitions is not None:
                # An UPDATE write: restore transitions.yml's prior content.
                self._transitions_path.write_text(prior_transitions, encoding="utf-8")
            else:
                # The very FIRST write: transitions.yml did not exist before, so restoring "prior
                # content" is meaningless — remove the just-landed transitions.yml entirely so a
                # failed first write leaves NEITHER file (all-or-nothing, not an orphan transitions).
                self._cleanup_temp(str(self._transitions_path))
            raise

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
    def _write_temp(path: Path, content: str) -> str:
        """Write ``content`` to a fsync'd temp file in ``path``'s parent dir; return the temp path.

        The temp file is created in the SAME directory as ``path`` so a later ``os.replace`` stays on
        one filesystem (atomic on POSIX). The content is flushed + fsync'd so a crash between write
        and rename cannot leave a half-written temp. The caller performs the ``os.replace`` (so both
        config files can be written to temps BEFORE either is renamed — the all-or-nothing property).

        Args:
            path: The destination file path (only its parent dir is used here).
            content: The UTF-8 content to write.

        Returns:
            The absolute path to the written temp file.
        """
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            ConfigService._cleanup_temp(tmp)
            raise
        return tmp

    @staticmethod
    def _cleanup_temp(tmp: str) -> None:
        """Best-effort unlink of a temp file (never raises)."""
        try:
            os.unlink(tmp)
        except OSError:
            pass
