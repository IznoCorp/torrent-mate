"""The accounts screen's routes: the roster, an account's creation, role and password, a role's creation and change.

Each route calls the account service; these tests hold the wire: the statuses and the
``Problem`` codes the contract declares, the rights each operation asks (``readAccounts``
opens to ``acquisition.reassign`` too; ``resetAccountPassword`` and ``setAccountAccess`` are an
Admin's only), and the
read-only clone refusing every write.
The guards themselves are proved in ``tests/unit/app/accounts/test_account_service.py`` and
``test_password_change.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
import structlog
from fastapi.testclient import TestClient

from personalscraper.app.accounts.events import AccountRightsChanged
from personalscraper.app.accounts.passwords import PASSWORD_MINIMUM
from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.rights import Right
from personalscraper.app.services import AppServices
from personalscraper.app.store.store import _MIGRATIONS_DIR
from personalscraper.conf.environment import StoreName, store_path
from personalscraper.conf.models.config import Config
from personalscraper.core.sqlite import open_db
from personalscraper.http_v1.session_cookie import SESSION_COOKIE

_PASSWORD = "A provisional one 1!"


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
            "signInAllowed": True,
        }
        assert [role["id"] for role in body["roles"]] == [
            "admin",
            "household",
            "plex-guest",
            "requester",
            "local-guest",
        ]

    def test_an_account_from_before_the_access_column_may_sign_in(
        self, v1_client: Callable[..., TestClient], test_config: Config
    ) -> None:
        """An ``app.db`` left at version 3 holding an account: migrated, it serves ``signInAllowed: true``."""
        db_path = store_path(test_config.paths.data_dir, StoreName.APP)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
        try:
            for script in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                if int(script.stem.split("_")[0]) <= 3:
                    conn.executescript(script.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO account (id, name, email, role_id, created_at, updated_at)"
                " VALUES ('account-old', 'Old', 'old@example.org', 'local-guest', 1, 1)"
            )
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        finally:
            conn.close()

        response = v1_client(role="admin").get("/accounts")

        assert response.status_code == 200
        old = next(one for one in response.json()["accounts"] if one["id"] == "account-old")
        assert old["signInAllowed"] is True

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

    def test_creates_a_local_account_on_the_role_given(self, v1_client: Callable[..., TestClient]) -> None:
        """201 ``AccountSummary`` on the role given."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "email": "new@example.org", "role": "local-guest", "password": _PASSWORD}
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
            "/accounts", json={"name": "New", "role": "local-guest", "email": "new@example.org", "password": "short"}
        )
        assert response.status_code == 400
        assert response.json()["code"] == "password.too_short"
        assert response.json()["params"] == {"minimum": PASSWORD_MINIMUM}

    def test_a_missing_password_is_required(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``password.required``."""
        response = v1_client(role="admin").post(
            "/accounts", json={"name": "New", "role": "local-guest", "email": "new@example.org"}
        )
        assert response.status_code == 400
        assert response.json()["code"] == "password.required"

    def test_a_missing_role_is_request_invalid(self, v1_client: Callable[..., TestClient]) -> None:
        """The role is required (the operator, 2026-10-04): 400 ``request.invalid``, nothing created."""
        client = v1_client(role="admin")
        response = client.post("/accounts", json={"name": "New", "email": "new@example.org", "password": _PASSWORD})
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert _services(client).app_store.accounts.account_by_email("new@example.org") is None

    def test_a_weak_password_is_too_weak(self, v1_client: Callable[..., TestClient]) -> None:
        """400 ``password.too_weak`` with ``params.minimum``: no uppercase, digit or special character."""
        response = v1_client(role="admin").post(
            "/accounts",
            json={"name": "New", "role": "local-guest", "email": "new@example.org", "password": "x" * PASSWORD_MINIMUM},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "password.too_weak"
        assert response.json()["params"] == {"minimum": PASSWORD_MINIMUM}

    @pytest.mark.parametrize("server_access", [None, "shared"], ids=["local", "plex-shared"])
    def test_an_admin_who_is_not_the_owner_giving_admin_is_403(
        self, v1_client: Callable[..., TestClient], server_access: str | None
    ) -> None:
        """403 ``account.admin_owner_only`` to a local or a Plex-shared Admin; the owner gives it (201)."""
        body = {"name": "New", "email": "new@example.org", "role": "admin", "password": _PASSWORD}
        refused = v1_client(role="admin", server_access=server_access).post("/accounts", json=body)
        assert refused.status_code == 403
        assert refused.json()["code"] == "account.admin_owner_only"
        created = v1_client(role="admin", server_access="owner").post("/accounts", json=body)
        assert created.status_code == 201
        assert created.json()["role"]["kind"] == "admin"

    def test_a_taken_email_is_409(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``account.email_taken``."""
        response = v1_client(role="admin").post(
            "/accounts",
            json={"name": "New", "role": "local-guest", "email": "ACCOUNT-1@example.org", "password": _PASSWORD},
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
            "/accounts",
            json={
                "name": "New",
                "role": "local-guest",
                "email": "new@example.org",
                "password": _PASSWORD,
                "admin": "yes-please",
            },
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

    @pytest.mark.parametrize("server_access", [None, "shared"], ids=["local", "plex-shared"])
    def test_an_admin_who_is_not_the_owner_promoting_to_admin_is_403(
        self, v1_client: Callable[..., TestClient], server_access: str | None
    ) -> None:
        """403 ``account.admin_owner_only`` to a local or a Plex-shared Admin; the owner promotes (200)."""
        client = v1_client(role="admin", server_access=server_access)
        _add_account(client, "account-guest", "local-guest")
        refused = client.patch("/accounts/account-guest", json={"role": "admin"})
        assert refused.status_code == 403
        assert refused.json()["code"] == "account.admin_owner_only"
        _link(client, "account-1", "owner")
        promoted = client.patch("/accounts/account-guest", json={"role": "admin"})
        assert promoted.status_code == 200
        assert promoted.json()["role"]["kind"] == "admin"

    @pytest.mark.parametrize("caller", ["the-owner", "another-admin"])
    def test_moving_the_owner_off_admin_is_403(self, v1_client: Callable[..., TestClient], caller: str) -> None:
        """403 ``account.owner_admin``, whoever asks: the owner's account stays on Admin.

        A second Admin stands, so the last-Admin guard would let the demotion through.
        """
        if caller == "the-owner":
            client = v1_client(role="admin", server_access="owner")
            _add_account(client, "account-admin-2", "admin")
            owner_id = "account-1"
        else:
            client = v1_client(role="admin")
            _add_account(client, "account-owner", "admin")
            _link(client, "account-owner", "owner")
            owner_id = "account-owner"
        response = client.patch(f"/accounts/{owner_id}", json={"role": "local-guest"})
        assert response.status_code == 403
        assert response.json()["code"] == "account.owner_admin"

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

    @pytest.mark.parametrize("name", ["", "   "], ids=["empty", "blank"])
    def test_a_blank_name_is_400(self, v1_client: Callable[..., TestClient], name: str) -> None:
        """400 ``role.name_required``."""
        response = v1_client(role="admin").post("/roles", json={"name": name, "rights": []})
        assert response.status_code == 400
        assert response.json()["code"] == "role.name_required"

    def test_a_taken_name_is_409(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``role.name_taken``, compared trimmed and regardless of case."""
        client = v1_client(role="admin")
        assert client.post("/roles", json={"name": "Friends", "rights": []}).status_code == 201
        response = client.post("/roles", json={"name": " FRIENDS ", "rights": []})
        assert response.status_code == 409
        assert response.json()["code"] == "role.name_taken"

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

    def test_a_rename_onto_a_taken_name_is_409(self, v1_client: Callable[..., TestClient]) -> None:
        """409 ``role.name_taken``."""
        client = v1_client(role="admin")
        assert client.post("/roles", json={"name": "Friends", "rights": []}).status_code == 201
        response = client.patch("/roles/requester", json={"name": "friends"})
        assert response.status_code == 409
        assert response.json()["code"] == "role.name_taken"


class TestDeleteRole:
    """``DELETE /roles/{roleId}`` — ``deleteRole``: only a role nothing depends on goes."""

    def test_an_unused_role_is_deleted(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``{"ok": true}``; the roster no longer lists it."""
        client = v1_client(role="admin")
        created = client.post("/roles", json={"name": "Friends", "rights": ["library.read"]}).json()

        response = client.delete(f"/roles/{created['id']}")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert created["id"] not in [role["id"] for role in client.get("/accounts").json()["roles"]]

    @pytest.mark.parametrize(
        ("role_id", "status", "code"),
        [
            ("nope", 404, "role.unknown"),
            ("admin", 409, "role.system_immutable"),
            ("plex-guest", 409, "role.default"),
            ("household", 409, "role.default"),
            ("requester", 409, "role.in_use"),
        ],
        ids=["unknown", "admin", "default-unheld", "default-held", "held"],
    )
    def test_a_role_something_depends_on_is_refused(
        self, v1_client: Callable[..., TestClient], role_id: str, status: int, code: str
    ) -> None:
        """The contract's refusals, in its order."""
        client = v1_client(role="admin")
        _add_account(client, "account-requester", "requester")
        _add_account(client, "account-household", "household")
        response = client.delete(f"/roles/{role_id}")
        assert response.status_code == status
        assert response.json()["code"] == code

    def test_a_manager_deleting_beyond_its_own_is_403(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``role.escalation``: ``requester`` holds rights the manager's role lacks."""
        response = v1_client(rights=frozenset({Right.ACCOUNTS_MANAGE})).delete("/roles/requester")
        assert response.status_code == 403
        assert response.json()["code"] == "role.escalation"

    def test_without_accounts_manage_is_right_missing(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``right.missing``."""
        response = v1_client(role="household").delete("/roles/requester")
        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"


def _link(client: TestClient, account_id: str, server_access: str) -> None:
    """Link an account of the client's base to Plex.

    Args:
        client: The test client.
        account_id: The account.
        server_access: ``owner`` or ``shared``.
    """
    _services(client).app_store.accounts.upsert_plex_link(
        PlexLinkRow(
            account_id=account_id,
            plex_id=900,
            plex_uuid="uuid-900",
            plex_username="plex-900",
            server_access=server_access,  # type: ignore[arg-type]
            token_ciphertext=None,
            token_stored_at=None,
            linked_at=9.0,
            last_sign_in_at=None,
        )
    )


class TestResetAccountPassword:
    """``POST /accounts/{accountId}/password`` — ``resetAccountPassword``, an Admin's act."""

    def test_an_admin_resets_and_the_sessions_stay(self, v1_client: Callable[..., TestClient]) -> None:
        """200 ``{"ok": true}``; the provisional password signs in; the account's session keeps running."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")
        running = _services(client).sessions.open("account-guest", user_agent="pytest")

        response = client.post("/accounts/account-guest/password", json={"password": _PASSWORD})

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert _services(client).sessions.resolve(running) is not None
        login = client.post("/auth/login", json={"email": "account-guest@example.org", "password": _PASSWORD})
        assert login.status_code == 200

    @pytest.mark.parametrize("account_id", ["account-guest", "account-1", "nope"], ids=["other", "own", "unknown"])
    def test_a_manager_who_is_not_admin_is_403_before_anything(
        self, v1_client: Callable[..., TestClient], account_id: str
    ) -> None:
        """403 ``password.reset_admin_only`` — its own account, and an id that names nobody (never 404)."""
        client = v1_client(rights=frozenset({Right.ACCOUNTS_MANAGE}))
        _add_account(client, "account-guest", "local-guest")
        response = client.post(f"/accounts/{account_id}/password", json={"password": _PASSWORD})
        assert response.status_code == 403
        assert response.json()["code"] == "password.reset_admin_only"

    def test_without_accounts_manage_is_right_missing(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``right.missing``."""
        response = v1_client(role="household").post("/accounts/account-1/password", json={"password": _PASSWORD})
        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"

    def test_an_admin_resetting_its_own_password_is_403(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``password.reset_own``: an Admin changes its own in Profil, its current password required."""
        response = v1_client(role="admin").post("/accounts/account-1/password", json={"password": _PASSWORD})
        assert response.status_code == 403
        assert response.json()["code"] == "password.reset_own"

    def test_the_owner_resetting_its_own_password_is_reset_own(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``password.reset_own``, not ``password.held_by_cli``: the caller's own account is checked first."""
        response = v1_client(role="admin", server_access="owner").post(
            "/accounts/account-1/password", json={"password": _PASSWORD}
        )
        assert response.status_code == 403
        assert response.json()["code"] == "password.reset_own"

    def test_an_unknown_account_is_404(self, v1_client: Callable[..., TestClient]) -> None:
        """For an Admin: 404 ``account.unknown``."""
        response = v1_client(role="admin").post("/accounts/nope/password", json={"password": _PASSWORD})
        assert response.status_code == 404
        assert response.json()["code"] == "account.unknown"

    @pytest.mark.parametrize(
        ("server_access", "code"),
        [("owner", "password.held_by_cli"), ("shared", "auth.plex_only")],
        ids=["owner", "plex-linked"],
    )
    def test_a_password_held_elsewhere_is_403(
        self, v1_client: Callable[..., TestClient], server_access: str, code: str
    ) -> None:
        """The owner's fallback is the CLI's; a Plex-linked account holds none."""
        client = v1_client(role="admin")
        _add_account(client, "account-linked", "household")
        _link(client, "account-linked", server_access)
        response = client.post("/accounts/account-linked/password", json={"password": _PASSWORD})
        assert response.status_code == 403
        assert response.json()["code"] == code

    @pytest.mark.parametrize(
        ("password", "code", "params"),
        [
            ("", "password.required", {}),
            ("x" * (PASSWORD_MINIMUM - 1), "password.too_short", {"minimum": PASSWORD_MINIMUM}),
            ("x" * PASSWORD_MINIMUM, "password.too_weak", {"minimum": PASSWORD_MINIMUM}),
        ],
        ids=["empty", "one-short", "too-weak"],
    )
    def test_a_refused_password_is_400(
        self, v1_client: Callable[..., TestClient], password: str, code: str, params: dict[str, int]
    ) -> None:
        """400 ``password.required`` / ``password.too_short`` with ``params.minimum``."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")
        response = client.post("/accounts/account-guest/password", json={"password": password})
        assert response.status_code == 400
        assert response.json()["code"] == code
        assert response.json()["params"] == params

    def test_the_password_is_never_echoed_nor_logged(self, v1_client: Callable[..., TestClient]) -> None:
        """Neither a refused nor a kept password reaches the answer or the log."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")
        short = "tiny-secret"
        with structlog.testing.capture_logs() as logs:
            refused = client.post("/accounts/account-guest/password", json={"password": short})
            kept = client.post("/accounts/account-guest/password", json={"password": _PASSWORD})
        assert refused.status_code == 400 and kept.status_code == 200
        for secret in (short, _PASSWORD):
            assert secret not in refused.text + kept.text
            assert secret not in str(logs)


class TestSetAccountAccess:
    """``PUT /accounts/{accountId}/access`` — ``setAccountAccess``, an Admin's act."""

    def test_cutting_ends_the_accounts_sessions_and_its_next_request_is_auth_required(
        self, v1_client: Callable[..., TestClient]
    ) -> None:
        """200, ``signInAllowed`` false; the cut account's next request is 401 ``auth.required``."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")
        running = _services(client).sessions.open("account-guest", user_agent="pytest")
        guest = TestClient(client.app, raise_server_exceptions=False)
        guest.cookies.set(SESSION_COOKIE, running)
        assert guest.get("/auth/me").status_code == 200

        response = client.put("/accounts/account-guest/access", json={"signInAllowed": False})

        assert response.status_code == 200
        body = response.json()
        assert (body["id"], body["signInAllowed"], body["signInKind"]) == ("account-guest", False, "local")
        after = guest.get("/auth/me")
        assert after.status_code == 401
        assert after.json()["code"] == "auth.required"
        assert client.get("/auth/me").status_code == 200

    def test_giving_back_answers_the_account_allowed(self, v1_client: Callable[..., TestClient]) -> None:
        """200, ``signInAllowed`` true, and the roster reads it."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")
        client.put("/accounts/account-guest/access", json={"signInAllowed": False})

        response = client.put("/accounts/account-guest/access", json={"signInAllowed": True})

        assert response.status_code == 200
        assert response.json()["signInAllowed"] is True
        roster = {account["id"]: account for account in client.get("/accounts").json()["accounts"]}
        assert roster["account-guest"]["signInAllowed"] is True

    @pytest.mark.parametrize("account_id", ["account-guest", "account-1", "nope"], ids=["other", "own", "unknown"])
    def test_a_manager_who_is_not_admin_is_403_before_anything(
        self, v1_client: Callable[..., TestClient], account_id: str
    ) -> None:
        """403 ``account.access_admin_only`` — its own account, and an id that names nobody (never 404)."""
        client = v1_client(rights=frozenset({Right.ACCOUNTS_MANAGE}))
        _add_account(client, "account-guest", "local-guest")
        response = client.put(f"/accounts/{account_id}/access", json={"signInAllowed": False})
        assert response.status_code == 403
        assert response.json()["code"] == "account.access_admin_only"

    def test_without_accounts_manage_is_right_missing(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``right.missing``."""
        response = v1_client(role="household").put("/accounts/account-1/access", json={"signInAllowed": False})
        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"

    def test_an_unknown_account_is_404(self, v1_client: Callable[..., TestClient]) -> None:
        """For an Admin: 404 ``account.unknown``."""
        response = v1_client(role="admin").put("/accounts/nope/access", json={"signInAllowed": False})
        assert response.status_code == 404
        assert response.json()["code"] == "account.unknown"

    @pytest.mark.parametrize(
        "body", [{}, {"signInAllowed": "no"}, {"signInAllowed": None}], ids=["absent", "a-string", "null"]
    )
    def test_a_body_without_a_boolean_is_request_invalid(
        self, v1_client: Callable[..., TestClient], body: dict[str, object]
    ) -> None:
        """400 ``request.invalid`` naming ``body.signInAllowed``; nothing changed."""
        client = v1_client(role="admin")
        _add_account(client, "account-guest", "local-guest")
        response = client.put("/accounts/account-guest/access", json=body)
        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert response.json()["params"]["fields"] == ["body.signInAllowed"]
        account = _services(client).app_store.accounts.account("account-guest")
        assert account is not None and account.sign_in_allowed is True

    def test_the_owner_is_owner_access(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``account.owner_access``: the fallback door is never cut."""
        client = v1_client(role="admin")
        _add_account(client, "account-owner", "admin")
        _link(client, "account-owner", "owner")
        response = client.put("/accounts/account-owner/access", json={"signInAllowed": False})
        assert response.status_code == 403
        assert response.json()["code"] == "account.owner_access"

    def test_its_own_account_is_own_access(self, v1_client: Callable[..., TestClient]) -> None:
        """403 ``account.own_access``: an Admin never locks itself out."""
        response = v1_client(role="admin").put("/accounts/account-1/access", json={"signInAllowed": False})
        assert response.status_code == 403
        assert response.json()["code"] == "account.own_access"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        (
            "POST",
            "/accounts",
            {"name": "New", "email": "new@example.org", "role": "local-guest", "password": _PASSWORD},
        ),
        ("PATCH", "/accounts/account-1", {"role": "local-guest"}),
        ("POST", "/roles", {"name": "X", "rights": ["library.read"]}),
        ("PATCH", "/roles/local-guest", {"name": "X"}),
        ("DELETE", "/roles/requester", None),
        ("POST", "/accounts/account-1/password", {"password": _PASSWORD}),
        ("PUT", "/accounts/account-1/access", {"signInAllowed": False}),
    ],
)
def test_every_write_on_the_read_only_clone_is_forbidden(
    v1_client: Callable[..., TestClient],
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    """``PERSONALSCRAPER_WEB_ROLE=staging``: 403 ``instance.forbidden_write``, the Admin included.

    Args:
        v1_client: The client factory.
        monkeypatch: Pytest's monkeypatch fixture.
        method: The write's method.
        path: Its path.
        body: Its body; ``None`` for a write that sends none.
    """
    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
    response = v1_client(role="admin").request(method, path, json=body)
    assert response.status_code == 403
    assert response.json()["code"] == "instance.forbidden_write"
