# Phase 25 — Final Cleanup + ROADMAP

**Type**: infra
**Goal**: Residual import audit, dead config purge, doc updates, ROADMAP entry, version bump verification.

## Gate (prereq)

Phase 24 complete. All providers migrated, all old modules deleted.

## Sub-phases

### 25.1 — Residual import audit

Verify zero references to deleted modules:

```bash
for old in \
  "scraper.tmdb_client" \
  "scraper.tvdb_client" \
  "scraper.circuit_breaker" \
  "scraper.http_retry" \
  "scraper.providers" \
  "ingest.qbit_client" \
  "personalscraper.notifier"
do
  count=$(rg "$old" personalscraper/ tests/ --files-with-matches | wc -l)
  echo "$old: $count"
  test "$count" = "0"
done
```

Expected: `0` for all. Any non-zero hit fails the gate.

### 25.2 — Dead exception types audit

```bash
! rg "TMDBError|TVDBError" personalscraper/ tests/
```

### 25.3 — Dead config audit

```bash
# No legacy config fields referencing old paths.
rg "tmdb_client|tvdb_client|qbit_client" config/ config.example/
```

Should return zero hits.

### 25.4 — Doc updates

Update `docs/reference/architecture.md`:

- New `api/` package tree (DESIGN §2.1).
- New neutral `core/circuit.py` location for reusable circuit breaking.
- Updated module map.
- New `TransportPolicy` contract reference.
- Old modules removed from documentation.

Update root `CLAUDE.md` reference index — add entries for new docs:

| When working on...                     | Read                                      |
| -------------------------------------- | ----------------------------------------- |
| API contracts, HttpTransport, policies | `docs/reference/architecture.md` (api/ §) |
| TMDB/TVDB/OMDB/Trakt providers         | `docs/reference/<provider>-api.md`        |
| Torrent clients (qBit, Transmission)   | `docs/reference/<provider>-api.md`        |
| Trackers (LaCale, C411)                | `docs/reference/<tracker>-api.md`         |
| Telegram + healthchecks                | `docs/reference/<provider>-api.md`        |

Archive docs (`docs/archive/`) NOT modified.

### 25.5 — ROADMAP update

Add to `ROADMAP.md` under P3:

```markdown
### P3 — Additional Trackers (torr9 + digitalcore)

Implement `api/tracker/torr9.py` and `api/tracker/digitalcore.py` following
the established TrackerClient Protocol. Study APIs, write docs in
`docs/reference/torr9-api.md` and `docs/reference/digitalcore-api.md`,
then implement.

Depends on: Third-Party API Consumer Unification (P0) — completed in 0.11.0.
```

### 25.6 — Version bump verification

Confirm `personalscraper/__init__.py` (or wherever `__version__` lives) reads `0.11.0`. Confirm `pyproject.toml` matches. Confirm changelog entry.

### 25.7 — Final full pipeline smoke test

Run a dry-run pipeline with all providers enabled (skip if not feasible in CI):

```bash
personalscraper init-config --check
personalscraper run --dry-run
```

Verify no warnings about missing config files, all providers report active, no `dict[str, Any]` warnings.

### 25.8 — Phase 25 gate (FINAL)

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "import personalscraper"
python -c "from personalscraper import __version__; assert __version__ == '0.11.0'"
python -c "from personalscraper.core.circuit import CircuitBreaker, CircuitState"
python -c "from personalscraper.core.http_helpers import build_retry_logger, make_retryable_predicate"

# All 7 deleted modules confirmed absent
for f in \
  personalscraper/scraper/tmdb_client.py \
  personalscraper/scraper/tvdb_client.py \
  personalscraper/scraper/circuit_breaker.py \
  personalscraper/scraper/http_retry.py \
  personalscraper/scraper/providers.py \
  personalscraper/ingest/qbit_client.py \
  personalscraper/notifier.py
do
  test ! -f "$f" || { echo "STILL EXISTS: $f"; exit 1; }
done

# All 10 reference docs present
for d in tmdb tvdb omdb trakt qbittorrent transmission lacale c411 telegram healthchecks; do
  test -f "docs/reference/$d-api.md" || { echo "MISSING DOC: $d"; exit 1; }
done

# All 5 config templates present
for c in metadata torrent tracker ranking notify; do
  test -f "config.example/$c.json5" || { echo "MISSING CONFIG: $c"; exit 1; }
done
```

**Commit**: `chore(api-unify): phase 25 gate — feature complete, ready for PR`
