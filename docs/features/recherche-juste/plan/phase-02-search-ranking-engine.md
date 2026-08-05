# Phase 2 — Le moteur de ranking + le jeu golden (test-first)

**Causes visées** : RC1, RC2, RC4 (usage).
**DESIGN** : §3, §6.

## Gate

```bash
make lint
make test
command python -m pytest tests/scraper/test_search_ranking.py -q | tail -2
git diff --name-only origin/main...HEAD -- \
  personalscraper/scraper/_match_score.py personalscraper/scraper/_match_movie.py \
  personalscraper/scraper/_match_tv.py personalscraper/scraper/movie_service.py   # VIDE
```

Attendu : le jeu golden passe (ACC-02), suite complète verte, diff scrape vide.

## L'ordre est imposé : les tests d'abord

Le jeu golden **précède** le moteur. Écrit après, il serait taillé sur le comportement obtenu
et ne prouverait rien. Écrit avant, il définit ce que « pertinent » veut dire, et le calibrage
des pondérations devient une opération mesurable au lieu d'un réglage à l'oreille.

## Sous-phases

### 2.1 — Capturer les fixtures provider

Créer `tests/fixtures/search/` avec les payloads **réels** capturés pour chaque requête du jeu
golden (TMDB `/search/movie`, TMDB `/search/tv`, TVDB `/search`). Un script de capture court,
lancé une fois, avec la sortie commitée — pas d'appel réseau dans les tests.

Requêtes à capturer : `monarch`, `spiderman`, `spider man`, `matrix`, `top chef`, plus un titre
localisé FR et un titre en script non-latin. Ces deux derniers sont à choisir sur des médias
réellement présents chez les providers — un titre inventé invaliderait le test (règle : la
preuve est un déroulé, pas une intention).

### 2.2 — Le jeu golden, rouge

`tests/scraper/test_search_ranking.py` : pour chaque requête, la cible attendue doit figurer
dans les N premiers du classement (top 3 pour les cinq premières, top 5 pour les deux
dernières — DESIGN §6). Tous rouges à ce stade : le module n'existe pas encore.

Ajouter les deux tests de non-régression qui reproduisent le bug signalé :

- `monarch` → `Monarch: Legacy of Monsters` n'est **pas** à un score de 0.0 et n'est **pas**
  au-delà du rang 3.
- `spiderman` → `Spider-Man: Brand New Day` idem.

Et le test qui verrouille l'insensibilité à la ponctuation : `spiderman` et `spider man`
donnent le **même** rang pour la cible. C'est le symptôme le plus vicieux de RC1 — le résultat
dépendait du tiret tapé.

### 2.3 — `personalscraper/scraper/search_ranking.py`

Contrat public (DESIGN §3) :

```python
def rank_search_results(
    query: str,
    results: list[SearchResult],
    *,
    kind: str,        # "movie" | "tv"
    now_year: int,    # injecté — jamais d'horloge implicite
) -> list[RankedResult]
```

`now_year` est un paramètre, pas un appel à l'horloge : sans ça le composant de récence rend
les tests non déterministes et le jeu golden pourrira tout seul l'an prochain.

Aucun import depuis `_match_score`, `_match_movie`, `_match_tv`. Le module réutilise
`media_processor` (`personalscraper/text_utils.py`) pour la normalisation — lowercase +
dépouillement des accents, déjà éprouvé, à ne pas réécrire.

Similarité de titre : meilleur score sur `{title, original_title, *aliases}`, avec les bonus
positifs du DESIGN §3.2 (préfixe +0.15, sous-ensemble de tokens +0.12, préfixe sans espaces
+0.15). **Ni `_length_ratio_guard`, ni `_superstring_penalty`** — c'est tout le point.

Score composite du DESIGN §3.2, popularité normalisée en `log1p(pop) / log1p(max_pop)` sur le
lot. Le cas « tout le lot à `None` » (TVDB seul) doit donner un terme de popularité neutre et
non une division par zéro.

### 2.4 — Calibrer les pondérations

Les valeurs du DESIGN (`0.55 / 0.30 / 0.10 / 0.05`) sont un **point de départ**. Faire varier
et retenir le jeu qui satisfait le golden avec la marge la plus large. Consigner le tableau des
essais dans le corps de la PR : une pondération sans justification mesurée est un réglage à
l'oreille, pas une décision.

Si aucune pondération ne satisfait l'ensemble du golden, c'est la **formule** qu'il faut revoir,
pas le golden qu'il faut assouplir. Signaler à l'opérateur plutôt que de baisser la barre.

### 2.5 — Cas limites

Requête vide, requête d'un seul caractère, lot vide, titres identiques à années différentes,
candidat sans année, candidat sans popularité. Chacun a son test. Aucun ne doit lever.

## Fichiers

| Fichier | Nature |
| --- | --- |
| `personalscraper/scraper/search_ranking.py` | module neuf |
| `tests/scraper/test_search_ranking.py` | jeu golden + non-régression + cas limites |
| `tests/fixtures/search/` | payloads provider capturés |

## Ce que cette phase ne fait pas

Elle ne branche le moteur sur aucune surface. Le module est prouvé isolément avant d'être
utilisé — si le classement est faux, on le sait ici, pas à travers une régression d'API.
