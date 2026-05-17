# Phase 1.2b — MetadataProvider consumer migration plan

Companion document to sub-phase 1.2. Lists every reference to the
legacy monolithic `MetadataProvider` Protocol (defined at
`personalscraper/api/metadata/_base.py:259`) and assigns each
consumer to the phase that migrates it onto the atomic capability
protocols introduced in sub-phase 1.2.

This document is **descriptive** : it records the current state of the
codebase (HEAD `bf5b676`, after sub-phase 1.2 commit) and the
target phase for each migration. It does not modify any production
code.

## Survey method

```
command rg -nF "MetadataProvider" personalscraper/ tests/ --type py
command rg -n "isinstance.*MetadataProvider\b|: MetadataProvider\b" personalscraper/ tests/ --type py
```

Filter out the look-alike `MetadataProviderConfig` Pydantic model
(`conf/models/api_config.py`) — it shares the prefix but is an
unrelated configuration class.

## Key finding

**Zero call sites annotate parameters or run isinstance checks with
`MetadataProvider` outside `tests/unit/test_api_metadata_base.py`.**
The monolithic Protocol is referenced only by:

1. Its own definition in `_base.py`.
2. A dedicated test in `tests/unit/test_api_metadata_base.py` that
   exercises the structural-subtyping contract via an in-test stub.
3. Docstrings on the four concrete clients (omdb, tmdb, trakt, tvdb)
   and on one integration fake (`tests/integration/conftest.py`).

Consumers (scraper services, trailer scanner, pipeline orchestrator)
call concrete client methods directly — they never type a parameter as
`MetadataProvider`. This means the Protocol can be deprecated and
removed without rewriting any call site : the migration is concentrated
in docstrings and one test module.

## References inventory

### Self-references — Protocol definition and decomposition

| File                                         | Line          | Nature                                                    | Migration phase                                       |
| -------------------------------------------- | ------------- | --------------------------------------------------------- | ----------------------------------------------------- |
| `personalscraper/api/metadata/_base.py`      | 255           | Section comment "MetadataProvider Protocol (DESIGN S4.1)" | Phase 1.5 (rewrite or delete on Protocol removal)     |
| `personalscraper/api/metadata/_base.py`      | 259           | Protocol definition (target of deprecation)               | Phase 1.5 (deprecation warning) / phase 15 (deletion) |
| `personalscraper/api/metadata/_base.py`      | 82            | Cross-reference docstring on `SeasonInfo`                 | Phase 5 (re-point to `EpisodeFetcher`)                |
| `personalscraper/api/metadata/_contracts.py` | 3, 16, 25, 56 | Migration-context docstrings, no action required          | —                                                     |

### Client implementations — docstring touch-ups only

| Client class                                    | File                                                    | Line  | Migration phase | Target capability composition                                                                                                                                                             |
| ----------------------------------------------- | ------------------------------------------------------- | ----- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TVDbClient`                                    | `personalscraper/api/metadata/tvdb.py:57`               | 57    | Phase 5         | `Searchable`, `TvDetailsProvider`, `EpisodeFetcher`, `IDValidator`, `IDCrossRef`, `ArtworkProvider`                                                                                       |
| `TMDbClient`                                    | `personalscraper/api/metadata/tmdb.py:57`               | 3, 57 | Phase 5         | `Searchable`, `MovieDetailsProvider`, `TvDetailsProvider`, `EpisodeFetcher`, `IDValidator`, `IDCrossRef`, `ArtworkProvider`, `KeywordProvider`, `VideoProvider`, `RecommendationProvider` |
| `OMDbAdapter` (renamed from `OMDbClient`)       | `personalscraper/api/metadata/omdb.py:3,96`             | 3, 96 | Phase 3         | _Internal backend only_ — no Protocol composition. Façades `IMDbClient` / `RottenTomatoesClient` compose `RatingProvider`, `IDValidator`, `IDCrossRef`.                                   |
| `TraktClient`                                   | `personalscraper/api/metadata/trakt.py:3,96`            | 3, 96 | Phase 5         | `Searchable`, `MovieDetailsProvider`, `TvDetailsProvider`, `RecommendationProvider` (subset to confirm during phase 5)                                                                    |
| `IMDbClient` (façade, new in phase 3)           | `personalscraper/api/metadata/imdb.py` (new)            | —     | Phase 3         | `IDValidator`, `RatingProvider`, `IDCrossRef`                                                                                                                                             |
| `RottenTomatoesClient` (façade, new in phase 3) | `personalscraper/api/metadata/rotten_tomatoes.py` (new) | —     | Phase 3         | `RatingProvider`                                                                                                                                                                          |

For each client, the migration step is :

1. Add explicit capability composition to the class signature
   (e.g. `class TMDbClient(Searchable, TvDetailsProvider, …):`).
2. Rename method(s) where the capability protocol uses a new name
   (e.g. `get_details` → `get_movie` / `get_tv`, `get_season` →
   `get_episodes`, `get_notations` → `get_rating`).
3. Update the docstring to list the composed capabilities instead of
   the legacy "MetadataProvider Protocol".

### Tests — one focused module to refactor

| File                                   | Line range  | Nature                                                                                                                    | Migration phase                                                                                                                                                                 |
| -------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/unit/test_api_metadata_base.py` | 14, 182-230 | `class TestMetadataProviderProtocol` + 2 tests that build a stub provider and assert `isinstance(stub, MetadataProvider)` | Phase 1.5 — replace with per-capability isinstance tests already present in `tests/unit/test_api_contracts.py` ; delete the legacy class once the new ones cover all 8 methods. |
| `tests/integration/conftest.py:474`    | 474         | Docstring on a fake provider's `search` method calling itself a "MetadataProvider protocol dispatch"                      | Phase 5 (rewording when the fake is updated for capability composition)                                                                                                         |

### Look-alike — unrelated config model

| File                                                 | Line     | Nature                                                                                 | Migration phase    |
| ---------------------------------------------------- | -------- | -------------------------------------------------------------------------------------- | ------------------ |
| `personalscraper/conf/models/api_config.py:18,36,82` | 18,36,82 | `MetadataProviderConfig` Pydantic model — same prefix, no relationship to the Protocol | None — keep as is. |

## Migration sequencing summary

| Phase    | Migration step                                                                                                 |
| -------- | -------------------------------------------------------------------------------------------------------------- |
| **1.2**  | Capabilities Protocols shipped (this sub-phase + 1.2).                                                         |
| **1.2b** | (this document) — inventory + sequencing.                                                                      |
| **1.5**  | `Notifier` + `HealthChecker` move out of `_base.py` (separate domain, unrelated to metadata).                  |
| **3**    | `OMDbAdapter` becomes internal ; `IMDbClient` and `RottenTomatoesClient` façades compose capabilities.         |
| **5**    | `TVDbClient`, `TMDbClient`, `TraktClient` declare explicit capability composition + method renames.            |
| **5**    | `tests/integration/conftest.py:474` docstring rewording.                                                       |
| **5/15** | Once every client composes capabilities, deprecate `MetadataProvider` Protocol in `_base.py` (warning import). |
| **15**   | If no orphan import remains, delete `MetadataProvider` Protocol from `_base.py`.                               |

## Acceptance — phase 1 only

This sub-phase is documentation only. The only file touched is this
document. No production import is rewritten, no client is refactored,
no test is changed. Subsequent phases own the actual migration steps
listed above.
