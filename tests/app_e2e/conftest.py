"""The app e2e lane: the BUILT client against a seeded v1 server, driven by a real browser.

The app build (``npm run build:app`` in ``webui/design``: no mock layer, no harness, no
phone frame) is served by the standalone v1 server itself, beside ``/api/v1``, so every
request the client makes is answered by v1 — nothing simulates the server. Each test
gets a fresh ``tmp`` data directory, its own server on a free port above 9000, and the
owner seeded the way the design host's dev seed does it (``accounts create-owner``).

ONE FILE PER SURFACE, and the lane grows with the server: an operation v1 starts serving
gets its surface's file here, against the same fixtures.

The lane runs under the ``app_e2e`` marker only (``pytest -m app_e2e tests/app_e2e``),
because it needs the built client and a Playwright Chromium; continuous integration
builds both in its own job.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from personalscraper.app.accounts.credentials import OwnerPlexIdentity
from personalscraper.app.composition import build_app_services
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.http_v1.session_cookie import SESSION_COOKIE
from personalscraper.http_v1.standalone import build_standalone_v1_app
from tests.unit.app.library.world import FixtureIndex

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page

#: The built client; ``npm run build:app`` writes it.
DIST: Final = Path(__file__).resolve().parents[2] / "webui" / "design" / "dist"

#: The ports this lane may take: above 9000, never a port the machine's hosts own.
_PORTS: Final = range(9100, 9400)

#: How long the server may take to come up or go down.
_SERVER_TIMEOUT_S: Final = 10.0

#: How long a page may take to show what a test waits for.
PAGE_TIMEOUT_MS: Final = 15_000

OWNER_EMAIL: Final = "owner@example.org"
OWNER_NAME: Final = "Server Owner"
OWNER_PASSWORD: Final = "Lane-owner fallback password 42"


@dataclass(frozen=True)
class SeededLibrary:
    """What the seed put in ``library.db``, for the library surface to find.

    Attributes:
        movie: The movie's title.
        show: The show's title.
    """

    movie: str = "Heat"
    show: str = "Outer Range"


@dataclass(frozen=True)
class AppServer:
    """A running server: the built client and v1, on one origin.

    Attributes:
        origin: ``http://localhost:<port>``.
        owner_session: A session token opened for the owner, for the surfaces that start signed in.
        library: What the seed put in the library.
    """

    origin: str
    owner_session: str
    library: SeededLibrary


def _free_port() -> int:
    """Find a port in the lane's range that nothing listens on.

    Returns:
        The port.

    Raises:
        RuntimeError: When every port of the range is taken.
    """
    for port in _PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free port in {_PORTS.start}-{_PORTS.stop - 1}")


def _serve_the_client(app: FastAPI, dist: Path) -> None:
    """Serve the built client beside v1: a file when the build has it, the document otherwise.

    The document for any other path is what a single-page host does, so a deep link
    boots the client at that address. Registered after v1's mount, which keeps
    ``/api/v1`` first.

    Args:
        app: The standalone v1 application.
        dist: The built client.
    """
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def client_file(path: str) -> FileResponse:
        """Answer one client path.

        Args:
            path: The requested path, without its leading slash.

        Returns:
            The built file, or ``index.html``.
        """
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(root / "index.html")


def seed(config: Config, library: SeededLibrary) -> str:
    """Seed the owner and the library, and open the owner a session.

    The owner is seeded through the same service call ``accounts create-owner`` makes,
    and the session through the one ``accounts open-session --owner`` makes.

    Args:
        config: The test's configuration, on its fresh data directory.
        library: The titles to write in ``library.db``.

    Returns:
        The owner's session token.
    """
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    assert config.indexer.db_path is not None
    index = FixtureIndex(Path(config.indexer.db_path))
    # A title is in the library when a file holds it: the movie one file, the show a season.
    index.movie_file(index.item(library.movie, kind="movie", year=1995, tmdb="949"))
    index.episodes(index.item(library.show, kind="show", year=None, tvdb="404040"), 1, [1, 2])
    index.conn.close()

    services = build_app_services(config, Settings(_env_file=None), event_bus=EventBus())  # type: ignore[call-arg]
    try:
        services.credentials.create_owner(
            email=OWNER_EMAIL,
            name=OWNER_NAME,
            password=OWNER_PASSWORD,
            plex=OwnerPlexIdentity(plex_id=1, plex_uuid="lane-owner", plex_username="lane-owner"),
        )
        owner = services.credentials.owner_account_id()
        assert owner is not None
        return services.credentials.open_proven_session(owner, user_agent="app-e2e").session_token
    finally:
        services.close()


@pytest.fixture(scope="session")
def built_client() -> Path:
    """The app build, refused when it is missing or is a maquette build.

    Returns:
        The ``dist`` directory.
    """
    document = DIST / "index.html"
    if not document.is_file():
        pytest.fail("no built client: run `npm run build:app` in webui/design")
    if 'id="desktop-switch"' in document.read_text(encoding="utf-8"):
        pytest.fail("dist/ is a maquette build: run `npm run build:app` in webui/design")
    return DIST


@pytest.fixture
def app_server(test_config: Config, built_client: Path) -> Iterator[AppServer]:
    """A seeded v1 server serving the built client, on a free port, stopped after the test.

    Args:
        test_config: The synthetic configuration on a fresh ``tmp`` data directory.
        built_client: The app build.

    Yields:
        The running server.
    """
    # The session cookie travels over plain http on localhost: the lane has no proxy.
    config = test_config.model_copy(update={"web": test_config.web.model_copy(update={"cookie_secure": False})})
    library = SeededLibrary()
    token = seed(config, library)
    app = build_standalone_v1_app(config, Settings(_env_file=None))  # type: ignore[call-arg]
    _serve_the_client(app, built_client)

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="app-e2e-server", daemon=True)
    thread.start()
    deadline = time.monotonic() + _SERVER_TIMEOUT_S
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError(f"the lane's server did not start on port {port}")
        time.sleep(0.05)
    try:
        yield AppServer(origin=f"http://localhost:{port}", owner_session=token, library=library)
    finally:
        server.should_exit = True
        thread.join(timeout=_SERVER_TIMEOUT_S)


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    """One headless Chromium for the whole lane — one browser at a time on this machine.

    Yields:
        The browser.
    """
    # Imported here: the default suite collects this directory and deselects it, on
    # runners that have no Playwright.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        launched = playwright.chromium.launch()
        try:
            yield launched
        finally:
            launched.close()


@pytest.fixture
def context(browser: Browser) -> Iterator[BrowserContext]:
    """A fresh browser context per test, in English, at a phone's size.

    Args:
        browser: The lane's browser.

    Yields:
        The context, closed after the test.
    """
    opened = browser.new_context(locale="en-US", viewport={"width": 390, "height": 844})
    opened.set_default_timeout(PAGE_TIMEOUT_MS)
    try:
        yield opened
    finally:
        opened.close()


@pytest.fixture
def signed_in_page(app_server: AppServer, context: BrowserContext) -> Page:
    """A page carrying the owner's session, as a browser that signed in earlier would.

    Args:
        app_server: The running server.
        context: The test's browser context.

    Returns:
        A blank page; the test opens the surface it reads.
    """
    context.add_cookies([{"name": SESSION_COOKIE, "value": app_server.owner_session, "url": app_server.origin}])
    return context.new_page()


def assert_the_app_document(page: Page) -> None:
    """The page is the app's document: no way out of a phone frame, no design note shown.

    Args:
        page: A page of the built client, rendered.
    """
    assert page.locator("#desktop-switch").count() == 0
    assert page.locator('[data-part="note"]:visible').count() == 0
