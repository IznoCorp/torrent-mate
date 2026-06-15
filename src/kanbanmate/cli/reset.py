"""``kanban reset`` — archive the kanban root so the operator starts clean (DESIGN §11).

``kanban reset`` does **not** delete anything: it *renames* the existing ``~/.kanban`` aside to a
timestamped backup (``~/.kanban.bak-<suffix>``) so the next ``kanban install`` re-creates a pristine
root while the previous state — including any pasted token — is preserved for recovery. This is the
deliberate counterpart to ``kanban uninstall``, which leaves the root in place (DESIGN §4.1 note).

Safety properties:

* **Never destructive** — the root is moved, never removed; a real PAT in ``token`` is never lost.
* **Collision-safe** — if the chosen backup path already exists, a numeric ``-1``, ``-2``, … is
  appended until a free name is found, so repeated resets never clobber an earlier archive.
* **Configurable + deterministic for tests** — both the ``root`` and the backup ``suffix`` are
  parameters; the production default derives the suffix from the wall clock, but tests pass an
  explicit suffix for a deterministic archive name.

Layering: ``cli`` is an entrypoint (DESIGN §3.2); this module is pure filesystem manipulation and
imports nothing from the lower layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# The default runtime root (DESIGN §4.1 / §5). Configurable via the ``root`` parameter so tests pass
# a ``tmp_path`` and never touch the real home directory.
DEFAULT_KANBAN_ROOT = Path("~/.kanban/").expanduser()

# The backup-directory name template: ``<root-name>.bak-<suffix>`` beside the original.
_BACKUP_TEMPLATE = "{name}.bak-{suffix}"

# The wall-clock format for the default backup suffix (sortable, filesystem-safe).
_SUFFIX_FORMAT = "%Y%m%d-%H%M%S"


@dataclass(frozen=True)
class ResetResult:
    """The outcome of a :func:`reset` call.

    Attributes:
        archived: ``True`` iff an existing root was moved aside; ``False`` when the root was absent
            (nothing to archive — a no-op reset).
        root: The runtime root that was targeted.
        backup: The path the root was moved to, or ``None`` when nothing was archived.
    """

    archived: bool
    root: Path
    backup: Path | None


def _default_suffix() -> str:
    """Return a sortable, filesystem-safe wall-clock backup suffix.

    ``datetime`` is normal application code here (not a forbidden harness wall-clock dependency): the
    suffix only names a backup directory, and tests inject an explicit ``suffix`` for determinism.

    Returns:
        A ``YYYYmmdd-HHMMSS`` timestamp string.
    """
    return datetime.now().strftime(_SUFFIX_FORMAT)


def _free_backup_path(root: Path, suffix: str) -> Path:
    """Resolve a non-colliding backup path beside ``root`` for ``suffix``.

    Starts from ``<root>.bak-<suffix>`` and appends ``-1``, ``-2``, … until a path that does not yet
    exist is found, so repeated resets within the same second never overwrite an earlier archive.

    Args:
        root: The runtime root being archived (its parent hosts the backup).
        suffix: The base backup suffix.

    Returns:
        A backup :class:`~pathlib.Path` that does not currently exist.
    """
    base = root.with_name(_BACKUP_TEMPLATE.format(name=root.name, suffix=suffix))
    if not base.exists():
        return base
    counter = 1
    while True:
        candidate = base.with_name(f"{base.name}-{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def reset(root: Path | str | None = None, *, suffix: str | None = None) -> ResetResult:
    """Archive the kanban root aside so the operator can start clean (DESIGN §11).

    Renames an existing ``root`` to a non-colliding ``<root>.bak-<suffix>`` directory. When the root
    does not exist the call is a no-op (idempotent-ish: a second reset right after the first simply
    finds nothing to archive). Nothing is ever deleted.

    Args:
        root: The kanban runtime root to archive; defaults to ``~/.kanban``. Pass a ``tmp_path`` in
            tests so no real runtime root is touched.
        suffix: The backup-name suffix; defaults to a wall-clock timestamp. Pass an explicit value
            in tests for a deterministic backup path.

    Returns:
        A :class:`ResetResult` recording whether an archive happened and where it landed.
    """
    resolved_root = DEFAULT_KANBAN_ROOT if root is None else Path(root)
    if not resolved_root.exists():
        # Nothing to archive — a clean no-op (e.g. reset on a never-installed host).
        return ResetResult(archived=False, root=resolved_root, backup=None)

    backup = _free_backup_path(resolved_root, suffix or _default_suffix())
    # rename is atomic on the same filesystem and never deletes — the old state survives intact.
    resolved_root.rename(backup)
    return ResetResult(archived=True, root=resolved_root, backup=backup)


def render_reset(result: ResetResult) -> str:
    """Render a :func:`reset` outcome as a one-line operator message.

    Args:
        result: The reset result to describe.

    Returns:
        A human-readable summary line.
    """
    if result.archived:
        return f"kanban reset: archived {result.root} -> {result.backup}"
    return f"kanban reset: nothing to archive (no root at {result.root})"
