# ACCEPTANCE — `recherche-juste` (déroulé exécuté 2026-08-05)

§méthode : aucun verdict « conforme » sans déroulé réel daté. Les critères qui exigent
des données live après déploiement sont **déclarés différés**, pas cochés d'avance.

## ACC-01 — le chemin de scrape est intact (invariant 1)
```
$ git diff --name-only origin/main...HEAD -- personalscraper/scraper/_match_score.py \
    personalscraper/scraper/_match_movie.py personalscraper/scraper/_match_tv.py \
    personalscraper/scraper/movie_service.py
(sortie vide)
```
**CONFORME.**

## ACC-02 — le jeu golden passe
```
$ python -m pytest tests/scraper/test_search_ranking.py -q
38 passed in 0.62s
```
**CONFORME.** Rang de la cible : `spiderman` #1, `spider man` #1, `monarch` (TMDB) #1,
`monarch` (union) #1, `matrix` #1, `top chef` #1, `les evades` #1, `기생충` #1, `進撃の巨人` #1.

## ACC-06 — les portes locales sont vertes
```
$ make check
10346 passed, 7 skipped, 1 xfailed, 872 warnings in 125.15s (0:02:05)
      Tests  1269 passed (1269)
exit=0
```
**CONFORME.**

## ACC-07 — pas de dérive OpenAPI
```
$ make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
exit=0 (aucune dérive)
```
**CONFORME.**

## ACC-08 — le deck de résolution utilise le même moteur (RC6)
```
$ rg -n "search_ranking" personalscraper/web/decisions/search.py personalscraper/web/acquisition/service.py
personalscraper/web/acquisition/service.py:3
personalscraper/web/decisions/search.py:2
```
**CONFORME** — occurrences dans **chacun** des deux fichiers.

## Vérification supplémentaire — les tests ne touchent plus le réseau

La CI a révélé que les tests du deck patchaient un matcher devenu inutilisé et tapaient donc
les **vrais** providers (verts en local grâce aux clés de la machine, 502 en CI). Corrigé en
patchant le seam client. Preuve :
```
$ TMDB_API_KEY=dummy TVDB_API_KEY=dummy make test
10483 passed, 7 skipped, 1 xfailed
```

## Différés — exigent le déploiement

- **ACC-03** — les deux requêtes signalées en tête, sur données live (staging puis prod).
- **ACC-04** — deux pages consécutives sans recouvrement, `total` identique.
- **ACC-05** — à 390 px : `body.scrollWidth === clientWidth` **et** `scrollWidth > clientWidth`
  sur le conteneur du carrousel (le défilement est borné à son conteneur).

Ces trois-là conditionnent le passage de la carte #409 en Done. « Mergé » n'est pas « vérifié ».
