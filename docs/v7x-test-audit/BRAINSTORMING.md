# V7.x — TEST AUDIT : Brainstorming

> Audit exhaustif des tests existants + golden files E2E pour valider l'exactitude des résultats de scrape et dispatch.

## Contexte

V7 a mis en place les tests E2E avec 3 tests pipeline (movie, tvshow, mixed CLI) et 2 tests roundtrip. Ces tests vérifient que le pipeline **ne plante pas** et **produit quelque chose**, mais pas que ce qu'il produit est **correct**.

### Problème identifié

Les assertions E2E actuelles sont des **smoke tests** :

| Assertion                    | Ce qu'elle vérifie                                 | Ce qu'elle NE vérifie PAS                         |
| ---------------------------- | -------------------------------------------------- | ------------------------------------------------- |
| `assert_scrape_complete()`   | Un `.nfo` existe + un poster existe                | Le contenu du NFO (TMDB ID, titre, année, genres) |
| `assert_verify_complete()`   | `status in {"valid", "fixed"}` + category not None | Que la catégorie est **correcte**                 |
| `assert_dispatch_complete()` | En dry-run → **rien vérifié**                      | Le disque cible, l'action (replace/merge/new)     |
| `assert_sort_complete()`     | Dossier existe dans 001-MOVIES ou 002-TVSHOWS      | Que c'est dans le **bon** répertoire              |

### Audit des tests unitaires

L'audit exhaustif des 729 tests a révélé :

**Couverture globale : 79%** — mais les modules orchestrateurs sont sous-couverts :

| Module                   | Couverture | Problème critique                                         |
| ------------------------ | ---------- | --------------------------------------------------------- |
| `ingest/ingest.py`       | 13%        | Orchestration V1 quasi non testée                         |
| `cli.py`                 | 22%        | CLI commands non testées, 1 test cassé (`test_sort_stub`) |
| `dispatch/dispatcher.py` | 48%        | Replace/merge/rsync — moitié non testée                   |
| `verify/verifier.py`     | 63%        | Cycle check→fix→recheck non testé                         |
| `scraper/scraper.py`     | 64%        | Orchestration process_movies/tvshows                      |
| `providers.py`           | 0%         | Protocol (6 lignes, acceptable)                           |

**Top 5 lacunes** identifiées par l'audit :

1. **Dispatch** — Aucun test pour rsync failure, transfert partiel, replace vs merge réel
2. **Confidence** — Pas de test pour réponses API malformées, conflits TMDB/TVDB
3. **Ingest orchestration** — 13% couverture, aucun test copy-if-seeding vs move-if-done
4. **Verifier cycle** — Le flux check→fix→recheck n'est pas testé end-to-end
5. **E2E assertions** — Vérifient la présence mais pas l'exactitude

**Test cassé** : `tests/test_cli.py::test_sort_stub` — AssertionError: assert 1 == 0 (exit code)

## Décisions prises

### D1 — Golden files hybrides (JSON + XML structurel)

Structure par torrent dans `assets/torrents/expected/` :

```
assets/torrents/expected/
├── jumanji_1995/
│   ├── expected_nfo.json          # Champs NFO invariants (titre, année, TMDB ID, genres)
│   ├── expected_artwork.json      # Fichiers artwork attendus (poster.jpg, fanart.jpg)
│   ├── expected_structure.json    # Arbre de fichiers attendu après scrape
│   └── expected_dispatch.json     # Disque cible, action, catégorie
└── malcolm_in_the_middle_s01/
    ├── expected_nfo.json          # tvshow.nfo + épisodes NFO champs
    ├── expected_artwork.json
    ├── expected_structure.json    # Saisons, épisodes S01E01-S01E16
    └── expected_dispatch.json
```

**Format hybride** :

- **JSON** pour les champs critiques invariants (TMDB ID, titre, année, genres, catégorie)
- **Vérification XML structurelle** pour les NFO (tags présents, pas le contenu exact des champs volatils comme synopsis ou vote_count)

**Raison** : Les APIs TMDB/TVDB peuvent changer leurs données (synopsis mis à jour, nouvelles images). Les golden files doivent vérifier les invariants sans casser sur les champs volatils.

### D2 — Dispatch : vérifier le DispatchResult

Vérifier le `DispatchResult` retourné par `run_dispatch(dry_run=True)` contre le golden file :

- `result.disk` → doit correspondre à un disque éligible
- `result.action` → "moved" (nouveau), "replaced" (film existant), "merged" (série existante)
- `result.destination` → contient la bonne catégorie dans le chemin

**Pas de faux disques** — on vérifie le résultat du dry-run, pas l'exécution réelle.

### D3 — Génération par exécution manuelle + validation humaine

1. Lancer le pipeline une fois sur chaque torrent (Jumanji + Malcolm)
2. Inspecter manuellement les résultats (NFO, artwork, catégorie, dispatch)
3. Valider et figer en golden files JSON

### D4 — Audit exhaustif + renforcement

Trois passes :

1. **Fix** — Corriger `test_sort_stub` cassé
2. **Renforcement ciblé** — Ajouter tests sur les 5 lacunes critiques identifiées
3. **Couverture** — Amener les modules orchestrateurs au-dessus de 70%

## Contraintes techniques

1. Les golden files sont des **fixtures statiques** — pas de dépendance réseau pour les lire
2. Les golden files doivent être **versionnés** (git) pour traçabilité
3. Les assertions golden file doivent être **rétrocompatibles** — les anciens tests continuent de fonctionner
4. Le format JSON doit être **extensible** — pouvoir ajouter des torrents sans changer le code d'assertion
5. La génération initiale des golden files nécessite **qBittorrent + API keys** — pas automatisable en CI

## Flux proposé

```
Phase 1: Fix test cassé + couverture critique
    └─ test_sort_stub fix
    └─ Tests dispatcher (replace/merge/rsync errors)
    └─ Tests ingest orchestration
    └─ Tests verifier cycle

Phase 2: Infrastructure golden files
    └─ Format JSON + schéma
    └─ Loader de golden files
    └─ Nouvelles fonctions d'assertion

Phase 3: Génération golden files (MANUELLE)
    └─ Exécuter pipeline sur Jumanji
    └─ Exécuter pipeline sur Malcolm S01
    └─ Inspecter et valider les résultats
    └─ Figer en JSON dans assets/torrents/expected/

Phase 4: Intégration E2E
    └─ Brancher golden files dans les 3 tests E2E
    └─ Assertion dispatch (DispatchResult vs golden)
    └─ Assertion episode structure (Malcolm S01)
```

## Points de design à trancher

Aucun — toutes les questions ont été tranchées lors du brainstorming.
