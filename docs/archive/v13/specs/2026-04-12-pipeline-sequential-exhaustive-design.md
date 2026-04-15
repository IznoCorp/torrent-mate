# Pipeline séquentiel exhaustif avec check de cohérence

**Date:** 2026-04-12
**Status:** Approved
**Scope:** Refactor `personalscraper run` pour garantir que le dispatch ne s'exécute que sur des items entièrement traités.

## Problème

Le pipeline actuel exécute les 5 steps linéairement (ingest→sort→scrape→verify→dispatch). Chaque step tourne une fois sur tout ce qui existe, puis on passe à la suivante. Conséquences :

1. Des fichiers ingérés et triés dans le même run arrivent dans 001-MOVIES/002-TVSHOWS mais ne sont pas toujours scrapés correctement (noms bruts non-reconnus, doublons non-fusionnés).
2. Le dispatch tourne même si des items sont "blocked" — il dispatch les items déjà clean et ignore les nouveaux, ce qui est correct techniquement mais confus pour l'utilisateur.
3. Des résidus persistent : dossiers vides après fusion, fichiers orphelins, doublons non-détectés.
4. Les tests E2E ne détectent pas ces problèmes car ils testent chaque step isolément.

## Solution

Pipeline séquentiel avec **gates** entre les phases et un **check de cohérence** obligatoire avant le dispatch. Chaque phase doit être 100% terminée avant la suivante.

## Architecture

```
personalscraper run [--interactive]

Phase 1: INGEST     complete/ ──→ 097-TEMP/
                    Tout copier/déplacer depuis qBittorrent

Phase 2: SORT       097-TEMP/ ──→ 001-MOVIES/, 002-TVSHOWS/...
                    Nettoyer noms + trier
                    GATE: assert 097-TEMP vide (sauf .gitkeep/.DS_Store)

Phase 3: PROCESS    001-MOVIES/, 002-TVSHOWS/
                    Pour chaque dossier:
                      a) Re-clean: renommer si nom brut détecté via guessit
                      b) Dedup: fusionner les doublons fuzzy
                      c) Scrape: NFO + artwork (skip si déjà fait)
                      d) Episode rename (séries uniquement)
                      e) Cleanup: supprimer dossiers vides récursivement

Phase 4: VERIFY     001-MOVIES/, 002-TVSHOWS/
                    Check de cohérence par item (critères ci-dessous)
                    → Items "valid"/"fixed" = dispatchable
                    → Items "blocked" = restent, rapport détaillé

Phase 5: DISPATCH   Uniquement les items valid/fixed
                    Les blocked restent dans 001/002
                    Ne tourne PAS si aucun item dispatchable
```

## Critères de cohérence (Phase 4)

### Film — MUST HAVE

| Critère                    | Check                                | Severity |
| -------------------------- | ------------------------------------ | -------- |
| Nom format `Title (Year)/` | Regex `^.+\s\(\d{4}\)$`              | ERROR    |
| >= 1 fichier vidéo         | Extensions vidéo, taille > 100 Mo    | ERROR    |
| NFO valide                 | XML parseable, contient `<uniqueid>` | ERROR    |
| Poster présent             | `Title-poster.jpg` existe            | ERROR    |
| Pas de sous-dossiers vides | Récursif                             | ERROR    |

### Série — MUST HAVE

| Critère                                | Check                                  | Severity |
| -------------------------------------- | -------------------------------------- | -------- |
| Nom format `Show Name (Year)/`         | Regex `^.+\s\(\d{4}\)$`                | ERROR    |
| `tvshow.nfo` valide                    | XML parseable, contient `<uniqueid>`   | ERROR    |
| >= 1 `Saison XX/` avec épisodes        | Sous-dossier avec fichiers vidéo       | ERROR    |
| Épisodes renommés `S01E01 - Title.ext` | Regex sur chaque vidéo dans Saison XX/ | ERROR    |
| `poster.jpg` présent                   | Existe à la racine du show             | ERROR    |
| Pas de sous-dossiers vides             | Récursif                               | ERROR    |

### Comportement `--interactive`

En mode interactif (lancement manuel), quand un match API échoue :

- Proposer les résultats proches trouvés par TMDB/TVDB
- L'utilisateur choisit ou skip
- Skip → l'item reste "blocked" au verify

En mode auto (cron, pas de `--interactive`) :

- Log un warning
- L'item reste dans son dossier, "blocked" au verify

## Changements par fichier

### `personalscraper/pipeline.py` (NOUVEAU)

Orchestrateur central qui remplace la logique inline de `cli.py:run()`.

```python
class Pipeline:
    """Séquentiel exhaustif pipeline orchestrator."""

    def run(self, settings, dry_run, interactive, verbose, console) -> PipelineReport:
        """Exécute les 5 phases avec gates."""

        # Phase 1: INGEST
        ingest_report = run_ingest(settings, dry_run)

        # Phase 2: SORT
        sort_report = run_sort(settings, dry_run)
        self._assert_temp_empty(settings)  # GATE

        # Phase 3: PROCESS (re-clean + dedup + scrape + episode rename + cleanup)
        process_report = run_process(settings, dry_run, interactive)

        # Phase 4: VERIFY
        verify_report, dispatchable = run_verify(settings, dry_run)

        # Phase 5: DISPATCH (seulement si des items dispatchable)
        if dispatchable:
            dispatch_report = run_dispatch(settings, dry_run, verified=dispatchable)
        else:
            dispatch_report = StepReport(name="dispatch", skip_count=1,
                                         details=["No dispatchable items"])

        return report
```

### `personalscraper/process.py` (NOUVEAU)

Phase 3 : re-clean + dedup + scrape + cleanup.

```python
def run_process(settings, dry_run, interactive) -> StepReport:
    """Process all items in category dirs: clean, dedup, scrape, cleanup."""

    staging = settings.staging_dir

    for category_dir_name in [settings.movies_dir_name, settings.tvshows_dir_name]:
        category_dir = staging / category_dir_name
        if not category_dir.exists():
            continue

        # a) Re-clean: rename raw folder names via guessit
        reclean_folders(category_dir)

        # b) Dedup: find and merge fuzzy duplicates
        dedup_folders(category_dir)

    # c) Scrape (existing run_scrape handles this)
    scrape_report = run_scrape(settings, dry_run, interactive)

    # d) Cleanup: remove empty dirs recursively
    for category_dir_name in [settings.movies_dir_name, settings.tvshows_dir_name]:
        cleanup_empty_dirs(staging / category_dir_name)

    return scrape_report  # ou combiné avec reclean/dedup stats
```

### `personalscraper/cli.py`

- `run()` délègue à `Pipeline.run()` au lieu de contenir la logique inline
- `_run_step()` reste pour le feedback console (utilisé par Pipeline)

### `personalscraper/sorter/run.py`

- Ajout de `assert_temp_empty(settings)` en post-sort gate
- Raise si 097-TEMP contient encore des fichiers non-triés (hors .gitkeep/.DS_Store)

### `personalscraper/verify/checker.py`

Critères renforcés :

- `episode_renamed` : vérifie que chaque vidéo dans `Saison XX/` matche `S\d{2}E\d{2} - .+\.\w+`
- `no_empty_dirs` : récursif sur tout le dossier média
- `poster_present` : vérifie l'existence du poster (films: `Title-poster.jpg`, séries: `poster.jpg`)

### Tests

- Tests unitaires pour `Pipeline.run()` avec mocks des 5 phases
- Test du gate `assert_temp_empty` (passe si vide, raise si pas vide)
- Test de `reclean_folders` (nom brut → nom propre)
- Test de `dedup_folders` (fusionne doublons)
- Test de `cleanup_empty_dirs` (supprime les vides récursivement)
- Tests verify renforcés : épisodes non-renommés → blocked, dossier vide → blocked
- Test d'intégration : pipeline complet avec fichier brut → dispatch seulement si tout clean

## Ce qui ne change PAS

- Les modules individuels (ingest.py, sorter.py, scraper.py, verifier.py, dispatcher.py)
- Le format StepReport/PipelineReport
- Les commandes standalone (`personalscraper ingest`, `personalscraper sort`, etc.)
- Le notifier Telegram, le healthcheck
- Les 898 tests existants (aucun ne doit casser)
- Le circuit breaker, le fuzzy matching, le lock

## Risques

| Risque                                                   | Mitigation                                                                      |
| -------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Phase 3 trop lente (re-scan tout à chaque run)           | Skip les items déjà scrapés (NFO exists) — c'est déjà le cas                    |
| Gate 097-TEMP bloque si un fichier ne peut pas être trié | Log l'erreur, continue — le gate vérifie qu'il ne reste QUE des erreurs connues |
| Dedup faux positif (fusionne deux médias différents)     | fuzzy_match_score avec year guard + length guard + threshold 90%+               |
| Episode rename échoue (pas de match API)                 | L'épisode reste non-renommé → blocked au verify, pas dispatché                  |
