"""v1's OpenAPI document declares no 422: v1 never answers it (an invalid request is 400 ``request.invalid``)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Query

from personalscraper.http_v1.app import include_v1_router
from personalscraper.http_v1.contract import PROBLEM_RESPONSES, ContractModel


class _Draft(ContractModel):
    """A body."""

    name: str


def _router() -> APIRouter:
    """A write with a body and a read with a query parameter: both draw FastAPI's 422.

    Returns:
        The router.
    """
    router = APIRouter()

    @router.post("/roles", operation_id="createRole", status_code=201, responses=PROBLEM_RESPONSES)
    def _create(draft: _Draft) -> dict[str, str]:
        """A planted write; never called."""
        return {}

    @router.get("/acquisition/search", operation_id="searchProviders", responses=PROBLEM_RESPONSES)
    def _search(query: Annotated[str, Query()]) -> dict[str, str]:
        """A planted read; never called."""
        return {}

    return router


def _document(make_v1_app: Callable[..., FastAPI]) -> dict[str, Any]:
    """The sub-application's document, the planted routes included.

    Args:
        make_v1_app: The sub-application factory.

    Returns:
        The document.
    """
    app = make_v1_app()
    include_v1_router(app, _router())
    app.openapi()
    document: dict[str, Any] = app.openapi()
    return document


def test_no_operation_declares_422(make_v1_app: Callable[..., FastAPI]) -> None:
    """A body or a parameter does not make an operation declare FastAPI's 422."""
    document = _document(make_v1_app)
    answers = {
        operation["operationId"]: set(operation["responses"])
        for item in document["paths"].values()
        for operation in item.values()
    }

    assert answers["createRole"] == {"201", "400", "401", "403", "409", "500", "503"}
    assert answers["searchProviders"] == {"200", "400", "401", "403", "409", "500", "503"}


def test_no_orphan_validation_schema(make_v1_app: Callable[..., FastAPI]) -> None:
    """FastAPI's validation schemas are not left behind, unreferenced."""
    document = _document(make_v1_app)

    assert {"HTTPValidationError", "ValidationError"}.isdisjoint(document["components"]["schemas"])
    assert "ValidationError" not in json.dumps(document)
