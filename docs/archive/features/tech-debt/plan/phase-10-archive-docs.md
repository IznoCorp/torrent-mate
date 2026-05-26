# Phase 10 — Archive DESIGN.md updates

**Effort** : 1-2 jours
**Theme** : amender les 7 archived DESIGN.md devenus stale post-refactor + cleanups doc rot
identifiés en REDO item 11 (P30 DOC_ROT pattern).

## Coverage matrix

| Item                                 | Sub-phase | Source pattern |
| ------------------------------------ | --------- | -------------- |
| DEV #24 + #26 — event-bus            | 10.1.a    | P30            |
| DEV #27 + #28 — provider-ids note    | 10.1.b    | P30, P23       |
| DEV #32 + #35 + #36 — media-indexer  | 10.1.c    | P30            |
| DEV #39 — pipeline-obs superseded    | 10.1.d    | P30            |
| DEV #42 + #43 — trailer              | 10.1.e    | P30            |
| DEV #45 — logging.md broken paths    | 10.1.f    | P30            |
| DEV #48 — legacy-cleanup VX leaks    | 10.1.g    | P30            |
| DEV #44 — \_exclusions.py docstring  | 10.2.a    | P30            |
| DEV #48 — MANUAL.md V3 + docs/\*.md  | 10.2.b    | P30            |
| DEV #45 + #47 + #24 — reference sync | 10.3      | P30            |

DESIGN sections impacted : §12 documentation conformity (full implementation here).
Note : DEV #9 mentioned in matrix but ALREADY shipped (commit 268cbee, not in scope).

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
- Phase 6 (heavy doc work) commited
- Phase 7 (matrix v2.1) commited
- **Phase 8 commited** (Plan A reset+rescrape done — 10.1.b banner cite le SHA Phase 8.10)
- DEV #24-#49 mapped to leverage items

## Sub-phases

### 10.1 Bannière "superseded" + old→new mapping — 7 features

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

#### 10.1.a event-bus (DEV #24)

Banner + mapping : v1 catalog 13 → 17 events (4 Backfill\* added by provider-ids) ;
`docs/reference/event-bus.md` catalog table updated; `personalscraper/events/__init__.py:__all__`
appended with the 4 Backfill\* event names.

Commit : `docs(tech-debt): event-bus archive banner + catalog v1.1 13→17 events (DEV #24, #26)`

#### 10.1.b provider-ids (DEV #27, #28 — note l'écart historique)

Banner explicite : "Plan A reset+rescrape executé en Phase 8 du tech-debt cycle (commit
0.16.0 SHA xxx). ACCEPTANCE #3 + #6 + #9 re-marked ❌ → ✅ post-cycle."

Commit : `docs(tech-debt): provider-ids archive banner + post-tech-debt status reconciliation`

#### 10.1.c media-indexer (DEV #32, #35, #36)

Banner + mapping :

- `media_item.tmdb_id/imdb_id/tvdb_id` columns → `external_ids_json` (mig 005)
- 3 indexes `idx_item_tmdb/imdb/tvdb` → 3 JSON-path indexes
- scan_run modes documented = 4 ; actual CHECK = 6 (+verify, +repair)
- `media_stream` extended (mig 004) : `hdr_format`, `is_atmos`, `is_default`, `forced`,
  `format`

Commit : `docs(tech-debt): media-indexer archive banner + mig 002-005 deltas`

#### 10.1.d pipeline-obs (DEV #39)

Banner CRITIQUE : "Entire architecture superseded by feat/event-bus. See
`docs/reference/event-bus.md`."

Old → New mapping table dans le banner :

- `PipelineObserver` Protocol → `EventBus` subscriber
- `StepEvent` → `StepProgress` event
- `notify_progress()` → `event_bus.emit(...)`
- `CollectorObserver` (testing) → `RecordingSubscriber` (testing)
- `RichConsoleObserver` → `RichConsoleSubscriber`

Commit : `docs(tech-debt): pipeline-obs archive superseded banner + observer→subscriber mapping`

#### 10.1.e trailer (DEV #42, #43)

Banner : "Mid-PR pivots cycle 3 changed §4 placement convention and §14 blocking semantics.
See `docs/reference/trailers.md` for current source-of-truth."

Old → New mapping :

- §4 "flat `{name}-trailer.{ext}` for movies AND TV" → "movies flat, TV in `Trailers/`
  subfolder (Plex-conformant)"
- §14 "status=partial does NOT block dispatch" → "Blocking by default ; --continue-on-trailer-error
  to override"

Commit : `docs(tech-debt): trailer archive banner + post-pivot mapping (DEV #42, #43)`

#### 10.1.f logging (DEV #45)

Banner : "Module paths in this archive reference pre-`api-unify` layout. See
`docs/reference/logging.md` for current paths."

Old → New mapping :

- `personalscraper.scraper.http_retry.build_retry_logger` → `personalscraper.core.http_helpers.build_retry_logger`
- `scraper/tmdb_client.py` (canonical template) → `personalscraper/api/metadata/tmdb.py`

Commit : `docs(tech-debt): logging archive banner + post-api-unify path mapping`

#### 10.1.g legacy-cleanup (DEV #48)

Banner : "Original scope was alpha-version cleanup. Doc rot remains in non-scope docs/\*.md
top-level (~43 VX hits). Resolved in `chore(tech-debt): 10.2 below`."

Commit : `docs(tech-debt): legacy-cleanup archive banner + scope reconciliation`

### 10.2 Cleanups associés (DEV #44, #48 résolution)

#### 10.2.a `_exclusions.py:383` docstring (DEV #44)

Rewrite the literal `"001-MOVIES/Inception (2010)"` as `"{movies_dir}/Inception (2010)"`
placeholder to restore Phase 2 success criterion 3.

#### 10.2.b VX leaks (DEV #48)

- `MANUAL.md` : 2 lines "remplacé par V3" → rewrite without VX token
- `docs/structlog-reference.md` + `docs/rich-reference.md` + 6 other docs/\*.md top-level :
  43 VX hits → sweep, replace with current naming or move to archive if obsolete

Commits :

- `docs(tech-debt): _exclusions.py docstring placeholder (DEV #44)`
- `docs(tech-debt): legacy-cleanup VX sweep in docs/*.md (DEV #48)`

### 10.3 Reference docs sync (DEV #45 + #47)

- `docs/reference/logging.md:82,139` → update module paths (DEV #45)
- `docs/reference/architecture.md` ou `models.md` → update `StepReport.details_payload` type
  (`Any | None` → `dict[str, Any] | None`) (DEV #47)
- `docs/reference/event-bus.md` → update event catalog table to 17 events (lié 10.1.a)

Commit : `docs(tech-debt): reference docs sync — logging paths, details_payload type,
event catalog 17 (DEV #45, #47, #24)`

### 10.4 Final cleanup — delete HANDOVER.md (closure)

**Site** : `docs/features/tech-debt/HANDOVER.md`

**Rationale** : `HANDOVER.md` est un document **transient** créé en fin de session
2026-05-22 pour transférer le contexte à la session suivante d'implémentation. Une fois
toutes les phases shippées, il est **obsolète** :

- Le contexte historique vit dans les commits + `audit/01..11.md` (permanent)
- L'état "next actions" est résolu (toutes les phases shipped)
- Les "user preferences memories" vivent dans `MEMORY.md` (global persistent)

Garder HANDOVER.md post-merge crée de la dette doc (P30 DOC_ROT que ce plan veut éliminer).

**Action** :

```bash
git rm docs/features/tech-debt/HANDOVER.md
```

Et update `IMPLEMENTATION.md` pour retirer la mention "READ FIRST HANDOVER.md" (puisqu'elle
n'existe plus). IMPLEMENTATION.md devient le seul tracker.

**Commit** : `chore(tech-debt): delete transient HANDOVER.md post-implementation closure`

## Phase 10 Gate (= PR final gate) — GATE COMMIT `<this commit>` (2026-05-24)

- [x] 10.1.a–g : 7 archived DESIGN.md ont banner + mapping — shipped via 10.1/1 (event-bus `9c2c801`, provider-ids `5350b54`, media-indexer `8f38a92`) + 10.1/2 (pipeline-obs `7064713`, trailer `05b64da`, logging `5fadadc`, legacy-cleanup `0e64616`) + ACC-46 mark `693acb5` → `6af0218`. **8th archive (arch-cleanup) added in 10.3** (`651726c`) because it was missed by the original 7-list and had `details_payload` type drift (DEV #47).
- [x] 10.2.a : \_exclusions.py docstring cleaned — `cbbc408` (`{movies_dir}/Inception (2010)` placeholder)
- [x] 10.2.b : MANUAL.md + docs/\*.md top-level VX-free — `4a73e5c` (5 alpha-version refs moved to `docs/archive/legacy-alpha/`) + `2e917a9` (4 inline rewrites for MANUAL + TVDB/TMDB/qbit API refs)
- [x] 10.3 : reference docs synced — `651726c` (arch-cleanup banner) + `3a89ba5` (ACC-49 ✅). Per orchestrator pre-audit, the other 2 spec items (logging.md paths DEV #45, event-bus.md catalog DEV #24) were already shipped via `329afbc` and `fb96adb` respectively
- [x] **10.4 : HANDOVER.md deleted + IMPLEMENTATION.md cleaned of HANDOVER references** — `fb36cd9` (rm HANDOVER.md, 752 lines deleted) + `74219f2` (IMPL header cleanup)
- [x] `make check` vert (modulo 3 pre-existing test failures carried from Phase 8/9 gates, NOT Phase 10 introduced)
- [x] `rg "\bV[0-9]+\b" docs/*.md` returns only docs/archive/ paths — verified empty
- [x] `test ! -f docs/features/tech-debt/HANDOVER.md` (closure ack) — verified

**Phase gate commit** : `chore(tech-debt): phase 10 gate — archive doc updates + HANDOVER closure (P30 DOC_ROT resolved)`
