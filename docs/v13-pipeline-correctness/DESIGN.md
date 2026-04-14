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
INGEST → SORT → [gate: 097-TEMP empty] → PROCESS (clean + scrape + cleanup) → ENFORCE → VERIFY → DISPATCH
                                                                                 ↑ NEW
```

ENFORCE est un nouveau step entre PROCESS et VERIFY. Pipeline passe de 7 à 8 StepReports.
ENFORCE est le dernier step qui modifie le filesystem. VERIFY est un gate read-only.
DISPATCH ne touche que les disques de stockage.

### Principes

1. **PROCESS répare ce qui relève de son domaine** — épisodes non-organisés, NFO résidus,
   artwork recovery. Le scraper ne skip plus aveuglément sur NFO valide.
2. **ENFORCE corrige tout le reste** — sanitize filenames, structure, doublons, .DS_Store,
   cohérence cross-step. Filet de sécurité transversal.
3. **VERIFY ne corrige rien** — gate pure. Si un item échoue VERIFY après ENFORCE, c'est
   un bug dans ENFORCE, pas un item à skipper. Le flag `--fix` existant dans VERIFY est
   supprimé en mode pipeline (post-ENFORCE). En mode standalone (`personalscraper verify`),
   `--fix` est conservé pour usage manuel mais deprecated avec warning.
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

### Problème — Deux niveaux de fast-skip

Le scraper a **deux niveaux** de fast-skip qui empêchent les réparations :

**Niveau 1 — `run_scrape()` dans `scraper/run.py`** : `_all_nfos_valid()` vérifie si
TOUS les NFOs de TOUTES les catégories sont valides. Si oui, le scraper entier est skippé
et `scrape_movie()`/`scrape_tvshow()` ne sont jamais appelés. C'est ce qui s'est passé
le 14 avril : "Scrape 0 OK / 41 skipped / 0 errors".

**Niveau 2 — `scrape_movie()`/`scrape_tvshow()` dans `scraper/scraper.py`** :
`_is_nfo_complete(nfo_path)` vérifie le NFO d'un item individuel. Si valide, le scraper
fait une artwork recovery puis return immédiatement. Le code de traitement des épisodes,
le cleanup des NFO résidus, et toutes les corrections ne sont jamais atteints.

```python
# scraper.py — comportement actuel (simplifié)
if _is_nfo_complete(nfo_path):
    # Artwork recovery existante (déjà implémentée)
    missing_art = self._check_missing_artwork(media_dir)
    if missing_art:
        self._recover_artwork(nfo_path, media_dir, result)
    # MAIS: pas de vérification des épisodes, NFO résidus, doublons...
    result.action = "skipped_already_done"
    return result
```

### Solution — Désactiver les fast-skips quand des réparations sont nécessaires

**Niveau 1 — `run_scrape()`** : Modifier `_all_nfos_valid()` pour vérifier non seulement
les NFOs mais aussi les conditions de repair. Si des épisodes non-organisés, des NFO
résidus, ou d'autres problèmes existent, NE PAS fast-skip le scraper même si les NFOs
sont valides. Nouvelle fonction : `_needs_repair(category_dir) -> bool`.

```python
# scraper/run.py — comportement révisé
def _should_skip_scrape(category_dir: Path) -> bool:
    """Skip only if ALL NFOs valid AND no repair needed."""
    return _all_nfos_valid(category_dir) and not _needs_repair(category_dir)
```

`_needs_repair()` vérifie rapidement (sans API) :

- Fichiers vidéo hors `Saison XX/` (épisodes non-organisés)
- Plus d'un `.nfo` dans un dossier film
- Fichiers `.nfo` à la racine d'un dossier série (hors `tvshow.nfo`)
- Fichiers vidéo à la racine d'un dossier série qui a des `Saison XX/`

**Niveau 2 — `scrape_movie()`/`scrape_tvshow()`** : Après le check NFO valide, appeler
`_repair_movie_dir()`/`_repair_tvshow_dir()` au lieu de return immédiatement.

```python
# scraper.py — comportement révisé
if _is_nfo_complete(nfo_path):
    # Artwork recovery existante (inchangée)
    missing_art = self._check_missing_artwork(media_dir)
    if missing_art:
        self._recover_artwork(nfo_path, media_dir, result)
    # NEW: repair pass
    repaired = self._repair_movie_dir(movie_dir, title)
    result.action = "repaired" if repaired else "validated"
    return result
```

### `_repair_movie_dir(movie_dir, title) -> bool` — Corrections films

1. **NFO résidus** — Lister tous les `.nfo` dans le dossier. Garder uniquement
   `{sanitized_title}.nfo`. Supprimer les autres (résidus release-group, doublons).
2. **Artwork recovery** — Si artwork manquant, extraire TMDB ID du NFO existant et
   re-télécharger (comportement existant, déjà implémenté dans le check au-dessus).

Returns True si au moins une correction a été appliquée.

### `_repair_tvshow_dir(show_dir) -> bool` — Corrections séries

1. **Épisodes non-organisés** — Chercher les fichiers vidéo hors `Saison XX/` via rglob
   (même logique que dans le bloc `scrape_tvshow()` "Process episodes"). Si trouvés :
   - Extraire TMDB ID du tvshow.nfo existant via `_extract_tmdb_id_from_nfo()`
     (pas de re-match API — réutilise l'ID déjà dans le NFO)
   - Fetch episodes API → `create_season_dirs()` → `match_episode_files()` → `rename_episodes()`
   - Supprimer les sous-dossiers torrent bruts vidés
   - Utilise le même `TMDBClient` (même circuit breaker + tenacity decorators)
2. **NFO résidus** — Supprimer tout `.nfo` à la racine sauf `tvshow.nfo`.
3. **MKV doublons à la racine** — Extraire le pattern `S\d+E\d+` du nom de chaque fichier
   vidéo à la racine (via regex simple, pas guessit). Si un épisode avec le même SxxExx
   existe dans `Saison XX/`, supprimer le doublon racine.
4. **Artwork recovery** — Si artwork manquant (poster/landscape), récupérer depuis TMDB ID
   du NFO (comportement existant).

Returns True si au moins une correction a été appliquée.

### Gestion d'erreur

Le repair est best-effort par sous-élément. Si le flatten d'un épisode échoue, log warning
et continue. ENFORCE attrapera les résidus. Les appels API utilisent le circuit breaker
et tenacity existants via le `TMDBClient` partagé.

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

### VERIFY — suppression du mode fix en pipeline

Le VERIFY actuel a un flag `--fix` activé par défaut (`fix: bool = typer.Option(True)`).
Ce flag est incompatible avec le principe "VERIFY ne corrige rien" post-ENFORCE.

- En mode pipeline (appelé par `pipeline.py`) : `run_verify(settings, fix=False)`
- En mode standalone CLI : `--fix` conservé mais deprecated avec warning
  `"--fix is deprecated, use 'personalscraper enforce' instead"`
- À terme (V14+) : supprimer complètement `--fix` de VERIFY

### Cascading step count update (7 → 8)

L'ajout d'ENFORCE change le pipeline de 7 à 8 StepReports. Locations à mettre à jour :

| Fichier       | Location                                | Changement                                       |
| ------------- | --------------------------------------- | ------------------------------------------------ |
| `pipeline.py` | `_step_icon()` dict                     | Ajouter `"enforce"` + renumberoter `1/8` à `8/8` |
| `pipeline.py` | Module docstring                        | "5 phases producing 8 StepReports"               |
| `models.py`   | `PipelineReport.to_html()` `step_icons` | Ajouter icône enforce (ex: 🔧)                   |
| `models.py`   | `StepReport.name` docstring             | Ajouter "enforce" à la liste                     |
| `cli.py`      | `run` command docstring                 | "8-step sequential flow"                         |
| `CLAUDE.md`   | Pipeline section                        | Mettre à jour le diagramme et la description     |
| `CLAUDE.md`   | Directory structure                     | Ajouter `enforce/` module                        |
| `CLAUDE.md`   | Pipeline Versions table                 | Ajouter V13                                      |

### Corrections ponctuelles

**Genre mapper (#12)** : Le bug est dans `categorize_from_nfo()` — elle appelle
`categorize_tvshow(genres, ...)` avec des noms de genres (strings) mais SANS `genre_ids`.
Le path par IDs (`_categorize_tvshow_tmdb`) n'est jamais emprunté depuis le NFO.
Pour "Fonction Juré", le genre TMDB est "Reality" (ID 10764), qui devrait mapper vers
"emissions" via `_categorize_tvshow_tmdb`. Fix : `categorize_from_nfo()` doit extraire
les genre IDs du NFO (tag `<genre>` avec attribut `id` si disponible) et les passer à
`categorize_tvshow()`. Si les IDs ne sont pas dans le NFO, fallback : enrichir
`_REALITY_NAMES` avec les variantes françaises TMDB.

**Dispatch .DS_Store (#1)** : Deux fixes complémentaires en défense en profondeur :

- Phase 2 (ENFORCE) : `file_sanitizer` supprime les `.DS_Store` du staging avant dispatch
- Phase 3 (dispatch) : Ajouter `--exclude=.DS_Store --exclude=._*` aux commandes rsync
  dans `dispatcher.py` comme filet de sécurité

### Mise à jour CLAUDE.md

- Pipeline section : diagramme 8 steps avec ENFORCE
- Directory structure : ajouter `personalscraper/enforce/`
- Pipeline Versions table : ajouter V13 "PIPELINE CORRECTNESS"
- Commands section : ajouter `personalscraper enforce`

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
- Inclure la suppression complète de VERIFY `--fix` (deprecated en V13)

---

## Interfaces

### `personalscraper/enforce/file_sanitizer.py`

```python
@dataclass
class SanitizeResult:
    """Result of sanitizing a single file or directory."""
    path: Path
    action: str  # "renamed", "deleted_duplicate", "deleted_ds_store", "skipped"
    old_name: str | None = None
    new_name: str | None = None

def sanitize_files(settings: Settings, dry_run: bool = False) -> list[SanitizeResult]:
    """Sanitize all filenames in staging categories.

    Renames NTFS-illegal characters, removes .DS_Store and ._ files.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, log actions without modifying filesystem.

    Returns:
        List of SanitizeResult for each action taken.
    """
```

### `personalscraper/enforce/structure_validator.py`

```python
@dataclass
class StructureResult:
    """Result of validating/fixing structure for one media item."""
    path: Path
    media_type: str  # "movie" or "tvshow"
    action: str  # "validated", "repaired", "error"
    fixes: list[str]  # Description of each fix applied
    warnings: list[str]  # Non-blocking issues

def validate_structure(settings: Settings, dry_run: bool = False) -> list[StructureResult]:
    """Validate and fix directory structure for all staging items.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, log actions without modifying filesystem.

    Returns:
        List of StructureResult for each media item.
    """
```

### `personalscraper/enforce/coherence_checker.py`

```python
@dataclass
class CoherenceResult:
    """Result of coherence check for one media item."""
    path: Path
    checks: list[str]   # Checks performed
    warnings: list[str]  # Incoherences detected (not auto-fixed)

def check_coherence(settings: Settings, dry_run: bool = False) -> list[CoherenceResult]:
    """Check cross-step coherence for all staging items.

    Args:
        settings: Pipeline configuration.
        dry_run: If True (no effect — coherence check is read-only).

    Returns:
        List of CoherenceResult for each media item.
    """
```

### `personalscraper/enforce/run.py`

```python
def run_enforce(settings: Settings, dry_run: bool = False) -> StepReport:
    """Run the enforce pipeline step.

    Executes sanitize → structure → coherence in order.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without modifying filesystem.

    Returns:
        StepReport with enforce counts and details.
    """
```

### Scraper repair methods (ajoutés à `Scraper` class)

```python
def _repair_movie_dir(self, movie_dir: Path, title: str) -> bool:
    """Repair a movie directory with valid NFO.

    Removes residual NFOs, checks artwork. Does not re-scrape.

    Args:
        movie_dir: Path to the movie directory.
        title: Parsed movie title from folder name.

    Returns:
        True if any repair was applied.
    """

def _repair_tvshow_dir(self, show_dir: Path) -> bool:
    """Repair a TV show directory with valid NFO.

    Organizes unstructured episodes into Saison XX/, removes
    residual NFOs, cleans root-level MKV duplicates.
    Uses existing TMDB ID from tvshow.nfo for API calls.

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        True if any repair was applied.
    """
```

### `_needs_repair()` (ajouté à `scraper/run.py`)

```python
def _needs_repair(category_dir: Path) -> bool:
    """Check if any item in category needs repair beyond NFO.

    Quick filesystem-only check (no API calls). Returns True if any
    item has unorganized episodes, residual NFOs, or root-level MKV
    duplicates.

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.

    Returns:
        True if at least one item needs repair.
    """
```

### Data flow

```
              ┌─────────────────────────────────────────────────────────────┐
  PROCESS     │ run_scrape()                                               │
              │   _should_skip_scrape(cat_dir)?                            │
              │     _all_nfos_valid() AND NOT _needs_repair() → skip       │
              │     else → for each item:                                  │
              │       _is_nfo_complete()?                                  │
              │         YES → _repair_movie_dir() / _repair_tvshow_dir()   │
              │         NO  → scrape from scratch (inchangé)               │
              └──────────────────────────┬──────────────────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────────────┐
  ENFORCE     │ run_enforce()                                              │
              │   1. sanitize_files()      → rename NTFS chars, rm .DS_S   │
              │   2. validate_structure()   → check/fix NFO, artwork, eps  │
              │   3. check_coherence()      → genre, IDs, sort↔process     │
              └──────────────────────────┬──────────────────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────────────┐
  VERIFY      │ run_verify(fix=False)   ← read-only gate                   │
              │   Checks: NFO valid, artwork present, NTFS-safe names,     │
              │           season structure, genre category                  │
              │   Output: dispatchable list                                │
              └──────────────────────────┬──────────────────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────────────┐
  DISPATCH    │ run_dispatch()                                             │
              │   index.rebuild() if empty (V12.4.5)                       │
              │   for each verified: merge / replace / move_new            │
              └────────────────────────────────────────────────────────────┘
```

---

## Bugs résolus par phase

| Phase              | Bugs                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------- |
| 0 (audit)          | Découverte de bugs supplémentaires éventuels                                                |
| 1 (scraper repair) | #4, #5, #18, #20 (épisodes bruts), #2, #3, #21 (NFO résidus), #6, #19 (doublons MKV racine) |
| 2 (ENFORCE)        | #8, #17, #22 (sanitize filenames), #1 (.DS_Store suppression staging)                       |
| 3 (intégration)    | #12 (genre_mapper), #1 (dispatch rsync exclude), step count 7→8                             |
| 4 (tests)          | Garantie non-régression pour tous les bugs                                                  |
| Transversal        | #23 (items non-dispatchés = conséquence des bugs PROCESS/VERIFY, résolu par phases 1-3)     |
| Transversal        | #24 (pattern récurrent = le meta-bug que toute V13 adresse, vérifié par phase 4 tests)      |

## Bugs déjà traités (V12.4.5)

| Bug                                   | Fix                                          |
| ------------------------------------- | -------------------------------------------- |
| #10 choose_disk() sans scan           | `index.rebuild()` au démarrage si index vide |
| #11 \_move_new() au lieu de \_merge() | Conséquence de #10                           |
| #13 media_index.json vide             | Conséquence de #10                           |
| #14 Invincible doublon                | S04 mergé Disk1→Disk2 manuellement           |

## Bugs non résolus par V13

| Bug                              | Raison                                                                                                                                                                                                                                                                                    |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #7 Spirale TMDB search 0 results | Cosmétique : NFO déjà valide, le colon dans la query n'a pas d'impact. Le rename du dossier par ENFORCE (Phase 2) ne change pas le comportement TMDB car le scraper parse le nom de dossier, pas le NFO. Si le dossier est renommé sans `:`, un futur re-scrape trouvera le bon résultat. |
| #9 Pluribus 0 vidéos             | Épisodes jamais téléchargés — hors scope pipeline                                                                                                                                                                                                                                         |
| #15 Fallout perte données        | Nécessite re-téléchargement manuel                                                                                                                                                                                                                                                        |
| #16 A Knight artefact            | Nettoyé, item en staging, sera traité au prochain dispatch                                                                                                                                                                                                                                |

---

## Dépendances

- `personalscraper.text_utils.sanitize_filename()` — réutilisé par ENFORCE
- `personalscraper.naming_patterns.NamingPatterns` — conventions de nommage
- `personalscraper.genre_mapper` — mapping genre → catégorie
- `personalscraper.scraper.scraper._extract_tmdb_id_from_nfo()` — extraction TMDB ID pour repair
- TMDB API — pour repair épisodes (fetch season details depuis TMDB ID du NFO)
- Circuit breaker + tenacity — protections API existantes, réutilisées par le repair path
- Pas de nouvelle dépendance externe
