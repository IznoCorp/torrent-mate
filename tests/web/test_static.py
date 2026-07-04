"""Tests for the SPA static file serving (tm-shell feature).

Exercises ``mount_spa`` with a temp static directory — the same public seam
that ``create_app`` calls. See docs/features/tm-shell/DESIGN.md §4.7.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.web.static import mount_spa


class TestSpaPresent:
    """SPA built → index.html fallback, /api not swallowed, /assets mounted."""

    @staticmethod
    def _make_static_dir(tmp_path: Path) -> Path:
        """Create a minimal built SPA directory with index.html and assets/.

        Args:
            tmp_path: Pytest temporary directory.

        Returns:
            Path to the static directory.
        """
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>SPA</html>")
        assets = static_dir / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log('hello');")
        return static_dir

    @staticmethod
    def _make_app(static_dir: Path, dev_mode: bool = False) -> TestClient:
        """Build a minimal FastAPI app with mount_spa and return a TestClient.

        Args:
            static_dir: Path to the static directory.
            dev_mode: Forwarded to mount_spa.

        Returns:
            A TestClient for the app.
        """
        app = FastAPI()
        mount_spa(app, static_dir, dev_mode)
        return TestClient(app)

    def test_catch_all_returns_index_html(self, tmp_path: Path) -> None:
        """Any non-/api, non-/ws path returns the index.html content."""
        static_dir = self._make_static_dir(tmp_path)
        client = self._make_app(static_dir)

        response = client.get("/some/random/path")

        assert response.status_code == 200
        assert "<html>SPA</html>" in response.text

    def test_root_returns_index_html(self, tmp_path: Path) -> None:
        """GET / returns index.html."""
        static_dir = self._make_static_dir(tmp_path)
        client = self._make_app(static_dir)

        response = client.get("/")

        assert response.status_code == 200
        assert "<html>SPA</html>" in response.text

    def test_api_paths_not_swallowed(self, tmp_path: Path) -> None:
        """/api/* paths are NOT served as index.html — fallback returns 404."""
        static_dir = self._make_static_dir(tmp_path)
        client = self._make_app(static_dir)

        response = client.get("/api/health")

        assert response.status_code == 404

    def test_ws_paths_not_swallowed(self, tmp_path: Path) -> None:
        """/ws/* paths are NOT served as index.html — fallback returns 404."""
        static_dir = self._make_static_dir(tmp_path)
        client = self._make_app(static_dir)

        response = client.get("/ws/events")

        assert response.status_code == 404

    def test_assets_mounted(self, tmp_path: Path) -> None:
        """Assets directory is mounted — GET /assets/app.js returns the file."""
        static_dir = self._make_static_dir(tmp_path)
        client = self._make_app(static_dir)

        response = client.get("/assets/app.js")

        assert response.status_code == 200
        assert "console.log" in response.text


class TestSpaMissing:
    """SPA not built → 503 fallback (safety net; boot refusal is CLI concern)."""

    @staticmethod
    def _make_missing_dir(tmp_path: Path) -> Path:
        """Create an empty directory (no index.html).

        Args:
            tmp_path: Pytest temporary directory.

        Returns:
            Path to the empty directory.
        """
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        return static_dir

    def test_dev_mode_returns_503_with_hint(self, tmp_path: Path) -> None:
        """Missing SPA + dev_mode=True → 503 with 'SPA not built (dev_mode)'."""
        static_dir = self._make_missing_dir(tmp_path)
        app = FastAPI()
        mount_spa(app, static_dir, dev_mode=True)
        client = TestClient(app)

        response = client.get("/any/path")

        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "SPA not built (dev_mode)"

    def test_prod_mode_returns_503(self, tmp_path: Path) -> None:
        """Missing SPA + dev_mode=False → 503 with 'SPA not built'."""
        static_dir = self._make_missing_dir(tmp_path)
        app = FastAPI()
        mount_spa(app, static_dir, dev_mode=False)
        client = TestClient(app)

        response = client.get("/any/path")

        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "SPA not built"

    def test_api_paths_still_return_404(self, tmp_path: Path) -> None:
        """/api/* paths return 404 even when SPA is missing."""
        static_dir = self._make_missing_dir(tmp_path)
        app = FastAPI()
        mount_spa(app, static_dir, dev_mode=False)
        client = TestClient(app)

        response = client.get("/api/health")

        assert response.status_code == 404
