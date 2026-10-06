"""The account surfaces: the profile (``readAccount``) and the roster (``readAccounts``), read from v1."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.app_e2e.conftest import OWNER_EMAIL, OWNER_NAME, AppServer, assert_the_app_document

if TYPE_CHECKING:
    from playwright.sync_api import Page

pytestmark = pytest.mark.app_e2e


def test_the_profile_shows_the_signed_in_account(app_server: AppServer, signed_in_page: Page) -> None:
    """``/account`` draws the account v1 answers for the session: its name and its e-mail."""
    page = signed_in_page
    with page.expect_response(lambda response: response.url.endswith("/api/v1/auth/me")) as me:
        page.goto(app_server.origin + "/account")

    assert me.value.status == 200
    profile = page.locator('[data-part="flux"]').first
    profile.get_by_text(OWNER_NAME, exact=True).wait_for()
    assert profile.get_by_text(OWNER_EMAIL, exact=True).is_visible()
    assert_the_app_document(page)


def test_the_roster_lists_the_owner(app_server: AppServer, signed_in_page: Page) -> None:
    """``/accounts`` draws the accounts v1 answers: the seeded owner is the one row."""
    page = signed_in_page
    with page.expect_response(lambda response: response.url.endswith("/api/v1/accounts")) as roster:
        page.goto(app_server.origin + "/accounts")

    assert roster.value.status == 200
    rows = page.locator('[data-part="accounts/account"]')
    rows.first.wait_for()
    assert rows.count() == 1
    assert OWNER_EMAIL in rows.first.inner_text()
    assert_the_app_document(page)
