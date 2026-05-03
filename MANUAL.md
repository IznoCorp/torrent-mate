# Manuel d'utilisation — Zone de tri media

Ce document explique comment utiliser la zone de staging (tri) et les outils disponibles pour organiser les fichiers media.

> Voir aussi : [README.md](README.md) (vue d'ensemble du projet) | [INSTALLATION.md](INSTALLATION.md) (prérequis et installation)

## Vue d'ensemble

```
Torrents terminés  →  staging  →  Disques de stockage
                    personalscraper run     (7 étapes séquentielles)
```

**Pipeline automatisé (PersonalScraper) :**

1. **Ingest** — Les torrents terminés sont copiés/déplacés depuis qBittorrent vers le dossier ingest (par défaut `097-TEMP/`, configurable via `staging_dirs`)
2. **Sort** — Les fichiers sont triés dans les sous-dossiers de staging (`001-MOVIES/`, `002-TVSHOWS/`, etc., définis dans `staging_dirs`)
3. **Clean** — Nettoyage noms (reclean) + dédoublonnage fuzzy (dedup)
4. **Scrape** — Métadonnées récupérées automatiquement via TMDB/TVDB APIs (.nfo, artwork, rename épisodes)
5. **Cleanup** — Suppression des dossiers vides
6. **Verify** — Contrôle qualité avant dispatch (checker + fixer + catégorisation genre)
7. **Dispatch** — Déplacement vers le bon disque de stockage (replace films, merge séries)

> **Note :** MediaElch reste disponible comme fallback manuel pour le scraping si l'API ne trouve pas le résultat.

---

## Staging layout

PersonalScraper uses a staging area where downloaded media lands before
being processed and dispatched to permanent storage. From version 0.4.0,
the staging tree lives **outside the repository** at the path configured
in `config/paths.json5` under `paths.staging_dir`.

The subdirectory names are defined by `staging_dirs` in `config/paths.json5`.
Each entry has an `id` (numeric prefix, 0–999) and a `name` (kebab-case).
The on-disk folder name is `{id:03d}-{name.upper()}`, e.g.:

| id  | name    | folder name |
| --- | ------- | ----------- |
| 1   | movies  | 001-MOVIES  |
| 2   | tvshows | 002-TVSHOWS |
| 97  | temp    | 097-TEMP    |

### Migrating from ≤ 0.3.0

After upgrading, your `config/` directory must be updated to include
`staging_dirs`. Without it, PersonalScraper will exit with:

> `staging_dirs` missing from config.json5 — see MANUAL.md §Staging layout for migration steps.

**Step 1**: Add `staging_dirs` to your `config/paths.json5`. Copy the section
from `config.example/staging_dirs` and adjust if you have custom directory names.

**Step 2**: Set `paths.staging_dir` to the external location. No
production default — pick a path outside the repository (e.g.
`/Volumes/<disk>/staging/`).

**Step 3**: Move your existing staging content to the new location.
Replace `<old_staging>` with the previous in-repo location and
`<new_staging>` with the new `paths.staging_dir` value; the two paths
**must** differ. One command per directory:

```bash
rsync -a "<old_staging>/001-MOVIES/"  "<new_staging>/001-MOVIES/"
rsync -a "<old_staging>/002-TVSHOWS/" "<new_staging>/002-TVSHOWS/"
rsync -a "<old_staging>/003-EBOOKS/"  "<new_staging>/003-EBOOKS/"
rsync -a "<old_staging>/004-AUDIO/"   "<new_staging>/004-AUDIO/"
rsync -a "<old_staging>/005-APPS/"    "<new_staging>/005-APPS/"
rsync -a "<old_staging>/006-ANDROID/" "<new_staging>/006-ANDROID/"
rsync -a "<old_staging>/097-TEMP/"    "<new_staging>/097-TEMP/"
rsync -a "<old_staging>/098-AUTRES/"  "<new_staging>/098-AUTRES/"
```

After rsync completes, verify the transfer, then delete the originals from
the repository directory if desired.

**Note on `099-SCRIPTS/`**: This directory has been removed from git
tracking but its files remain on disk at their original location. The user
is responsible for moving or archiving these files separately.

---

## Commandes PersonalScraper (CLI)

Le pipeline automatisé est accessible via la commande `personalscraper` :

```bash
# Pipeline complet (7 étapes en séquence)
personalscraper run                 # Exécute tout : ingest → sort → clean → scrape → cleanup → verify → dispatch
personalscraper run --dry-run       # Prévisualiser sans modifier

# Phase process seule (reclean + dedup + scrape + cleanup)
personalscraper process             # Nettoyer, dédoublonner, scraper, supprimer vides
personalscraper process --dry-run   # Prévisualiser

# Étapes individuelles
personalscraper ingest              # Copier/déplacer les torrents terminés depuis qBittorrent
personalscraper ingest --dry-run    # Prévisualiser
personalscraper sort                # Trier dans 001-MOVIES, 002-TVSHOWS, etc.
personalscraper scrape              # Récupérer métadonnées TMDB/TVDB (.nfo, artwork)
personalscraper verify              # Contrôle qualité avant dispatch
personalscraper dispatch            # Déplacer vers disques de stockage
```

Chaque commande supporte des options supplémentaires (`--dry-run`, `--movies-only`, `--tvshows-only`, etc.). Voir `personalscraper <command> --help`.

**Prérequis :** fichier `.env` configuré (clés API TMDB/TVDB, credentials qBittorrent). Voir `.env.example`.

**Scheduling :** un agent launchd (`com.personalscraper.pipeline.plist`) peut exécuter le pipeline automatiquement à 3h du matin.

```bash
# Installer et activer
cp com.personalscraper.pipeline.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.personalscraper.pipeline.plist

# Désactiver
launchctl unload ~/Library/LaunchAgents/com.personalscraper.pipeline.plist

# Lancer manuellement
launchctl start com.personalscraper.pipeline

# Statut
launchctl list | grep personalscraper
```

---

## Tests

```bash
# Tests unitaires (rapide, ~6s)
make test                               # ou: python -m pytest -v

# Tests E2E torrents (MANUEL — nécessite qBittorrent actif)
python -m pytest -m e2e_torrent -v -s   # 3 tests pipeline (film, série, CLI mixte)

# Tests E2E roundtrip (MANUEL — nécessite clés API TMDB/TVDB)
python -m pytest -m roundtrip -v -s     # 2 tests (matching aller-retour film + série)
```

**Important :** les tests E2E ne sont **jamais** lancés par `make test` — ils nécessitent un lancement manuel explicite avec `-m e2e_torrent` ou `-m roundtrip`. Ils téléchargent de vrais torrents depuis les fichiers `.torrent` dans `assets/torrents/`, appellent les APIs TMDB/TVDB, et nettoient tout à la fin. Le dispatch tourne toujours en dry-run (les disques de stockage ne sont jamais modifiés).

---

## Commandes shell

### torrent-sort

Trie les fichiers à la racine de la zone de staging dans les bons sous-dossiers.

```bash
# Trier (mode normal)
torrent-sort

# Prévisualiser sans déplacer
torrent-sort --dry-run

# Trier + supprimer les restes
torrent-sort --verbose --clean
```

L'outil **FileMate** (`~/dev/FileMate/`) est appelé en arrière-plan. Les associations type → dossier sont configurées dans `~/dev/FileMate/.env`.

### Espace disque

```bash
df -h /Volumes/Disk{1,2,3,4}
```

---

## Commandes Claude Code (archivées)

> **Note :** Les anciennes commandes `/check-staging` et `/move-to-disk` ont été remplacées par le pipeline automatisé (`personalscraper verify` et `personalscraper dispatch`). Elles sont archivées dans `.claude-old/skills/`.

---

## Disques de stockage

| Disque | Montage               | Catégories disponibles                                                                                                                        |
| ------ | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Disk1  | /Volumes/Disk1/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk2  | /Volumes/Disk2/medias | series, series animes                                                                                                                         |
| Disk3  | /Volumes/Disk3/medias | films, films animations, films documentaires, livres audios, series, series animations, series documentaires, spectacles, theatres, emissions |
| Disk4  | /Volumes/Disk4/medias | films, films animations, series, series animations, series documentaires, emissions                                                           |

---

## Structure des dossiers

### Zone de tri

```
<repo>/
├── personalscraper/     Package Python (CLI)
│   ├── ingest/          qBittorrent → dossier ingest (ex: 097-TEMP/)
│   ├── sorter/          guessit + strategies → dossiers catégorie
│   ├── process/         reclean, dedup, cleanup
│   ├── scraper/         TMDB/TVDB matching, NFO, artwork
│   ├── verify/          contrôle qualité renforcé
│   ├── dispatch/        rsync vers disques configurés
│   └── pipeline.py      Orchestrateur 7 étapes séquentiel
├── tests/               Tests unitaires + E2E
└── assets/torrents/     Fichiers .torrent pour tests E2E
```

Les dossiers de staging (`001-MOVIES/`, `002-TVSHOWS/`, etc.) se trouvent dans le dossier
défini par `paths.staging_dir` dans `config.json5` — en dehors du dépôt par défaut.
Ils ne sont pas suivis par git.

### Nommage des films

```
Titre du Film (Année)/
  Titre du Film.mkv
  Titre du Film.nfo
  Titre du Film-poster.jpg
  Titre du Film-fanart.jpg
  Titre du Film-banner.jpg
  Titre du Film-clearlogo.png
  Titre du Film-clearart.png
  Titre du Film-discart.png
  Titre du Film-landscape.jpg
  .actors/
```

### Nommage des séries

```
Nom de la Série (Année)/
  tvshow.nfo
  poster.jpg
  fanart.jpg
  banner.jpg
  clearlogo.png
  season01-poster.jpg
  .actors/
  Saison 01/
    S01E01 - Titre de l'Episode.mkv
    S01E01 - Titre de l'Episode.nfo
    S01E01 - Titre de l'Episode-thumb.jpg
  Saison 02/
    ...
```

- Dossiers de saison en français : `Saison 01`, `Saison 02`, etc.
- Fichiers d'épisodes : `S{nn}E{nn} - {Titre}.{ext}`

---

## Scraping des métadonnées

### Automatique (recommandé) — `personalscraper scrape`

Le scraping est automatisé via les APIs TMDB et TVDB :

```bash
personalscraper scrape              # Scrape tous les médias (films + séries)
```

Produit : fichiers `.nfo` (XML Kodi), posters, fanarts, banners, et renomme les épisodes au format `S01E01 - Titre.mkv`.

### Fallback manuel — MediaElch

Si l'API ne trouve pas un résultat, MediaElch (application de bureau GUI) peut être utilisé manuellement :

1. Ouvrir MediaElch, charger le dossier de staging des films ou des séries (ex: `001-MOVIES/` ou `002-TVSHOWS/`)
2. Lancer la recherche (TMDb/TheTVDB)
3. Télécharger poster, fanart, banner, etc.
4. Sauvegarder → génère le fichier `.nfo`

**Un media est prêt à déplacer quand il a au minimum :** un fichier vidéo + un fichier `.nfo`.

---

## Protections Claude Code

Hooks actifs dans `.claude/settings.json` :

1. **Blocage attribution AI** (`block_ai_attribution.py`) — Empêche les commits contenant `Co-Authored-By`, Claude, ou Anthropic
2. **Blocage fichiers sensibles** (`block_sensitive_files.py`) — Empêche l'édition de fichiers sensibles (.env, clés API)
3. **Auto-format** (`auto_format.py`) — Formate automatiquement après chaque édition
4. **Loggers** — `bash_logger.py`, `agent_logger.py`, `skill_logger.py` enregistrent les actions

> **Note :** Les hooks `block_media_files.py` et `block_disk_destructive.py` sont configurés dans settings.json mais les fichiers Python n'existent pas dans `.claude/hooks/` — ces protections sont **inactives**. La commande `rm` est bloquée via la liste `deny` des permissions.

---

## Scripts legacy (099-SCRIPTS/)

Anciens outils, tous renommés en `.bak`. Remplacés par PersonalScraper.

| Script                      | Usage d'origine                               | Statut                    |
| --------------------------- | --------------------------------------------- | ------------------------- |
| PackUnpack.py.bak           | Aplatir les sous-dossiers + nettoyer les noms | Archivé (chemins Windows) |
| Unpack.py.bak               | Variante d'unpack seul                        | Archivé                   |
| TVDBNameToNum.py.bak        | Matcher les noms d'épisodes via TheTVDB       | Archivé → remplacé par V3 |
| EpisodesTVDBNamer.py.bak    | Renommage d'épisodes TVDB                     | Archivé → remplacé par V3 |
| videoCutter.py.bak          | Couper des vidéos                             | Archivé                   |
| videoMerger.py.bak          | Fusionner des vidéos                          | Archivé                   |
| SensCritiqueScrapper.py.bak | Scraping SensCritique                         | Archivé                   |

---

## Notes importantes

- **Espaces dans les chemins** — Toujours mettre les chemins entre guillemets dans le terminal : `"/path/to/staging/"`
- **Casse des disques** — Les vrais points de montage sont `/Volumes/Disk1` (pas DISK1). Certains vieux scripts utilisent DISK1 en majuscules.
- **Configuration FileMate** — Les associations dossier-type sont dans `~/dev/FileMate/.env`
