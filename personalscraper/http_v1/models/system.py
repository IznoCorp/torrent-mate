"""The ``system`` tag's bodies."""

from __future__ import annotations

from personalscraper.http_v1.contract import ContractModel


class Version(ContractModel):
    """``readVersion``'s answer (the contract's ``GET /version`` 200).

    Attributes:
        version: The package version the running process serves.
        commit: The git commit it booted with, or ``"dev"``.
    """

    version: str
    commit: str
