# torrent-fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a chosen `TrackerResult` into a `TorrentSource` by adding a binary-GET capability to `HttpTransport` and a tracker-agnostic fetch boundary in `api/tracker/_fetch.py`.

**Architecture:** A standalone `_fetch.py` module (not per-tracker) calls `HttpTransport.get_bytes` (new), which uses a dedicated download circuit breaker and rate limiter so download failures never open the search circuit. Magnet URLs bypass the network entirely; `.torrent` bytes are strictly validated via the existing `_bencode_info_hash` gate before a `TorrentSource` is returned.

**Tech Stack:** Python 3.11+, `requests` (streaming), `tenacity` (retry), `CircuitBreaker` + `RateLimiter` (existing), `hashlib` (info-hash), `base64` (base32 decode), `pytest` (unit tests, fake transport via `MagicMock`).

---

## Phases

| #   | Phase                                                                   | File                                                               | Status |
| --- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ | ------ |
| 1   | Errors module — `TrackerAuthError` + `TorrentFetchError`                | [phase-01-errors.md](phase-01-errors.md)                           | [ ]    |
| 2   | Transport binary GET — `get_bytes` + dedicated download circuit/limiter | [phase-02-transport-get-bytes.md](phase-02-transport-get-bytes.md) | [ ]    |
| 3   | Fetcher module + public surface + docstring fix                         | [phase-03-fetcher.md](phase-03-fetcher.md)                         | [ ]    |
| 4   | ACCEPTANCE.md + reference docs + `make check` gate                      | [phase-04-acceptance.md](phase-04-acceptance.md)                   | [ ]    |

## Dependency graph

```
Phase 1 (errors)
    └── Phase 2 (transport get_bytes)
            └── Phase 3 (fetcher + public surface)
                    └── Phase 4 (ACCEPTANCE + make check)
```

## Files touched

| File                                          | Action            | Phase |
| --------------------------------------------- | ----------------- | ----- |
| `personalscraper/api/tracker/_errors.py`      | **Create**        | 1     |
| `tests/unit/test_tracker_errors.py`           | **Create**        | 1     |
| `personalscraper/api/transport/_http.py`      | **Modify**        | 2     |
| `tests/unit/test_http_transport_get_bytes.py` | **Create**        | 2     |
| `personalscraper/api/tracker/_fetch.py`       | **Create**        | 3     |
| `personalscraper/api/tracker/__init__.py`     | **Modify**        | 3     |
| `personalscraper/api/tracker/_base.py`        | **Fix docstring** | 3     |
| `tests/unit/test_tracker_fetch.py`            | **Create**        | 3     |
| `docs/features/torrent-fetch/ACCEPTANCE.md`   | **Create**        | 4     |

## Commit convention

All commits use scope `torrent-fetch`:

```
feat(torrent-fetch): <description>
fix(torrent-fetch): <description>
docs(torrent-fetch): <description>
```
