"""The « Comptes » routes: ``readAccounts``, ``createAccount``, ``updateAccount``, ``createRole``, ``updateRole``.

Each route calls the account service; these tests hold the wire: the statuses and the
``Problem`` codes the contract declares, the rights each operation asks (``readAccounts``
opens to ``acquisition.reassign`` too), and the read-only clone refusing every write.
The guards themselves are proved in ``tests/unit/app/accounts/test_account_service.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from personalscraper.app.accounts.events import AccountRightsChanged
from personalscraper.app.accounts.passwords import PASSWORD_MINIMUM
from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.services import AppServices

_PASSWORD = "a provisional one"


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts on a production instance: no ceiling from the environment.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)


def _services(client: TestClient) -> AppServices:
    """The services the client's application was built with.

    Args:
        client: The test client.

    Returns:
        Its services.
    """
    services: AppServices = client.app.state.services  # type: ignore[attr-defined]
    return services


def _add_account(client: TestClient, account_id: str, role_id: str) -> None:
    """Add an account to the client's base.

    Args:
        client: The test client.
        account_id: Its key; its e-mail is ``<key>@example.org``.
        role_id: Its role.
    """
    _services(client).app_store.accounts.insert_account(
        AccountRow(
            id=account_id,
            name=account_id,
            email=f"{account_id}@example.org",
            avatar="",
            role_id=role_id,
            password_hash=None,
            created_at=9.0,
            updated_at=9.0,
        )
    )


class TestReadAccounts:
    """``GET /accounts`` — ``readAccounts``."""

    def test_an_admin_reads_the_roster(self, v1_client: Callable[..., TestClient]) -> None:
        """200: every account as ``AccountSummary``, every role."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")

        response = client.get("/accounts")

        assert response.status_code == 200
        body = response.json()
        assert [one["id"] for one in body["accounts"]] == ["account-1", "account-guest"]
        guest = body["accounts"][1]
        assert guest == {
            "id": "account-guest",
            "name": "account-guest",
            "email": "account-guest@example.org",
            "role": {"id": "local-guest", "kind": "ordinary", "rights": ["library.read"], "defaultFor": ["local"]},
            "signInKind": "local",
        }
        assert [role["id"] for role in body["roles"]] == [
            "admin",
            "household",
            "plex-guest",
            "requester",
            "local-guest",
        ]

    def test_reassign_alone_opens_it_without_the_admin_accounts(self, v1_client: Callable[..., TestClient]) -> None:
        """200 under ``acquisition.reassign`` only; the Admin's account is left out (M7)."""
        client = v1_client(rights=frozenset({Right.ACQUISITION_REASSIGN}))
        _add_account(client, "account-admin", "admin")

        response = client.get("/accounts")

        assert response.status_code == 200
        assert "account-admin" not in [one["id"] for one in response.json()["accounts"]]

    def test_neither_right_is_right_missing(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``right.missing``."""
        response = v1_client(role="household").get("/accounts")
        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"


class TestCreateAccount:
    """``POST /accounts`` — ``createAccount``."""

    def test_creates_a_local_account_on_the_local_start_role(self, v1_client: Callable[..., TestClient]) -> None:
        """201 ``AccountSummary``; no role asked ⇒ Invité."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "email": "new@example.org", "password": _PASSWORD}
        )

        assert response.status_code == 201
        body = response.json()
        assert body["id"].startswith("account-")
        assert (body["name"], body["email"], body["signInKind"]) == ("New", "new@example.org", "local")
        assert body["role"]["id"] == "local-guest"
        assert "password" not in response.text

    def test_on_the_role_asked(self, v1_client: Callable[..., TestClient]) -> None:
        """``role`` names the role it starts on."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "email": "new@example.org", "role": "requester", "password": _PASSWORD}
        )
        assert response.status_code == 201
        assert response.json()["role"]["id"] == "requester"

    def test_an_unknown_role_is_404(self, v1_client: Callable[..., TestClient]) -> None:
        """404 ``role.unknown``."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "email": "new@example.org", "role": "nope", "password": _PASSWORD}
        )
        assert response.status_code == 404
        assert response.json()["code"] == "role.unknown"

    def test_a_short_password_names_the_minimum(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``password.too_short`` with ``params.minimum``."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "email": "new@example.org", "password": "short"}
        )
        assert response.status_code == 400
        assert response.json()["code"] == "password.too_short"
        assert response.json()["params"] == {"minimum": PASSWORD_MINIMUM}

    def test_a_missing_password_is_required(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``password.required``."""
        response = v1_client(role="admin").post("/accounts", json={"name": "New", "email": "new@example.org"})
        assert response.status_code == 400
        assert response.json()["code"] == "password.required"

    def test_a_taken_email_is_409(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``account.email_taken``."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "email": "ACCOUNT-1@example.org", "password": _PASSWORD}
        )
        assert response.status_code == 409
        assert response.json()["code"] == "account.email_taken"

    def test_a_manager_giving_admin_is_403(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``role.escalation``."""
        response = v1_client(rights=frozenset({Right.ACCOUNTS_MANAGE})).post(
            "/accounts", json={"name": "New", "email": "new@example.org", "role": "admin", "password": _PASSWORD}
        )
        assert response.status_code == 403
        assert response.json()["code"] == "role.escalation"

    def test_an_unknown_field_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``request.invalid``, the offending value never echoed."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "email": "new@example.org", "password": _PASSWORD, "admin": "yes-please"}
        )
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert "yes-please" not in response.text


class TestUpdateAccount:
    """``PATCH /accounts/{accountId}`` — ``updateAccount``."""

    def test_assigns_a_role_and_publishes_e8(self, v1_client: Callable[..., TestClient]) -> None:
        """200 on the new role; E8 on the services' bus."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")
        published: list[AccountRightsChanged] = []
        _services(client).event_bus.subscribe(AccountRightsChanged, published.append)

        response = client.patch("/accounts/account-guest", json={"role": "requester"})

        assert response.status_code == 200
        assert response.json()["role"]["id"] == "requester"
        assert [event.account_ids for event in published] == [("account-guest",)]

    def test_an_unknown_account_is_404(self, v1_client: Callable[..., TestClient]) -> None:
        """404 ``account.unknown``."""
        response = v1_client(role="admin").patch("/accounts/nope", json={"role": "requester"})
        assert response.status_code == 404
        assert response.json()["code"] == "account.unknown"

    def test_demoting_the_last_admin_is_409(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``account.last_admin``."""
        response = v1_client(role="admin").patch("/accounts/account-1", json={"role": "local-guest"})
        assert response.status_code == 409
        assert response.json()["code"] == "account.last_admin"

    def test_a_manager_touching_its_own_role_is_403(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``role.own_role``."""
        client = v1_client(rights=frozenset({Right.ACCOUNTS_MANAGE, Right.LIBRARY_READ}))
        response = client.patch("/accounts/account-1", json={"role": "local-guest"})
        assert response.status_code == 403
        assert response.json()["code"] == "role.own_role"


class TestCreateRole:
    """``POST /roles`` — ``createRole``."""

    def test_creates_an_ordinary_role(self, v1_client: Callable[..., TestClient]) -> None:
        """201 ``Role``."""
        response = v1_client(role="admin").post("/roles", json={"name": "Friends", "rights": ["library.read"]})

        assert response.status_code == 201
        body = response.json()
        assert body["id"].startswith("role-")
        assert {key: body[key] for key in ("name", "kind", "rights")} == {
            "name": "Friends",
            "kind": "ordinary",
            "rights": ["library.read"],
        }
        assert "defaultFor" not in body

    def test_an_unknown_right_on_the_wire_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """The body's rights are the contract's ``Right``: 400 ``request.invalid``."""
        response = v1_client(role="admin").post("/roles", json={"name": "X", "rights": ["auth.password"]})
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"

    def test_a_manager_widening_beyond_its_own_is_403(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``role.escalation``."""
        response = v1_client(rights=frozenset({Right.ACCOUNTS_MANAGE})).post(
            "/roles", json={"name": "X", "rights": ["library.delete"]}
        )
        assert response.status_code == 403
        assert response.json()["code"] == "role.escalation"


class TestUpdateRole:
    """``PATCH /roles/{roleId}`` — ``updateRole``."""

    def test_renames_and_sets_rights(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``Role``."""
        response = v1_client(role="admin").patch(
            "/roles/local-guest", json={"name": "Visitors", "rights": ["library.read", "trackers.view"]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "id": "local-guest",
            "name": "Visitors",
            "kind": "ordinary",
            "rights": ["library.read", "trackers.view"],
            "defaultFor": ["local"],
        }

    def test_the_admin_role_is_409(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``role.system_immutable``."""
        response = v1_client(role="admin").patch("/roles/admin", json={"name": "Boss"})
        assert response.status_code == 409
        assert response.json()["code"] == "role.system_immutable"

    def test_an_unknown_role_is_404(self, v1_client: Callable[..., TestClient]) -> None:
        """404 ``role.unknown``."""
        response = v1_client(role="admin").patch("/roles/nope", json={"name": "X"})
        assert response.status_code == 404
        assert response.json()["code"] == "role.unknown"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/accounts", {"name": "New", "email": "new@example.org", "password": _PASSWORD}),
        ("PATCH", "/accounts/account-1", {"role": "local-guest"}),
        ("POST", "/roles", {"name": "X", "rights": ["library.read"]}),
        ("PATCH", "/roles/local-guest", {"name": "X"}),
    ],
)
def test_every_write_on_the_read_only_clone_is_forbidden(
    v1_client: Callable[..., TestClient],
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    body: dict[str, object],
) -> None:
    """``PERSONALSCRAPER_WEB_ROLE=staging``: 403 ``instance.forbidden_write``, the Admin included.

    Args:
        v1_client: The client factory.
        monkeypatch: Pytest's monkeypatch fixture.
        method: The write's method.
        path: Its path.
        body: Its body.
    """
    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
    response = v1_client(role="admin").request(method, path, json=body)
    assert response.status_code == 403
    assert response.json()["code"] == "instance.forbidden_write"
