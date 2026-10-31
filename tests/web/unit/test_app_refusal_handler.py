"""``create_app`` answers an application-layer refusal as v0 always answered it.

The application layer raises :class:`AppRefusal` subclasses (no HTTP framework);
v0 answers them as ``{"detail": ...}`` with the refusal's status — byte-for-byte
the answer of the ``HTTPException`` raises they replaced.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.app.errors import (
    AppConflict,
    AppInternalError,
    AppPreconditionRequired,
    AppRefusal,
    AppValidationError,
)


@pytest.mark.parametrize(
    ("exc_type", "status"),
    [
        (AppConflict, 409),
        (AppValidationError, 422),
        (AppPreconditionRequired, 428),
        (AppInternalError, 500),
    ],
)
def test_refusal_is_answered_as_v0_detail(test_config: Any, exc_type: type[AppRefusal], status: int) -> None:
    """Each refusal class answers its status with ``{"detail": <text>}`` and nothing else."""
    from personalscraper.config import Settings
    from personalscraper.web.app import create_app

    app = create_app(test_config, Settings(_env_file=None))  # type: ignore[call-arg]

    @app.get("/_probe")
    def _probe() -> None:
        raise exc_type("Verbatim detail: 'x'")

    # create_app ends with the SPA catch-all, which would shadow a later route.
    app.router.routes.insert(0, app.router.routes.pop())

    response = TestClient(app, raise_server_exceptions=False).get("/_probe")
    assert exc_type.status == status
    assert response.status_code == status
    assert response.json() == {"detail": "Verbatim detail: 'x'"}
