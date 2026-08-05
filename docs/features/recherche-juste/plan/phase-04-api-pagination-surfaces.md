# Phase 4 — Pagination API + branchement des deux surfaces

**Causes visées** : RC3, RC6.
**DESIGN** : §7, §8.

## Gate

```bash
make lint
make test
make openapi && git diff --exit-code openapi.json frontend/src/api/schema.d.ts   # ACC-07
rg -n "search_ranking" --type py \
  personalscraper/web/decisions/search.py personalscraper/web/acquisition/service.py   # ACC-08
cd frontend && npm run lint && npx tsc -b --noEmit && npm run test -- --run
```

Attendu : portes Python vertes, **zéro dérive OpenAPI**, le moteur référencé dans **chacun**
des deux fichiers, portes frontend vertes.

`tsc --noEmit` seul ne vérifie rien dans `frontend/` (le tsconfig racine est un solution file) —
c'est `tsc -b --noEmit` qu'il faut, comme en CI. Et la gate eslint est **séparée** du typecheck :
les deux doivent passer.

## Le problème, prouvé

`_results_to_candidates(..., limit=5)` (`_match_score.py:320`) plafonne à 5 par chaîne : 5 films
+ 5 séries = les 10 propositions constatées, et 5 quand un filtre de type est actif.
`MediaSearchResponse` (`personalscraper/web/models/acquisition.py:323`) ne porte que `results` —
ni total, ni offset : la pagination est impossible côté client.

Et `personalscraper/web/decisions/search.py:114-122` appelle les **mêmes** matchers de scrape :
le deck de résolution a strictement le même défaut (RC6).

## Sous-phases

### 4.1 — Modèles de réponse

`personalscraper/web/models/acquisition.py` :

- `MediaSearchResult` gagne les champs de classement utiles à l'affichage (année déjà présente ;
  exposer ce qui justifie le rang reste au périmètre de la phase 5 si l'UI en a besoin).
- `MediaSearchResponse` gagne `total`, `offset`, `limit`.

**`total` est le nombre réel de candidats classés**, pas la taille de la page servie. §8 : ne
jamais laisser croire qu'on a tout vu. Un test verrouille cette sémantique — c'est exactement le
genre d'invariant qu'une refonte ultérieure casse sans s'en rendre compte.

### 4.2 — Route

`personalscraper/web/routes/acquisition.py:758` : paramètres `offset` (défaut 0, ≥ 0) et `limit`
(défaut 20, borné haut). Les bornes sont **validées par Pydantic/Query**, pas par une lecture
optimiste : un `limit=100000` ne doit pas devenir un déni de service sur les providers.

La route reste typée (`response_model`) et derrière le `guarded_api` unique — ne jamais ajouter
de `Depends(require_session)` par route.

### 4.3 — Brancher `run_media_search`

`personalscraper/web/acquisition/service.py:317` : remplacer les appels à `match_movie_detailed`
et `match_tvshow_detailed` par le moteur de la phase 2 et l'union de la phase 3, puis trancher
la page demandée. Le contrôle d'appartenance à la médiathèque (`already_owned`, §5 de la
constitution) est conservé tel quel — il s'applique à la page servie.

TMDB fournit déjà jusqu'à 100 résultats (`max_pages=5`) : le rappel existe, il suffit d'arrêter
de le jeter.

### 4.4 — Brancher le deck de résolution (RC6)

`personalscraper/web/decisions/search.py::search_candidates` : même moteur. Différence utile —
le deck connaît souvent l'**année**, qui doit servir de signal fort au classement sans
réintroduire les garde-fous du scrape.

Vérifier les consommateurs avant d'écrire : `personalscraper/web/routes/decisions.py` et
`personalscraper/web/routes/staging.py:490` appellent `search_candidates`. Le type de retour
doit rester compatible, ou les deux appelants sont mis à jour dans la même phase — pas de
signature changée en laissant un appelant derrière.

### 4.5 — Régénérer le contrat

```bash
make openapi
git add -f openapi.json frontend/src/api/schema.d.ts
```

Sans ça, la CI casse sur le drift guard. Ce n'est pas optionnel et ce n'est pas un détail de
fin de phase : tout changement de route ou de `response_model` l'impose.

### 4.6 — Tests d'API

- La cible remonte en tête sur les deux requêtes signalées, via le vrai chemin de route.
- `offset=0` et `offset=20` ne partagent aucun `provider_id`, et `total` est identique entre
  les deux appels (ACC-04).
- `limit` hors bornes est rejeté proprement (422), pas silencieusement corrigé.
- Le deck de résolution classe correctement avec année connue.

Attention aux asserts vacués sous `TestClient` : le threadpool casse l'affinité SQLite. Vérifier
que chaque assert échoue bien si on casse volontairement le code (mutation check) avant de le
déclarer probant.

## Fichiers

| Fichier | Nature |
| --- | --- |
| `personalscraper/web/models/acquisition.py` | `total` / `offset` / `limit` |
| `personalscraper/web/routes/acquisition.py` | params de pagination |
| `personalscraper/web/acquisition/service.py` | branchement moteur + page |
| `personalscraper/web/decisions/search.py` | branchement moteur (RC6) |
| `openapi.json`, `frontend/src/api/schema.d.ts` | régénérés + commités |
| `tests/unit/web/routes/test_acquisition_read.py` | tests d'API |

## Ce que cette phase ne fait pas

Elle ne touche pas l'UI. À l'issue de la phase 4, l'API sert la bonne réponse paginée ; la
grille existante affichera simplement la première page — visiblement mieux qu'avant, pas encore
navigable.
