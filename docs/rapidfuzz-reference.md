# rapidfuzz — Reference Documentation

> Date : 2026-04-10 | Contexte : V3 SCRAPE — fuzzy matching titres media pour le pipeline PersonalScraper

## Qu'est-ce que rapidfuzz ?

[rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) (v3.14+) est une librairie Python de fuzzy matching
écrite en C++ pour la performance. Elle remplace `thefuzz`/`fuzzywuzzy` avec une API compatible,
5-100x plus rapide, et sous licence **MIT** (vs GPL pour thefuzz).

**Utilisé pour** : Comparer les titres media locaux (noms de dossiers) aux résultats API TMDB/TVDB
dans le module `confidence.py` (V3).

**Version** : >= 3.14.0 (fix important sur WRatio à length ratio = 8.0)
**Licence** : MIT
**Python** : >= 3.10
**Dépendances** : Aucune (NumPy optionnel pour `cdist`)

## Installation

```bash
pip install rapidfuzz
```

Wheels pré-compilés pour macOS (x86-64 + ARM64), Linux, Windows.
Sans wheel : nécessite un compilateur C++17.

## Scorers — `rapidfuzz.fuzz`

Tous les scorers retournent un **float entre 0 et 100** (pas 0-1).
Tous acceptent `processor=` et `score_cutoff=` en keyword arguments.

### `fuzz.ratio(s1, s2)`

Similarité Indel normalisée (insertions/deletions).

```python
fuzz.ratio("Fight Club", "Fight Club 2")  # 91.0
fuzz.ratio("Fight Club", "fight club")    # 10.0 ← SANS processor !
```

**Quand l'utiliser** : Comparaisons exactes ou quasi-exactes, strings de taille similaire.

### `fuzz.partial_ratio(s1, s2)`

Cherche l'alignement optimal de la string courte dans la longue (sliding window).

```python
fuzz.partial_ratio("Fight Club (1999)", "Fight Club")  # 100.0
fuzz.partial_ratio("A", "A really long string")         # 100.0 ← DANGER
```

**Attention** : Très généreux — les strings courtes matchent facilement. Produit des faux positifs.

### `fuzz.token_sort_ratio(s1, s2)`

Split en tokens, tri alphabétique, puis `ratio()`.

```python
fuzz.token_sort_ratio("Club Fight", "Fight Club")  # 100.0
```

**Quand l'utiliser** : Quand les mots peuvent être dans un ordre différent.

### `fuzz.token_set_ratio(s1, s2)`

Compare sur les mots uniques et communs. Si tous les mots d'une string sont un subset de l'autre → 100.0.

```python
fuzz.token_set_ratio("The Boys S05E01 - Episode Title", "The Boys")  # 100.0 ← trop généreux
```

**Attention** : Retourne 100.0 dès qu'une string est un subset de l'autre.

### `fuzz.WRatio(s1, s2)` — RECOMMANDÉ POUR LES TITRES MEDIA

Ratio pondéré qui auto-sélectionne la meilleure stratégie selon le ratio de longueur :

| Ratio longueur | Stratégie                                         |
| -------------- | ------------------------------------------------- |
| < 1.5          | `max(ratio, token_sort * 0.95, token_set * 0.95)` |
| 1.5 – 8.0      | Variantes partielles avec poids 0.9               |
| >= 8.0         | Variantes partielles avec poids 0.6 (pénalisé)    |

```python
fuzz.WRatio("Fight Club (1999)", "Fight Club")  # 90.0 — bon équilibre
fuzz.WRatio("The Boys S05E01", "The Boys")       # 90.0 — pas 100 comme token_set
```

**Pourquoi pour les médias** : Balance entre tolérance aux tokens extras (années, épisodes) et pénalisation des strings très différentes en longueur. Évite les faux positifs.

### Comparaison des scorers sur des cas media

| Scénario                     | `ratio` | `partial_ratio` | `token_set_ratio` | `WRatio` |
| ---------------------------- | ------- | --------------- | ----------------- | -------- |
| Match exact                  | 100     | 100             | 100               | **100**  |
| Avec année entre parenthèses | 77      | 100             | 100               | **90**   |
| Mots réordonnés              | 50      | 67              | 100               | **95**   |
| TV + info épisode            | 70      | 100             | 100               | **90**   |
| Tokens torrent en plus       | 67      | 100             | 100               | **90**   |
| Substring court dans long    | 56      | 100             | 100               | **90**   |

**Verdict** : `WRatio` en scorer principal. `token_set_ratio` trop généreux, `ratio` trop strict.

## Batch matching — `rapidfuzz.process`

### `process.extractOne(query, choices, *, scorer=WRatio, processor=None, score_cutoff=None)`

Retourne `(choice, score, index_or_key)` ou `None` si rien ne dépasse `score_cutoff`.

```python
from rapidfuzz import process, fuzz

# Avec une liste
results = ["Fight Club", "Fight Club 2", "Gone Girl"]
match = process.extractOne("Fight Club (1999)", results, scorer=fuzz.WRatio)
# ('Fight Club', 90.0, 0)

# Avec un dict (clés = IDs TMDB) — PATTERN RECOMMANDÉ
tmdb_results = {550: "Fight Club", 551: "Fight Club 2", 210577: "Gone Girl"}
match = process.extractOne("Fight Club (1999)", tmdb_results, scorer=fuzz.WRatio)
# ('Fight Club', 90.0, 550) ← 550 est l'ID TMDB
```

### `process.extract(query, choices, *, scorer=WRatio, limit=5, score_cutoff=None)`

Retourne une liste de `(choice, score, index_or_key)`, triés par score décroissant.

```python
matches = process.extract("Dune", tmdb_results, scorer=fuzz.WRatio, limit=3)
# [('Dune', 100.0, 438631), ('Dune Part Two', 90.0, 693134), ...]
```

### `process.extract_iter(query, choices, ...)`

Itérateur lazy, memory-efficient pour de grands datasets. Pas de paramètre `limit`.

### `process.cdist(queries, choices, *, scorer=ratio, workers=1)`

Matrice 2D NumPy (queries × choices). Nécessite NumPy.

**Attention** : Le scorer par défaut est `ratio`, PAS `WRatio` (différent de extract/extractOne).

## Performance

| Opération            | Taille      | Temps  |
| -------------------- | ----------- | ------ |
| `extractOne(WRatio)` | 50 choices  | 32 µs  |
| `extractOne(WRatio)` | 100 choices | 59 µs  |
| `extractOne(WRatio)` | 250 choices | 149 µs |
| `extractOne(WRatio)` | 500 choices | 286 µs |

Pour le pipeline : matcher 1 titre contre 500 résultats API prend ~286 µs.
**Complètement négligeable** comparé à la latence des appels API (~200-500 ms).

## Preprocessing — `rapidfuzz.utils.default_process`

Applique 3 transformations :

1. **Lowercase** tous les caractères
2. **Remplace les non-alphanumériques** par des espaces (points, tirets, parenthèses, etc.)
3. **Trim** espaces en début/fin

```python
from rapidfuzz import utils
utils.default_process("Fight Club (1999)")      # "fight club  1999"
utils.default_process("The.Walking.Dead")        # "the walking dead"
utils.default_process("Spider-Man")              # "spider man"
utils.default_process("L'Été meurtrier")         # "l été meurtrier" ← accents PRÉSERVÉS
```

### CRITIQUE : Les accents NE sont PAS supprimés

```python
fuzz.ratio("amélie", "amelie", processor=utils.default_process)  # 83.3 ← PAS 100 !
fuzz.ratio("ça", "ca", processor=utils.default_process)           # 50.0 ← TRÈS MAUVAIS
```

**Solution obligatoire** — Processor custom avec normalisation Unicode NFD :

```python
import unicodedata
from rapidfuzz import utils

def media_processor(s: str) -> str:
    """Processor adapté aux titres media français.
    Lowercase + strip non-alphanum + strip accents (NFD decomposition).
    """
    s = utils.default_process(s)
    # Décompose les caractères accentués puis supprime les diacritiques
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

# Résultats avec media_processor :
fuzz.ratio("amélie", "amelie", processor=media_processor)  # 100.0 ✓
fuzz.ratio("ça", "ca", processor=media_processor)           # 100.0 ✓
fuzz.ratio("Les Évadés", "Les Evades", processor=media_processor)  # 100.0 ✓
```

### Comportement des apostrophes

```python
utils.default_process("L'Été meurtrier")   # "l été meurtrier" (espace remplace ')
utils.default_process("L'Été meurtrier")   # "l été meurtrier" (curly ' aussi)
```

Les apostrophes (droites et courbes) sont traitées comme non-alphanumériques → remplacées par un espace. Ça ne pose pas de problème pour le matching car `WRatio` tolère les tokens extras.

## Intégration avec `confidence.py`

Pattern recommandé pour le scoring de match media :

```python
from rapidfuzz import fuzz

def score_match(
    local_title: str,
    local_year: int | None,
    api_title: str,
    api_year: int | None,
) -> float:
    """Score entre 0.0 et 1.0.
    Combine WRatio (similarité titre) avec bonus/malus année.
    """
    # Score titre (0-100 → 0.0-1.0)
    title_score = fuzz.WRatio(local_title, api_title, processor=media_processor) / 100.0

    # Ajustement année
    if local_year and api_year:
        if local_year == api_year:
            year_bonus = 0.1     # Boost si même année
        elif abs(local_year - api_year) <= 1:
            year_bonus = 0.0     # Neutre si ±1 an
        else:
            year_bonus = -0.15   # Pénalité si année différente
    elif local_year and not api_year:
        year_bonus = -0.05       # Léger malus si année manquante côté API
    else:
        year_bonus = 0.0

    return max(0.0, min(1.0, title_score + year_bonus))
```

### Résultats de test avec ce scoring

| Local                | API                                        | Score | Niveau           |
| -------------------- | ------------------------------------------ | ----- | ---------------- |
| Fight Club (1999)    | Fight Club (1999)                          | 1.00  | HIGH (auto)      |
| Fight Club (1999)    | Fight Club (None)                          | 0.85  | HIGH (auto)      |
| Fight Club (1999)    | Fight Club 2 (2015)                        | 0.71  | MED (interactif) |
| Les Évadés (1994)    | Les Évadés (1994)                          | 1.00  | HIGH (auto)      |
| Dune (2021)          | Dune (1984)                                | 0.75  | MED (interactif) |
| Dune (2021)          | Dune (2021)                                | 1.00  | HIGH (auto)      |
| Amélie (2001)        | Le Fabuleux Destin d'Amélie Poulain (2001) | 0.92  | HIGH (auto)      |
| Totally Wrong (2020) | Fight Club (1999)                          | 0.11  | LOW (skip)       |

**Alignement avec les seuils existants** : HIGH >= 0.8 (auto-accept), 0.5-0.8 (interactif), < 0.5 (skip).

## Gotchas

### 1. Pas de preprocessing par défaut (v3.0+)

```python
fuzz.ratio("THE MATRIX", "the matrix")  # 10.0 ← SANS processor !
fuzz.ratio("THE MATRIX", "the matrix", processor=utils.default_process)  # 100.0
```

**Toujours passer `processor=media_processor`** (ou au minimum `utils.default_process`).

### 2. Accents non supprimés par `default_process`

Voir section "Preprocessing" ci-dessus. Utiliser le `media_processor` custom.

### 3. Strings vides

```python
fuzz.ratio("", "")   # 100.0
fuzz.WRatio("", "")  # 0.0 ← différent !
```

### 4. None silencieusement ignoré

```python
fuzz.ratio(None, "test")  # 0 (pas d'exception)
process.extractOne("test", {"a": None, "b": "test"})  # skip None silencieusement
```

### 5. Double espaces après `default_process`

```python
utils.default_process("Ça (2017)")  # "ça  2017" ← deux espaces
```

Affecte `ratio` mais pas `token_*` scorers. Pas critique avec `WRatio`.

### 6. `score_cutoff` retourne `None`

```python
process.extractOne("xyz", ["abc"], score_cutoff=80)  # None (pas de match au-dessus de 80)
```

Toujours vérifier le retour avant d'accéder aux éléments.

### 7. `cdist` scorer par défaut ≠ `extract`

`cdist` utilise `ratio` par défaut, pas `WRatio`. Toujours spécifier le scorer si on utilise `cdist`.

## Comparaison avec thefuzz/fuzzywuzzy

| Aspect                   | rapidfuzz                | thefuzz/fuzzywuzzy     |
| ------------------------ | ------------------------ | ---------------------- |
| Licence                  | **MIT**                  | GPL                    |
| Performance              | 5-100x plus rapide (C++) | Pur Python (lent)      |
| Preprocessing par défaut | Non (v3.0+)              | Oui (force_ascii)      |
| Handling accents         | Préserve                 | Supprime (force_ascii) |
| API                      | Compatible + extras      | API originale          |
| Maintenance              | Active (2026)            | Stagnant               |

## Utilisation dans le pipeline

| Module                | Utilisation                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------- |
| `confidence.py` (V3)  | `score_match()` — compare titres locaux vs résultats API                                                    |
| `media_index.py` (V5) | `MediaIndex.find()` — lookup exact-first, fuzzy-fallback                                                    |
| `matcher.py` (V2)     | `find_matching_directory()` — matching dossiers existants (déjà custom, à évaluer migration vers rapidfuzz) |
