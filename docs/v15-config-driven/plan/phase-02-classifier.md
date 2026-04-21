# Phase 2 — Classifier pipeline + équivalence V14↔V15

## Objectif

Implémenter `conf/classifier.py` avec les 6 niveaux de priorité et faire passer la golden table équivalence comme gate.

## Sous-phases

### 2.1 — Squelette `classifier.py` + `_read_nfo_category`

- [ ] Créer `personalscraper/conf/classifier.py` avec :
  - `import logging; logger = logging.getLogger(__name__)`
  - `MediaType = Literal["movie", "tv"]`
  - Signature `classify(config, *, media_type, path, title, tmdb_genres, tmdb_genre_ids, tvdb_genre_ids, tmdb_keywords, origin_country, nfo_path) -> tuple[str | None, str]`
  - `_read_nfo_category(nfo_path) -> str | None` avec priorité `source="personalscraper"` puis fallback bare element
- [ ] Tests unitaires NFO reader : element avec attribute, element sans attribute (legacy), multiple elements, NFO invalide, element vide

**Commit** : `v15.2.1: Add classifier.py skeleton with NFO category reader`

### 2.2 — Niveau 1 : NFO override

- [ ] Implémenter la priorité 1 dans `classify()` :
  - Si NFO existe et `<category>` valide ET ID connu → return `(cid, "nfo_override")`
  - Si NFO existe et `<category>` mais ID INCONNU → `logger.warning()` + fall through
- [ ] Tests : NFO valide, NFO avec ID obsolète (fall-through + warning), NFO absent

**Commit** : `v15.2.2: Implement NFO override as classification priority 1`

### 2.3 — Niveau 2 : `category_rules` avec `_rule_matches`

- [ ] Implémenter `_rule_matches(rule, *, path, title, tmdb_genres, tmdb_keywords) -> bool` :
  - `path_contains` : `in str(path)`
  - `path_regex` : `re.search`
  - `title_regex` : `re.search`
  - `tmdb_genre_contains` : case-insensitive substring any
  - `tmdb_keyword` : intersection any keyword
- [ ] Implémenter niveau 2 dans `classify()` : premier match gagne, return `(rule.category, "category_rules[i]")`
- [ ] Tests : chaque type de pattern, premier-match-gagne, multiple rules

**Commit** : `v15.2.3: Implement pattern-based category_rules as priority 2`

### 2.4 — Niveau 3 : `anime_rule`

- [ ] Implémenter niveau 3 :
  - Si `ar.enabled` et `ar.applies_to in (media_type, "both")`
  - Si `tmdb_genre_ids contains ar.requires_genre_id`
  - Si `origin_country intersects ar.requires_origin_country`
  - → return `(ar.maps_to, "anime_rule")`
- [ ] Tests : TV anime (JP), TV animation non-JP, disabled anime_rule, applies_to="movies"

**Commit** : `v15.2.4: Implement anime_rule as classification priority 3`

### 2.5 — Niveau 4-5 : `genre_mapping` + defaults

- [ ] Implémenter niveau 4 :
  - Movie : loop `tmdb_genre_ids`, first match in `genre_mapping.tmdb_movies` → return
  - TV : loop `tvdb_genre_ids` first (TVDB priority), then `tmdb_genre_ids`
- [ ] Implémenter niveau 5 :
  - Movie : return `(default_movies_category, "default_movies")`
  - TV : return `(default_tv_category, "default_tv")`
- [ ] Niveau 6 : return `(None, "no_match")` (unreachable en pratique, keep for safety)
- [ ] Tests : chaque priorité avec inputs contrôlés, transitions entre niveaux

**Commit** : `v15.2.5: Implement genre_mapping and defaults as classification priorities 4-5`

### 2.6 — Golden-table equivalence test : faire passer

- [ ] Retirer `@pytest.mark.skip` de `test_classifier_v14_vs_v15.py`
- [ ] Importer `V14_LABEL_TO_ID` depuis `conf/migration.py` (le créer minimal si besoin — juste le dict, le reste vient en Phase 4)
- [ ] Pour chaque cas du golden : invoke `classifier.classify(...)` avec les inputs sérialisés → assert result_id = `V14_LABEL_TO_ID[expected_v14_label]`
- [ ] Si des cas V14 ne matchent pas V15 → investiguer (bug V15 ou cas V14 edge non capturé dans DESIGN)
- [ ] Tous les 50+ cas passent → Phase 1 gate fermé

**Commit** : `v15.2.6: Enable equivalence suite — V15 classifier matches V14 behavior`

## Tests de cohérence P2→P3

- [ ] `tests/conf/test_classifier.py` : tests unitaires 6 niveaux passent
- [ ] `tests/equivalence/test_classifier_v14_vs_v15.py` : **passe** (gate fermé)
- [ ] `classifier.classify()` est pure (aucun side effect, aucun accès réseau)
- [ ] mypy strict : 0 erreur sur `conf/classifier.py`
- [ ] `logger` correctement utilisé pour warnings (NFO IDs obsolètes)
