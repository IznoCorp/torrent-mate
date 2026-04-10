# V7 — E2E TESTS : Brainstorming

> Tests end-to-end complets du pipeline V1→V6 avec de vrais fichiers torrents

## Contexte

Après implémentation de V0→V6, le pipeline complet est :

```
Magnet links → qBittorrent → torrents/complete → V1 (ingest) → A TRIER/
  → V2 (sort+clean) → V3 (scrape) → V4 (verify) → V5 (dispatch) → Disk1-4
  → V6 (log+notify)
```

V7 teste ce pipeline de bout en bout avec de vrais fichiers : vrais torrents téléchargés via
qBittorrent, vrais appels API TMDB/TVDB, vraies opérations fichiers. Les fichiers de test
sont nettoyés après les tests.

## Décisions prises

### Approche : vrais fichiers, vrai pipeline

- **Vrais torrents** : l'utilisateur fournit une liste de liens magnet (films + séries) stockée dans un fichier de configuration
- **Vrai qBittorrent** : les magnets sont ajoutés à qBit via l'API, téléchargés, puis le pipeline est exécuté
- **Vrais appels API** : TMDB et TVDB sont appelés en production (pas de mocks)
- **Vrai dispatch** : les fichiers sont déplacés vers les disques de destination
- **Vrai cleanup** : les fichiers de test sont supprimés après les tests

### Sécurité du cleanup (CRITIQUE)

**⚠️ Les disques contiennent de vrais médias. Le cleanup ne doit JAMAIS effacer des fichiers existants.**

Stratégie de protection multi-couches :

1. **Marker file** : chaque dossier créé par le test contient un fichier `.e2e-test-marker` avec un UUID de session unique. Le cleanup ne supprime QUE les dossiers contenant ce marker avec le bon UUID.

2. **Registre de test** : à chaque étape, le test enregistre les paths exacts créés dans un fichier `e2e-test-registry-{uuid}.json`. Le cleanup parcourt ce registre, vérifie le marker, puis supprime.

3. **Double vérification** : avant de supprimer un dossier sur un disque, vérifier :
   - Le marker `.e2e-test-marker` existe
   - Le contenu du marker correspond à l'UUID de session
   - Le chemin est dans le registre

4. **Pas de rm -rf sur les disques** : la suppression se fait fichier par fichier, en vérifiant chaque dossier parent.

5. **Dry-run par défaut** : le cleanup affiche ce qui sera supprimé AVANT de supprimer. L'utilisateur doit confirmer (ou passer `--force`).

6. **Timeout de sécurité** : si le registre a plus de 24h, avertir que les fichiers de test traînent.

### Données de test

Fichier de configuration : `tests/e2e/test_magnets.json`

```json
{
  "movies": [
    {
      "magnet": "magnet:?xt=urn:btih:...",
      "expected_title": "Movie Title",
      "expected_year": 2024,
      "expected_category": "films"
    }
  ],
  "tvshows": [
    {
      "magnet": "magnet:?xt=urn:btih:...",
      "expected_title": "Show Name",
      "expected_year": 2023,
      "expected_category": "series",
      "expected_seasons": [1]
    }
  ]
}
```

**L'utilisateur fournit les magnet links.** Le fichier `test_magnets.json` est gitignored (contient des magnet links). Un `test_magnets.example.json` montre la structure attendue.

### Phases du test E2E

```
1. SETUP    : Ajouter les magnets à qBittorrent, attendre le téléchargement
2. INGEST   : Exécuter V1 (ingest) → fichiers arrivent dans A TRIER/
3. SORT     : Exécuter V2 (sort+clean) → fichiers triés dans 001-MOVIES/, 002-TVSHOWS/
4. SCRAPE   : Exécuter V3 (scrape) → NFO, artwork, renommage épisodes
5. VERIFY   : Exécuter V4 (verify) → vérification + catégorisation
6. DISPATCH : Exécuter V5 (dispatch) → déplacement vers disques
7. ASSERT   : Vérifier l'état final sur les disques (fichiers présents, NFO valides, artwork OK)
8. CLEANUP  : Supprimer les fichiers de test des disques et de A TRIER/
```

### Assertions par étape

| Étape    | Assertions                                                                              |
| -------- | --------------------------------------------------------------------------------------- |
| INGEST   | Fichiers présents dans A TRIER/, pas dans torrents/complete                              |
| SORT     | Films dans 001-MOVIES/, séries dans 002-TVSHOWS/, noms nettoyés                         |
| SCRAPE   | NFO présents + valides, artwork téléchargé, épisodes renommés                           |
| VERIFY   | Tous les dossiers de test = "valid" ou "fixed", catégories identifiées                  |
| DISPATCH | Fichiers présents sur le bon disque dans la bonne catégorie                              |
| CLEANUP  | Tous les fichiers de test supprimés, aucun fichier existant touché, torrents supprimés  |

### Gestion des erreurs de test

- Si un test échoue à mi-parcours → le cleanup doit quand même tourner (finally/atexit)
- Si le cleanup échoue → afficher les fichiers restants pour suppression manuelle
- Si qBittorrent n'est pas accessible → skip les tests E2E (pas de fail)
- Si un torrent ne se télécharge pas dans le timeout → skip ce torrent, continuer les autres

### Contraintes techniques

1. **Durée** : les tests E2E sont longs (téléchargement torrent + API calls). Pas dans la CI standard.
2. **qBittorrent** : doit être running avec l'API Web activée
3. **Disques** : au moins un disque de destination monté
4. **Internet** : requis pour torrents + APIs
5. **Exécution manuelle** : `personalscraper test-e2e` ou `pytest tests/e2e/ -m e2e`
6. **Pas dans pytest standard** : marqué `@pytest.mark.e2e`, exclu par défaut
