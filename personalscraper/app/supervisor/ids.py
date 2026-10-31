"""The supervisor's typed id: a leaf module, so ``model`` and the repositories import it at runtime.

A ``NewType`` costs nothing at runtime, so the wire still carries a plain string, and mypy
refuses any other string where a run's uid is due.
"""

from __future__ import annotations

from typing import NewType

#: A run request's key: 32 lowercase hex characters (a ``uuid4`` hex), the future ``pipeline_run.run_uid``.
RunUid = NewType("RunUid", str)
