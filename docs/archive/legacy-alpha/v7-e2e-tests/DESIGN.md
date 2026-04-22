# V7 — E2E TESTS : Design

> Tests end-to-end complets du pipeline V1→V6 avec de vrais fichiers torrents

## Architecture

### Fichiers

```
tests/e2e/
├── __init__.py
├── conftest.py              # Fixtures pytest (session-scoped : UUID, registry, qBit client, magnets)
├── test_magnets.example.json# Exemple de structure (commité, schéma ci-dessous)
├── test_magnets.json        # Vrais magnets de test (gitignored)
├── setup_torrents.py        # Script : ajouter magnets à qBit + attendre téléchargement
├── cleanup.py               # Script : supprimer les fichiers de test (avec protections)
├── registry.py              # Registre des fichiers créés par le test (tracking)
├── markers.py               # Gestion des fichiers .e2e-test-marker
├── assertions.py            # Fonctions d'assertion par étape du pipeline
├── test_pipeline_movies.py  # Test E2E pipeline complet pour les films
└── test_pipeline_tvshows.py # Test E2E pipeline complet pour les séries
```

```
personalscraper/
└── cli.py                   # Ajout commande `personalscraper test-e2e` (optionnel)
```

### Schéma `test_magnets.json`

```json
[
  {
    "name": "The Matrix",
    "magnet": "magnet:?xt=urn:btih:...",
    "type": "movie",
    "expected_category": "films",
    "verify_nfo_fields": ["title", "year", "uniqueid[@type='imdb']"]
  }
]
```

### Dépendances

- `pytest` — framework de test (déjà dans deps)
- `qbittorrent-api` — ajout/suppression torrents (déjà dans deps via V1)
- Aucune nouvelle dépendance

## Interfaces

### `registry.py` — Registre des fichiers de test

```python
class TestRegistry:
    """Enregistre tous les fichiers/dossiers créés par un test E2E.
    Sérialisé en JSON pour survie entre étapes."""

    def __init__(self, session_id: str):
        self.session_id = session_id       # UUID unique par session de test
        self.registry_path: Path           # e2e-test-registry-{uuid}.json
        self.created_paths: list[Path]     # Chemins créés (ordonnés chronologiquement)
        self.torrent_hashes: list[str]     # Hashes des torrents ajoutés à qBit

    def register(self, path: Path) -> None:
        """Enregistrer un chemin créé. Persiste immédiatement en JSON."""

    def register_torrent(self, torrent_hash: str) -> None:
        """Enregistrer un hash de torrent ajouté."""

    def save(self) -> None:
        """Sauvegarder le registre en JSON."""

    @classmethod
    def load(cls, registry_path: Path) -> "TestRegistry":
        """Charger un registre existant."""

    def get_cleanup_order(self) -> list[Path]:
        """Retourner les chemins à supprimer en ordre inverse (enfants d'abord)."""

    def cleanup(self) -> None:
        """Supprimer le fichier registry JSON lui-même après cleanup complet."""
```

### `markers.py` — Fichiers marqueurs

```python
MARKER_FILENAME = ".e2e-test-marker"

def place_marker(directory: Path, session_id: str) -> None:
    """Créer un fichier .e2e-test-marker contenant le session_id."""

def verify_marker(directory: Path, session_id: str, registry: "TestRegistry") -> bool:
    """Vérifier qu'un dossier contient le bon marker avec le bon session_id.
    TRIPLE CHECK avant toute suppression :
    1. Le fichier marker existe
    2. Le contenu correspond au session_id attendu
    3. Le chemin est dans le registre (registry.created_paths)
    Les 3 checks doivent passer. Si UN SEUL échoue → retourne False."""

def find_orphan_markers(base_paths: list[Path]) -> list[Path]:
    """Trouver des markers orphelins (tests précédents non nettoyés)."""
```

### `setup_torrents.py` — Setup des torrents

```python
class TorrentSetup:
    """Ajoute les magnets de test à qBittorrent et attend le téléchargement."""

    def __init__(self, qbit_client, registry: TestRegistry, timeout: int = 3600):
        ...

    def load_magnets(self, config_path: Path) -> list[dict]:
        """Charger test_magnets.json."""

    def add_magnets(self, magnets: list[dict], category: str = "e2e-test") -> list[str]:
        """Ajouter les magnets à qBit avec une catégorie dédiée 'e2e-test'.
        Retourne les hashes des torrents ajoutés.
        La catégorie permet d'identifier les torrents de test."""

    def wait_for_completion(self, hashes: list[str]) -> dict[str, bool]:
        """Attendre que tous les torrents soient téléchargés.
        Timeout par torrent. Retourne {hash: completed}."""

    def get_downloaded_paths(self, hashes: list[str]) -> list[Path]:
        """Récupérer les chemins des fichiers téléchargés."""
```

### `cleanup.py` — Nettoyage sécurisé

```python
class TestCleanup:
    """Supprime les fichiers de test avec protections multi-couches.

    ⚠️ SÉCURITÉ CRITIQUE : les disques contiennent de vrais médias.
    Ne JAMAIS supprimer un fichier sans triple vérification.
    """

    def __init__(self, registry: TestRegistry, dry_run: bool = True):
        """dry_run=True par défaut — affiche sans supprimer."""

    def cleanup_staging(self) -> list[Path]:
        """Nettoyer les fichiers de test dans A TRIER/.
        Pour chaque path dans le registre situé dans A TRIER/ :
        - Vérifier le marker + session_id
        - Supprimer fichier par fichier (pas rm -rf)
        """

    def cleanup_disks(self) -> list[Path]:
        """Nettoyer les fichiers de test sur Disk1-4.
        TRIPLE VÉRIFICATION par dossier :
        1. .e2e-test-marker existe dans le dossier
        2. Le contenu du marker = session_id de cette session
        3. Le chemin est dans le registre
        Si UN SEUL check échoue → NE PAS SUPPRIMER, logger l'alerte."""

    def cleanup_torrents(self) -> None:
        """Supprimer les torrents de test de qBittorrent.
        Utiliser la catégorie 'e2e-test' pour identifier.
        Supprimer le torrent ET ses fichiers dans torrents/complete."""

    def cleanup_all(self, force: bool = False) -> dict:  # {"staging": N, "disks": N, "torrents": N}
        """Nettoyage complet. Si dry_run et pas force : afficher le plan.
        Retourne un résumé {staging: N, disks: N, torrents: N}."""

    def verify_clean(self) -> list[Path]:
        """Post-cleanup : vérifier qu'il ne reste aucun marker orphelin."""
```

Après cleanup complet, le fichier registry JSON lui-même est supprimé via `registry.cleanup()`.

### `assertions.py` — Assertions par étape

```python
def assert_ingest_complete(staging_dir: Path, expected: list[dict]) -> None:
    """Vérifier que les fichiers torrents sont arrivés dans A TRIER/."""

def assert_sort_complete(movies_dir: Path, tvshows_dir: Path, expected: list[dict]) -> None:
    """Vérifier le tri : films dans 001-MOVIES/, séries dans 002-TVSHOWS/."""

def assert_scrape_complete(movies_dir: Path, tvshows_dir: Path, expected: list[dict]) -> None:
    """Vérifie :
    - Chaque média a un .nfo valide (XML parseable)
    - Artwork présent (poster obligatoire, fanart recommandé)
    - Épisodes TV renommés au format S##E## avec .nfo individuel
    Raises AssertionError avec message détaillé."""

def assert_verify_complete(results: list) -> None:
    """Vérifier que tous les dossiers de test sont 'valid' ou 'fixed'."""

def assert_dispatch_complete(disk_paths: list[Path], expected: list[dict]) -> None:
    """Vérifier que les fichiers sont sur le bon disque dans la bonne catégorie."""

def assert_pipeline_report(report) -> None:
    """Vérifier que V6 (log+notify) a produit un PipelineReport cohérent :
    - Toutes les étapes (ingest→dispatch) ont un StepReport
    - Le log file a été écrit et contient les événements attendus"""

def assert_cleanup_complete(registry: TestRegistry) -> None:
    """Vérifier qu'aucun fichier de test ne reste nulle part."""
```

## Flux de données

```
test_magnets.json
    │
    ▼
┌──────────────────┐     ┌──────────────┐
│ setup_torrents   │────▶│ qBittorrent  │──▶ torrents/complete/
│  + registry      │     └──────────────┘    (fichiers téléchargés)
│  + markers       │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Pipeline V1→V6   │──▶ A TRIER/ → 001-MOVIES/ → Disk1-4/
│ (exécution réelle│     (marker initial se propage avec les dossiers)
│  du pipeline)    │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ assertions       │──▶ Vérification état final
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ cleanup          │──▶ Suppression fichiers de test (triple vérification)
│ (triple check)   │    Suppression torrents qBit
└──────────────────┘
```

## Cycle de vie du marker `.e2e-test-marker` à travers le pipeline

> **Critique** : le marker est la base de toute la stratégie de sécurité du cleanup.
> Son comportement à chaque étape du pipeline DOIT être documenté et testé.

| Étape                            | Opération filesystem                                | Le marker survit ?                                                                 | Explication                                                                                                                                                          |
| -------------------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Setup** (torrent download)     | qBit télécharge dans `torrents/complete/`           | N/A                                                                                | Marker placé APRÈS le téléchargement, sur le dossier dans `torrents/complete/`                                                                                       |
| **V1 Ingest** (copy/move)        | `shutil.copytree` ou `shutil.move` vers `A TRIER/`  | **OUI** si copytree (copie tout le contenu). **OUI** si move sur même FS (rename). | Marker placé par le test setup sur le dossier dans `torrents/complete/` AVANT ingest. Survit à copytree (seeding) ou move (terminé). Pas de re-placement nécessaire. |
| **V2 Sort** (move)               | `shutil.move` vers `001-MOVIES/` ou `002-TVSHOWS/`  | **OUI** (même FS = rename atomique, le dossier entier est renommé)                 | Le marker est un fichier dans le dossier, il suit le rename                                                                                                          |
| **V3 Scrape** (rename dossier)   | `Path.rename()` pour `Show Name → Show Name (Year)` | **OUI** (rename sur même FS)                                                       | Le dossier est renommé, pas recréé                                                                                                                                   |
| **V5 Dispatch** (rsync cross-FS) | `rsync -a` de SSD vers Disk1-4                      | **OUI** (rsync copie TOUS les fichiers, y compris le marker)                       | `rsync -a` préserve le marker car c'est un fichier régulier dans le dossier                                                                                          |

**Stratégie marker** :

1. Le test place un marker initial après chaque création de dossier par le setup
2. Le marker survit naturellement à travers toutes les étapes (rename/move/rsync)
3. Au cleanup, `verify_marker()` vérifie que le marker est toujours là avec le bon session_id
4. **Pas besoin de re-créer** le marker à chaque étape — il se propage naturellement

**Test unitaire requis** (Phase 1, infra) : simuler un dossier avec marker passant par
move (V2-style), rename (V3-style), et copie récursive (V5-style). Vérifier que le marker
survit dans chaque cas.

## Gestion d'erreurs

| Situation                         | Comportement                                                    |
| --------------------------------- | --------------------------------------------------------------- |
| qBittorrent non accessible        | Skip tous les tests E2E (pytest.skip)                           |
| Torrent timeout (pas téléchargé)  | Skip ce torrent, tester les autres                              |
| Disque non monté                  | Skip le test dispatch pour ce disque                            |
| API TMDB/TVDB inaccessible        | Fail le test scrape avec message clair                          |
| Échec en milieu de pipeline       | finally/atexit exécute le cleanup quoi qu'il arrive             |
| Cleanup échoue sur un fichier     | Logger l'erreur, continuer les autres, afficher résumé à la fin |
| Marker absent sur un dossier disk | NE PAS SUPPRIMER, logger l'alerte, signaler à l'utilisateur     |
| Registre introuvable              | Chercher les markers orphelins, proposer un cleanup manuel      |
| test_magnets.json absent          | Skip les tests E2E avec message explicite                       |

Notifications Telegram désactivées pendant les tests E2E (`settings.telegram_bot_token = ""`). Logs structlog capturés normalement.
