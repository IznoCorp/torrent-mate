"""The library surface: the listing (``readLibraryItems``) and its categories, read from v1's ``library.db``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.app_e2e.conftest import AppServer, assert_the_app_document

if TYPE_CHECKING:
    from playwright.sync_api import Page

pytestmark = pytest.mark.app_e2e


def test_the_library_lists_the_seeded_titles(app_server: AppServer, signed_in_page: Page) -> None:
    """``/media`` draws the titles v1 reads from the seeded ``library.db``, and only them."""
    page = signed_in_page
    with page.expect_response(lambda response: "/api/v1/library/items" in response.url) as items:
        page.goto(app_server.origin + "/media")

    assert items.value.status == 200
    assert items.value.json()["total"] == 2
    body = page.locator('[data-part="surface/body"]')
    body.get_by_text(app_server.library.movie, exact=True).wait_for()
    assert body.get_by_text(app_server.library.show, exact=True).is_visible()
    assert_the_app_document(page)
