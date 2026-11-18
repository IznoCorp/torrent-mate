"""The sign-in surface: the gate's password door, against v1's ``signIn`` and ``readAccount``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.app_e2e.conftest import OWNER_EMAIL, OWNER_PASSWORD, AppServer, assert_the_app_document

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

pytestmark = pytest.mark.app_e2e

_GATE = '[data-part="login"]'


def _submit_password(page: Page, email: str, password: str) -> int:
    """Open the password door, fill it and send it.

    Args:
        page: A page showing the gate.
        email: The e-mail typed.
        password: The password typed.

    Returns:
        The status v1 answered the sign-in with.
    """
    page.click('[data-part="login/password-disclosure"]')
    page.fill('#loginform input[name="username"]', email)
    page.fill('#loginform input[name="password"]', password)
    with page.expect_response(lambda response: response.url.endswith("/api/v1/auth/login")) as answered:
        page.click('[data-part="login/submit"]')
    return answered.value.status


def test_a_visitor_lands_on_the_gate(app_server: AppServer, context: BrowserContext) -> None:
    """With no session, v1 answers ``readAccount`` 401 and the client shows the gate at its address."""
    page = context.new_page()
    with page.expect_response(lambda response: response.url.endswith("/api/v1/auth/me")) as me:
        page.goto(app_server.origin + "/")

    assert me.value.status == 401
    page.wait_for_url("**/login")
    assert page.locator(_GATE).is_visible()
    assert_the_app_document(page)


def test_the_owner_signs_in_with_the_password(app_server: AppServer, context: BrowserContext) -> None:
    """The fallback password signs the owner in: v1 sets the session and the gate gives way to the app."""
    page = context.new_page()
    page.goto(app_server.origin + "/")
    page.wait_for_url("**/login")

    status = _submit_password(page, OWNER_EMAIL, OWNER_PASSWORD)

    assert status == 200
    page.wait_for_url(lambda url: not url.endswith("/login"))
    page.locator(_GATE).wait_for(state="hidden")
    assert any(cookie["name"] == "tm_v1_session" for cookie in context.cookies())
    assert_the_app_document(page)


def test_a_wrong_password_keeps_the_gate(app_server: AppServer, context: BrowserContext) -> None:
    """A refused password leaves the visitor on the gate, with no session."""
    page = context.new_page()
    page.goto(app_server.origin + "/")
    page.wait_for_url("**/login")

    status = _submit_password(page, OWNER_EMAIL, OWNER_PASSWORD + " wrong")

    assert status == 401
    assert page.url.endswith("/login")
    assert page.locator(_GATE).is_visible()
    assert not any(cookie["name"] == "tm_v1_session" for cookie in context.cookies())
