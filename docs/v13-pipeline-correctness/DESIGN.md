# V13 — PIPELINE CORRECTNESS

## Objectif

Garantir que le pipeline est réellement idempotent : chaque re-run détecte et corrige les
problèmes au lieu de les ignorer. Résoudre les 24 bugs identifiés lors du pipeline run
2026-04-14 et vérifier que tout ce qui a été promis dans V0-V12 est implémenté.

## Contexte — Pourquoi cette version

Le pipeline run du 14 avril 2026 a révélé un pattern systémique : le fast-skip dans
PROCESS déclare "terminé" dès qu'un NFO valide est trouvé, ignorant tous les autres
problèmes (fichiers NTFS-illegaux, épisodes non-organisés, doublons, résidus). Le dispatch
envoyait tout vers Disk1 car `MediaIndex.rebuild()` n'était jamais appelé (feature conçue
en V5 mais jamais intégrée). 24 bugs catalogués, dont 5 critiques.

Ref: `docs/pipeline-runs/2026-04-14-10h32-pipeline-run.md`

## Architecture

### Pipeline révisé

```
INGEST → SORT → PROCESS → ENFORCE → VERIFY → DISPATCH
                             ↑ NEW
```

ENFORCE est un nouveau step entre PROCESS et VERIFY. C'est le dernier step qui modifie
le filesystem. VERIFY est un gate read-only. DISPATCH ne touche que les disques de stockage.

### Principes

1. **PROCESS répare ce qui relève de son domaine** — épisodes non-organisés, NFO résidus,
   artwork recovery. Le scraper ne skip plus aveuglément sur NFO valide.
2. **ENFORCE corrige tout le reste** — sanitize filenames, structure, doublons, .DS_Store,
   cohérence cross-step. Filet de sécurité transversal.
3. **VERIFY ne corrige rien** — gate pure. Si un item échoue VERIFY après ENFORCE, c'est
   un bug dans ENFORCE, pas un item à skipper.
4. **Idempotence réelle** — run 1 corrige, run 2 est un no-op. Testé par fixtures + E2E.
5. **Défense en profondeur** — PROCESS et ENFORCE ont un chevauchement intentionnel
   (NFO résidus, doublons). PROCESS corrige ce qu'il peut dans son domaine (scraping),
   ENFORCE rattrape ce que PROCESS a raté. Le chevauchement est un filet de sécurité,
   pas une duplication : ENFORCE est idempotent, donc re-vérifier un item déjà corrigé
   par PROCESS est un no-op.

---

## Phase 0 — Audit V0-V12

### Objectif

Vérifier que chaque feature promise dans les brainstorming/design/plan de V0-V12 est :

- Implémentée dans le code
- Testée
- Appelée dans le flow du pipeline

### Méthodologie

Pour chaque version VX :

1. Lire `docs/vX-*/BRAINSTORMING.md` → extraire features promises
2. Lire `docs/vX-*/DESIGN.md` → extraire spécifications techniques
3. Lire `docs/vX-*/plan/INDEX.md` → extraire phases et sous-phases
4. Pour chaque feature : grep code → grep tests → vérifier flow pipeline
5. Classifier : OK | BUG (implémentée mais défaillante) | MISSING (jamais implémentée)

### Livrable

`docs/v13-pipeline-correctness/AUDIT-V0-V12.md` — rapport "promis vs implémenté".

Bugs → scope V13. Missing hors-scope → `BACKLOG-V14.md`.

---

## Phase 1 — Refonte fast-skip dans PROCESS (scraper)

### Problème

```python
# scraper.py — comportement actuel
if _is_nfo_complete(nfo_path):
    return "skipped_already_done"  # TOUT le reste ignoré
```

Le scraper vérifie UN critère (NFO valide) et return immédiatement. Le code de traitement
des épisodes (lignes 908-949), le cleanup, et toutes les corrections ne sont jamais atteints
pour les items "déjà faits".

### Solution

Le scraper ne skip plus. Il valide et répare :

```python
if _is_nfo_complete(nfo_path):
    repaired = self._repair_media_dir(media_dir, media_type)
    result.action = "repaired" if repaired else "validated"
    return result
```

### `_repair_movie_dir(movie_dir, title)` — Corrections films

1. **NFO résidus** — Lister tous les `.nfo` dans le dossier. Garder uniquement
   `{sanitized_title}.nfo`. Supprimer les autres (résidus release-group, doublons).
2. **Artwork recovery** — Si artwork manquant, extraire TMDB ID du NFO existant et
   re-télécharger (comportement existant, déjà implémenté).

### `_repair_tvshow_dir(show_dir)` — Corrections séries

1. **Épisodes non-organisés** — Chercher les fichiers vidéo hors `Saison XX/` via rglob
   (même code que le scrape normal, lignes 908-916). Si trouvés :
   - Extraire TMDB ID du tvshow.nfo existant (pas de re-match API)
   - Fetch episodes API → `create_season_dirs()` → `match_episode_files()` → `rename_episodes()`
   - Supprimer les sous-dossiers torrent bruts vidés
2. **NFO résidus** — Supprimer tout `.nfo` à la racine sauf `tvshow.nfo`.
3. **MKV doublons à la racine** — Si un fichier vidéo à la racine correspond à un épisode
   déjà dans `Saison XX/` (même SxxExx pattern), supprimer le doublon racine.
4. **Artwork recovery** — Si artwork manquant (poster/landscape), récupérer depuis TMDB ID
   du NFO.

### Gestion d'erreur

Le repair est best-effort par sous-élément. Si le flatten d'un épisode échoue, log warning
et continue. ENFORCE attrapera les résidus.

---

## Phase 2 — Step ENFORCE

### Module `personalscraper/enforce/`

```
personalscraper/enforce/
├── __init__.py
├── file_sanitizer.py       # Invariants fichiers
├── structure_validator.py   # Invariants structure
├── coherence_checker.py     # Cohérence cross-step
└── run.py                   # Orchestrateur
```

### `file_sanitizer.py` — Invariants fichiers

Scan récursif de tous les fichiers et dossiers dans 001-MOVIES/ et 002-TVSHOWS/.

**Actions :**

- Renommer fichiers/dossiers contenant des caractères NTFS-illegaux (`: < > " / \ | ? *`)
  - Si le nom sanitisé existe déjà → supprimer le fichier legacy (c'est un doublon)
  - Sinon → renommer vers le nom sanitisé
- Supprimer `.DS_Store` récursivement
- Supprimer `._*` (resource forks macOS) récursivement

**Cas spécial** : dossier `Spirale : L'Héritage de Saw (2021)` — le dossier lui-même est
renommé. Le NFO interne garde le titre API original avec `:` (c'est du XML, pas un nom
de fichier).

### `structure_validator.py` — Invariants structure

**Films (001-MOVIES/) :**

- Exactement 1 fichier vidéo principal
- Exactement 1 NFO nommé `{Title}.nfo` (match titre dossier sans année)
- Au minimum poster + landscape (artwork)
- Pas de sous-dossiers torrent bruts (hors `.actors/`)
- NFO en trop → supprimer (garder celui qui match le titre du dossier)
- Artwork en double (même type, noms différents) → garder le sanitisé, supprimer le legacy

**Séries (002-TVSHOWS/) :**

- `tvshow.nfo` à la racine
- Chaque fichier vidéo dans un dossier `Saison XX/`
- Nommage épisodes : `SxxExx - Title.ext`
- Pas de MKV à la racine (sauf si aucune `Saison XX/` n'existe encore)
- Pas de sous-dossiers torrent bruts résiduels
- MKV doublons racine → supprimer si même épisode dans `Saison XX/`
- Sous-dossiers torrent vides → supprimer

### `coherence_checker.py` — Cohérence cross-step

**Cohérence genre/catégorie :**

- Lire le NFO → extraire genre/type
- Mapper via `genre_mapper` → catégorie attendue
- Comparer avec dossier parent (001-MOVIES vs 002-TVSHOWS) et catégorie dispatch
- Incohérence → WARNING dans le rapport (pas de correction auto, décision humaine)

**Cohérence NFO IDs :**

- Au moins TMDB ou IMDB présent et non-vide
- Warning si un seul des deux (non bloquant)

**Cohérence SORT → PROCESS :**

- Film dans 001-MOVIES a un NFO movie (pas tvshow.nfo)
- Série dans 002-TVSHOWS a un tvshow.nfo (pas {Title}.nfo seul)

### `run.py` — Orchestrateur

```python
def run_enforce(settings, dry_run=False) -> StepReport:
    """Run the enforce pipeline step.

    Executes sanitize → structure → coherence in order.
    Each component works on the state left by the previous one.
    """
    results = []
    results += sanitize_files(settings, dry_run)
    results += validate_structure(settings, dry_run)
    results += check_coherence(settings, dry_run)
    return _to_step_report(results)
```

- Mode dry-run supporté (log ce qui serait fait, ne modifie rien)
- Idempotent : re-runner ne change rien si tout est conforme
- Produit un `StepReport` standard (success/skip/error/warnings/details)

---

## Phase 3 — Intégration + corrections ponctuelles

### Intégration pipeline

- `pipeline.py` : ajouter ENFORCE entre PROCESS et VERIFY dans la séquence
- `cli.py` : ajouter commande `personalscraper enforce` (standalone)
- ENFORCE hérite des mêmes garanties que les autres steps :
  - Error isolation (un échec sur un item n'arrête pas les autres)
  - StepReport standard
  - Dry-run support
  - Logging structuré (structlog)

### Corrections ponctuelles

- **Genre mapper** (#12) : Fonction Juré → type "emissions" au lieu de "series".
  Investiguer le mapping TMDB genre → catégorie dans `genre_mapper.py`.
- **Dispatch .DS_Store** (#1) : Ajouter `--exclude=.DS_Store --exclude=._*` aux commandes
  rsync dans `dispatcher.py` (ligne de construction rsync).

---

## Phase 4 — Tests E2E idempotence

### Fixtures synthétiques

Dossier `tests/enforce/fixtures/` avec 9 fixtures reproduisant les bugs connus :

| Fixture                      | Bugs couverts    | Contenu                                    |
| ---------------------------- | ---------------- | ------------------------------------------ |
| `movie_colon_files/`         | #8, #17          | Artwork avec `:`, NFO résidu release-group |
| `movie_duplicate_nfos/`      | #2, #3, #21      | Film avec 2-3 NFOs                         |
| `tvshow_raw_torrent_dirs/`   | #4, #5, #18, #20 | Épisodes dans sous-dossiers torrent        |
| `tvshow_duplicate_root_mkv/` | #6, #19          | MKV doublons racine + Saison XX/           |
| `tvshow_colon_folder/`       | #8               | Dossier avec `:` dans le nom               |
| `movie_old_artwork_naming/`  | #22              | Artwork avec ancien nommage (`:`)          |
| `ds_store_cleanup/`          | #1               | .DS_Store récursifs                        |
| `genre_incoherence/`         | #12              | NFO genre "Reality" dans series/           |
| `cross_step_incoherence/`    | cohérence        | Série dans 001-MOVIES                      |

### Pattern de test

Chaque fixture suit le cycle :

1. Setup : copier fixture vers tmp_path
2. Run 1 : exécuter PROCESS + ENFORCE → assert corrections appliquées
3. Run 2 : re-exécuter → assert 0 modifications (idempotent)

### Tests E2E réels

Marker `e2e_idempotence` (manuel uniquement, nécessite staging réel) :

1. Runner ENFORCE sur 001-MOVIES/ et 002-TVSHOWS/ réels
2. Vérifier : 0 fichiers avec `:`, 0 dossiers bruts, 0 NFO doublons, 0 .DS_Store
3. Runner une 2ème fois → 0 modifications

---

## Phase 5 — Rapport V14+

- Relire le rapport audit phase 0
- Extraire les items MISSING hors-scope V13
- Documenter dans `docs/v13-pipeline-correctness/BACKLOG-V14.md`

---

## Bugs résolus par phase

| Phase              | Bugs                                                            |
| ------------------ | --------------------------------------------------------------- |
| 0 (audit)          | Découverte de bugs supplémentaires éventuels                    |
| 1 (scraper repair) | #4, #5, #18, #20 (épisodes bruts), #2, #3, #21 (NFO résidus)    |
| 2 (ENFORCE)        | #8, #17, #22 (sanitize), #6, #19 (doublons MKV), #1 (.DS_Store) |
| 3 (intégration)    | #12 (genre_mapper), #1 (dispatch rsync exclude)                 |
| 4 (tests)          | Garantie non-régression pour tous les bugs                      |

## Bugs déjà traités (V12.4.5)

| Bug                                   | Fix                                          |
| ------------------------------------- | -------------------------------------------- |
| #10 choose_disk() sans scan           | `index.rebuild()` au démarrage si index vide |
| #11 \_move_new() au lieu de \_merge() | Conséquence de #10                           |
| #13 media_index.json vide             | Conséquence de #10                           |
| #14 Invincible doublon                | S04 mergé Disk1→Disk2 manuellement           |

## Bugs non résolus par V13

| Bug                       | Raison                                                     |
| ------------------------- | ---------------------------------------------------------- |
| #9 Pluribus 0 vidéos      | Épisodes jamais téléchargés — hors scope pipeline          |
| #15 Fallout perte données | Nécessite re-téléchargement manuel                         |
| #16 A Knight artefact     | Nettoyé, item en staging, sera traité au prochain dispatch |

---

## Dépendances

- `personalscraper.text_utils.sanitize_filename()` — réutilisé par ENFORCE
- `personalscraper.naming_patterns.NamingPatterns` — conventions de nommage
- `personalscraper.genre_mapper` — mapping genre → catégorie
- TMDB API — pour repair épisodes (fetch season details depuis TMDB ID du NFO)
- Pas de nouvelle dépendance externe
