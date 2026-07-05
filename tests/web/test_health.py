"""Tests for the health-check route (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.4.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from personalscraper.conf.models.web import WebConfig
from personalscraper.config import Settings
from personalscraper.web.app import create_app


class TestHealthRoute:
    """Health endpoint returns 200 with status/redis/db keys."""

    def test_returns_200_with_correct_shape(self, web_app: TestClient) -> None:
        """GET /api/health returns 200 and all three required keys."""
        response = web_app.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "redis" in data
        assert "db" in data

    def test_redis_false_when_port_closed(self, test_config) -> None:
        """A closed port on localhost → instant connection refusal → redis: false.

        Uses ``redis://127.0.0.1:1/0`` (port 1 is reserved and closed on
        macOS/Linux) so the 1-second connect timeout triggers immediately
        rather than waiting for a SYN timeout.
        """
        web_cfg = WebConfig(redis_url="redis://127.0.0.1:1/0")
        cfg = test_config.model_copy(update={"web": web_cfg})
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        app = create_app(cfg, settings)
        client = TestClient(app)

        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["redis"] is False

    def test_redis_true_when_ping_succeeds(self, web_app: TestClient) -> None:
        """A reachable Redis → ping returns True → redis: true."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("redis.Redis.from_url", return_value=mock_redis):
            response = web_app.get("/api/health")

        assert response.status_code == 200
        assert response.json()["redis"] is True

    def test_db_false_when_library_db_missing(self, web_app: TestClient) -> None:
        """No library.db on the test data_dir → db: false."""
        response = web_app.get("/api/health")

        assert response.status_code == 200
        assert response.json()["db"] is False

    def test_db_true_when_library_db_exists(self, test_config) -> None:
        """A library.db file on disk → db: true."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "library.db").write_text("")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        app = create_app(test_config, settings)
        client = TestClient(app)

        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["db"] is True
