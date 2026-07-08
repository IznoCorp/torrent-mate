"""Tests for personalscraper.conf.loader.validate_candidate."""

import hashlib
import os
import threading
from pathlib import Path

import pytest

from personalscraper.conf.loader import (
    ConfigConflictError,
    ConfigLoadError,
    ConfigValidationError,
    validate_candidate,
)
from personalscraper.conf.models.config import Config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_master(path: Path, tmp_path: Path, overlay_names: list[str] | None = None) -> None:
    """Write a minimal master config.json5 with the given overlay declarations.

    Args:
        path: File path (should be ``<config_dir>/config.json5``).
        tmp_path: Root used for disk/staging/complete directory paths.
        overlay_names: Overlay filenames declared in the master's ``overlays``
            key.  If ``None``, no overlays key is written.
    """
    overlays_fragment = ""
    if overlay_names is not None:
        names_literal = ", ".join(f'"{n}"' for n in overlay_names)
        overlays_fragment = f"overlays: [{names_literal}],"

    content = f"""{{
        config_version: 1,
        {overlays_fragment}
        paths: {{
            torrent_complete_dir: "{tmp_path / "complete"}",
            staging_dir: "{tmp_path / "staging"}",
            data_dir: "{tmp_path / ".data"}",
        }},
        disks: [
            {{
                id: "disk_a",
                path: "{tmp_path / "disk_a"}",
                categories: ["movies", "tv_shows"],
            }},
        ],
        staging_dirs: [
            {{ id: 1, name: "movies", file_type: "movie" }},
            {{ id: 2, name: "tvshows", file_type: "tvshow" }},
            {{ id: 3, name: "ebooks", file_type: "ebook" }},
            {{ id: 4, name: "audio", file_type: "audio" }},
            {{ id: 5, name: "apps", file_type: "app" }},
            {{ id: 6, name: "android", file_type: "app" }},
            {{ id: 97, name: "temp", file_type: null, role: "ingest" }},
            {{ id: 98, name: "autres", file_type: "other" }},
        ],
    }}"""
    path.write_text(content, encoding="utf-8")


def _write_categories_overlay(path: Path, folder_name: str = "Films") -> None:
    """Write a categories overlay file.

    Args:
        path: File path (e.g. ``<config_dir>/categories.json5``).
        folder_name: Value for ``categories.movies.folder_name``.
    """
    path.write_text(
        f"""{{
            categories: {{
                movies: {{ folder_name: "{folder_name}" }},
            }},
        }}""",
        encoding="utf-8",
    )


def _write_anime_overlay(path: Path) -> None:
    """Write an anime_rule overlay file."""
    path.write_text(
        """{
            anime_rule: {
                enabled: true,
                maps_to: "anime",
                requires_origin_country: ["JP"],
            },
        }""",
        encoding="utf-8",
    )


def _build_config_dir(base: Path, tmp_path: Path) -> Path:
    """Create a valid split-config directory with master + two overlays.

    Returns the config directory path.
    """
    cfg_dir = base / "config"
    cfg_dir.mkdir(parents=True)
    _write_master(cfg_dir / "config.json5", tmp_path, overlay_names=["categories.json5", "anime.json5"])
    _write_categories_overlay(cfg_dir / "categories.json5")
    _write_anime_overlay(cfg_dir / "anime.json5")
    return cfg_dir


def _dir_checksum(cfg_dir: Path) -> str:
    """Return a deterministic checksum of all files in *cfg_dir* (recursive)."""
    h = hashlib.sha256()
    for root, _dirs, files in sorted(os.walk(str(cfg_dir))):
        for fname in sorted(files):
            fpath = Path(root) / fname
            h.update(fpath.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# validate_candidate tests
# ---------------------------------------------------------------------------


class TestValidateCandidate:
    """Tests for the validate_candidate function."""

    # -- Happy path ----------------------------------------------------------

    def test_valid_candidate_accepted(self, tmp_path: Path) -> None:
        """A valid replacement dict must return (Config, warnings) tuple."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)

        config, warnings = validate_candidate(
            cfg_dir,
            replaced={"categories.json5": {"categories": {"movies": {"folder_name": "Movies-Test"}}}},
        )

        assert isinstance(config, Config)
        assert isinstance(warnings, list)
        assert config.category("movies").folder_name == "Movies-Test"

    # -- Replacement substitution -------------------------------------------

    def test_replaced_value_lands_in_config(self, tmp_path: Path) -> None:
        """A value changed via *replaced* must appear in the validated Config."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)

        config, _warnings = validate_candidate(
            cfg_dir,
            replaced={"categories.json5": {"categories": {"movies": {"folder_name": "Substituted"}}}},
        )

        assert config.category("movies").folder_name == "Substituted"

    def test_replaced_anime_rule_used(self, tmp_path: Path) -> None:
        """Replacing the anime overlay must change the validated Config."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)

        config, _warnings = validate_candidate(
            cfg_dir,
            replaced={
                "anime.json5": {
                    "anime_rule": {
                        "enabled": False,
                        "maps_to": "tv_shows",
                        "requires_origin_country": ["FR"],
                    },
                }
            },
        )

        assert config.anime_rule.enabled is False
        assert config.anime_rule.maps_to == "tv_shows"

    def test_local_json5_substitution(self, tmp_path: Path) -> None:
        """local.json5 can be substituted even when the file doesn't exist on disk."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)

        config, _warnings = validate_candidate(
            cfg_dir,
            replaced={
                "local.json5": {"categories": {"movies": {"folder_name": "LocalOverride"}}},
            },
        )

        assert config.category("movies").folder_name == "LocalOverride"

    # -- Invalid input -------------------------------------------------------

    def test_invalid_candidate_rejected(self, tmp_path: Path) -> None:
        """A candidate missing required fields must raise ConfigValidationError."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)

        with pytest.raises(ConfigValidationError, match="Validation error"):
            validate_candidate(
                cfg_dir,
                replaced={
                    "categories.json5": {"paths": None},  # invalid: paths must be an object
                },
            )

    def test_unknown_replacement_key_raises(self, tmp_path: Path) -> None:
        """A key in *replaced* not matching any overlay must raise ConfigLoadError."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)

        with pytest.raises(ConfigLoadError, match="nonexistent.json5"):
            validate_candidate(
                cfg_dir,
                replaced={"nonexistent.json5": {"some": "data"}},
            )

    # -- Cross-reference validation ------------------------------------------

    def test_cross_reference_violation_rejected(self, tmp_path: Path) -> None:
        """A category_rules entry referencing an unknown category must fail validation."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)

        with pytest.raises(ConfigValidationError, match="Validation error"):
            validate_candidate(
                cfg_dir,
                replaced={
                    "categories.json5": {
                        "category_rules": [
                            {
                                "category": "nonexistent_category",
                                "patterns": ["*.mkv"],
                            },
                        ],
                    },
                },
            )

    # -- No disk mutation ----------------------------------------------------

    def test_no_disk_mutation(self, tmp_path: Path) -> None:
        """validate_candidate must not write anything to the config directory."""
        cfg_dir = _build_config_dir(tmp_path, tmp_path)
        checksum_before = _dir_checksum(cfg_dir)

        validate_candidate(
            cfg_dir,
            replaced={"categories.json5": {"categories": {"movies": {"folder_name": "Changed"}}}},
        )

        checksum_after = _dir_checksum(cfg_dir)
        assert checksum_before == checksum_after, "validate_candidate mutated the config directory"

    # -- ContextVar isolation (sequential) ----------------------------------

    def test_sequential_calls_dont_leak_project_roots(self, tmp_path: Path) -> None:
        """Two sequential validate_candidate calls must not leak the ContextVar.

        Different config dirs must not leak the ContextVar between calls.
        """
        cfg_a = _build_config_dir(tmp_path / "a", tmp_path / "a")
        cfg_b = _build_config_dir(tmp_path / "b", tmp_path / "b")

        # cfg_a and cfg_b have different project roots.
        config_a, _ = validate_candidate(
            cfg_a,
            replaced={"categories.json5": {"categories": {"movies": {"folder_name": "FromA"}}}},
        )
        config_b, _ = validate_candidate(
            cfg_b,
            replaced={"categories.json5": {"categories": {"movies": {"folder_name": "FromB"}}}},
        )

        assert config_a.category("movies").folder_name == "FromA"
        assert config_b.category("movies").folder_name == "FromB"

    # -- ContextVar isolation (threading) -----------------------------------

    def test_concurrent_calls_no_cross_contamination(self, tmp_path: Path) -> None:
        """Two concurrent validate_candidate calls must not cross-contaminate ContextVar.

        Uses RELATIVE data_dir values so path resolution depends on
        ``_PROJECT_ROOT`` ContextVar.  If ``_PROJECT_ROOT`` were a plain module
        global, concurrent threads would cross-contaminate and resolve data_dir
        under the wrong project root (or CWD).
        """

        def _write_config(cfg_dir: Path, data_dir_rel: str, folder_name: str) -> None:
            """Write a config dir whose paths.json5 uses a RELATIVE data_dir."""
            cfg_dir.mkdir(parents=True)
            (cfg_dir / "config.json5").write_text(
                f"""{{
                    config_version: 1,
                    overlays: ["categories.json5"],
                    paths: {{
                        torrent_complete_dir: "/tmp/complete",
                        staging_dir: "/tmp/staging",
                        data_dir: "{data_dir_rel}",
                    }},
                    disks: [
                        {{
                            id: "disk_a",
                            path: "/tmp/disk_a",
                            categories: ["movies", "tv_shows"],
                        }},
                    ],
                    staging_dirs: [
                        {{ id: 1, name: "movies", file_type: "movie" }},
                        {{ id: 2, name: "tvshows", file_type: "tvshow" }},
                        {{ id: 3, name: "ebooks", file_type: "ebook" }},
                        {{ id: 4, name: "audio", file_type: "audio" }},
                        {{ id: 5, name: "apps", file_type: "app" }},
                        {{ id: 6, name: "android", file_type: "app" }},
                        {{ id: 97, name: "temp", file_type: null, role: "ingest" }},
                        {{ id: 98, name: "autres", file_type: "other" }},
                    ],
                }}""",
                encoding="utf-8",
            )
            (cfg_dir / "categories.json5").write_text(
                f"""{{
                    categories: {{
                        movies: {{ folder_name: "{folder_name}" }},
                    }},
                }}""",
                encoding="utf-8",
            )

        root_a = tmp_path / "project_a"
        root_b = tmp_path / "project_b"
        cfg_a = root_a / "config"
        cfg_b = root_b / "config"

        _write_config(cfg_a, ".data-a", "ProjectA")
        _write_config(cfg_b, ".data-b", "ProjectB")

        barrier = threading.Barrier(2)
        results_a: list[Path] = []
        results_b: list[Path] = []

        def _validate_loop(cfg_dir: Path, results: list[Path]) -> None:
            barrier.wait()  # synchronise start to force overlap
            for _ in range(20):
                config, _ = validate_candidate(
                    cfg_dir,
                    replaced={"categories.json5": {"categories": {"movies": {"folder_name": "Test"}}}},
                )
                results.append(config.paths.data_dir)

        t_a = threading.Thread(target=_validate_loop, args=(cfg_a, results_a))
        t_b = threading.Thread(target=_validate_loop, args=(cfg_b, results_b))

        t_a.start()
        t_b.start()
        t_a.join()
        t_b.join()

        expected_a = (root_a / ".data-a").resolve()
        expected_b = (root_b / ".data-b").resolve()

        for i, path in enumerate(results_a):
            assert path == expected_a, f"Iteration {i}: expected {expected_a}, got {path} (cross-contamination?)"
        for i, path in enumerate(results_b):
            assert path == expected_b, f"Iteration {i}: expected {expected_b}, got {path} (cross-contamination?)"

    # -- ConfigConflictError propagation ------------------------------------

    def test_conflict_error_propagated(self, tmp_path: Path) -> None:
        """Raise ConfigConflictError when two non-local overlays define the same key."""
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        # Two overlays both define "shared_key".
        _write_master(cfg_dir / "config.json5", tmp_path, overlay_names=["a.json5", "b.json5"])
        (cfg_dir / "a.json5").write_text('{"shared_key": 1}', encoding="utf-8")
        (cfg_dir / "b.json5").write_text('{"shared_key": 2}', encoding="utf-8")

        with pytest.raises(ConfigConflictError, match="shared_key"):
            validate_candidate(cfg_dir, replaced={"a.json5": {"shared_key": 3}})

    # -- Orphan check skipped ------------------------------------------------

    def test_orphan_check_not_called(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """validate_candidate must NOT invoke _check_category_orphans."""
        import personalscraper.conf.loader as loader_mod

        called = []

        def _fake_orphan_check(_config: Config) -> None:
            called.append(True)

        monkeypatch.setattr(loader_mod, "_check_category_orphans", _fake_orphan_check)

        cfg_dir = _build_config_dir(tmp_path, tmp_path)
        validate_candidate(
            cfg_dir,
            replaced={"categories.json5": {"categories": {"movies": {"folder_name": "Test"}}}},
        )

        assert len(called) == 0, "validate_candidate called _check_category_orphans"
