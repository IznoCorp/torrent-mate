# DESIGN — `recherche-juste` : la recherche des Acquisitions trouve ce qu'on lui demande

**Type**: fix · **Bump**: 0.84.0 → 0.85.0 (minor — nouveau moteur de ranking + pagination API + champs provider)
**Branche**: `fix/recherche-juste`
**Ticket**: KanbanMate #409
**Constitution servie**: §5 (Acquisitions — « une recherche **trouve** un média »), §12 (mobile first),
§13 (l'interface reflète l'état réel des données), §8 (rien en silence), DOIT-1.

Source du diagnostic : `docs/analysis/2026-08-05-acquisition-search-relevance-diagnosis.md`.
Le diagnostic n'est **pas refait ici** — causes racines RC1→RC6 prouvées par exécution live,
prototype de ranking validé. Ce document fixe le mécanisme du correctif.

---

## 1. Le défaut, en une phrase

`GET /api/acquisition/search` réutilise les matchers de **scrape**
(`match_movie_detailed` / `match_tvshow_detailed`), qui répondent à « ce dossier de release
EST-IL ce média ? » — une décision d'identité calibrée contre les faux positifs. Une recherche
interactive pose la question inverse : « quels médias ressemblent à ce mot-clé ? ». Chaque
garde-fou qui rend le matcher correct en scrape rend la recherche fausse.

Preuves (exécution live 2026-08-05, providers interrogés en vrai) :

| Requête | Le provider renvoie la cible en | L'API sert |
| --- | --- | --- |
| `spiderman` | **#1/81** — `Spider-Man : Brand New Day` (2026), popularité 1990 | score **0.000**, rang 19/81 → invisible |
| `monarch` | **#3/50** TVDB — `Monarch: Legacy of Monsters` (2023) | score **0.000**, rang 27/50 → invisible |

La couche provider est saine. C'est notre re-classement qui détruit le résultat.

**Violation constitutionnelle** : §5 énonce « une recherche **trouve** un média (film ou série)
et l'ajoute à la liste de suivi ». Aujourd'hui elle ne le trouve pas. C'est l'implémentation
qui est fausse, pas le §.

---

## 2. Invariants non négociables (gelés)

1. **Le chemin de scrape ne bouge pas.** `_match_score.py`, `_match_movie.py`, `_match_tv.py`,
   `scraper/movie_service.py` restent **strictement inchangés**. Toute modification de ces
   fichiers est un échec de conception, pas un raccourci. Zéro régression sur l'identification
   automatique du pipeline.
2. **TVDB reste canonique pour les séries dans le scrape.** L'union TVDB ∪ TMDB décrite en §5
   ne concerne **que** les surfaces de recherche interactive. L'invariant du pipeline est intact.
3. **L'id de suivi reste l'id TVDB** pour une série, même quand la ligne a été remontée par TMDB
   (§5 constitution : identité conservée, provider-ID choisi à l'ajout).
4. **La page ne scrolle jamais latéralement** (§12). Le carrousel scrolle dans **son** conteneur ;
   `document.body.scrollWidth === clientWidth` à 390 px reste vrai, prouvé.
5. **Rien en silence** (§8). Une recherche qui ne trouve rien le dit ; une erreur provider remonte
   bruyamment. Aucun résultat n'est écarté sans que le total le reflète.
6. **Les pondérations du score sont calibrées, pas devinées.** Aucune valeur n'est figée sans le
   jeu golden qui la justifie.

---

## 3. Le nouveau moteur — `personalscraper/scraper/search_ranking.py`

Module neuf, sans dépendance vers les matchers de scrape. Contrat public :

```python
def rank_search_results(
    query: str,
    results: list[SearchResult],
    *,
    kind: str,          # "movie" | "tv" — tag porté sur la sortie
    now_year: int,      # injecté (jamais time.time() implicite — testabilité)
) -> list[RankedResult]
```

### 3.1 Ce qui disparaît par rapport au matcher de scrape

- **Pas de `_length_ratio_guard`.** C'est RC1 : il ne pénalise pas la cible, il la **saute**,
  score 0.000. Une requête courte face à un titre long est le cas NORMAL d'une recherche.
- **Pas de `_superstring_penalty`.** C'est RC2 : en recherche, l'opérateur tape un préfixe
  **pour** trouver l'extension. Rétrograder l'extension est l'inverse de l'intention.

### 3.2 Ce qui les remplace

Similarité de titre = meilleur score sur `{title, original_title, *aliases}`, avec un **bonus
positif** au lieu d'un garde-fou :

| Signal | Bonus |
| --- | --- |
| le titre normalisé commence par la requête normalisée | +0.15 |
| les tokens de la requête sont un sous-ensemble des tokens du titre | +0.12 |
| idem en ignorant les espaces (`spiderman` → `spider man`) | +0.15 |

Score composite, valeurs **de départ à calibrer** (§6) :

```
score = 0.55 × similarité_titre
      + 0.30 × popularité_normalisée      # log1p(pop) / log1p(max_pop) sur le lot
      + 0.10 × récence                    # 1 - (now_year - year)/40, borné [0,1]
      + 0.05 × titre_exact
```

La normalisation logarithmique est délibérée : les popularités TMDB s'étalent sur trois ordres
de grandeur (1990 vs 0.3), une normalisation linéaire écraserait tout sauf le blockbuster.

Réutilise `media_processor` (`personalscraper/text_utils.py`) pour la normalisation —
lowercase + dépouillement des accents, déjà éprouvé. Ne pas réécrire.

---

## 4. Prérequis — porter le signal de popularité

`SearchResult` (`personalscraper/api/metadata/_base.py`) n'a **aucun** champ de popularité, et
`parse_search_result` (`_tmdb_parsers.py`) **jette** `popularity`, `vote_average`, `vote_count`
que TMDB renvoie sur chaque item. Sans ce portage, RC4 est intraitable.

- Ajouter `popularity: float | None = None` et `vote_count: int | None = None` à `SearchResult`.
- Les peupler dans `_tmdb_parsers.parse_search_result`.
- **Défauts neutres obligatoires** : le chemin de scrape ne lit pas ces champs, son comportement
  doit rester identique au bit près (invariant 1).
- TVDB ne fournit **pas** de popularité dans `/search` (payload vérifié) — `None` y est la
  valeur honnête, et le ranking doit se comporter correctement quand tout le lot est à `None`
  (popularité neutre, la similarité et la récence décident).

---

## 5. La recherche TV — union au lieu d'exclusion

RC5 : `match_tvshow_detailed` retourne dès que TVDB renvoie **quoi que ce soit**, et
`match_tvshow_tvdb_detailed` prend `scored[0]` sans seuil. Un seul déchet TVDB à 0.0 bloque donc
TMDB — alors que TMDB classait la cible #1.

Pour les surfaces de recherche **uniquement** :

1. Interroger TVDB **et** TMDB TV.
2. Dédupliquer via `remote_ids` de l'item TVDB, qui porte déjà l'id TMDB (vérifié :
   `Monarch: Legacy of Monsters` → `TheMovieDB.com: 202411`). **Aucun appel API supplémentaire.**
3. Fusionner : ligne TVDB conservée comme identité (invariant 3), popularité TMDB utilisée pour
   le classement.
4. Repli honnête : si `remote_ids` est absent, dédupliquer sur `(titre normalisé, année)` et,
   à défaut, garder les deux lignes plutôt que d'en perdre une.

---

## 6. Calibrage — le jeu golden est la condition de merge

Les pondérations du §3.2 sont un **point de départ**, pas un acquis. Un jeu de requêtes réelles,
avec la cible attendue, sert de garde-fou exécutable :

| Requête | Cible attendue | Contrainte |
| --- | --- | --- |
| `monarch` | `Monarch: Legacy of Monsters` (2023) | top 3 |
| `spiderman` | `Spider-Man: Brand New Day` (2026) | top 3 |
| `spider man` | idem | top 3 |
| `matrix` | `Matrix` (1999) | top 3 |
| `top chef` | famille `Top Chef` | top 3 |
| un titre localisé FR | la cible FR | top 5 |
| un titre en script non-latin | la cible | top 5 |

Les fixtures sont des **payloads provider capturés** (pas de mock inventé) — un test qui
n'exerce pas de vraies formes de données ne prouve rien. Les deux dernières lignes sont à
instancier sur des titres réellement présents chez les providers ; un titre inventé invaliderait
le test.

---

## 7. API — pagination

`MediaSearchResponse` (`personalscraper/web/models/acquisition.py`) ne porte que `results` :
ni total, ni offset. La pagination est donc impossible côté client.

- Réponse : `results`, `total`, `offset`, `limit`.
- Route `GET /api/acquisition/search` : paramètres `offset` (défaut 0) et `limit` (défaut 20,
  borné). RC3 disparaît : le `limit=5` en dur par chaîne n'a plus cours.
- TMDB fournit déjà jusqu'à 100 résultats (`max_pages=5`) — le rappel existe, il suffisait de
  ne plus le jeter.
- **`total` est le nombre réel de candidats classés**, pas la taille de la page. §8 : ne jamais
  laisser croire qu'on a tout vu.

⚠ **Portes CI** : tout changement de route ou de `response_model` impose `make openapi` **et**
le commit de `openapi.json` + `frontend/src/api/schema.d.ts`. Sans ça la CI casse sur le drift
guard.

---

## 8. Les deux surfaces

RC6 : `personalscraper/web/decisions/search.py` (deck de résolution) appelle les mêmes matchers
et souffre du même défaut. Le nouveau moteur sert **les deux** :

| Surface | Fichier | Différence |
| --- | --- | --- |
| Ajout par recherche (Acquisitions) | `personalscraper/web/acquisition/service.py` | requête libre, pagination |
| Deck de résolution | `personalscraper/web/decisions/search.py` | titre + année connus, pas de pagination |

Le deck fournit souvent une **année** : le ranking doit s'en servir (accord d'année = signal
fort) sans réintroduire les garde-fous du scrape.

---

## 9. UI — mobile first (§12)

`frontend/src/components/acquisition/MediaSearchAdd.tsx` affiche aujourd'hui une grille figée
`grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`, sans compteur ni pagination.

- **Rangée horizontale à défilement par accroche** (`snap-x snap-mandatory`), scrollable au doigt
  sur téléphone.
- **Flèches ← → à partir de `sm`**, masquées sur mobile (le pouce suffit ; une flèche y volerait
  de la largeur, §12 « la largeur est la ressource rare »).
- **Compteur de résultats** visible (« 81 résultats ») — l'opérateur doit savoir qu'il y a une
  suite (§8).
- **Page suivante chargée à l'approche du bord**, sans bouton à viser.
- **Le conteneur scrolle, jamais la page** (invariant 4). C'est la lecture retenue du §12 :
  la règle « sans scroll horizontal » vise le **débordement accidentel** d'une surface hors du
  viewport, pas une interaction latérale délibérée et bornée. Cette lecture est **prouvée** par
  ACC-05, pas postulée.
- `MediaCard` (`frontend/src/components/ds/MediaCard`) est réutilisé tel quel — la composition
  de carte est une règle gravée (§12), on n'y touche pas.

---

## 10. Découpage en phases

| # | Phase | Défaut visé |
| --- | --- | --- |
| 1 | Porter `popularity` / `vote_count` sur `SearchResult` + parsers, défauts neutres | RC4 (prérequis) |
| 2 | `search_ranking.py` + jeu golden — test-first, la cible remonte | RC1, RC2, RC4 |
| 3 | Union TVDB ∪ TMDB pour la recherche TV, dédup `remote_ids` | RC5 |
| 4 | Pagination API + branchement des deux surfaces + `make openapi` | RC3, RC6 |
| 5 | UI carrousel mobile-first + preuve 390 px | §12 |
| 6 | Portes, PR, CI, merge, déploiement, vérification réelle | — |

L'ordre porte du sens : le signal de popularité doit exister avant le moteur qui le consomme ;
le moteur doit être prouvé avant d'être branché sur deux surfaces ; l'UI vient après une API
qui pagine réellement.

---

## 11. ACCEPTANCE (critères exécutables — format SH-16)

Chaque critère est une commande, avec sa sortie attendue. Aucun critère en prose.

**ACC-01 — le chemin de scrape est intact (invariant 1)**
```bash
git diff --name-only origin/main...HEAD -- \
  personalscraper/scraper/_match_score.py \
  personalscraper/scraper/_match_movie.py \
  personalscraper/scraper/_match_tv.py \
  personalscraper/scraper/movie_service.py
```
Attendu : **sortie vide**.

**ACC-02 — le jeu golden passe**
```bash
command python -m pytest tests/ -k "search_ranking or golden_search" -q | tail -3
```
Attendu : `N passed`, 0 failed.

**ACC-03 — les deux cas signalés remontent en tête, sur données live**
```bash
curl --connect-timeout 10 --max-time 30 -s \
  "https://tm-staging.iznogoudatall.xyz/api/acquisition/search?q=monarch&kind=tv&limit=5" \
  | jq -r '.results[0].title, .total'
curl --connect-timeout 10 --max-time 30 -s \
  "https://tm-staging.iznogoudatall.xyz/api/acquisition/search?q=spiderman&kind=movie&limit=5" \
  | jq -r '.results[0].title, .total'
```
Attendu : `Monarch: Legacy of Monsters` puis un total > 5 ; `Spider-Man : Brand New Day` puis un
total > 5. (Endpoint authentifié — exécuter avec le cookie de session, cf. `docs/reference/web-ui.md`.)

**ACC-04 — la pagination sert des lots distincts**
```bash
# offset=0 et offset=20 ne partagent aucun provider_id
```
Attendu : intersection vide, et `total` identique entre les deux appels.

**ACC-05 — la page ne déborde pas à 390 px (§12, invariant 4)**
```bash
# harnais iframe 390 px (docs/reference/web-ui.md) sur /acquisitions, recherche "spiderman"
# mesure : document.body.scrollWidth vs clientWidth
```
Attendu : `scrollWidth === clientWidth` ; le conteneur du carrousel, lui, a `scrollWidth > clientWidth`
(c'est la preuve que le défilement est **borné au conteneur**).

**ACC-06 — les portes locales sont vertes**
```bash
make check
```
Attendu : lint 0 erreur, tests `NNNN passed` 0 failed/error, module-size OK.

**ACC-07 — pas de dérive OpenAPI**
```bash
make openapi && git diff --exit-code openapi.json frontend/src/api/schema.d.ts
```
Attendu : exit 0 (fichiers régénérés déjà commités).

**ACC-08 — le deck de résolution utilise le même moteur (RC6)**
```bash
rg -n "search_ranking" --type py personalscraper/web/decisions/search.py personalscraper/web/acquisition/service.py
```
Attendu : au moins une occurrence dans **chacun** des deux fichiers.

---

## 12. Hors périmètre (explicite)

- **L'identification automatique du scrape** — RC1/RC2 y sont des comportements **corrects**.
  Le ticket #149 « Name-keyed matching (triage) » traite ce terrain, séparément.
- **L'archivage des 7 autres codenames non archivés** de `docs/features/` — signalé à
  l'opérateur, laissé à son arbitrage.
- **Le portage de popularité vers TVDB** via `/series/{id}` : coûterait N appels par recherche.
  TMDB suffit, l'union du §5 le rend disponible pour les séries.
