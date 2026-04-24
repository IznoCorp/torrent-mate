# Phase 9 — E2E + docs + gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §10 (integration test, DESIGN open question) and DESIGN §11
(observability reference). End-to-end integration test behind `@pytest.mark.network`.
Reference documentation `docs/reference/trailers.md`. CLAUDE.md trigger-table entry. Full
quality gate: `pytest -q`, `ruff check`, `mypy`. Final milestone commit.

**Architecture:** Phase 9 starts with an E2E fixture check (per DESIGN Open Questions):
determine whether `tests/e2e/` already has a full `ingest → dispatch` fixture usable for
the trailers step. If yes, add the trailers step to it. If no, create a minimal staging-only
fixture (sub-phase 9.1a).

**Tech Stack:** Python, `pytest.mark.network`, `yt-dlp`, `ruff`, `mypy`, `make`.

---

## Gate (entry condition)

All prior phases must be complete:

```bash
python -c "from personalscraper.conf.models import TrailersConfig; c=TrailersConfig(); assert not c.enabled; print('Phase 8 OK')"
python -c "from personalscraper.trailers.cli import app; print('Phase 7 OK')"
python -c "from personalscraper.trailers.orchestrator import TrailersOrchestrator; print('Phase 6 OK')"
```

---

## Dependencies

All phases 1 through 8.

---

## Invariants for this phase

- The `@pytest.mark.network` integration test is skipped in CI by default
  (guarded by `TRAILER_INTEGRATION_TESTS` env var).
- Documentation files are in English (project convention for reference docs).
- No functionality changes — this phase is verification, documentation, and final gate only.
- The CLAUDE.md trigger-table entry does NOT expose API keys or cookie paths.

---

## Sub-phase 9.0 — Register the `network` pytest marker (pre-requirement)

Before any `@pytest.mark.network` test is created, register the marker in
`pyproject.toml` under `[tool.pytest.ini_options]` `markers` (markers list sits at
lines ~65-70 with `e2e`, `roundtrip`, `e2e_torrent`, `e2e_idempotence`). Add:

```toml
"network: Tests hitting real external networks (opt-in via TRAILER_INTEGRATION_TESTS env var)",
```

Without this registration, `pytest -W error::pytest.PytestUnknownMarkWarning` (or any
strict-markers config) aborts with `PytestUnknownMarkWarning`. Commit as
`chore(trailer): register network pytest marker` before the first `@pytest.mark.network`
test is added.

## Sub-phase 9.1 — Check existing E2E fixture

### Step 1: Inspect `tests/e2e/` for a usable pipeline fixture

```bash
ls "$(git rev-parse --show-toplevel)/tests/e2e/"
```

Read `tests/e2e/test_pipeline_movies.py` and `tests/e2e/test_pipeline_tvshows.py` to
determine whether they exercise the full `ingest → sort → process → dispatch` sequence.

**Decision tree:**

- If a full pipeline fixture exists (e.g. `tests/e2e/conftest.py` has a `pipeline_run` fixture
  covering all steps): proceed to sub-phase 9.2 and add the trailers step to that fixture.
- If no such fixture exists, or if the existing fixtures do not cover `process → dispatch`:
  create `tests/trailers/test_integration.py` as a standalone staging-only E2E test (sub-phase 9.1b).

Based on the current repo state (read `tests/e2e/test_pipeline_movies.py` during Phase 9
execution to confirm), the plan assumes **the full-pipeline fixture does exist** in
`tests/e2e/`. If it does not, follow sub-phase 9.1b below.

### Sub-phase 9.1a — Hermetic E2E (always runs) + opt-in network E2E

Every E2E fixture comes in **two flavours**: one hermetic (runs by default, no network,
no external key), one gated behind `@pytest.mark.network`. Running on CI without the gate
must exercise the full discovery → download → placement → state path at least once.

**Files:**

| Action | Path                                          | Responsibility                                            |
| ------ | --------------------------------------------- | --------------------------------------------------------- |
| Create | `tests/trailers/test_integration_hermetic.py` | Mock-HTTP E2E — runs by default, covers golden path       |
| Create | `tests/trailers/test_integration_network.py`  | Real-network E2E — opt-in via `TRAILER_INTEGRATION_TESTS` |
| Create | `tests/trailers/fixtures/sample-trailer.mp4`  | Tiny CC-licensed mp4 used by the hermetic test            |

### Hermetic test — `tests/trailers/test_integration_hermetic.py`

Uses the actual `TrailerFinder → YtdlpDownloader → placement → state` stack, but replaces
the network edges with mocks so the test is deterministic and fast (< 1 s). `YtdlpDownloader`
is patched so that instead of calling `yt_dlp.YoutubeDL(...).download([url])` it copies
`tests/trailers/fixtures/sample-trailer.mp4` to the target output path. The TMDB + YouTube
layers return canned fixture responses.

This closes the reviewer-flagged hole where Phase 9's only E2E was `@pytest.mark.network`
(and therefore skipped on CI). The hermetic path proves the full stack works end-to-end on
every push.

### Opt-in network test — `tests/trailers/test_integration_network.py`

Same shape as before but guarded by `@pytest.mark.network` and
`TRAILER_INTEGRATION_TESTS=1`. Uses a stable CC-licensed clip on the Blender Foundation
channel (URL `aqz-KE-bpKQ`, available since 2017) rather than the ambiguous "Big Buck
Bunny" ID that the reviewer flagged as unstable.

Create `tests/trailers/test_integration_network.py`:

```python
"""End-to-end integration test for the trailers feature.

Requires TRAILER_INTEGRATION_TESTS=1 (real network) and TMDB_API_KEY in env.
Downloads a known-stable trailer to a tmpdir to verify the full stack:
TrailerFinder → YtdlpDownloader → placement.trailer_exists().

Skipped in CI by default.
"""

import os
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not os.getenv("TRAILER_INTEGRATION_TESTS"),
    reason="Network integration test — set TRAILER_INTEGRATION_TESTS=1 to run",
)
def test_trailer_finder_and_download_e2e(tmp_path):
    """Download the Big Buck Bunny trailer end-to-end using the real TMDB client.

    Big Buck Bunny is a freely licensed Blender Foundation film. Its TMDB ID
    is 10378 (confirmed stable). This test verifies:
    1. TMDBClient.fetch_movie_videos returns at least one video entry.
    2. YtdlpDownloader downloads the trailer to tmpdir without error.
    3. trailer_exists() confirms the file meets the minimum size threshold.
    """
    api_key = os.environ.get("TMDB_READ_ACCESS_TOKEN") or os.environ.get("TMDB_API_KEY")
    if not api_key:
        pytest.skip("TMDB_READ_ACCESS_TOKEN not set — skipping integration test")

    from personalscraper.scraper.tmdb_client import TMDBClient
    from personalscraper.scraper.trailers_cache import TrailersCache
    from personalscraper.scraper.youtube_search import YoutubeSearch
    from personalscraper.scraper.trailer_finder import TrailerFinder
    from personalscraper.scraper.ytdlp_downloader import YtdlpDownloader
    from personalscraper.trailers.placement import trailer_path_for, trailer_exists

    # Big Buck Bunny TMDB ID
    TMDB_ID = 10378
    TITLE = "Big Buck Bunny"
    YEAR = 2008
    MIN_SIZE = 100 * 1024  # 100 KiB

    # Wire up the discovery stack
    from personalscraper.scraper.circuit_breaker import CircuitBreaker
    from personalscraper.scraper.json_ttl_cache import JsonTTLCache
    client = TMDBClient(api_key=api_key, language="en-US")
    cache = TrailersCache(tmp_path / "test_trailers_cache.json")
    searcher = YoutubeSearch(
        query_format="{title} {year} trailer",
        api_key=os.environ.get("YOUTUBE_API_KEY", ""),
        quota_cache=JsonTTLCache(tmp_path / "quota.json"),
        breaker=CircuitBreaker(errors_threshold=5, cooldown_sec=60),
    )
    finder = TrailerFinder(
        tmdb_client=client,
        youtube_search=searcher,
        cache=cache,
        languages=["en-US"],
    )

    url = finder.find(TMDB_ID, "movie", title=TITLE, year=YEAR)
    assert url is not None, "TrailerFinder returned None — no trailer found for Big Buck Bunny"

    # Download to tmpdir
    movie_dir = tmp_path / f"{TITLE} ({YEAR})"
    movie_dir.mkdir()
    output_path = trailer_path_for(movie_dir, f"{TITLE} ({YEAR})", ext="mp4")

    downloader = YtdlpDownloader(
        output_dir=tmp_path,
        ytdlp_format="worst[ext=mp4]/worst",  # Smallest for test speed
        socket_timeout_sec=60,
        retries=2,
        cookie_config=None,
    )
    from personalscraper.scraper.ytdlp_downloader import DownloadStatus
    result = downloader.download(url, output_path)

    assert result.status == DownloadStatus.SUCCESS, (
        f"Download failed with status={result.status}: {result.error_message}"
    )
    assert trailer_exists(output_path, min_size_bytes=MIN_SIZE), (
        f"Trailer file missing or too small: {output_path}"
    )
```

Commit: `test(trailer): add @pytest.mark.network E2E integration test (Big Buck Bunny)`

### Sub-phase 9.1b — If existing full-pipeline E2E fixture: extend it

Read the existing `tests/e2e/conftest.py` and `test_pipeline_movies.py`. Add a test
that verifies the trailers step runs (with `skip_trailers=False`) in the pipeline and
produces a `StepReport` with `name="trailers"`.

Commit: `test(trailer): extend pipeline E2E fixture to cover trailers step`

---

## Sub-phase 9.2 — Coverage audit

### Step 1: Run full test suite with coverage

```bash
cd "$(git rev-parse --show-toplevel)"
python -m pytest -q --cov=personalscraper --cov-report=term-missing 2>&1 | tail -30
```

### Step 2: Identify uncovered lines in trailer modules

Focus on:

- `personalscraper/trailers/*.py`
- `personalscraper/scraper/trailer_finder.py`
- `personalscraper/scraper/ytdlp_downloader.py`
- `personalscraper/scraper/trailers_cache.py`

### Step 3: Add missing unit tests for uncovered branches

For each module with coverage below the project baseline (check with
`pytest --cov-fail-under=N` if the project has a threshold configured):

- Add edge-case unit tests for the uncovered branches.
- Focus on error paths (exception handlers, boundary conditions).

Commit each test file fix separately:

```
test(trailer): improve coverage for <module> edge cases
```

---

## Sub-phase 9.3 — Reference documentation

Documentation is not just `trailers.md` — four existing reference docs need to be updated
so Claude's lazy-load triggers surface trailer content for related tasks, and so the test
marker / naming / CLI conventions are discoverable without reading source.

### Files

| Action | Path                             | What gets added                                                                                                                                                                                                                                                                             |
| ------ | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create | `docs/reference/trailers.md`     | Main reference doc for the trailers feature (see sections below).                                                                                                                                                                                                                           |
| Modify | `docs/reference/architecture.md` | Module map: add `scraper/json_ttl_cache.py`, `scraper/youtube_search.py`, `scraper/trailer_finder.py`, `scraper/ytdlp_downloader.py`, `scraper/trailers_cache.py`, `trailers/` package (step/scanner/orchestrator/state/placement/cli). Update the pipeline-steps diagram from 8 → 9 steps. |
| Modify | `docs/reference/commands.md`     | New section for `personalscraper trailers scan/download/verify/purge` — flags, exit codes, examples. Add `--skip-trailers` and `--continue-on-trailer-error` to `personalscraper run`.                                                                                                      |
| Modify | `docs/reference/testing.md`      | Document the `@pytest.mark.network` marker and the `TRAILER_INTEGRATION_TESTS=1` env var. Note the hermetic E2E fixture runs by default.                                                                                                                                                    |
| Modify | `docs/reference/naming.md`       | Trailer file naming convention: `{folder}/{name}-trailer.{ext}` (flat, used for movies AND TV shows). Accepted extensions: `.mp4`, `.mkv`, `.webm` (in priority order). NFO `<trailer>` tag carries the YouTube URL.                                                                        |
| Modify | `docs/reference/scraping.md`     | TMDB `/videos` endpoint: response shape, `site` field, filtering rules (`site=='YouTube'` required, prefer `official` + `type in {Trailer, Teaser}`).                                                                                                                                       |
| Modify | `docs/reference/libraries.md`    | Note on yt-dlp version pinning (`>=2025.x,<2026.x`) and ffmpeg dependency (`shutil.which('ffmpeg')` check at startup).                                                                                                                                                                      |

### Step 1: Create `docs/reference/trailers.md`

The reference doc must cover (English, following existing docs/reference/ style):

**Sections:**

1. **Overview** — one paragraph on what the trailers feature does and when it runs.
2. **Configuration** — `config.json5` `trailers` block (all keys with types and defaults),
   including the two-tier search, two circuit breakers, and quota accounting.
3. **Environment variables** — `YOUTUBE_API_KEY` (primary), `YOUTUBE_COOKIES_FILE`,
   `YOUTUBE_COOKIES_FROM_BROWSER`.
4. **Pipeline step** — position in pipeline (between `verify` and `dispatch`), non-blocking
   semantics, `--skip-trailers` flag, `--continue-on-trailer-error` override.
5. **CLI commands** — `personalscraper trailers scan|download|verify|purge` with all flags,
   exit codes (0/1/2), and examples using the project `Disk1-4` convention.
6. **State file** — `.data/trailers_state.json` format, composite keys
   (`movie:tmdb:{id}` / `tv:tmdb:{id}` / `manual:{sha256(title|year|type)}`), retry policy,
   `bot_detected_max_consecutive_attempts`.
7. **Placement convention** — flat `{folder}/{name}-trailer.{ext}` for movies AND TV shows.
   NFO `<trailer>` tag is populated with the YouTube URL (Plex remote-trailer fallback).
8. **Security** — cookie file requirements (APFS-only, mode 600); `.env` gitignored.
9. **ToS note** — downloading YouTube content is grey-area; this feature is for personal
   use only, per YouTube Terms of Service §5. Do not redistribute downloaded content.
10. **Troubleshooting** — common failure modes (`bot_detected`, expired cookies, NTFS
    rejection, YouTube quota exhausted, yt-dlp out of date, ffmpeg missing).

### Step 2: Update the six existing reference docs

Apply the changes listed in the table above. Each file gets its own small commit so the
docs change is bisectable:

```bash
git add docs/reference/trailers.md
git commit -m "docs(trailer): add trailers reference doc"

git add docs/reference/architecture.md
git commit -m "docs(trailer): update architecture module map + pipeline step count"

git add docs/reference/commands.md
git commit -m "docs(trailer): document personalscraper trailers CLI commands"

git add docs/reference/testing.md
git commit -m "docs(trailer): document @pytest.mark.network and TRAILER_INTEGRATION_TESTS"

git add docs/reference/naming.md
git commit -m "docs(trailer): document flat {name}-trailer.{ext} convention"

git add docs/reference/scraping.md
git commit -m "docs(trailer): document TMDB /videos response shape and filtering rules"

git add docs/reference/libraries.md
git commit -m "docs(trailer): document yt-dlp pinning and ffmpeg dependency"
```

---

## Sub-phase 9.4 — CLAUDE.md trigger-table update

### Files

| Action | Path        | Responsibility                                                         |
| ------ | ----------- | ---------------------------------------------------------------------- |
| Modify | `CLAUDE.md` | Add trailers row to Reference Index + brief "Current Feature" rollback |

### Step 1: Add the trailers entry to the Reference Index table in `CLAUDE.md`

Find the `| When working on...` table in `CLAUDE.md` and add:

```
| Trailer discovery, download, state, CLI, flat `{name}-trailer.{ext}` placement | `docs/reference/trailers.md`           |
```

### Step 2: Roll back the "Current Feature" section

Remove the `ext-staging` entry from the "Current Feature" block at the bottom of
`CLAUDE.md` and replace it with `trailer` (this feature). The block will be removed again
by `/implement:archive` after merge.

### Step 2: Commit

```bash
git add CLAUDE.md
git commit -m "docs(trailer): add trailers.md to CLAUDE.md reference index"
```

---

## Sub-phase 9.5 — Final quality gate

### Step 1: Full test suite

```bash
cd "$(git rev-parse --show-toplevel)"
make test
```

Expected: all tests pass. No skipped tests except `@pytest.mark.network` ones.

### Step 2: Ruff lint

```bash
make lint
```

Expected: no errors, no warnings.

### Step 3: mypy full check

```bash
python -m mypy personalscraper/trailers/ personalscraper/scraper/trailer_finder.py \
  personalscraper/scraper/json_ttl_cache.py personalscraper/scraper/trailers_cache.py \
  personalscraper/scraper/youtube_search.py personalscraper/scraper/ytdlp_downloader.py
```

Expected: `Success: no issues found` for all modules.

### Step 4: Verify import surface

```bash
python -c "
from personalscraper.scraper.tmdb_client import TMDBClient, Video
from personalscraper.scraper.json_ttl_cache import JsonTTLCache
from personalscraper.scraper.trailer_finder import TrailerFinder
from personalscraper.scraper.youtube_search import YoutubeSearch
from personalscraper.scraper.ytdlp_downloader import YtdlpDownloader, CookieConfig, DownloadResult
from personalscraper.scraper.trailers_cache import TrailersCache
from personalscraper.trailers.placement import trailer_path_for, trailer_exists
from personalscraper.trailers.state import TrailerStateStore, TrailerStatus, make_state_key
from personalscraper.trailers.step import run_trailers
from personalscraper.trailers.scanner import Scanner, ScanItem
from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.cli import app as trailers_app
from personalscraper.conf.models import TrailersConfig
print('All imports OK')
"
```

Expected: `All imports OK`.

### Step 5: Verify CLI help

```bash
python -m personalscraper trailers --help
python -m personalscraper trailers scan --help
python -m personalscraper trailers download --help
python -m personalscraper trailers verify --help
python -m personalscraper trailers purge --help
```

Expected: each command prints its help text with all flags visible.

---

## Phase 9 quality gate summary

- [ ] `make test` — full suite green (unit + e2e, excluding network tests)
- [ ] `make lint` — no ruff errors
- [ ] `python -m mypy personalscraper/trailers/` — no type errors
- [ ] All imports verified
- [ ] CLI help pages verified
- [ ] `docs/reference/trailers.md` exists
- [ ] CLAUDE.md trigger-table entry added

## Milestone commit (final feature gate)

```bash
git commit --allow-empty -m "chore(trailer): phase 09 gate — E2E test, trailers reference doc, full quality gate"
```

This is the final commit on `feat/trailer` before the PR. The `/implement:feature-pr`
skill takes over from here: local gate check → push → create PR → poll CI.
