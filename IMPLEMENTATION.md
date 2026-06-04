# Implementation Progress — torrent-fetch

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP1a — Torrent fetch boundary (authenticated .torrent download + magnet exception, routable 401) (minor)
**Version bump**: 0.21.0 → 0.22.0
**Branch**: feat/torrent-fetch
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/90
**Design**: docs/features/torrent-fetch/DESIGN.md
**Master plan**: docs/features/torrent-fetch/plan/INDEX.md

## Phases

| #   | Phase                                                                   | File                            | Status |
| --- | ----------------------------------------------------------------------- | ------------------------------- | ------ |
| 1   | Errors module — `TrackerAuthError` + `TorrentFetchError`                | phase-01-errors.md              | [x]    |
| 2   | Transport binary GET — `get_bytes` + dedicated download circuit/limiter | phase-02-transport-get-bytes.md | [x]    |
| 3   | Fetcher module + public surface + docstring fix                         | phase-03-fetcher.md             | [x]    |
| 4   | ACCEPTANCE.md + reference docs + `make check` gate                      | phase-04-acceptance.md          | [x]    |
| 5   | PR fixes cycle 1 (review #90)                                           | phase-05-pr-fixes-cycle-1.md    | [x]    |

## Review cycles

### Cycle 1 — 2026-06-04

pr-review-toolkit (4 agents: code-reviewer, silent-failure-hunter, pr-test-analyzer,
type-design-analyzer) + Opus filter vs DESIGN. **Verdict: implementation sound** — every
core invariant (D3 isolation, D9 no-auth-remerge, D10 URL handling, agnostic-ValueError
split, magnet bypass, hash canonicalization) confirmed correct; tests confirmed real (not
vacuous). No design contradiction.

- Findings received: ~14 (across 4 agents, deduped)
- Retained: 7 (0 critical, 1 major, 3 medium, 3 minor)
- Ignored: pre-existing `count_retries=True` docstring drift (carried from main — out of scope)
- Fix phase created: phase-05-pr-fixes-cycle-1.md
- Status: fix phase dispatched → fixes applied inline

**Retained — major:**

- **F1 (major)** `resolve_source` empty-string `download_url` (`""`) bypasses the
  `is None` guard → `get_bytes("")` GETs the tracker root instead of raising. Fix:
  `if not download_url:` + guard `fetch_torrent_source` + tests.

**Retained — medium:**

- **F2** non-canonicalizable truthy `expected_info_hash` silently skipped, no log/test →
  module-logger `warning` + regression test.
- **F3** streamed response not `close()`d on oversize abort (connection leak on the
  defensive path) → `try/finally resp.close()` in `_download_mapper` + test.
- **F4** `_fetch.py` reaches `transport._policy.provider_name` (cross-module private) →
  public `provider_name` property on `HttpTransport`.

**Retained — minor:** dead `_ResponseMapper` alias (delete), stale `_is_retryable`
docstring (`_do_request`→`_do_request_raw`), missing 404-propagation test.

### Cycle 2 — 2026-06-04

Focused re-review of the cycle-1 fix commit (`b2c1cf18`) — code-reviewer + silent-failure-hunter
on the fix diff. **Verdict: all 7 fixes correct, complete, non-vacuously tested; NO new findings
at any severity.** CI green; PR mergeable (clean).

- Findings received: 0 (re-review of fixes)
- Retained: 0
- Ignored: 1 observation (non-2xx streamed response not explicitly closed) — non-issue (error
  path drains the body via the json/text preview read) + pre-existing, out of scope.
- Fix phase created: none
- Status: clean — proceeding to merge (manual)

## Next action

Review clean (2 cycles). **Manual merge**: squash-merge PR #90 when ready, then run `/implement:archive`.
