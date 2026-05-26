"""Shared base for ``library-fix-*`` CLI Stats dataclasses.

Each ``library-fix-X`` command defines a per-command ``FixXStats`` dataclass
to track outcomes. They all need:

- ``snapshot()`` — return an independent copy safe for downstream emitters.
- ``to_log_dict()`` — projection to a ``dict[str, int]`` for structlog.

These are factored out so each subclass only declares its counter fields
and its ``to_cli_json`` specialization.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any


@dataclass
class CliFixStatsMixin:
    r"""Mixin providing ``snapshot`` + ``to_log_dict`` for ``library-fix-*`` Stats.

    Subclasses must be ``@dataclass``\ es.  The mixin reads ``fields(self)`` —
    it works generically across any subclass field set.

    Subclasses with non-int fields (e.g. ``list``) that require deep-copy or
    filtering should override ``snapshot`` / ``to_log_dict``.
    """

    def snapshot(self) -> "CliFixStatsMixin":
        """Return an independent (non-aliased) copy.

        Safe to pass to log emitters that may mutate, or to retain across
        further updates to the original instance.
        """
        return replace(self)

    def to_log_dict(self) -> dict[str, int]:
        """Project all fields to a ``dict[str, int]`` for structlog ``stats=``."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def to_cli_json(self, *, apply: bool) -> dict[str, Any]:
        """Project to the CLI JSON output shape (overridden per subclass)."""
        raise NotImplementedError
