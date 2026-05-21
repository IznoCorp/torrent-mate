# Phase 9 — Archive DESIGN.md updates

**Effort** : 1-2 jours
**Theme** : amender les 7 archived DESIGN.md devenus stale post-refactor + cleanups doc rot
identifiés en REDO item 11 (P30 DOC_ROT pattern).

## Gate

- Phase 6 (heavy doc work) commited
- Phase 7 (matrix v2.1) commited
- DEV #24-#49 mapped to leverage items

## Sub-phases

### 9.1 Bannière "superseded" + old→new mapping — 7 features

**Format universel** à appliquer en haut de chaque archived DESIGN.md :

```markdown
> **⚠ STATUS** : This DESIGN.md is an archived as-designed snapshot. Some claims are
> superseded by later features. See `docs/reference/<topic>.md` for the current source-of-truth.
>
> **Old → New mapping** :
> | Old (DESIGN.md) | New (current) | Replaced by |
> |---|---|---|
> | `Symbol1` | `NewSymbol1` | `feat/X` |
> | `Section §N claim` | `New behavior` | `feat/Y` |
```

#### 9.1.a event-bus (DEV #24)

Banner + mapping : v1 catalog 13 → 17 events (4 Backfill\* added by provider-ids) ;
`docs/reference/event-bus.md` catalog table updated; `personalscraper/events/__init__.py:__all__`
appended with the 4 Backfill\* event names.

Commit : `docs(tech-debt): event-bus archive banner + catalog v1.1 13→17 events (DEV #24, #26)`

#### 9.1.b provider-ids (DEV #27, #28 — note l'écart historique)

Banner explicite : "Plan A reset+rescrape executé en Phase 8 du tech-debt cycle (commit
0.16.0 SHA xxx). ACCEPTANCE #3 + #6 + #9 re-marked ❌ → ✅ post-cycle."

Commit : `docs(tech-debt): provider-ids archive banner + post-tech-debt status reconciliation`

#### 9.1.c media-indexer (DEV #32, #35, #36)

Banner + mapping :

- `media_item.tmdb_id/imdb_id/tvdb_id` columns → `external_ids_json` (mig 005)
- 3 indexes `idx_item_tmdb/imdb/tvdb` → 3 JSON-path indexes
- scan_run modes documented = 4 ; actual CHECK = 6 (+verify, +repair)
- `media_stream` extended (mig 004) : `hdr_format`, `is_atmos`, `is_default`, `forced`,
  `format`

Commit : `docs(tech-debt): media-indexer archive banner + mig 002-005 deltas`

#### 9.1.d pipeline-obs (DEV #39)

Banner CRITIQUE : "Entire architecture superseded by feat/event-bus. See
`docs/reference/event-bus.md`."

Old → New mapping table dans le banner :

- `PipelineObserver` Protocol → `EventBus` subscriber
- `StepEvent` → `StepProgress` event
- `notify_progress()` → `event_bus.emit(...)`
- `CollectorObserver` (testing) → `RecordingSubscriber` (testing)
- `RichConsoleObserver` → `RichConsoleSubscriber`

Commit : `docs(tech-debt): pipeline-obs archive superseded banner + observer→subscriber mapping`

#### 9.1.e trailer (DEV #42, #43)

Banner : "Mid-PR pivots cycle 3 changed §4 placement convention and §14 blocking semantics.
See `docs/reference/trailers.md` for current source-of-truth."

Old → New mapping :

- §4 "flat `{name}-trailer.{ext}` for movies AND TV" → "movies flat, TV in `Trailers/`
  subfolder (Plex-conformant)"
- §14 "status=partial does NOT block dispatch" → "Blocking by default ; --continue-on-trailer-error
  to override"

Commit : `docs(tech-debt): trailer archive banner + post-pivot mapping (DEV #42, #43)`

#### 9.1.f logging (DEV #45)

Banner : "Module paths in this archive reference pre-`api-unify` layout. See
`docs/reference/logging.md` for current paths."

Old → New mapping :

- `personalscraper.scraper.http_retry.build_retry_logger` → `personalscraper.core.http_helpers.build_retry_logger`
- `scraper/tmdb_client.py` (canonical template) → `personalscraper/api/metadata/tmdb.py`

Commit : `docs(tech-debt): logging archive banner + post-api-unify path mapping`

#### 9.1.g legacy-cleanup (DEV #48)

Banner : "Original scope was alpha-version cleanup. Doc rot remains in non-scope docs/\*.md
top-level (~43 VX hits). Resolved in `chore(tech-debt): 9.2 below`."

Commit : `docs(tech-debt): legacy-cleanup archive banner + scope reconciliation`

### 9.2 Cleanups associés (DEV #44, #48 résolution)

#### 9.2.a `_exclusions.py:383` docstring (DEV #44)

Rewrite the literal `"001-MOVIES/Inception (2010)"` as `"{movies_dir}/Inception (2010)"`
placeholder to restore Phase 2 success criterion 3.

#### 9.2.b VX leaks (DEV #48)

- `MANUAL.md` : 2 lines "remplacé par V3" → rewrite without VX token
- `docs/structlog-reference.md` + `docs/rich-reference.md` + 6 other docs/\*.md top-level :
  43 VX hits → sweep, replace with current naming or move to archive if obsolete

Commits :

- `docs(tech-debt): _exclusions.py docstring placeholder (DEV #44)`
- `docs(tech-debt): legacy-cleanup VX sweep in docs/*.md (DEV #48)`

### 9.3 Reference docs sync (DEV #45 + #47)

- `docs/reference/logging.md:82,139` → update module paths (DEV #45)
- `docs/reference/architecture.md` ou `models.md` → update `StepReport.details_payload` type
  (`Any | None` → `dict[str, Any] | None`) (DEV #47)
- `docs/reference/event-bus.md` → update event catalog table to 17 events (lié 9.1.a)

Commit : `docs(tech-debt): reference docs sync — logging paths, details_payload type,
event catalog 17 (DEV #45, #47, #24)`

## Phase 9 Gate

- [ ] 9.1.a–g : 7 archived DESIGN.md ont banner + mapping
- [ ] 9.2.a : \_exclusions.py docstring cleaned
- [ ] 9.2.b : MANUAL.md + docs/\*.md top-level VX-free
- [ ] 9.3 : reference docs synced
- [ ] `make check` vert
- [ ] `rg "\bV[0-9]+\b" docs/*.md` returns only docs/archive/ paths

**Phase gate commit** : `chore(tech-debt): phase 9 gate — archive doc updates (P30 DOC_ROT
resolved for 7 features)`
