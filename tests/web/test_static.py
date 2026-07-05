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

    # -- PWA root-file regression tests (fix: real files at static root
    #    must NOT be shadowed by the SPA index.html fallback).

    def test_sw_js_served_verbatim(self, tmp_path: Path) -> None:
        """GET /sw.js returns the real file with a javascript content-type."""
        static_dir = self._make_static_dir(tmp_path)
        (static_dir / "sw.js").write_text("self.addEventListener('install', ...);")
        client = self._make_app(static_dir)

        response = client.get("/sw.js")

        assert response.status_code == 200
        assert "self.addEventListener" in response.text
        # Starlette infers text/javascript for .js files.
        assert "javascript" in response.headers.get("content-type", "")

    def test_manifest_webmanifest_served_with_correct_mime(self, tmp_path: Path) -> None:
        """GET /manifest.webmanifest returns application/manifest+json."""
        static_dir = self._make_static_dir(tmp_path)
        manifest_bytes = b'{"name":"Test","start_url":"/"}'
        (static_dir / "manifest.webmanifest").write_bytes(manifest_bytes)
        client = self._make_app(static_dir)

        response = client.get("/manifest.webmanifest")

        assert response.status_code == 200
        assert response.content == manifest_bytes
        assert response.headers.get("content-type") == "application/manifest+json"

    def test_png_at_root_served_as_image(self, tmp_path: Path) -> None:
        """GET /pwa-192x192.png returns the real file with image/png."""
        static_dir = self._make_static_dir(tmp_path)
        # Minimal valid PNG: 1×1 red pixel.
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010802"
            "00000000907753de0000000c4944415408996378fa0100030003"
            "f9089e76000000004945ae426082"
        )
        (static_dir / "pwa-192x192.png").write_bytes(png_bytes)
        client = self._make_app(static_dir)

        response = client.get("/pwa-192x192.png")

        assert response.status_code == 200
        assert response.content == png_bytes
        assert response.headers.get("content-type") == "image/png"

    def test_spa_route_still_falls_back_to_index_html(self, tmp_path: Path) -> None:
        """A deep SPA route that does not exist on disk still returns index.html."""
        static_dir = self._make_static_dir(tmp_path)
        # No file at /some/spa/route — must fall back.
        client = self._make_app(static_dir)

        response = client.get("/some/spa/route")

        assert response.status_code == 200
        assert "<html>SPA</html>" in response.text

    def test_path_traversal_double_dot_does_not_escape_static_dir(self, tmp_path: Path) -> None:
        """/../../etc/passwd does NOT leak files outside static_dir."""
        static_dir = self._make_static_dir(tmp_path)
        client = self._make_app(static_dir)

        response = client.get("/../../etc/passwd")

        # Must fall back to index.html, never serve an external file.
        assert response.status_code == 200
        assert "<html>SPA</html>" in response.text

    def test_path_traversal_encoded_does_not_escape_static_dir(self, tmp_path: Path) -> None:
        """URL-encoded traversal /..%2f.. does NOT leak files outside static_dir."""
        static_dir = self._make_static_dir(tmp_path)
        client = self._make_app(static_dir)

        response = client.get("/..%2f..%2fetc%2fpasswd")

        # Must fall back to index.html, never serve an external file.
        assert response.status_code == 200
        assert "<html>SPA</html>" in response.text


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
