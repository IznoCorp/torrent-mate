"""The idempotency records' typed ids: a leaf module, so the repository and the service import them.

A ``NewType`` costs nothing at runtime; mypy refuses a bare string where a claim's id is due.
"""

from __future__ import annotations

from typing import NewType

#: A claim's run, ``uuid4`` hex.
ClaimId = NewType("ClaimId", str)
