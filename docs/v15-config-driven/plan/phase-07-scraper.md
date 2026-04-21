# Phase 7 — Scraper refactor : classifier + TMDB keywords + NFO

## Objectif

Remplacer l'utilisation de `genre_mapper.GenreMapper` dans le scraper par `classifier.classify()`, ajouter le fetch TMDB `/keywords` avec cache, écrire `<category source="personalscraper">` dans les NFOs, supprimer `genre_mapper.py`.

## Sous-phases

### 7.1 — TMDB keywords cache : module + interface

- [ ] Créer `personalscraper/scraper/keywords_cache.py` avec :
  - `class KeywordsCache(data_dir: Path)` avec backing `data_dir/tmdb_keywords_cache.json`
  - `get(tmdb_id: int, media_type: Literal["movie", "tv"]) -> list[str] | None` (None = miss ou expired)
  - `set(tmdb_id, media_type, keywords: list[str]) -> None`
  - TTL 30 jours (`datetime.now() - cached_at > timedelta(days=30)` → miss)
  - Écriture atomique via `tempfile.NamedTemporaryFile` + `os.replace`
- [ ] Tests : hit, miss, expired, concurrent write safety

**Commit** : `v15.7.1: Add KeywordsCache with 30-day TTL and atomic writes`

### 7.2 — TMDB client : fetch `/keywords` endpoint

- [ ] Modifier `personalscraper/scraper/tmdb_client.py` :
  - Nouvelle méthode `get_keywords(tmdb_id: int, media_type: Literal["movie", "tv"]) -> list[str]`
  - Endpoint : `GET /movie/{id}/keywords` ou `GET /tv/{id}/keywords`
  - Fail-soft : 404 → `[]` ; API down (timeout/5xx après retries) → `[]` + warn
- [ ] Tests avec mock HTTP : success, 404, 500, timeout

**Commit** : `v15.7.2: Add TMDB /keywords endpoint with fail-soft on errors`

### 7.3 — Scraper : branchement `classify()` avant NFO write

- [ ] Modifier `personalscraper/scraper/scraper.py` :
  - Instance `KeywordsCache(config.paths.data_dir)` passed at init
  - Dans le flow scrape, pour chaque item après fetch TMDB/TVDB :
    - Déterminer si des `category_rules` utilisent `tmdb_keyword` (scan `config.category_rules`) → si oui, fetch keywords (via cache then API)
    - Appeler `classifier.classify(config, media_type=..., path=..., title=..., tmdb_genres=..., tmdb_genre_ids=..., tvdb_genre_ids=..., tmdb_keywords=..., origin_country=..., nfo_path=item_nfo_path_if_exists)`
    - Capturer `(category_id, reason)` → passer à NFO writer + dispatch
  - Si `category_id is None` → skip + append to `skip_report` (V14 error reporting style)
- [ ] Tests scraper : classification appelée avec bons args, skip_report généré correctement

**Commit** : `v15.7.3: Scraper calls classifier.classify with keywords fetch per category_rules`

### 7.4 — NFO generator : écrit `<category source="personalscraper">`

- [ ] Modifier `personalscraper/scraper/nfo_generator.py` :
  - Accepte `category_id: str` en paramètre
  - Insère `<category source="personalscraper">{category_id}</category>` dans l'XML généré (après `<genre>` elements pour lisibilité)
  - Si le NFO existait déjà avec un `<category source="personalscraper">` : remplacer (idempotent)
- [ ] Tests : write new NFO, overwrite existing, preserve other elements, `source` attribute présent

**Commit** : `v15.7.4: nfo_generator writes category element with source attribute`

### 7.5 — Suppression de `genre_mapper.py`

- [ ] **Vérifier** : test equivalence V14↔V15 (P2.6) passe toujours
- [ ] **Vérifier** : tests scraper + dispatch passent avec le nouveau pipeline
- [ ] **Vérifier** : grep confirme aucun import de `genre_mapper.GenreMapper` ou `KNOWN_CATEGORIES` dans le code prod (hors migration.py qui importe via une copie inline)
- [ ] Supprimer `personalscraper/genre_mapper.py`
- [ ] Supprimer `tests/test_genre_mapper.py` si existe (devenu obsolète — équivalence couverte par golden)
- [ ] Grep final : `grep -r "genre_mapper" personalscraper/ tests/` → 0 occurrence

**Commit** : `v15.7.5: Delete genre_mapper.py (replaced by classifier with equivalence proof)`

## Tests de cohérence P7→P8

- [ ] `tests/scraper/test_scraper.py` : tous passent avec config fixture
- [ ] `tests/scraper/test_keywords_cache.py` : 5 cas (hit/miss/expired/404/API-down)
- [ ] `tests/scraper/test_nfo_generator.py` : `<category source="personalscraper">` présent
- [ ] Test equivalence V14↔V15 passe toujours (pas de régression)
- [ ] `grep -r "KNOWN_CATEGORIES\|GenreMapper\|genre_mapper" personalscraper/` → 0
- [ ] `grep -r '"films"\|"series"' personalscraper/scraper/` → 0 (hors tests de migration inline)
- [ ] mypy strict : 0 erreur sur `scraper/*`
