# Healthchecks API — Reference

> Healthchecks.io ping protocol — reference for the future
> `api/notify/healthchecks.py` provider.
> Source: <https://healthchecks.io/docs/http_api/>
> Last updated: 2026-05-07

---

## Table of Contents

- [Authentication](#authentication)
- [Base URL](#base-url)
- [Lifecycle Endpoints](#lifecycle-endpoints)
- [Response Format](#response-format)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Self-hosted Variants](#self-hosted-variants)
- [Particularities](#particularities)
- [Test Samples](#test-samples)
- [Open decisions for Phase 24](#open-decisions-for-phase-24)

---

## Authentication

**No auth header, no API key**. The UUID embedded in the URL **is** the
credential — anyone holding the URL can ping the check. Treat the full ping
URL as a secret.

Stored in `.env`:

```bash
HEALTHCHECK_URL=https://hc-ping.com/<uuid>     # full base, no trailing slash
```

The pipeline reads this via `Settings.healthcheck_url`. An empty string
disables pings silently — `notifier.ping_healthcheck()` short-circuits before
any HTTP call.

Implementation: `auth = NoAuth()`. The UUID lives in `base_url` exactly the
way Telegram embeds the bot token.

---

## Base URL

```
https://hc-ping.com/<uuid>
```

- HTTPS only (HTTP redirects to HTTPS).
- All responses: `Content-Type: text/plain` — **not JSON**.
- `Server: nginx` (Cloudflare in front for the SaaS endpoint).

---

## Lifecycle Endpoints

All four are GET requests on the same prefix. POST is also accepted but adds
nothing — GET is the canonical form.

| Path                 | Meaning                            | When the pipeline calls it      |
| -------------------- | ---------------------------------- | ------------------------------- |
| `<base>` (no suffix) | Success — job finished cleanly     | End of pipeline run, no errors  |
| `<base>/start`       | Job started — start the run timer  | Before the first step runs      |
| `<base>/fail`        | Job failed                         | End of pipeline run, has errors |
| `<base>/<exit-code>` | Job finished with this exit code   | Not used by this project today  |
| `<base>/log`         | Append a log line to the dashboard | Out of scope                    |

Mapping in `personalscraper.notifier.ping_healthcheck()`:

```python
ping_healthcheck(url, "/start")    # before run
ping_healthcheck(url, "")          # success
ping_healthcheck(url, "/fail")     # failure
```

---

## Response Format

**Plain-text**, not JSON. There is no body schema — successful pings return
a literal `OK` string, errors return a short human-readable line.

| HTTP  | Body                 | Meaning                                     |
| ----- | -------------------- | ------------------------------------------- |
| `200` | `OK`                 | Ping recorded.                              |
| `200` | `OK (already up)`    | Duplicate success ping (idempotent).        |
| `400` | `invalid url format` | UUID malformed in URL path.                 |
| `404` | `(not found)`        | UUID well-formed but unknown to the server. |

Captured `400` shape: see `docs/reference/_samples/healthchecks/ping-not-found.txt`.
Real `200/OK` and `404/(not found)` samples are not reproducible without a
registered UUID; the 400 sample is sufficient to validate the parser path.

---

## Rate Limiting

Healthchecks.io publishes no formal rate cap. The product is designed for
high-frequency telemetry — production users routinely ping every few seconds.

Project default: `RateLimitPolicy(requests_per_second=0.0)` — disabled. The
pipeline issues at most 2 pings per run (start + end), so throttling is
unnecessary.

---

## Error Handling

- **400 / 404** — configuration error: the URL is wrong. Log a warning, return
  silently. **Do not retry** — the URL will not become valid by retrying.
- **5xx** — transient outage at hc-ping.com. The default `RetryPolicy`
  (5xx + 429 + 504) handles it; tenacity backoff is sufficient.
- **Connection errors / timeout** — network glitch. Same fail-soft contract as
  Telegram: log a warning, return — pipeline never aborts.

**Critical fail-soft contract** (`HealthChecker` Protocol, DESIGN §7.1):
`ping_start()`, `ping_success()`, `ping_fail()` MUST NEVER raise. They are
pure side-effects with `-> None` return type. The pipeline calls them around
the real work; an unreachable hc-ping.com must NOT abort the pipeline run.

---

## Self-hosted Variants

Healthchecks.io is open source. Self-hosted instances live behind arbitrary
hostnames and may use a non-`/<uuid>` URL shape (e.g. `/ping/<uuid>` for the
Docker image's default routing).

**Treat `HEALTHCHECK_URL` as the full prefix.** Do not assume `hc-ping.com`,
do not strip path components — the user is responsible for setting the env
var to the exact prefix accepted by their installation. Suffixes (`/start`,
`/fail`) are appended verbatim.

---

## Particularities

1. **Plain-text response** (`text/plain`). The unified `HttpTransport` already
   supports this via `TransportPolicy.response_format = "text"` (Phase 1
   §3.7). Phase 24 uses that path — no bypass, no direct `requests.get`.

2. **UUID is the credential**. `auth = NoAuth()`, URL holds the secret. The
   `_SECRET_FIELDS` set in `personalscraper/config.py` already lists
   `healthcheck_url` to redact it from `__repr__`.

3. **`base_url` includes the UUID**. Identical pattern to Telegram's
   token-in-URL: `base_url = settings.healthcheck_url`, suffixes appended via
   `path` argument to `transport.get(path="/start")` etc.

4. **No `chat_id` equivalent**. The URL fully identifies the target. Client
   construction is just `HealthcheckClient(transport)`.

5. **No JSON parsing**. The transport returns `str`, not `dict[str, Any]`.
   The provider does not even need to inspect it — a 200 response is success
   by definition.

6. **Self-hosted differs from SaaS**. Treat `HEALTHCHECK_URL` as opaque; do
   not concatenate `hc-ping.com` anywhere.

7. **`/log` and `/<exit-code>` endpoints are not used today**. Out of scope
   for Phase 24; can be added without breaking the Protocol if a future
   feature wants them.

---

## Test Samples

| File                                       | What it shows                                   |
| ------------------------------------------ | ----------------------------------------------- |
| `_samples/healthchecks/ping-not-found.txt` | 400 plain-text response (`invalid url format`). |

`200 OK` and `404 (not found)` cases are documented but not captured —
hc-ping.com will not respond `OK` without a registered UUID, and this project
does not expose its real ping URL in samples (it's a secret).

---

## Open decisions for Phase 24

Defaults stand unless overridden during Phase 23 user checkpoint:

1. **Plain-text handling**: Option A — `TransportPolicy.response_format = "text"`.
   Reuses the Phase 1 transport contract; preserves common logging, retry,
   and circuit behavior. Option B (bypass via direct `_session.get`) is
   rejected: it duplicates retry/circuit logic and breaks the "all calls via
   HttpTransport" rule (DESIGN §3.7).

2. **`base_url` is the env var verbatim**. Suffixes (`/start`, `/fail`)
   appended as path arguments to `transport.get()`.

3. **Fail-soft**: `ApiError` and any other exception caught, warning logged,
   no return value (Protocol returns `None`).

4. **Rate limit**: `RateLimitPolicy(0.0)` — disabled. 2 pings per run.

5. **Retry policy**: default — 5xx + 429 retried, 4xx not retried.

6. **Final removal of `notifier.py`** in Phase 24 — the helper module shrinks
   to zero usages and is deleted.
