# V10 — PIPELINE RESILIENCE : Design

> Idempotence renforcee des 7 phases, reprise apres crash via validation par contenu, nettoyage artefacts partiels, tests filesystem realistes.

## Architecture

### Fichiers modifies

```
personalscraper/
├── ingest/ingest.py       # MODIFIE — fast-skip si aucun torrent, nettoyage orphelins renforce
├── sorter/sorter.py       # MODIFIE — skip item si deja present en 001/002 (fuzzy match)
├── sorter/run.py          # MODIFIE — fast-skip si 097-TEMP vide
├── process/reclean.py     # MODIFIE — skip dossier source disparu (crash mid-rename)
├── process/run.py         # MODIFIE — fast-skip clean si aucun dossier pollue
├── scraper/scraper.py     # MODIFIE — validation NFO (parsable + uniqueid), re-scrape si corrompu
├── scraper/run.py         # MODIFIE — fast-skip si tous NFO valides
├── verify/verifier.py     # MODIFIE — skip re-fix si item passe deja tous les checks
├── verify/run.py          # MODIFIE — fast-skip si rien a verifier
├── dispatch/dispatcher.py # MODIFIE — nettoyage orphelins _tmp_dispatch + .merge_backup au debut
├── dispatch/run.py        # MODIFIE — fast-skip (existant, deja OK)
├── pipeline.py            # MODIFIE — log fast-skip dans console output
```

### Aucun nouveau module

Pas de nouveau fichier. Renforcement des modules existants uniquement.

### Dependances

Aucune nouvelle dependance externe.

## Interfaces

### Validation NFO (scraper.py)

```python
def _is_nfo_complete(nfo_path: Path) -> bool:
    """Check if an NFO file is complete and valid.

    A complete NFO must:
    1. Be parsable as XML
    2. Contain at least one <uniqueid> element with non-empty text

    Args:
        nfo_path: Path to the .nfo file.

    Returns:
        True if the NFO is complete and valid.
    """
```

Utilisee dans `scrape_movie()` et `scrape_tvshow()` au lieu du simple `nfo_path.exists()`.

### Fast-skip helpers

```python
# sorter/run.py
def _has_unsorted_items(settings: Settings) -> bool:
    """Check if 097-TEMP contains non-hidden items to sort."""

# process/run.py — dans run_clean()
def _has_polluted_folders(category_dir: Path) -> bool:
    """Check if any folder in category_dir has a polluted name."""

# scraper/run.py
def _has_unscraped_items(settings: Settings) -> bool:
    """Check if any media folder lacks a valid NFO."""

# verify/run.py
def _has_items_to_verify(settings: Settings) -> bool:
    """Check if any media folder needs verification."""
```

Ces fonctions sont des checks legers en debut de phase. Elles ne remplacent pas la logique de la phase — elles permettent juste de skipper la phase entiere si rien a faire.

### Scraper : re-download artwork manquants

```python
# scraper/scraper.py — dans scrape_movie() et scrape_tvshow()
# Apres le check NFO valide, nouveau check :
# Si NFO valide mais artwork manquant → re-download sans re-scrape le NFO

def _check_artwork_complete(media_dir: Path, media_type: str) -> list[str]:
    """List missing artwork files for a media directory.

    Args:
        media_dir: Path to the media directory.
        media_type: "movie" or "tvshow".

    Returns:
        List of missing artwork filenames. Empty if all present.
    """
```

### Verify : skip fixes inutiles

```python
# verify/verifier.py — dans verify_movie() et verify_tvshow()
# Avant d'appeler le fixer : verifier si l'item passe deja tous les checks
# Si oui → status="valid", pas de fix

# Changement dans _classify() ou directement dans verify_movie/verify_tvshow :
# Ne lancer le fixer QUE si des checks fixables echouent (deja le cas)
# Le vrai probleme : le fixer tourne et modifie des choses meme quand tout est OK?
# → Non, le fixer ne modifie que les checks qui echouent avec fixable=True
# → Le fix est deja conditionnel. Le vrai probleme est le re-check post-fix.
# Solution : si le premier check n'a aucun fail → skip fix + re-check
```

### Sort : skip deja trie

```python
# sorter/sorter.py — dans sort_item()
# Avant de deplacer : verifier si un dossier avec le meme titre existe deja
# dans la categorie destination (001-MOVIES/, 002-TVSHOWS/)
# Utilise fuzzy_match_score pour detecter "Movie.Title.2024" deja present
# comme "Movie Title (2024)"
```

## Flux de donnees

```
Pipeline.run()
  │
  ├─ INGEST
  │    ├─ _cleanup_orphan_temps()          ← nettoyage artefacts
  │    ├─ Aucun torrent non-ingere?        ← fast-skip check
  │    │    └─ Oui → StepReport(skip) en <1s
  │    └─ Non → run_ingest() normal (deja idempotent via hash tracker)
  │
  ├─ SORT
  │    ├─ 097-TEMP vide?                   ← fast-skip check
  │    │    └─ Oui → StepReport(skip) en <1s
  │    └─ Non → sort chaque item
  │         └─ Item deja present en 001/002? → skip avec log
  │
  ├─ GATE: assert_temp_empty (existant)
  │
  ├─ CLEAN
  │    ├─ Aucun dossier pollue?            ← fast-skip check
  │    │    └─ Oui → StepReport(skip) en <1s
  │    └─ Non → reclean + dedup (deja idempotent pour dedup)
  │         └─ Dossier source disparu (crash mid-rename)? → skip
  │
  ├─ SCRAPE
  │    ├─ Tous les NFO valides?            ← fast-skip check
  │    │    └─ Oui → StepReport(skip) en <1s
  │    └─ Non → scrape chaque item
  │         ├─ NFO existe mais invalide? → supprimer + re-scrape
  │         ├─ NFO valide mais artwork manquant? → re-download artwork
  │         └─ NFO absent → scrape normal
  │
  ├─ CLEANUP (deja idempotent)
  │
  ├─ VERIFY
  │    ├─ Tous checks passent sans fix?    ← fast-skip (optionnel)
  │    └─ verify_movie/verify_tvshow
  │         └─ Premier check tout OK? → skip fix + re-check
  │
  └─ DISPATCH
       ├─ _cleanup_orphan_temps()          ← nettoyage artefacts
       └─ dispatch normal (deja idempotent via MediaIndex)
```

## Nettoyage d'artefacts (validation par contenu)

| Artefact                  | Ou                        | Detection                                 | Action                         |
| ------------------------- | ------------------------- | ----------------------------------------- | ------------------------------ |
| NFO tronque               | 001-MOVIES/, 002-TVSHOWS/ | XML parse fail ou `<uniqueid>` absent     | Supprimer NFO → re-scrape      |
| Artwork partiel           | 001-MOVIES/, 002-TVSHOWS/ | NFO valide mais poster/landscape manquant | Re-download manquants          |
| `.ingest_tmp_*`           | 097-TEMP/                 | Prefixe connu                             | Supprimer en debut d'ingest    |
| `_tmp_dispatch_*`         | 001-MOVIES/, 002-TVSHOWS/ | Prefixe connu                             | Supprimer en debut de dispatch |
| `.merge_backup/`          | Sous-dossiers medias      | Nom connu                                 | Supprimer en debut de dispatch |
| Dossier source post-merge | 001-MOVIES/, 002-TVSHOWS/ | Source + target existent                  | Re-tenter merge                |
| Dossier vide              | 001-MOVIES/, 002-TVSHOWS/ | Aucun fichier reel                        | Supprime par cleanup (naturel) |

## Gestion d'erreurs

| Situation                          | Comportement                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------ |
| NFO corrompu detecte               | Log WARNING, supprimer, re-scrape. Si re-scrape echoue → error dans StepReport |
| Artwork manquant detecte           | Log INFO, re-download. Si download echoue → warning (pas bloquant)             |
| Sort: item deja present            | Log INFO "already sorted", skip_count += 1                                     |
| Crash mid-rename (source disparue) | Log WARNING, skip. Pas d'erreur si la target existe                            |
| Orphelin temp detecte              | Log INFO, supprimer. Pas d'erreur                                              |
| Fast-skip active                   | Log INFO "nothing to do", StepReport avec skip_count = N items                 |
| Verify: tous checks OK             | Skip fix phase, status = "valid" directement                                   |

## Tests de resilience (filesystem)

Tous les tests creent de vrais etats corrompus sur le filesystem :

| #   | Test                            | Setup                                      | Assertion                                |
| --- | ------------------------------- | ------------------------------------------ | ---------------------------------------- |
| 1   | NFO tronque recovery            | Ecrire XML invalide dans dossier film      | Scrape supprime et re-cree un NFO valide |
| 2   | NFO sans uniqueid recovery      | Ecrire XML parsable sans `<uniqueid>`      | Scrape supprime et re-cree un NFO valide |
| 3   | Artwork partiel recovery        | NFO valide + poster, pas de landscape      | Scrape re-download landscape manquant    |
| 4   | Merge partiel recovery          | Source + target existent (merge incomplet) | Reclean re-tente le merge                |
| 5   | Orphelin \_tmp_dispatch cleanup | Creer `_tmp_dispatch_*` dans 001-MOVIES/   | Dispatch nettoie en debut de phase       |
| 6   | Sort double-run idempotent      | Trier, relancer sort                       | Deuxieme run skip tout                   |
| 7   | Pipeline double-run idempotent  | Run complet, relancer                      | Deuxieme run skip tout (fast path)       |
| 8   | Kill mid-scrape simule          | NFO partiel + artwork partiel              | Pipeline recovery re-scrape              |
| 9   | Verify double-run               | Verifier, relancer verify                  | Pas de re-fix, meme resultat             |
| 10  | Clean double-run                | Reclean, relancer clean                    | Dossiers propres skip                    |

Note : les tests 1-3 et 8 necessitent des appels API mocks pour le re-scrape (on ne peut pas appeler TMDB/TVDB dans les tests unitaires). Le setup filesystem est reel, seule l'API est mockee.

Dispatch reste en **dry-run** dans tous les tests.

## Securite

- Aucune donnee de production touchee par les tests (tmp_path uniquement)
- Disques de stockage jamais montes/accedes dans les tests
- Suppression d'artefacts uniquement sur prefixes connus (`_tmp_dispatch_*`, `.ingest_tmp_*`, `.merge_backup/`)
- NFO supprime uniquement si invalide (jamais si valide)
