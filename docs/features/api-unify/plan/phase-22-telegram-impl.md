# Phase 22 — Telegram Migration

**Type**: impl
**Goal**: Migrate `TelegramNotifier` from `notifier.py` → `api/notify/telegram.py`. Remove Telegram half from old module.

## Gate (prereq)

Phase 21 complete.

## Sub-phases

### 22.1 — Build `api/notify/telegram.py`

```python
class TelegramNotifier:
    REQUIRED_CREDS: ClassVar[list[str]] = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    provider_name = "telegram"

    @classmethod
    def policy(cls, bot_token: str) -> TransportPolicy:
        return TransportPolicy(
            provider_name="telegram",
            base_url=f"https://api.telegram.org/bot{bot_token}",
            auth=NoAuth(),
            timeout_seconds=10,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=10, cooldown_seconds=60),  # tolerant
            rate_limit=RateLimitPolicy(requests_per_second=1),  # per chat
        )

    def __init__(self, transport: HttpTransport, chat_id: str) -> None:
        self._transport = transport
        self._chat_id = chat_id

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        try:
            for chunk in self._chunk(message, max_len=4096):
                self._transport.post("/sendMessage", data={
                    "chat_id": self._chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                })
            return True
        except ApiError as e:
            log.warning("telegram_send_failed", error=str(e))
            return False  # fail-soft

    def send_report(self, report: PipelineReport) -> bool: ...

    @staticmethod
    def _chunk(text: str, max_len: int) -> list[str]: ...
```

### 22.2 — Update consumers + partial removal

```bash
rg "from personalscraper\.notifier import (TelegramNotifier|telegram)" personalscraper/ tests/
```

Rewrite imports to `from personalscraper.api.notify.telegram import TelegramNotifier`.

In `personalscraper/notifier.py`: **remove** Telegram code (class + helpers). Keep healthchecks code only. The file shrinks but stays.

If `notifier.py` becomes effectively empty (healthchecks code is small enough to keep in same file until Phase 24), document the staging in a comment at top of `notifier.py`:

```python
"""TRANSITIONAL — healthchecks only.
Telegram migrated to api/notify/telegram.py (Phase 22).
Healthchecks migration scheduled in Phase 24.
This module will be deleted in Phase 24."""
```

### 22.3 — Tests

`tests/unit/test_telegram_notifier.py`:

- `send()` mocked → `responses` confirms POST `/sendMessage`.
- `send()` on 400 → returns False (fail-soft), logs warning.
- Long message chunking at 4096 chars → multiple POSTs.
- Bot token correctly embedded in URL path.

### 22.4 — Phase 22 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.notify.telegram import TelegramNotifier"
! rg "TelegramNotifier" personalscraper/notifier.py
```

**Commit**: `chore(api-unify): phase 22 gate — telegram migration done`
