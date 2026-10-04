"""#18 — POST /api/acquisition/ranking/preview (ranking editor live preview).

The preview endpoint is pure: it scores a fixed, representative sample set with
the POSTed candidate ranking so the editor can show — live — how a weight/value
change reorders releases, WITHOUT running a real search. Two guarantees matter:

  * the candidate criteria actually reorder the samples (provider/language), and
  * ``min_seeders`` FLAGS rows (``excluded``) instead of dropping them — a live
    preview must never make a row silently vanish.

Direct-call tests cover the scoring/exclusion/sort logic; one HTTP test proves
the route is mounted behind the auth guard and round-trips JSON.
"""

from __future__ import annotations

from typing import Any

from personalscraper.conf.models._ranking import RankingConfig, RankingCriterion
from personalscraper.config import Settings
from personalscraper.web.auth.tokens import create_session_token
from personalscraper.web.models.acquisition import RankingPreviewResponse
from personalscraper.web.routes.acquisition import router as acquisition_router
from personalscraper.web.routes.acquisition_ranking import preview_ranking
from personalscraper.web.routes.acquisition_ranking import router as ranking_router
from tests.web._web_harness import guarded_client


class TestPreviewRankingLogic:
    """Direct-call coverage of the pure preview endpoint."""

    def test_provider_and_language_put_tr4ker_multi_on_top(self) -> None:
        """A tr4ker + MULTI sample wins under a provider+language ranking."""
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(field="provider", weight=1, values={"tr4ker": 15, "c411": 5}),
                RankingCriterion(field="language", weight=2, values={"MULTI": 20, "VOSTFR": 6}),
            ],
            min_seeders=1,
        )
        resp = preview_ranking(cfg)
        assert isinstance(resp, RankingPreviewResponse)
        assert len(resp.ranked) == 12, "no sample may be dropped from the preview"
        top = resp.ranked[0]
        assert top.provider == "tr4ker"
        assert top.language == "MULTI"
        assert len(resp.known_trackers) >= 1, "known_trackers must not be empty"
        # Exact-roster pin: the response exposes the factory roster and NOTHING
        # else — removed trackers must never resurface in the select options.
        assert resp.known_trackers == ["c411", "tr4ker"]
        # The samples themselves may only advertise live trackers: relabelling
        # one onto a removed tracker keeps the count and the roster intact, so
        # only this set pin catches it.
        assert {r.provider for r in resp.ranked} == {"c411", "tr4ker"}
        assert all(r.leechers >= 0 for r in resp.ranked), "leechers must be >= 0"

    def test_min_seeders_flags_but_never_drops(self) -> None:
        """min_seeders marks low-seed rows excluded and sinks them — never drops."""
        cfg = RankingConfig(
            criteria=[RankingCriterion(field="provider", weight=1, values={"tr4ker": 15})],
            min_seeders=10,
        )
        resp = preview_ranking(cfg)
        assert len(resp.ranked) == 12, "excluded samples must still be present"
        # The seeders <= 5 samples are below 10 → flagged excluded.
        assert any(r.excluded and r.seeders < 10 for r in resp.ranked)
        # Excluded rows sink to the end; the non-excluded prefix has none flagged.
        first_excluded = next((i for i, r in enumerate(resp.ranked) if r.excluded), len(resp.ranked))
        assert all(not r.excluded for r in resp.ranked[:first_excluded])
        assert all(r.excluded for r in resp.ranked[first_excluded:])

    def test_empty_ranking_scores_zero_keeps_all(self) -> None:
        """Empty criteria + zeroed bonuses scores every sample 0, still returns twelve."""
        # Zero the bonuses too: freeleech samples would otherwise earn the default
        # +10 freeleech bonus even with no criteria.
        cfg = RankingConfig(criteria=[], bonuses={"freeleech": 0, "silverleech": 0}, min_seeders=1)
        resp = preview_ranking(cfg)
        assert len(resp.ranked) == 12
        assert all(r.score == 0 for r in resp.ranked)


class TestPreviewRankingRoute:
    """The route is mounted behind the auth guard and round-trips JSON."""

    def test_http_preview_returns_scored_samples(self, test_config: Any) -> None:
        """POST with a candidate ranking returns 200 + twelve scored samples."""
        settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
        client = guarded_client(
            config=test_config,
            settings=settings,
            routers=[acquisition_router, ranking_router],
            with_auth=False,
            https=False,
        )
        token = create_session_token("izno", "testsecret", 24)
        resp = client.post(
            "/api/acquisition/ranking/preview",
            json={
                "criteria": [{"field": "provider", "weight": 1, "values": {"tr4ker": 15, "c411": 5}}],
                "min_seeders": 1,
            },
            cookies={"tm_session": token},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["ranked"]) == 12
        assert data["ranked"][0]["provider"] == "tr4ker"
        # known_trackers asserted.
        assert isinstance(data["known_trackers"], list)
        assert len(data["known_trackers"]) >= 1, "known_trackers must not be empty"
        # Exact-roster pin: only live factory trackers, removed ones stay gone.
        assert data["known_trackers"] == ["c411", "tr4ker"]
        # Every release carries leechers.
        assert all("leechers" in r and isinstance(r["leechers"], int) for r in data["ranked"])

    def test_http_preview_requires_auth(self, test_config: Any) -> None:
        """Without a session cookie the guard rejects the request."""
        settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
        client = guarded_client(
            config=test_config,
            settings=settings,
            routers=[acquisition_router, ranking_router],
            with_auth=False,
            https=False,
        )
        resp = client.post(
            "/api/acquisition/ranking/preview",
            json={"criteria": [], "min_seeders": 1},
        )
        assert resp.status_code in (401, 403)
