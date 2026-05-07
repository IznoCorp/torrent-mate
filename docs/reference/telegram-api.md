# Telegram Bot API — Reference

> Telegram Bot API — reference for the `api/notify/telegram.py` provider.
> Source: <https://core.telegram.org/bots/api>
> Last updated: 2026-05-07

---

## Table of Contents

- [Authentication](#authentication)
- [Base URL](#base-url)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [`sendMessage` Endpoint](#sendmessage-endpoint)
- [Parse Modes](#parse-modes)
- [Message Length & Chunking](#message-length--chunking)
- [`getMe` Endpoint](#getme-endpoint)
- [Particularities](#particularities)
- [Test Samples](#test-samples)
- [Open decisions for Phase 22](#open-decisions-for-phase-22)

---

## Authentication

**Token-in-URL** — no `Authorization` header, no API key query param. The bot
token is part of the URL path itself:

```
https://api.telegram.org/bot<TOKEN>/<method>
```

The literal `bot` prefix is required (e.g. `bot8266923011:AA…`). Tokens are
issued by [@BotFather](https://t.me/BotFather) and look like
`<bot_id>:<35-char-secret>`.

Stored in `.env`:

```bash
TELEGRAM_BOT_TOKEN=8266923011:AA...   # from BotFather
TELEGRAM_CHAT_ID=1234567890           # target user/group/channel
```

Implementation: `auth = NoAuth()` because the credential lives in the URL.
The `TransportPolicy.base_url` is built dynamically per-instance:

```python
base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
```

This shape works cleanly with `HttpTransport` — `auth = NoAuth()` and the
secret never appears in headers, query params, or bodies.

---

## Base URL

```
https://api.telegram.org/bot<TOKEN>/<method>
```

- HTTPS only.
- All responses: `Content-Type: application/json; charset=utf-8`.
- Cloudflare CDN in front of the public endpoint.

---

## Rate Limiting

Per the [Telegram FAQ](https://core.telegram.org/bots/faq#broadcasting-to-users):

- **Global**: ≤ 30 messages/second across all chats served by the bot.
- **Per chat**: ≤ 1 message/second to a single chat.
- **Per group**: ≤ 20 messages/minute to the same group chat.

For our pipeline use case (a handful of report sends per pipeline run, all to
one private chat) — `HttpTransport.max_requests_per_second = 1.0` is more than
sufficient and matches the per-chat ceiling exactly.

Telegram does not advertise a `Retry-After` header for non-429 responses; on
429 it returns `parameters.retry_after` (seconds) inside the JSON body.

---

## Error Handling

Telegram uses HTTP status codes **and** an in-band `ok` flag. The two are
correlated but not redundant — the JSON body always carries the canonical
information:

```json
{
  "ok": false,
  "error_code": 400,
  "description": "Bad Request: chat not found"
}
```

Mapping to `ApiError`:

| HTTP status | `ok`    | Meaning                                            | Action                                                                 |
| ----------- | ------- | -------------------------------------------------- | ---------------------------------------------------------------------- |
| 200         | `true`  | success                                            | parse `result`                                                         |
| 400         | `false` | client error (bad chat_id, bad parse, …)           | raise `ApiError(provider="telegram", http_status=400, message=desc)`   |
| 401         | `false` | bad token                                          | raise `ApiError(http_status=401, message=desc)` — config error         |
| 403         | `false` | bot blocked by user / kicked from group            | raise `ApiError(http_status=403, message=desc)` — recipient lost       |
| 429         | `false` | rate-limited; retry after `parameters.retry_after` | raise `ApiError(http_status=429, message=desc, retry_after=<seconds>)` |
| 5xx         | n/a     | upstream Telegram outage                           | retry per `RetryPolicy` (default tenacity behavior)                    |

**Fail-soft contract** (`Notifier` Protocol, DESIGN §7.1):
`TelegramNotifier.send()` MUST catch `ApiError`, log a structured warning, and
return `False`. It MUST NEVER raise — the pipeline already finished its real
work; a notification failure is observability noise, not a pipeline failure.

---

## `sendMessage` Endpoint

**Method**: `POST` (also accepts `GET` with query params, but POST is preferred
for body length and URL-encoding cleanliness).

**Path**: `/sendMessage`

**Required body fields**:

| Field     | Type          | Notes                                          |
| --------- | ------------- | ---------------------------------------------- |
| `chat_id` | int \| string | Target chat. Numeric ID or `@channelusername`. |
| `text`    | string        | Message body. ≤ 4096 chars.                    |

**Optional body fields** (subset relevant to this project):

| Field                      | Type   | Notes                                           |
| -------------------------- | ------ | ----------------------------------------------- |
| `parse_mode`               | string | `HTML`, `Markdown`, `MarkdownV2`. Omit = plain. |
| `disable_web_page_preview` | bool   | Suppress link previews (default `false`).       |
| `disable_notification`     | bool   | Silent send (default `false`).                  |

**Success response** (`200 OK`, `ok: true`):

```json
{
  "ok": true,
  "result": {
    "message_id": 4153,
    "from": { "id": 8266923011, "is_bot": true, "username": "<bot-username>" },
    "chat": {
      "id": 1234567890,
      "type": "private",
      "username": "<user-username>"
    },
    "date": 1778170892,
    "text": "Phase 21 sample — telegram-api.md study",
    "entities": [{ "offset": 0, "length": 15, "type": "bold" }]
  }
}
```

`message_id` is the only field the project ever needs from `result` (used
nowhere today; we discard the body and return `True`). The full shape is
documented for future-proofing only.

---

## Parse Modes

Three formatters are accepted by Telegram:

| `parse_mode` | Style                                 | Notes                                                   |
| ------------ | ------------------------------------- | ------------------------------------------------------- |
| `HTML`       | `<b>`, `<i>`, `<code>`, `<a href>`, … | **Current behavior of `notifier.py`** — preserve in 22. |
| `Markdown`   | Legacy mode; `*bold*`, `_italic_`     | Deprecated by Telegram (still accepted).                |
| `MarkdownV2` | New Telegram-flavored Markdown        | Strict escaping rules; not used by this project.        |

**Allowed HTML tags** (per Telegram docs): `b`, `strong`, `i`, `em`, `u`, `ins`,
`s`, `strike`, `del`, `span` (with `tg-spoiler` class), `tg-spoiler`, `a`,
`code`, `pre`, `blockquote`, `tg-emoji`. Any other tag triggers a 400 with
`Bad Request: can't parse entities`.

**Mismatched tags** are rejected with the same 400 — see
`docs/reference/_samples/telegram/sendMessage-html-malformed-error.json`. This
is the most common runtime failure when `PipelineReport.to_html()` injects
user-controlled fragments (file names, error messages) without escaping.

**Mitigation**: `PipelineReport.to_html()` already escapes free-text fields
via `html.escape`. Adding a Telegram-specific second pass is not needed today
and is therefore not in Phase 22's scope.

---

## Message Length & Chunking

Hard cap: **4096 characters** per `text` field. Longer messages return
`400 Bad Request: message is too long`.

Current `notifier.py` does **not** chunk — `PipelineReport.to_html()` empirically
fits within the cap (≤ ~2 KB for a typical run). If a future report grows past
4096 chars, the API will refuse it and the fail-soft contract simply logs a
warning and drops the message; no silent truncation, no partial send.

**Phase 22 decision**: do NOT add chunking. YAGNI — the current report sizes
are well under cap. If a real-world overrun happens, add chunking then with a
test that reproduces the exact payload.

---

## `getMe` Endpoint

**Path**: `/getMe`. Returns the bot's own user object. Used as a cheap
connectivity / token-validity check.

```json
{
  "ok": true,
  "result": {
    "id": 8266923011,
    "is_bot": true,
    "first_name": "<bot-first-name>",
    "username": "<bot-username>",
    "can_join_groups": true,
    "can_read_all_group_messages": false,
    "supports_inline_queries": false
  }
}
```

Phase 22 does not call `getMe` (no startup pre-check is wired). Documented
for completeness.

---

## Particularities

1. **Token-in-URL auth**. No header, no query param. `auth = NoAuth()` and
   `base_url = f"https://api.telegram.org/bot{TOKEN}"`. The token is in the
   URL path → it MUST be redacted from logs. `HttpTransport` already redacts
   the path before logging URLs (verify in Phase 22 test).

2. **Always-200-on-validation-error pattern is FALSE for Telegram**. Unlike
   OMDB, Telegram returns the matching HTTP status (400/401/403/429) AND a
   structured JSON body with `ok: false`. The two channels agree. Either is
   sufficient to detect failure.

3. **`ok:false` → `ApiError`**. The `HttpTransport` should treat any non-2xx
   as a transport error (standard behavior); the provider layer additionally
   inspects `body.ok` for 200-with-`ok:false` (rare but possible per docs).

4. **Fail-soft**: `TelegramNotifier.send()` catches `ApiError`, logs
   `telegram_send_failed` with the description, returns `False`. Mirrors the
   existing fail-soft behavior of `notifier.py:60-75`.

5. **HTML escaping is the consumer's job**. `PipelineReport.to_html()` already
   escapes text — the Telegram client itself should NOT re-escape.

6. **`chat_id` accepts int or string**. Numeric IDs are stable; usernames
   (`@channelname`) only work for public channels. The project uses numeric
   IDs from `.env`.

7. **No retry on 400/401/403**. Bad-request, bad-token, and bot-blocked are
   permanent failures — retrying wastes the rate budget. Default tenacity
   policy already excludes these (only 5xx + 429 are retried).

8. **No streaming, no upload**: `sendMessage` is text-only. File sends use
   `sendDocument` / `sendPhoto` — out of scope.

---

## Test Samples

Captured from real bot account on 2026-05-07. All PII (chat IDs, first names,
usernames) redacted with placeholder strings. Bot ID retained — it's public
information (the prefix of any Telegram bot token) and harmless without the
secret half.

| File                                    | What it shows                                  |
| --------------------------------------- | ---------------------------------------------- |
| `getMe.json`                            | Bot identity probe (`ok: true`, full bot).     |
| `sendMessage-html-success.json`         | Valid HTML message — entities array shape.     |
| `sendMessage-html-malformed-error.json` | 400 — unmatched HTML tags, full description.   |
| `sendMessage-bad-token.json`            | 401 — `Unauthorized: invalid token specified`. |
| `sendMessage-bad-chat.json`             | 400 — `Bad Request: chat not found`.           |

Path: `docs/reference/_samples/telegram/`.

---

## Open decisions for Phase 22

Defaults stand unless overridden during Phase 21 user checkpoint:

1. **Token-in-URL**: `base_url` built per-instance from `TELEGRAM_BOT_TOKEN`,
   `auth = NoAuth()`. URL is redacted in transport logs.
2. **`ok:false` handling**: `HttpTransport` raises `ApiError` on non-2xx;
   `TelegramNotifier.send()` catches and returns `False` (fail-soft).
3. **Message chunking**: NOT implemented in Phase 22. Reports ≤ 4096 chars
   today; if exceeded, warning logged and message dropped.
4. **Parse mode**: `HTML` (current behavior); `parse_mode` is a `send()`
   keyword arg with default `"HTML"`.
5. **Retry policy**: default `RetryPolicy` (5xx + 429 only); 400/401/403 are
   permanent failures.
6. **Rate limit**: `max_requests_per_second = 1.0` (matches Telegram's per-chat
   ceiling — we only send to one chat).
7. **Healthchecks half stays in `notifier.py`** until Phase 24; Phase 22
   removes only the Telegram half.
