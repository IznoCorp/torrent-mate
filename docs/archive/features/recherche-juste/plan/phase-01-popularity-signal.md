# Phase 1 — Porter le signal de popularité sur `SearchResult`

**Cause visée** : RC4 (prérequis). Sans ce portage, aucun classement par pertinence n'est possible.
**DESIGN** : §4.

## Gate

```bash
make lint
make test
git diff --name-only origin/main...HEAD -- \
  personalscraper/scraper/_match_score.py personalscraper/scraper/_match_movie.py \
  personalscraper/scraper/_match_tv.py personalscraper/scraper/movie_service.py   # VIDE
command python -m pytest tests/unit/test_tmdb_parsers.py tests/unit/test_tmdb_parsers_branches.py \
  tests/unit/test_api_metadata_base.py tests/unit/test_tvdb_parsers.py -q | tail -2
```

Attendu : lint 0 erreur, suite complète verte, diff scrape vide, tests parsers verts.

## Le problème, prouvé

`personalscraper/api/metadata/_tmdb_parsers.py::parse_search_result` construit un `SearchResult`
sans `popularity`, `vote_average` ni `vote_count` — alors que le payload TMDB les porte sur
**chaque** item (vérifié en live : `Spider-Man : Brand New Day` → `popularity: 1990.6295`,
`vote_count: 946`). `SearchResult` (`personalscraper/api/metadata/_base.py:25`) n'a aucun champ
pour les recevoir.

TVDB `/search` ne renvoie **pas** de champ de popularité (clés du payload vérifiées) : `None`
y est la valeur honnête. Le moteur de la phase 2 doit se comporter correctement quand tout le
lot est à `None`.

## Sous-phases

### 1.1 — Test rouge : le parser perd la popularité

Dans `tests/unit/test_tmdb_parsers.py`, ajouter un test qui construit un item TMDB réaliste
(copié d'un payload capturé, avec `popularity` et `vote_count`) et assert que le `SearchResult`
produit les expose. Le test doit être **rouge** avant 1.2.

Ajouter le pendant TVDB dans `tests/unit/test_tvdb_parsers.py` : un item TVDB sans champ de
popularité produit `popularity is None` et `vote_count is None` — l'absence est explicite,
jamais un `0.0` qui mentirait sur un média inconnu.

### 1.2 — Étendre `SearchResult`

`personalscraper/api/metadata/_base.py` :

```python
popularity: float | None = None
vote_count: int | None = None
```

Défauts `None` **obligatoires** : le chemin de scrape ne lit pas ces champs et son comportement
doit rester identique au bit près. Documenter les deux attributs dans la docstring de la classe
(Google-style, comme les champs existants), en indiquant que la sémantique diffère par provider
et que TVDB ne les fournit pas en recherche.

### 1.3 — Peupler dans le parser TMDB

`_tmdb_parsers.parse_search_result` : lire `raw.get("popularity")` et `raw.get("vote_count")`,
en coercition défensive (un champ absent ou non numérique donne `None`, jamais une exception —
le parser est sur le chemin du scrape, il ne doit pas devenir une source de panne).

### 1.4 — Vérifier la neutralité sur le chemin de scrape

Ajouter un test qui prouve que `_score_result` produit **exactement** le même score avec et sans
les nouveaux champs peuplés. C'est la preuve exécutable de l'invariant 1 du DESIGN, pas une
intention.

## Fichiers

| Fichier | Nature |
| --- | --- |
| `personalscraper/api/metadata/_base.py` | +2 champs sur `SearchResult` + docstring |
| `personalscraper/api/metadata/_tmdb_parsers.py` | peuplement défensif |
| `tests/unit/test_tmdb_parsers.py` | test rouge → vert |
| `tests/unit/test_tvdb_parsers.py` | absence explicite côté TVDB |
| `tests/scraper/test_confidence.py` | neutralité du score de scrape |

## Ce que cette phase ne fait pas

Elle ne consomme pas la popularité. Aucun classement ne change à l'issue de la phase 1 — c'est
volontaire : le portage est isolé pour que sa neutralité soit prouvable seule.
