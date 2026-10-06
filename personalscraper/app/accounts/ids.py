"""The accounts' typed ids: a leaf module, so ``actor`` and ``model`` import them at runtime.

A ``NewType`` costs nothing at runtime, so the wire still carries a plain string, and mypy
refuses an account id where a role id is due.
"""

from __future__ import annotations

from typing import NewType

#: An account's key, ``account-<uuid4 hex>``.
AccountId = NewType("AccountId", str)

#: A role's key: a seed's id, or ``role-<uuid4 hex>``.
RoleId = NewType("RoleId", str)
