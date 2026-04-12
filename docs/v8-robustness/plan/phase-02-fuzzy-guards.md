# Phase 2 — Anti-faux-positifs Fuzzy Matching

## Objectif

Empêcher les faux positifs du fuzzy matching qui font que "Matrix" peut matcher "Matrix Reloaded" ou "Alien" matcher "Aliens". Trois garde-fous combinés : contrainte d'année, ratio de longueur, seuil adaptatif.

## Sous-phases

### 8.2.1 — Fonction partagée fuzzy_match_score

- [x] Ajouter `fuzzy_match_score()` dans `personalscraper/text_utils.py`
- [x] Paramètres : query, candidate, query_year, candidate_year
- [x] Garde 1 — Année : si les deux ont une année, `abs(diff) <= 1` sinon rejet (return None)
- [x] Garde 2 — Longueur : `len(shorter) / len(longer) >= 0.67` après processing, sinon rejet
- [x] Garde 3 — Seuil adaptatif : si `len(processed_query) <= 10` → seuil 95%, sinon → seuil 90%
- [x] Score : `fuzz.WRatio(query, candidate, processor=media_processor)` si ≥ seuil adaptatif
- [x] Écrire tests dans `tests/test_text_utils.py` :
  - "Matrix" vs "Matrix Reloaded" → None (length guard)
  - "Alien" vs "Aliens" → None (adaptive threshold, 5 chars → 95%)
  - "The Matrix (1999)" vs "The Matrix (1999)" → score élevé
  - "Jumanji (1995)" vs "Jumanji (1996)" → score (±1 an OK)
  - "Jumanji (1995)" vs "Jumanji (2017)" → None (year guard)
  - "Les Évadés" vs "Les Evades" → score (accents gérés par media_processor)

**Commit** : `v8.2.1: Add fuzzy_match_score with anti-false-positive guards`

### 8.2.2 — Intégrer dans MediaIndex.find()

- [x] Remplacer le fuzzy matching inline dans `media_index.py:find()` par `fuzzy_match_score()`
- [x] Extraire l'année du `name` et de chaque `entry.name` pour passer à `fuzzy_match_score()`
- [x] Mettre à jour `tests/dispatch/test_media_index.py` :
  - Ajouter test : "The Matrix" ne matche PAS "The Matrix Reloaded" dans l'index
  - Ajouter test : "Alien (1979)" ne matche PAS "Aliens (1986)" dans l'index
  - Ajouter test : "Jumanji (1995)" MATCHE "Jumanji (1995)" dans l'index
  - Vérifier que les 10 tests existants passent

**Commit** : `v8.2.2: Use fuzzy_match_score in MediaIndex.find()`

### 8.2.3 — Intégrer dans matcher.py

- [x] Modifier `find_matching_directory()` pour utiliser `fuzzy_match_score()`
- [x] Remplacer le year check strict (exact match) par ±1 an (via fuzzy_match_score)
- [x] Ajouter length guard et seuil adaptatif (via fuzzy_match_score)
- [x] Mettre à jour `tests/sorter/test_matcher.py` :
  - Ajouter test : titres courts rejetés sous 95%
  - Ajouter test : titres longs acceptés à 90%+
  - 3 tests existants adaptés aux nouveaux gardes (comportement V8 attendu)
  - 14 tests existants passent sans modification
- [x] 501 tests passent (modules avec deps installées)

**Commit** : `v8.2.3: Use fuzzy_match_score in find_matching_directory()`
