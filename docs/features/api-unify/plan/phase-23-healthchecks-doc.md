# Phase 23 — Healthchecks API Doc (interactive)

**Type**: doc
**Goal**: Study healthchecks.io ping protocol, write reference doc.

## Gate (prereq)

Phase 22 complete.

## Sub-phases

### 23.1 — Study healthchecks.io

Source: <https://healthchecks.io/docs/http_api/>.

Ping URL pattern: `https://hc-ping.com/<UUID>` (or self-hosted equivalent).

Lifecycle endpoints:

- `GET /<UUID>/start` — signal job started.
- `GET /<UUID>` — signal success.
- `GET /<UUID>/fail` — signal failure.
- `GET /<UUID>/<exit-code>` — signal with exit code.

No auth (UUID in URL is the auth).

### 23.2 — Real test calls

With `HEALTHCHECK_PING_URL` from `.env`:

- Start ping → success → confirm dashboard reflects.
- Failure ping → confirm.

Capture samples (response bodies are tiny: `OK` text or `(not found)`).

### 23.3 — Write `docs/reference/healthchecks-api.md`

Sections:

- URL structure: full ping URL stored in `.env`, lifecycle suffixes appended.
- No JSON, no auth, response is plain text `OK` (200) or error.
- Rate limits: high tolerance, but no published cap. Default `RateLimitPolicy(0)` (disabled).
- Fail-soft: never raise from a ping (notification failure shouldn't break the pipeline).

### 23.4 — Particularities checklist

- Plain-text response (NOT JSON). `HttpTransport` supports `response_format="text"` from Phase 1; confirm whether healthchecks should use that path or bypass transport entirely.
- URL contains the UUID — `base_url` from env, suffixes constructed per call.
- Self-hosted healthchecks: URL pattern differs. Treat the env var as the full prefix.

### 23.5 — Interactive user checkpoint

> Doc complete: `docs/reference/healthchecks-api.md`.
> Particularities found: <list>
>
> Architectural decision needed:
>
> - Plain-text response handling.
> - Option A: Use TransportPolicy.response_format="text".
> - Option B: HealthCheckClient calls a thin wrapper over self.\_transport.\_session directly (bypass \_do_request) — lighter, but breaks the "all calls via HttpTransport" rule.
>
> Recommendation: Option A — uses the stable Phase 1 transport contract and preserves common logging/retry/circuit behavior.
>
> Proposed scope (Phase 24):
>
> - api/notify/healthchecks.py with HealthcheckClient(HealthChecker).
> - Final removal of notifier.py.
>
> Confirm before next phase?

### 23.6 — Phase 23 gate

```bash
ls docs/reference/healthchecks-api.md
```

**Commit**: `docs(api-unify): phase 23 gate — healthchecks api doc complete

User checkpoint captured:

- Transport option: <A|B>
- <decisions>`
