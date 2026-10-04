"""The contract's root, the base of every v1 model, its ``Problem``, and the refusal statuses every operation declares.

``Problem`` lives here beside ``ContractModel`` because ``PROBLEM_RESPONSES``
names it: ``problem.py`` answers it, this module only describes it.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from personalscraper.app.errors import RefusalCode

#: The contract's server root, where v0's application mounts v1: a v1 route's path is the
#: contract's without its ``/api``, and a link v1 serves is formed under it.
V1_PREFIX: Final = "/api/v1"


class ContractModel(BaseModel):
    """A v1 body: snake_case in Python, the contract's camelCase on the wire (X2)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid", frozen=True)


class Problem(ContractModel):
    """The contract's ``Problem`` (``#/components/schemas/Problem``).

    Attributes:
        status: The HTTP status, repeated in the body.
        title: What went wrong, in one English line — the code's title.
        detail: The real reason, an English developer line; never shown as is.
        code: The refusal's code; the interface renders it through ``fr.json``.
        params: The typed facts the interface composes its sentence from.
    """

    status: int
    title: str
    detail: str | None = None
    code: RefusalCode
    params: dict[str, Any] = Field(default_factory=dict)


_PROBLEM: Final[dict[str, Any]] = {"model": Problem, "description": "A refusal, answered as a Problem."}

#: The refusal statuses every contract operation declares; a route adds 201, 404 or 429
#: where its operation declares it.
PROBLEM_RESPONSES: Final[dict[int | str, dict[str, Any]]] = {
    status: _PROBLEM for status in (400, 401, 403, 409, 500, 503)
}
