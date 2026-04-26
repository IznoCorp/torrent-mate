# Libraries Reference

Python library gotchas: rapidfuzz, tenacity, structlog, rich, guessit.

## rapidfuzz (fuzzy matching)

- `default_process` does **NOT** strip accents — use `media_processor` from `personalscraper/text_utils.py` (NFD decomposition) for French titles.
- **v3.0+ has NO automatic preprocessing** — always pass `processor=media_processor` or scores will be wrong.
- `WRatio` is the recommended scorer for media titles (balances exact match with tolerance for extra tokens).

### fuzzy_match_score guards

`fuzzy_match_score()` in `text_utils.py` provides 3 anti-false-positive guards:

1. **Year**: ±1 year tolerance
2. **Length ratio**: ≥ 0.67 required
3. **Adaptive threshold**: ≤10 chars → 95%, >10 → 90%

Used by the sorter matcher and dispatch media_index.

## tenacity (retry)

- `@retry` without args retries **FOREVER** with NO delay — always specify `stop` and `wait`.
- `reraise=True` is recommended — otherwise exceptions are wrapped in `RetryError`.

## structlog (logging)

- `ProcessorFormatter.wrap_for_formatter` **MUST** be the last structlog processor — `JSONRenderer` goes in `ProcessorFormatter`, NOT in `structlog.configure`.
- `cache_logger_on_first_use=True` makes `configure()` calls after first log silently ignored — configure early.

## rich (CLI output)

- `Console(quiet=True)` suppresses all output natively — no need for `if not quiet:` checks.
- Rich markup in log messages: keep `markup=False` on `RichHandler` to avoid `[brackets]` being interpreted as tags.


## yt-dlp (trailer downloads)

- Version pin: >=2025.1,<2026 (YouTube changes format fingerprints frequently; pin to avoid breakage)
- ffmpeg dependency: checked at startup via shutil.which("ffmpeg"). If absent, yt-dlp cannot merge
  separate video and audio streams into a single mp4. Install with: brew install ffmpeg
- Cookie file mode: yt-dlp rejects cookie files with permissions wider than 600 (security check)
- Default search prefix: "ytsearch1:" -- used when no YouTube API key is configured
- Format selector: "bestvideo[height<=1080]+bestaudio/best[height<=1080]" -- capped at 1080p

## guessit (filename parsing)

Used by the sorter for media filename parsing. Reference: `docs/guessit-evaluation.md`.
