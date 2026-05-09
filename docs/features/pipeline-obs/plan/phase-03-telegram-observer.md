# Phase 3 — TelegramObserver

**Type**: core
**Codename**: pipeline-obs

## NO DEFERRAL

Every sub-phase fully implemented. Telegram notification parity maintained.

## Gate (pre-phase)

- [x] Phase 1 complete — `PipelineObserver` Protocol exists
- [x] Phase 2 complete — `RichConsoleObserver` exists

## Sub-phases

### Sub-phase 3.1 — TelegramObserver

**Files:**

- Create: `personalscraper/observers/telegram.py`
- Create: `tests/unit/test_telegram_observer.py`

**`personalscraper/observers/telegram.py`:**

```python
"""Telegram observer — sends pipeline summary via Telegram on completion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.api.notify.telegram import TelegramNotifier
from personalscraper.api.transport._http import HttpTransport
from personalscraper.config import Settings
from personalscraper.pipeline_observer import PipelineObserver, StepEvent

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


class TelegramObserver:
    """Sends the pipeline summary to a Telegram chat via on_pipeline_end."""

    name = "telegram"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def on_pipeline_start(self, report: PipelineReport) -> None:
        pass

    def on_pipeline_end(self, report: PipelineReport) -> None:
        transport = HttpTransport(TelegramNotifier.policy(self._settings.telegram_bot_token))
        notifier = TelegramNotifier(transport, self._settings.telegram_chat_id)
        notifier.send_report(report)

    def on_step_start(self, step: str) -> None:
        pass

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:
        pass

    def on_step_error(self, step: str, error: Exception) -> None:
        pass

    def on_progress(self, event: StepEvent) -> None:
        pass
```

### Sub-phase 3.2 — Tests

**`tests/unit/test_telegram_observer.py`:**

```python
"""Tests for TelegramObserver."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from personalscraper.models import PipelineReport, StepReport
from personalscraper.observers.telegram import TelegramObserver
from personalscraper.pipeline_observer import PipelineObserver


class TestTelegramObserver:
    """TelegramObserver tests."""

    def test_is_pipeline_observer(self):
        """TelegramObserver satisfies the Protocol."""
        settings = MagicMock()
        settings.telegram_bot_token = "fake-token"
        settings.telegram_chat_id = "123"
        assert isinstance(TelegramObserver(settings), PipelineObserver)

    def test_name(self):
        settings = MagicMock()
        assert TelegramObserver(settings).name == "telegram"

    def test_on_pipeline_end_sends_report(self):
        settings = MagicMock()
        settings.telegram_bot_token = "t"
        settings.telegram_chat_id = "1"
        obs = TelegramObserver(settings)
        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest", success_count=1))
        report.finished_at = datetime.now()

        with patch("personalscraper.observers.telegram.TelegramNotifier") as mock_notifier_cls:
            mock_notifier = MagicMock()
            mock_notifier_cls.return_value = mock_notifier

            with patch("personalscraper.observers.telegram.HttpTransport"):
                obs.on_pipeline_end(report)

            mock_notifier.send_report.assert_called_once_with(report)

    def test_all_other_callbacks_are_noop(self):
        settings = MagicMock()
        obs = TelegramObserver(settings)
        report = PipelineReport(started_at=datetime.now())
        step_report = StepReport(name="test")

        assert obs.on_pipeline_start(report) is None
        assert obs.on_step_start("ingest") is None
        assert obs.on_step_end("ingest", step_report, 1.0) is None
        assert obs.on_step_error("ingest", ValueError()) is None
        assert obs.on_progress(MagicMock()) is None
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] Commit: `feat(pipeline-obs): add TelegramObserver`
