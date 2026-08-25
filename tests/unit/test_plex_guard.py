"""Plex match coherence guard — hermetic tests over the live-captured shapes.

The fixtures under ``plex_guard_fixtures/`` were captured from the live Plex
server (2026-08-25) for the two films of the wrong-match incident —
ratingKeys 210743 (« The Gentlemen », tmdb 522627) and 210147
(« On l'appelait Robin des Bois », tmdb 1284465). Both items were repaired by
the live API test, so their captured guids are CORRECT: the dry-run of the
guard must report them ALIGNED, exactly as the live state demands.

What these tests pin:

- the guard compares the pipeline's canonical id against the provider guids
  Plex reports, and the two live shapes come back aligned;
- a misaligned item resolves through ``matches`` and is reported (dry-run) or
  re-matched (repair) — and the request sequence matches → match is pinned in
  call order, because a match call without its resolution would be guessing;
- fail-soft: a Plex that cannot be asked turns items into ``plex_error``, never
  ``not_found`` (which would claim the item does not exist);
- the mutation contract: disabling the guid comparison must make the
  misalignment test fall (exercised during development, see module docstring).

The token never appears in any fixture (captured bodies were scrubbed).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from personalscraper.api.plex import PlexClient
from personalscraper.maintenance.plex_guard import (
    STATE_ALIGNED,
    STATE_AMBIGUOUS,
    STATE_MISALIGNED,
    STATE_PLEX_ERROR,
    STATE_REPAIR_FAILED,
    STATE_REPAIRED,
    run_plex_guard,
)

_TOKEN = "PLEX-T0KEN-DO-NOT-LOG-9f3a"
_FIXTURES = Path(__file__).parent / "plex_guard_fixtures"


def _fixture(name: str) -> dict[str, Any]:
    """Load one captured Plex payload."""
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


#: Sections as the live server reports them — the Films section alone, with
#: the exact Location roots the captured paths live under.
_SECTIONS_PAYLOAD: dict[str, Any] = {
    "MediaContainer": {
        "Directory": [
            {
                "key": "4",
                "title": "Films",
                "Location": [{"path": "/Volumes/Disk1/medias/films"}],
            }
        ]
    }
}

#: Section listing (/library/sections/4/all) reduced to what the guard reads:
#: ratingKey + Media/Part.file. The captured item fixtures carry the full
#: shape; the listing only needs the path join.
_SECTION_ALL_PAYLOAD: dict[str, Any] = {
    "MediaContainer": {
        "Metadata": [
            {
                "ratingKey": "210743",
                "Media": [{"Part": [{"file": "/Volumes/Disk1/medias/films/The Gentlemen (2020)/The Gentlemen.mkv"}]}],
            },
            {
                "ratingKey": "210147",
                "Media": [
                    {
                        "Part": [
                            {
                                "file": (
                                    "/Volumes/Disk1/medias/films/On l'appelait Robin des Bois (2026)/"
                                    "On l'appelait Robin des Bois.mkv"
                                )
                            }
                        ]
                    }
                ],
            },
        ]
    }
}


class _FakeResponse:
    """Minimal stand-in for :class:`requests.Response`."""

    def __init__(self, status_code: int = 200, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        """Return the canned payload."""
        return self._payload


class _FakeSession:
    """Routes canned responses by (method, path) and records every call."""

    def __init__(self, routes: dict[tuple[str, str], Any], *, default: Any | None = None) -> None:
        self._routes = routes
        self._default = default if default is not None else _FakeResponse(200, {})
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        params: Any = None,
        headers: Any = None,
        timeout: Any = None,
        allow_redirects: Any = None,
    ) -> Any:
        """Record the GET and return the routed response."""
        self.calls.append({"method": "GET", "url": url, "params": params})
        nxt = self._routes.get(("GET", url), self._default)
        if callable(nxt):
            nxt = nxt()
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def put(
        self,
        url: str,
        *,
        params: Any = None,
        headers: Any = None,
        timeout: Any = None,
        allow_redirects: Any = None,
    ) -> Any:
        """Record the PUT and return the routed response."""
        self.calls.append({"method": "PUT", "url": url, "params": params})
        nxt = self._routes.get(("PUT", url), self._default)
        if callable(nxt):
            nxt = nxt()
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _client(session: _FakeSession) -> PlexClient:
    """Build a client over a fake session."""
    return PlexClient("http://localhost:32400", _TOKEN, session=session)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test DB — the two live items with their canonical ids and dispatch paths
# ---------------------------------------------------------------------------


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """An indexer DB with the columns ``item_repo`` reads, seeded with the two films."""
    conn = sqlite3.connect(str(tmp_path / "library.db"))
    conn.executescript(
        """
        CREATE TABLE media_item (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            title_sort TEXT NOT NULL,
            original_title TEXT,
            year INTEGER,
            category_id TEXT NOT NULL,
            external_ids_json TEXT,
            ratings_json TEXT,
            canonical_provider TEXT,
            nfo_status TEXT NOT NULL DEFAULT 'valid',
            artwork_json TEXT,
            date_created INTEGER NOT NULL,
            date_modified INTEGER NOT NULL,
            date_metadata_refreshed INTEGER,
            is_locked INTEGER NOT NULL DEFAULT 0,
            preferred_lang TEXT NOT NULL DEFAULT 'fr'
        );
        CREATE TABLE item_attribute (
            item_id INTEGER NOT NULL REFERENCES media_item(id),
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY (item_id, key)
        );
        """
    )
    items = [
        (
            210743,
            "movie",
            "The Gentlemen",
            "gentlemen",
            '{"tmdb": {"series_id": "522627"}, "imdb": {"series_id": "tt8367814"}}',
            "/Volumes/Disk1/medias/films/The Gentlemen (2020)",
        ),
        (
            210147,
            "movie",
            "On l'appelait Robin des Bois",
            "robin des bois",
            '{"tmdb": {"series_id": "1284465"}, "imdb": {"series_id": "tt32273171"}}',
            "/Volumes/Disk1/medias/films/On l'appelait Robin des Bois (2026)",
        ),
    ]
    for item_id, kind, title, sort, ids_json, dispatch_path in items:
        conn.execute(
            "INSERT INTO media_item (id, kind, title, title_sort, category_id, external_ids_json, "
            "date_created, date_modified) VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
            (item_id, kind, title, sort, "movies", ids_json),
        )
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, ?, ?)",
            (item_id, "dispatch_normalized_title", sort),
        )
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, ?, ?)",
            (item_id, "dispatch_disk", "drive_disk1"),
        )
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, ?, ?)",
            (item_id, "dispatch_path", dispatch_path),
        )
    conn.commit()
    return conn


def _routes(
    *,
    gentlemen_guid: str = "tmdb://522627",
    section_all: Any | None = None,
    gentlemen_matches: Any | None = None,
    match_status: int = 200,
) -> dict[tuple[str, str], Any]:
    """Standard route table: sections, the section listing, and one item each.

    The gentlemen guid is MUTABLE state: the match PUT flips it to the
    canonical id, so the guard's post-PUT verification read (which re-reads
    the same metadata route) sees the repaired item — exactly like the live
    server behaves.

    Args:
        gentlemen_guid: The guid the metadata route starts with — the real
            capture is correct, a wrong one simulates the incident.
        section_all: Override for the section listing (None = the two-item one).
        gentlemen_matches: Override for the gentlemen matches payload (None =
            the captured single-candidate one). Pass a two-SearchResult
            payload for the ambiguity test.
        match_status: HTTP status the match PUT answers with (500 = refused).
    """
    state: dict[str, str] = {"gentlemen_guid": gentlemen_guid}
    gentlemen = _fixture("item-gentlemen")
    robin = _fixture("item-robin")

    def gentlemen_route() -> _FakeResponse:
        payload = json.loads(json.dumps(gentlemen))
        payload["MediaContainer"]["Metadata"][0]["Guid"] = [
            {"id": g} for g in ["imdb://tt8367814", state["gentlemen_guid"], "tvdb://131524"]
        ]
        return _FakeResponse(200, payload)

    def match_route() -> _FakeResponse:
        state["gentlemen_guid"] = "tmdb://522627"
        return _FakeResponse(match_status, {})

    return {
        ("GET", "http://localhost:32400/library/sections"): _FakeResponse(200, _SECTIONS_PAYLOAD),
        ("GET", "http://localhost:32400/library/sections/4/all"): _FakeResponse(
            200, section_all if section_all is not None else _SECTION_ALL_PAYLOAD
        ),
        ("GET", "http://localhost:32400/library/metadata/210743"): gentlemen_route,
        ("GET", "http://localhost:32400/library/metadata/210147"): _FakeResponse(200, robin),
        ("GET", "http://localhost:32400/library/metadata/210743/matches"): _FakeResponse(
            200, gentlemen_matches if gentlemen_matches is not None else _fixture("matches-gentlemen")
        ),
        ("GET", "http://localhost:32400/library/metadata/210147/matches"): _FakeResponse(
            200, _fixture("matches-robin")
        ),
        ("PUT", "http://localhost:32400/library/metadata/210743/match"): match_route,
        ("PUT", "http://localhost:32400/library/metadata/210147/match"): _FakeResponse(match_status, {}),
    }


# ---------------------------------------------------------------------------
# The check itself
# ---------------------------------------------------------------------------


class TestLiveShapesAreAligned:
    """The two captured items carry their canonical ids — dry-run says so."""

    def test_both_live_items_report_aligned(self, db_conn: sqlite3.Connection) -> None:
        """Dry-run over the real captured shapes: 2 aligned, 0 repair."""
        session = _FakeSession(_routes())
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=False, now="2026-08-25T00:00:00Z")

        assert result.aligned_count == 2
        assert result.repaired_count == 0
        assert result.skipped_count == 0
        assert [f.state for f in result.findings] == [STATE_ALIGNED, STATE_ALIGNED]
        assert [f.canonical_id for f in result.findings] == ["522627", "1284465"]

        # A dry-run issues no PUT — ever.
        assert not any(call["method"] == "PUT" for call in session.calls)

    def test_guid_comparison_is_what_holds_the_green(self, db_conn: sqlite3.Connection) -> None:
        """A wrong guid on Plex's side must flip the finding to misaligned.

        This is the mutation-check's red half: if the guid comparison were
        disabled (or trivially true), the finding would stay aligned and this
        test would fail — which is exactly what it is for.
        """
        session = _FakeSession(_routes(gentlemen_guid="imdb://tt30141774"))
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=False, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_MISALIGNED
        assert by_item[210743].canonical_id == "522627"
        assert by_item[210147].state == STATE_ALIGNED
        assert result.aligned_count == 1
        assert not any(call["method"] == "PUT" for call in session.calls)


class TestRepair:
    """The matches → match sequence, pinned in order."""

    def test_repair_resolves_then_applies_in_that_order(self, db_conn: sqlite3.Connection) -> None:
        """A wrong guid gets resolved through matches, then re-matched."""
        session = _FakeSession(_routes(gentlemen_guid="imdb://tt30141774"))
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=True, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_REPAIRED
        assert by_item[210147].state == STATE_ALIGNED
        assert result.repaired_count == 1

        # Characterization pin: for the repaired item, matches() precedes
        # match(), and the item is RE-READ after the PUT — « repaired » is
        # only ever claimed on the verified guid, never on the PUT's status.
        # A match call without its resolution would be guessing; a repair
        # without the verification read would be trusting.
        gentlemen_calls = [
            (call["method"], call["url"], call["params"]) for call in session.calls if "210743" in call["url"]
        ]
        assert gentlemen_calls[:3] == [
            ("GET", "http://localhost:32400/library/metadata/210743", None),
            (
                "GET",
                "http://localhost:32400/library/metadata/210743/matches",
                {"manual": "1", "title": "tmdb-522627"},
            ),
            (
                "PUT",
                "http://localhost:32400/library/metadata/210743/match",
                {"guid": "plex://movie/5d77704aad5437001f81e604", "name": "The Gentlemen", "year": "2020"},
            ),
        ]
        # The PUT is followed by a verification re-read (bounded retries —
        # the live server's match is eventual-consistent, so the first read
        # may not see it yet). The pin allows the retries but forbids any
        # call that is not a metadata re-read after the PUT.
        assert gentlemen_calls[3:]
        assert all(
            call == ("GET", "http://localhost:32400/library/metadata/210743", None) for call in gentlemen_calls[3:]
        )

    def test_refused_put_reports_plex_error_not_repaired(self, db_conn: sqlite3.Connection) -> None:
        """A 500 on the match PUT must never be reported green."""
        session = _FakeSession(_routes(gentlemen_guid="imdb://tt30141774", match_status=500))
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=True, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_PLEX_ERROR
        assert result.repaired_count == 0

    def test_unverified_repair_reports_repair_failed(
        self, db_conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PUT that does not take (guid still wrong on re-read) is repair_failed."""
        # The retry loop sleeps between attempts — collapse it so the test
        # measures the RETRIES, not the wall clock.
        monkeypatch.setattr("personalscraper.maintenance.plex_guard.time.sleep", lambda _s: None)
        # matches route returns the captured candidate, but the match PUT is a
        # no-op: the metadata route keeps the wrong guid even after it.
        session = _FakeSession(_routes(gentlemen_guid="imdb://tt30141774", gentlemen_matches=None))
        # Force the PUT handler to NOT flip the guid: a route override that
        # answers 200 without touching the state.
        session._routes[("PUT", "http://localhost:32400/library/metadata/210743/match")] = _FakeResponse(200, {})  # noqa: SLF001
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=True, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_REPAIR_FAILED
        assert result.repaired_count == 0

    def test_ambiguous_candidates_are_never_applied(self, db_conn: sqlite3.Connection) -> None:
        """Two candidates ⇒ no repair, in BOTH modes — applying one would be a guess."""
        two_candidates = {
            "MediaContainer": {
                "SearchResult": [
                    _fixture("matches-gentlemen")["MediaContainer"]["SearchResult"][0],
                    {
                        "guid": "plex://movie/5d77704aad5437001f81e6ff",
                        "name": "The Gentlemen (other edition)",
                        "year": 2020,
                    },
                ]
            }
        }
        session = _FakeSession(_routes(gentlemen_guid="imdb://tt30141774", gentlemen_matches=two_candidates))
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=True, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_AMBIGUOUS
        assert not any(call["method"] == "PUT" for call in session.calls)

    def test_dry_run_reports_misaligned_without_writing(self, db_conn: sqlite3.Connection) -> None:
        """Dry-run and repair must differ ONLY by the PUT."""
        session = _FakeSession(_routes(gentlemen_guid="imdb://tt30141774"))
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=False, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_MISALIGNED
        assert not any(call["method"] == "PUT" for call in session.calls)


class TestFailSoft:
    """Plex failures degrade to reported states, never to exceptions."""

    def test_plex_down_marks_items_plex_error_not_not_found(self, db_conn: sqlite3.Connection) -> None:
        """An unreachable Plex (no sections) must not claim items do not exist."""
        session = _FakeSession(
            {("GET", "http://localhost:32400/library/sections"): _FakeResponse(200, {"MediaContainer": {}})}
        )
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=True, now="2026-08-25T00:00:00Z")

        assert all(f.state == STATE_PLEX_ERROR for f in result.findings)
        assert result.skipped_count == 2
        assert not any(call["method"] == "PUT" for call in session.calls)

    def test_item_absent_from_plex_is_not_found(self, db_conn: sqlite3.Connection) -> None:
        """A folder Plex has not scanned yet is ``not_found`` — a real, distinct state."""
        # Section listing without the Gentlemen folder.
        session = _FakeSession(
            _routes(
                section_all={
                    "MediaContainer": {
                        "Metadata": [
                            {
                                "ratingKey": "210147",
                                "Media": [
                                    {
                                        "Part": [
                                            {
                                                "file": (
                                                    "/Volumes/Disk1/medias/films/On l'appelait Robin des Bois (2026)/"
                                                    "On l'appelait Robin des Bois.mkv"
                                                )
                                            }
                                        ]
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=True, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == "not_found"
        assert by_item[210147].state == STATE_ALIGNED


class TestCliRegistration:
    """``personalscraper plex-guard`` exists and documents its modes."""

    def test_help_exits_zero_and_documents_modes(self) -> None:
        """The command is registered; dry-run default and --repair are stated."""
        from typer.testing import CliRunner

        from personalscraper.cli import app

        result = CliRunner().invoke(app, ["plex-guard", "--help"])
        assert result.exit_code == 0, result.output
        assert "--repair" in result.output
        assert "--item-id" in result.output


# ---------------------------------------------------------------------------
# Show family — the half the live sweep broke on
# ---------------------------------------------------------------------------

_TV_SECTIONS_PAYLOAD: dict[str, Any] = {
    "MediaContainer": {
        "Directory": [
            {
                "key": "5",
                "title": "Séries",
                "Location": [{"path": "/Volumes/Disk4/medias/series"}],
            }
        ]
    }
}

#: The show-level listing carries NO path (the live shape that broke the first
#: sweep); the EPISODE listing (``?type=4``) carries Part.file +
#: grandparentRatingKey — the join the guard uses.
_TV_EPISODE_LISTING_PAYLOAD: dict[str, Any] = {
    "MediaContainer": {
        "Metadata": [
            {
                "ratingKey": "21655",
                "grandparentRatingKey": "21654",
                "Media": [{"Part": [{"file": "/Volumes/Disk4/medias/series/Chernobyl (2019)/Saison 01/S01E01.mkv"}]}],
            }
        ]
    }
}

_CHERNOBYL_ITEM_PAYLOAD: dict[str, Any] = {
    "MediaContainer": {
        "Metadata": [
            {
                "ratingKey": "21654",
                "title": "Chernobyl",
                "type": "show",
                "Guid": [{"id": "imdb://tt7366338"}, {"id": "tvdb://360893"}, {"id": "tmdb://87108"}],
                "Location": [{"path": "/Volumes/Disk4/medias/series/Chernobyl (2019)"}],
            }
        ]
    }
}

_CHERNOBYL_MATCHES_PAYLOAD: dict[str, Any] = {
    "MediaContainer": {
        "SearchResult": [{"guid": "plex://show/5d776bb37a53e9001e72dae3", "name": "Chernobyl", "year": 2019}]
    }
}


@pytest.fixture
def show_db_conn(tmp_path: Path) -> sqlite3.Connection:
    """An indexer DB seeded with one dispatched show (Chernobyl, tvdb-360893)."""
    conn = sqlite3.connect(str(tmp_path / "library.db"))
    conn.executescript(
        """
        CREATE TABLE media_item (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            title_sort TEXT NOT NULL,
            original_title TEXT,
            year INTEGER,
            category_id TEXT NOT NULL,
            external_ids_json TEXT,
            ratings_json TEXT,
            canonical_provider TEXT,
            nfo_status TEXT NOT NULL DEFAULT 'valid',
            artwork_json TEXT,
            date_created INTEGER NOT NULL,
            date_modified INTEGER NOT NULL,
            date_metadata_refreshed INTEGER,
            is_locked INTEGER NOT NULL DEFAULT 0,
            preferred_lang TEXT NOT NULL DEFAULT 'fr'
        );
        CREATE TABLE item_attribute (
            item_id INTEGER NOT NULL REFERENCES media_item(id),
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY (item_id, key)
        );
        """
    )
    conn.execute(
        "INSERT INTO media_item (id, kind, title, title_sort, category_id, external_ids_json, "
        "date_created, date_modified) VALUES (2032, 'show', 'Chernobyl', 'chernobyl', 'tv_shows', ?, 0, 0)",
        ('{"tvdb": {"series_id": "360893"}}',),
    )
    for key, value in (
        ("dispatch_normalized_title", "chernobyl"),
        ("dispatch_disk", "drive_disk4"),
        ("dispatch_path", "/Volumes/Disk4/medias/series/Chernobyl (2019)"),
    ):
        conn.execute("INSERT INTO item_attribute (item_id, key, value) VALUES (2032, ?, ?)", (key, value))
    conn.commit()
    return conn


def _show_routes(*, item_payload: Any | None = None, matches_payload: Any | None = None) -> dict[tuple[str, str], Any]:
    """Route table for the TV section: sections, type=4 listing, show item.

    The show item payload is MUTABLE state: the match PUT flips its guid to
    the canonical id, so the guard's post-PUT verification read sees the
    repaired item — like the live server behaves.
    """
    state: dict[str, Any] = {"item": item_payload if item_payload is not None else _CHERNOBYL_ITEM_PAYLOAD}

    def item_route() -> _FakeResponse:
        return _FakeResponse(200, state["item"])

    def match_route() -> _FakeResponse:
        repaired = json.loads(json.dumps(_CHERNOBYL_ITEM_PAYLOAD))
        state["item"] = repaired
        return _FakeResponse(200, {})

    return {
        ("GET", "http://localhost:32400/library/sections"): _FakeResponse(200, _TV_SECTIONS_PAYLOAD),
        ("GET", "http://localhost:32400/library/sections/5/all"): _FakeResponse(200, _TV_EPISODE_LISTING_PAYLOAD),
        ("GET", "http://localhost:32400/library/metadata/21654"): item_route,
        ("GET", "http://localhost:32400/library/metadata/21654/matches"): _FakeResponse(
            200, matches_payload if matches_payload is not None else _CHERNOBYL_MATCHES_PAYLOAD
        ),
        ("PUT", "http://localhost:32400/library/metadata/21654/match"): match_route,
    }


class TestShowFamily:
    """A show is located through the episode listing, compared by tvdb id."""

    def test_show_located_via_episode_listing_reports_aligned(self, show_db_conn: sqlite3.Connection) -> None:
        """The type=4 listing is the ONLY path a show has — pinned here."""
        session = _FakeSession(_show_routes())
        result = run_plex_guard(
            client=_client(session), connection=show_db_conn, repair=False, now="2026-08-25T00:00:00Z"
        )

        (finding,) = result.findings
        assert finding.state == STATE_ALIGNED
        assert finding.rating_key == "21654"
        assert finding.canonical_provider == "tvdb"
        assert finding.canonical_id == "360893"
        # The show is located through the EPISODE listing — the show-level
        # listing is never even requested, because its shape carries no path.
        assert any(call["params"] == {"type": "4"} for call in session.calls)

    def test_misaligned_show_repairs_via_tvdb_hint(self, show_db_conn: sqlite3.Connection) -> None:
        """A wrong-guid show resolves through tvdb-{id} and is re-matched."""
        wrong = json.loads(json.dumps(_CHERNOBYL_ITEM_PAYLOAD))
        wrong["MediaContainer"]["Metadata"][0]["Guid"] = [{"id": "tvdb://999999"}]
        session = _FakeSession(_show_routes(item_payload=wrong))
        result = run_plex_guard(
            client=_client(session), connection=show_db_conn, repair=True, now="2026-08-25T00:00:00Z"
        )

        (finding,) = result.findings
        assert finding.state == STATE_REPAIRED
        match_call = next(c for c in session.calls if "matches" in c["url"])
        assert match_call["params"] == {"manual": "1", "title": "tvdb-360893"}


class TestPathRobustness:
    """The path join survives the divergence classes the repo documents."""

    def test_case_drift_in_plex_path_still_finds_the_item(self, db_conn: sqlite3.Connection) -> None:
        """Plex holds the file under different casing than the stored path."""
        drifted = {
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "210743",
                        "Media": [
                            {"Part": [{"file": "/Volumes/disk1/Medias/Films/The Gentlemen (2020)/the gentlemen.mkv"}]}
                        ],
                    },
                    {
                        "ratingKey": "210147",
                        "Media": [
                            {
                                "Part": [
                                    {
                                        "file": (
                                            "/Volumes/Disk1/medias/films/On l'appelait Robin des Bois (2026)/"
                                            "On l'appelait Robin des Bois.mkv"
                                        )
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        }
        session = _FakeSession(_routes(section_all=drifted))
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=False, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_ALIGNED  # case drift folded away
        assert by_item[210147].state == STATE_ALIGNED

    def test_boundary_violation_never_matches(self, db_conn: sqlite3.Connection) -> None:
        """``/films`` must never match a folder Plex holds under ``/films-old``."""
        sibling = {
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "210743",
                        "Media": [
                            {
                                "Part": [
                                    {"file": ("/Volumes/Disk1/medias/films-old/The Gentlemen (2020)/The Gentlemen.mkv")}
                                ]
                            }
                        ],
                    },
                    {
                        "ratingKey": "210147",
                        "Media": [
                            {
                                "Part": [
                                    {
                                        "file": (
                                            "/Volumes/Disk1/medias/films/On l'appelait Robin des Bois (2026)/"
                                            "On l'appelait Robin des Bois.mkv"
                                        )
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        }
        session = _FakeSession(_routes(section_all=sibling))
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=False, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == "not_found"  # films-old is a sibling, not a prefix
        assert by_item[210147].state == STATE_ALIGNED

    def test_title_suspect_is_surfaced_on_an_aligned_item(self, db_conn: sqlite3.Connection) -> None:
        """Right guid + wrong display title ⇒ aligned + title_suspect (operator sees it)."""
        wrong_title = json.loads(json.dumps(_fixture("item-gentlemen")))
        wrong_title["MediaContainer"]["Metadata"][0]["title"] = "Shameless: Very Important Punk"
        session = _FakeSession(_routes())
        session._routes[("GET", "http://localhost:32400/library/metadata/210743")] = _FakeResponse(  # noqa: SLF001
            200, wrong_title
        )
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=False, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_ALIGNED  # the id IS the identity
        assert by_item[210743].title_suspect is True
        assert by_item[210743].plex_title == "Shameless: Very Important Punk"
        assert by_item[210147].state == STATE_ALIGNED

    def test_plex_french_localization_is_not_suspect(self, db_conn: sqlite3.Connection) -> None:
        """Plex's own localised title is not a mismatch when it matches original_title."""
        db_conn.execute("UPDATE media_item SET original_title = 'Frères d''armes' WHERE id = 210743")
        db_conn.commit()
        localized = json.loads(json.dumps(_fixture("item-gentlemen")))
        localized["MediaContainer"]["Metadata"][0]["title"] = "Frères d'armes"
        session = _FakeSession(_routes())
        session._routes[("GET", "http://localhost:32400/library/metadata/210743")] = _FakeResponse(  # noqa: SLF001
            200, localized
        )
        result = run_plex_guard(client=_client(session), connection=db_conn, repair=False, now="2026-08-25T00:00:00Z")

        by_item = {f.item_id: f for f in result.findings}
        assert by_item[210743].state == STATE_ALIGNED
        assert by_item[210743].title_suspect is False
