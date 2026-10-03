"""The instance ceiling: the writes an instance forbids to every account, Admin included (ruling 23).

Production forbids nothing; the preprod forbids ``library.delete``; the read-only
clone forbids every write, the session's own included. The ceiling subtracts
before the role adds (``frontend/maquette/design/src/lib/rights.ts``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.conf.environment import Environment, current_environment

#: The variable naming today's read-only clone (``staging``), as v0 reads it in ``web/deps.py``.
WEB_ROLE_VAR: Final[str] = "PERSONALSCRAPER_WEB_ROLE"
_READ_ONLY_ROLE: Final[str] = "staging"


@dataclass(frozen=True)
class InstanceCeiling:
    """What this instance forbids, whatever the role.

    Attributes:
        forbidden: The write rights no account holds here (served as ``Account.forbiddenWrites``).
        read_only: True when every write is refused, the session's own writes included.
    """

    forbidden: frozenset[Right]
    read_only: bool


def current_ceiling() -> InstanceCeiling:
    """Read this instance's ceiling from the environment, at each call.

    ``PERSONALSCRAPER_WEB_ROLE=staging`` (the read-only clone) is read first and
    wins; then ``PERSONALSCRAPER_ENV=staging`` (the preprod).

    Returns:
        Every write and read-only on the read-only clone; ``library.delete`` alone on
        the preprod; nothing otherwise.

    Raises:
        EnvironmentSettingError: ``PERSONALSCRAPER_ENV`` holds a value that is not an environment.
    """
    if os.environ.get(WEB_ROLE_VAR, "prod") == _READ_ONLY_ROLE:
        return InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)
    if current_environment() is Environment.STAGING:
        return InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)
    return InstanceCeiling(forbidden=frozenset(), read_only=False)
