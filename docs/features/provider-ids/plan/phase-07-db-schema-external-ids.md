# Phase 7 — DB Schema : external_ids_json + ratings_json + canonical_provider

## Goal

Refondre le schéma `library.db` table `media_item` pour adopter `external_ids_json` (unique source de vérité IDs), `ratings_json` (notes), `canonical_provider` (enum). **Drop** des colonnes legacy `tvdb_id`, `tmdb_id`, `imdb_id`. Per mémoire `feedback_no_backcompat_before_v1` : **pas de script de migration generic** — la phase modifie le schéma ET applique le changement à la BDD réelle de l'unique instance dans le même PR.

## Gate (prerequisites)

- Phase 5 mergée (les nouveaux scrapes produisent déjà les IDs cross-ref).
- Phase 6 mergée (ratings collectés au scrape).

## Sub-phases

### 7.1 — `indexer/schema.py` : nouvelles colonnes + drop legacy

Modifier le schema definition :

- DROP colonnes `tvdb_id`, `tmdb_id`, `imdb_id` sur `media_item`.
- ADD `external_ids_json TEXT NOT NULL DEFAULT '{}'`.
- ADD `ratings_json TEXT NULL`.
- ADD `canonical_provider TEXT NULL CHECK(canonical_provider IN ('tvdb', 'tmdb'))`.
- CREATE INDEX sur les expressions JSON : `idx_external_ids_tvdb`, `idx_external_ids_tmdb`, `idx_external_ids_imdb`.

Commit : `feat(provider-ids): schema migration external_ids_json + ratings_json + canonical_provider`

### 7.2 — Script ad-hoc one-shot pour la BDD réelle

Script SQL `scripts/migrate_provider_ids_v0_15_0.sql` (one-shot, à supprimer après usage) qui :

- Crée les 3 nouvelles colonnes.
- COPY les valeurs existantes `tvdb_id`/`tmdb_id`/`imdb_id` vers `external_ids_json` (en construisant le JSON via SQLite `json_object`).
- DROP les 3 colonnes legacy.
- CREATE INDEX.

Exécuter sur la BDD réelle (`.data/library.db`). Commit le script puis sub-phase 7.6 le supprimera (memory `feedback_no_backcompat_before_v1` — pas de script générique persistant).

Commit : `chore(provider-ids): one-shot migration script for local library.db v0.15.0`

### 7.3 — `indexer/query.py` : `json_extract` pour les requêtes existantes

`personalscraper/indexer/query.py:113,302,557` : remplacer `media_item.tvdb_id` etc. par `json_extract(media_item.external_ids_json, '$.tvdb.series_id')` (et idem tmdb, imdb). FieldSpec adaptés. Tests existants doivent passer post-refactor.

Commit : `refactor(provider-ids): indexer/query uses json_extract on external_ids_json`

### 7.4 — Helper Pydantic models pour external_ids_json + ratings_json

Nouveau `indexer/models/external_ids.py` :

```python
class ExternalIds(BaseModel):
    tvdb: dict[str, str | None] = Field(default_factory=lambda: {"series_id": None, "episode_id": None})
    tmdb: dict[str, str | None] = ...
    imdb: dict[str, str | None] = ...

class Ratings(BaseModel):
    imdb: str | None = None
    rottentomatoes: str | None = None
    metacritic: str | None = None
    themoviedb: str | None = None
```

Sérialisation/désérialisation utilisée par `scanner.py`, `query.py`, `recommender.py`.

Commit : `feat(provider-ids): Pydantic models for external_ids_json + ratings_json`

### 7.5 — `indexer/scanner.py` write side

Adapter les writes via `external_ids_json` + `ratings_json`. Les scrapes phase 5+6 écrivent déjà ces formats — le scanner doit les persister.

Commit : `feat(provider-ids): indexer scanner writes via external_ids_json`

### 7.6 — Cleanup : supprimer le script one-shot

Une fois la BDD réelle migrée et tests verts → supprimer `scripts/migrate_provider_ids_v0_15_0.sql`. Pas conservé dans le repo (pas de retro-compat needed).

Commit : `chore(provider-ids): remove one-shot migration script after applying to local db`

## Tests to write

- `test_schema_external_ids_json_column_present_after_init`
- `test_schema_legacy_id_columns_dropped`
- `test_external_ids_pydantic_model_serializes_round_trip`
- `test_ratings_pydantic_model_serializes_round_trip`
- `test_query_by_tmdb_id_uses_json_extract_correctly`
- `test_field_spec_tmdb_id_returns_json_path`
- `test_existing_recommender_query_via_imdb_id_still_works_post_refactor` (integration)
- `test_scanner_persists_external_ids_json_on_new_item`

## Acceptance criteria

- Tests pass à 100% post-refactor (notamment `recommender.py`, `verify/checker.py` qui consomment ces données).
- `library.db` réelle de l'instance ne contient plus les colonnes legacy.
- `library-search` CLI et `library-report` fonctionnent inchangés côté usage.
- Aucune query qui SELECT/WHERE sur les anciennes colonnes ne reste dans le code (grep `--type py` retourne 0).

## Migration / config touch

**OBLIGATOIRE** (memory `feedback_no_backcompat_before_v1`) :

- Modif `.data/library.db` réelle de cette instance via le script 7.2 dans le même PR.
- Validation : `sqlite3 .data/library.db .schema media_item` doit montrer les nouvelles colonnes et plus les legacy.
- Le script one-shot supprimé en 7.6 — pas conservé.

## DESIGN reference

§6.5 (indexer/), §8 (Migration locale), §3 décision Q3.
