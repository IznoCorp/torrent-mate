# Manuel d'utilisation — Zone de tri media

Ce document explique comment utiliser la zone de tri "A TRIER" et les outils disponibles pour organiser les fichiers media.

> Voir aussi : [README.md](README.md) (vue d'ensemble du projet) | [INSTALLATION.md](INSTALLATION.md) (prérequis et installation)

## Vue d'ensemble

```
Torrents terminés  →  A TRIER (staging)  →  Disques de stockage
                    personalscraper run     (7 étapes V1→V10)
```

**Pipeline automatisé (PersonalScraper V0-V10) :**

1. **V1 Ingest** — Les torrents terminés sont copiés/déplacés depuis qBittorrent vers `097-TEMP/`
2. **V2 Sort** — Les fichiers sont triés dans les sous-dossiers (001-MOVIES, 002-TVSHOWS, etc.)
3. **V9 Clean** — Nettoyage noms (reclean) + dédoublonnage fuzzy (dedup)
4. **V3 Scrape** — Métadonnées récupérées automatiquement via TMDB/TVDB APIs (.nfo, artwork, rename épisodes)
5. **V9 Cleanup** — Suppression des dossiers vides
6. **V4 Verify** — Contrôle qualité avant dispatch (checker + fixer + catégorisation genre)
7. **V5 Dispatch** — Déplacement vers le bon disque de stockage (replace films, merge séries)

> **Note :** MediaElch reste disponible comme fallback manuel pour le scraping si l'API ne trouve pas le résultat.

---

## Commandes PersonalScraper (CLI)

Le pipeline automatisé est accessible via la commande `personalscraper` :

```bash
# Pipeline complet (7 étapes en séquence)
personalscraper run                 # Exécute tout : ingest → sort → clean → scrape → cleanup → verify → dispatch
personalscraper run --dry-run       # Prévisualiser sans modifier

# Phase process seule (reclean + dedup + scrape + cleanup)
personalscraper process             # V9: Nettoyer, dédoublonner, scraper, supprimer vides
personalscraper process --dry-run   # Prévisualiser

# Étapes individuelles
personalscraper ingest              # V1: Copier/déplacer les torrents terminés depuis qBittorrent
personalscraper ingest --dry-run    # Prévisualiser
personalscraper sort                # V2: Trier dans 001-MOVIES, 002-TVSHOWS, etc.
personalscraper scrape              # V3: Récupérer métadonnées TMDB/TVDB (.nfo, artwork)
personalscraper verify              # V4: Contrôle qualité avant dispatch
personalscraper dispatch            # V5: Déplacer vers disques de stockage
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

Trie les fichiers à la racine de A TRIER dans les bons sous-dossiers.

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
A TRIER/
├── 001-MOVIES/          Films en attente
├── 002-TVSHOWS/         Séries en attente
├── 003-EBOOKS/          Ebooks
├── 004-AUDIO/           Livres audio
├── 005-APPS/            Applications
├── 006-ANDROID/         APK Android
├── 097-TEMP/            Espace temporaire
├── 098-AUTRES/          Divers
├── 099-SCRIPTS/         Scripts legacy (.bak, gitignored)
├── personalscraper/     Package Python (CLI V0-V9)
│   ├── ingest/          V1: qBittorrent → 097-TEMP/
│   ├── sorter/          V2: guessit + strategies → dossiers catégorie
│   ├── process/         V9: reclean, dedup, cleanup
│   ├── scraper/         V3: TMDB/TVDB matching, NFO, artwork
│   ├── verify/          V4+V9: contrôle qualité renforcé
│   ├── dispatch/        V5: rsync vers Disk1-4
│   └── pipeline.py      V9: Orchestrateur 7 étapes séquentiel
├── tests/               Tests unitaires + E2E
└── assets/torrents/     Fichiers .torrent pour tests E2E
```

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

1. Ouvrir MediaElch, charger le dossier 001-MOVIES ou 002-TVSHOWS
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

Anciens outils, tous renommés en `.bak`. Remplacés par PersonalScraper V0-V9.

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

- **Espaces dans les chemins** — Toujours mettre les chemins entre guillemets dans le terminal : `"/Volumes/IznoServer SSD/A TRIER/"`
- **Casse des disques** — Les vrais points de montage sont `/Volumes/Disk1` (pas DISK1). Certains vieux scripts utilisent DISK1 en majuscules.
- **Configuration FileMate** — Les associations dossier-type sont dans `~/dev/FileMate/.env`
