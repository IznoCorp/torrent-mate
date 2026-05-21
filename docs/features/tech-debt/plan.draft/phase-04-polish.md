# Phase 4 — Polish + final ACCEPTANCE pass

**Goal** : Documentation hygiene + final ACCEPTANCE re-run on the live instance. Close the audit cycle.

## Gate (in)

- Phase 3 complete
- `make check` green
- `personalscraper info` lists version `0.15.1`
- Live `personalscraper library-index` succeeds end-to-end (multi-disk OK)

## Gate (out)

- All N1-N7 polish items applied
- ACCEPTANCE.md re-validation document complete with live command outputs
- IMPLEMENTATION.md status = TERMINÉ
- Branch ready for `/implement:feature-pr` → `/implement:pr-review`

## Sub-phases

### 4.1 — Stale module docstrings (N3)

**Files** :

- `personalscraper/api/metadata/tmdb.py`
- `personalscraper/api/metadata/omdb.py`
- `personalscraper/api/metadata/trakt.py`
- `personalscraper/api/tracker/c411.py`
- `personalscraper/api/tracker/lacale.py`

**Action** : strip "Implements MetadataClient + MetadataProvider Protocol" / "Implements TrackerClient Protocol" lines from module-level docstrings. Replace with "Composes <atomic protocols> from `<contracts module>`" matching the actual inheritance.

**Commit** : `docs(tech-debt): refresh stale module docstrings on api/* clients`

### 4.2 — Retired-version refs (N5)

**Files** :

- `docs/reference/architecture.md`
- `docs/reference/c411-api.md`
- `docs/reference/lacale-api.md`
- `docs/reference/event-bus.md`

**Action** : strip "api-unify (0.11.0)" / "Phase 18/20" / "pre-0.13" historical artifacts. Reference docs describe current state ; feature history belongs in `docs/archive/features/`.

**Commit** : `docs(tech-debt): drop retired-version refs from reference docs`

### 4.3 — `/implement:pr-review` doc consistency (N6)

**Files** :

- `CLAUDE.md` ("max-3 fix cycles")
- `.claude/skills/implement:pr-review/SKILL.md` ("max 5")

**Action** : pick one limit (recommendation : max-3, matches CLAUDE.md) and align both.

**Commit** : `docs(tech-debt): align implement:pr-review max-cycle count between CLAUDE.md and skill`

### 4.4 — `LIBRARY_ANALYZER_MAX_WORKERS` doc/migration (N2 + Q3)

**Decision** (Q3 from DESIGN §8) :

- **Option A — Promote to `preferences.json5`** : add a `library_analyzer_max_workers` field to the preferences config schema. Add to `config.example/preferences.json5`. Read via `cfg.preferences.library_analyzer_max_workers` instead of `os.environ.get`.
- **Option B — Stay env-var, document in `.env.example`** : add the line with default value + explanatory comment.

**Recommendation** : B (smaller change, env-var is fine for a tuning knob).

**Commit** : `docs(tech-debt): document LIBRARY_ANALYZER_MAX_WORKERS env var in .env.example` (Option B)

### 4.5 — `personalscraper info` regression test (N1)

**File** : `tests/test_cli.py` or new `tests/commands/test_info.py`

**Action** : add a regression test using `CliRunner` :

```python
result = runner.invoke(app, ["info"])
assert result.exit_code == 0
assert "personalscraper 0.15.1" in result.output  # or whatever current VERSION
```

**Commit** : `test(tech-debt): add regression test for personalscraper info command`

### 4.6 — Drop `extract_nfo_ids` 2-tuple wrapper (N7)

**Files** :

- `personalscraper/library/scanner.py` (the wrapper itself)
- `personalscraper/library/rescraper.py` (caller — migrate to `extract_nfo_metadata`)
- `personalscraper/trailers/scanner.py` (caller — migrate)
- `tests/library/test_scanner.py` (drop `TestExtractNfoIds` after migration)

**Action** : migrate both callers to read from the rich `extract_nfo_metadata` dict ; delete the wrapper. Keep the function name as a re-export if backward compat with external scripts matters (probably not for a personal project).

**Commit** : `refactor(tech-debt): drop extract_nfo_ids compat wrapper after caller migration`

### 4.7 — Resolved-TODO leftover (N4)

**File** : `personalscraper/scraper/tv_service.py:662`

**Action** : delete the resolved-TODO commentary block ; keep only the surrounding logic. Trivial cleanup.

**Commit** : `style(tech-debt): drop resolved-TODO leftover in tv_service`

### 4.8 — Final ACCEPTANCE re-run on live instance

**Action** :

1. On the live `.data/library.db`, run every verifiable command from the rewritten `ACCEPTANCE.md` (Phase 2.2)
2. Record outputs in `docs/archive/features/provider-ids/ACCEPTANCE-validation.md`
3. Update `IMPLEMENTATION.md` (this branch's) → status "TERMINÉ" with link to validation doc

**Commit** : `docs(tech-debt): final provider-ids ACCEPTANCE re-validation on live instance`

## Definition of done

- 8 commits on `fix/tech-debt`
- `make check` green
- IMPLEMENTATION.md = TERMINÉ
- All polish items applied (N1-N7)
- Final ACCEPTANCE pass documented
- Branch ready for `/implement:feature-pr`
