# Phase 3 — Recherche TV : union TVDB ∪ TMDB par `remote_ids`

**Cause visée** : RC5.
**DESIGN** : §5.

## Gate

```bash
make lint
make test
command python -m pytest tests/scraper/test_search_ranking.py -q | tail -2
git diff --name-only origin/main...HEAD -- \
  personalscraper/scraper/_match_tv.py personalscraper/scraper/movie_service.py   # VIDE
```

Attendu : golden TV vert **par l'union** (et non par un TVDB chanceux), diff scrape vide.

## Le problème, prouvé

`match_tvshow_detailed` (`personalscraper/scraper/_match_tv.py:418`) retourne dès que
`tvdb_match is not None`, et `match_tvshow_tvdb_detailed:214` fait `_, best_match = scored[0]`
**sans seuil**. Un seul résultat TVDB, même à 0.0, suffit donc à empêcher toute consultation de
TMDB. Or sur `monarch`, TMDB classait la cible **#1** (popularité 34.4, 1368 votes) là où TVDB
la mettait #3 sans aucun signal de popularité.

Ces deux fichiers **ne doivent pas être modifiés** (invariant 1). L'union se construit dans la
couche recherche, en appelant les deux clients directement.

## Sous-phases

### 3.1 — Test rouge : l'union ramène ce que TVDB seul n'a pas

Dans `tests/scraper/test_search_ranking.py`, un cas qui fournit un lot TVDB pauvre (la cible
présente mais sans popularité, noyée) **et** un lot TMDB où la cible est populaire, et qui
assert que la fusion la place en tête. Rouge avant 3.3.

### 3.2 — Test rouge : la dédup ne perd ni ne duplique

Trois cas, chacun avec son test :

- `remote_ids` porte l'id TMDB → **une seule** ligne en sortie, identité **TVDB** conservée.
- `remote_ids` absent, titre + année identiques → une seule ligne, identité TVDB.
- `remote_ids` absent, rien ne correspond → **les deux** lignes sortent. Perdre une ligne par
  excès de dédup est pire que d'en montrer deux : l'opérateur peut arbitrer ce qu'il voit, pas
  ce qui a disparu.

### 3.3 — Implémenter la fusion

Fonction de fusion dans `search_ranking.py` (ou un module frère si la taille l'impose — plafond
de 1000 LOC par module, `python3 scripts/check-module-size.py`).

Clé de fusion : `remote_ids` de l'item TVDB, qui porte déjà l'id TMDB. Vérifié en live :
`Monarch: Legacy of Monsters` (tvdb 422598) → `{'id': '202411', 'sourceName': 'TheMovieDB.com'}`.
**Aucun appel API supplémentaire** — c'est ce qui rend l'union gratuite.

Le parser TVDB doit exposer `remote_ids` sur `SearchResult` s'il ne le fait pas déjà
(`personalscraper/api/metadata/_tvdb_parsers.py` — à vérifier avant d'écrire : le champ existe
peut-être déjà sous une autre forme). Si un champ est ajouté, même discipline qu'en phase 1 :
défaut neutre, neutralité du chemin de scrape prouvée par test.

Règles de fusion :

- L'identité retenue est **TVDB** (provider + provider_id), invariant 3 du DESIGN et §5 de la
  constitution : le suivi d'une série garde son id TVDB pour le scraping.
- La popularité retenue est celle de **TMDB**, seule disponible.
- Une série que seul TMDB connaît sort avec l'identité TMDB — mieux vaut un suivi TMDB qu'un
  média invisible ; le `tvdb_unresolved` existant signalera l'inertie de détection.

### 3.4 — Fail-soft par provider

Si TVDB échoue, l'union sert TMDB seul, et inversement. Une recherche ne meurt pas parce qu'un
provider tousse. Mais l'échec **est journalisé** (§8, rien en silence) — pas avalé. Un test par
sens de panne.

## Fichiers

| Fichier | Nature |
| --- | --- |
| `personalscraper/scraper/search_ranking.py` | fusion + dédup |
| `personalscraper/api/metadata/_tvdb_parsers.py` | exposer `remote_ids` si absent |
| `personalscraper/api/metadata/_base.py` | champ `remote_ids` si nécessaire |
| `tests/scraper/test_search_ranking.py` | union, dédup ×3, fail-soft ×2 |
| `tests/unit/test_tvdb_parsers.py` | `remote_ids` parsé |

## Ce que cette phase ne fait pas

Elle ne touche pas au chemin de scrape TV. L'invariant « TVDB canonique » du pipeline reste
exactement ce qu'il était — l'union ne vit que dans la couche recherche.
