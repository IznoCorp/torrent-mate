"""``grab`` speaks through the translation layer: one representative line, in both languages."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.context import AcquireContext
from personalscraper.acquire.store import build_acquire_store
from personalscraper.cli import app
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.i18n import Language, t, use_language
from tests.conftest import make_cli_runner

runner = make_cli_runner()


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_dry_run_empty_queue_line_comes_from_the_catalogue(
    test_config: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: Language
) -> None:
    """The « no pending wanted items » line is the catalogue's text, each language shows its own text."""
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    app_context = AppContext(
        config=MagicMock(),
        settings=MagicMock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(),
        acquire=AcquireContext(tracker_registry=MagicMock(), store=store),
    )

    @contextmanager
    def _boundary(config: Any, settings: Any, **kwargs: Any) -> Any:
        yield app_context

    monkeypatch.setattr("personalscraper.commands.grab.per_step_boundary", _boundary)
    try:
        with (
            use_language(language),
            patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/fake/config.json5")),
            patch("personalscraper.conf.loader.load_config", return_value=test_config),
        ):
            result = runner.invoke(app, ["grab", "--dry-run"])
    finally:
        store.close()

    assert result.exit_code == 0, result.output
    expected = t("cli_acquisition.grab.dry_run_empty", language=language)
    assert expected in result.output
    if language is Language.EN:
        assert expected == "No pending wanted items."
    else:
        # The French side is its own text (not the English one) and keeps the values the command passes.
        assert expected != "No pending wanted items."
        assert "wanted" in expected
