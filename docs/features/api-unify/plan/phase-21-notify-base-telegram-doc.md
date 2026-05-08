# Phase 21 — Notify Family Base + Telegram API Doc

**Type**: mixed (infra + doc)
**Goal**: Ship `api/notify/_base.py` with both Protocols. Write Telegram reference doc. Interactive checkpoint.

## Gate (prereq)

Phase 20 complete. All metadata + torrent + tracker families migrated.

## Sub-phases

### 21.1 — `api/notify/__init__.py` + `_base.py`

`_base.py`:

- `Notifier` Protocol (per DESIGN §7.1) — `send`, `send_report`.
- `HealthChecker` Protocol — `ping_start`, `ping_success`, `ping_fail`.
- `PipelineReport` import path documented (existing model in `personalscraper/models.py`).

**Commit**: `feat(api-unify): add notify family base — Notifier + HealthChecker Protocols`

### 21.2 — Study Telegram Bot API

Source: <https://core.telegram.org/bots/api>.

Endpoint: `https://api.telegram.org/bot<TOKEN>/sendMessage` (token in URL path).

Auth model: token in URL — no `Authorization` header. Query params: `chat_id`, `text`, `parse_mode`.

### 21.3 — Real test calls

With `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` from `.env`:

- `POST /sendMessage` with `parse_mode=HTML`.
- `POST /sendMessage` with malformed HTML (verify error response shape).

Capture samples to `docs/reference/_samples/telegram/`.

### 21.4 — Write `docs/reference/telegram-api.md`

Sections:

- Auth: token in URL path. The `base_url` of `TransportPolicy` includes the token. `auth = NoAuth()`.
- `parse_mode`: `HTML` | `Markdown` | `MarkdownV2`. HTML is current behavior.
- Response format: `{"ok": true, "result": {...}}` on success, `{"ok": false, "description": "...", "error_code": N}` on failure.
- Rate limits: 30 messages/sec global, 1/sec per chat.
- Message length: 4096 chars max — current code likely chunks longer reports. Document.
- `text` URL-encoding pitfalls.

### 21.5 — Particularities checklist

- Token-in-URL auth model. `ApiError` mapping: response `ok:false` → raise `ApiError(http_status=resp.status_code, message=description)`. Same pattern as OMDB's `Response:False`.
- Long-message chunking: existing behavior in `notifier.py` — preserve.
- `send_report(PipelineReport)`: serializes report to HTML. Current implementation lives in `notifier.py` — port verbatim.
- Fail-soft: notifier never raises (catches `ApiError`, logs warning, returns `False`).

### 21.6 — Interactive user checkpoint

> Phase 21 base + Telegram doc complete.
> Particularities found: <list>
>
> Implementation decisions to confirm:
>
> - Token-in-URL: build base_url dynamically from TELEGRAM_BOT_TOKEN at policy() time. auth=NoAuth().
> - "ok:false" response: raise ApiError, then send() catches and returns False (fail-soft).
> - Message chunking strategy preserved as-is.
>
> Proposed scope (Phase 22):
>
> - api/notify/telegram.py with TelegramNotifier(Notifier).
> - Partial removal of notifier.py — Telegram half deleted, healthchecks half stays until Phase 24.
>
> Confirm before next phase?

### 21.7 — Phase 21 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.notify._base import Notifier, HealthChecker"
ls docs/reference/telegram-api.md
```

**Commit**: `chore(api-unify): phase 21 gate — notify base + telegram doc done

User checkpoint captured: <decisions>`
