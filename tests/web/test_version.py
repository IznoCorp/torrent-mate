"""Tests for the version route (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.5.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestVersionRoute:
    """Version endpoint returns app version and build commit."""

    def test_returns_200_with_version_and_build_commit(self, web_app: TestClient) -> None:
        """GET /api/version returns 200 with version + build_commit keys."""
        response = web_app.get("/api/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "build_commit" in data

    def test_version_is_non_empty_string(self, web_app: TestClient) -> None:
        """The version field is a non-empty string (Python package version)."""
        response = web_app.get("/api/version")

        data = response.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_build_commit_is_dev_when_no_static_dir(self, web_app: TestClient) -> None:
        """Without a BUILD_COMMIT file, the build_commit defaults to 'dev'."""
        response = web_app.get("/api/version")

        data = response.json()
        assert data["build_commit"] == "dev"
