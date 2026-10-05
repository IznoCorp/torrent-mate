"""Unit tests for ``personalscraper.app.errors`` — the refusals' code, params and v0 answer."""

from __future__ import annotations

import json

from _repo_paths import CONTRACT
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.app import errors
from personalscraper.web.refusals import install_refusal_handler


def test_code_and_params_default() -> None:
    """A refusal raised the K0 way carries no code and empty params."""
    refusal = errors.AppConflict("x")

    assert refusal.code is None
    assert refusal.params == {}
    assert refusal.detail == "x"


def test_code_and_params_are_carried() -> None:
    """A coded refusal keeps its code and its typed facts."""
    refusal = errors.AppForbidden("no", code=errors.RefusalCode.RIGHT_MISSING, params={"rights": ["library.read"]})

    assert refusal.code is errors.RefusalCode.RIGHT_MISSING
    assert refusal.params == {"rights": ["library.read"]}


def test_new_subclasses_carry_their_status() -> None:
    """The six subclasses v1 needs answer the statuses DESIGN C.4 names."""
    statuses = {
        cls: cls.status
        for cls in (
            errors.AppBadRequest,
            errors.AppUnauthenticated,
            errors.AppForbidden,
            errors.AppNotFound,
            errors.AppTooManyRequests,
            errors.AppUnavailable,
        )
    }

    assert statuses == {
        errors.AppBadRequest: 400,
        errors.AppUnauthenticated: 401,
        errors.AppForbidden: 403,
        errors.AppNotFound: 404,
        errors.AppTooManyRequests: 429,
        errors.AppUnavailable: 503,
    }
    assert all(issubclass(cls, errors.AppRefusal) for cls in statuses)


def test_v0_answer_unchanged() -> None:
    """v0 answers a coded refusal exactly as before: ``{"detail"}`` and its status, no code, no params."""
    app = FastAPI()
    install_refusal_handler(app)

    @app.get("/x")
    def _raise() -> None:
        """Raise a coded refusal."""
        raise errors.AppConflict("x", code=errors.RefusalCode.INTERNAL, params={"n": 1})

    response = TestClient(app).get("/x")

    assert response.status_code == 409
    assert response.json() == {"detail": "x"}


def test_every_code_is_a_contract_code() -> None:
    """Every refusal code the layer raises is one the contract's ``RefusalCode`` lists, spelt the same."""
    listed = set(json.loads(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]["RefusalCode"]["enum"])

    assert {code.value for code in errors.RefusalCode} <= listed


def test_the_library_deletion_codes() -> None:
    """Deletion by medium refuses an ambiguous id and a library the pipeline holds, by code (K2-10)."""
    assert errors.RefusalCode.MEDIA_AMBIGUOUS.value == "media.ambiguous"
    assert errors.RefusalCode.LIBRARY_LOCKED.value == "library.locked"
