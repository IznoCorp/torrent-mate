r"""NTFS-safe-names check (DISPATCH stage, both media types).

Ported verbatim from ``verify/checker.py::_check_ntfs_safe_names``. Scans
recursively for files containing ``<>:"/\|?*`` in their names — these cause
rsync failures on NTFS storage disks. ``fixable=True``; the real ``fix()``
is added in Phase 3 — for now it is a stub.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.text_utils import _NTFS_ILLEGAL
from personalscraper.verify.checks.base import CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

if TYPE_CHECKING:
    from personalscraper.verify.checks.base import CheckContext, FixAction


@register_check
class NtfsSafeNames:
    r"""Check all filenames for NTFS-illegal characters (``<>:"/\|?*``)."""

    name = "ntfs_safe_names"
    group = "ntfs"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "Filenames must be NTFS-safe"

    def run(self, ctx: "CheckContext") -> list[CheckResult]:
        """Return ``[CheckResult]`` — passed=False when NTFS-illegal names exist.

        Args:
            ctx: Shared check context.

        Returns:
            Single-element list with the ``ntfs_safe_names`` result.
        """
        illegal_files = []
        for f in ctx.media_dir.rglob("*"):
            if f.is_file() and _NTFS_ILLEGAL.search(f.name):
                illegal_files.append(f.name)

        if illegal_files:
            sample = ", ".join(illegal_files[:3])
            suffix = f" (+{len(illegal_files) - 3} more)" if len(illegal_files) > 3 else ""
            message = f"NTFS-illegal filenames: {sample}{suffix}"
        else:
            message = ""

        return [
            CheckResult(
                name="ntfs_safe_names",
                passed=len(illegal_files) == 0,
                severity=Severity.ERROR,
                message=message,
                fixable=True,
            )
        ]

    def fix(self, ctx: "CheckContext") -> "list[FixAction]":
        """Stub — the real NTFS-rename fix is wired in Phase 3.

        Args:
            ctx: Shared check context (respects ``ctx.dry_run``).

        Returns:
            Currently an empty list (no-op placeholder).
        """
        return []
