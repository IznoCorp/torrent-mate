# Manuel d'utilisation — TorrentMate

Ce document explique comment utiliser le pipeline de tri media, ses commandes CLI,
la répartition sur les disques de stockage, les conventions de nommage, et l'interface
web **TorrentMate**.

> Voir aussi : [README.md](README.md) (vue d'ensemble du projet) | [INSTALLATION.md](INSTALLATION.md) (prérequis et installation)

## Vue d'ensemble

```
Torrents terminés  →  staging/  →  Disques de stockage
                    torrentmate run   (9 étapes séquentielles)
```

**Pipeline automatisé (TorrentMate) — ordre d'exécution :**

1. **ingest** — Copie les torrents terminés depuis qBittorrent vers le dossier d'ingestion (rôle `ingest` dans `staging_dirs`, ex. `097-TEMP/`) ; ignore ce qui est déjà ingéré.
2. **sort** — Trie les fichiers dans les sous-dossiers catégorie (`001-MOVIES/`, `002-TVSHOWS/`, …) + première sanitisation des noms.
3. **clean** — Re-nettoyage des noms de dossiers + dédoublonnage fuzzy.
4. **scrape** — Récupère métadonnées + artwork (TMDB/TVDB) et écrit les `.nfo`.
5. **cleanup** — Supprime les dossiers vides laissés par les étapes précédentes.
6. **enforce** — Sanitise les noms de fichiers, valide la structure, supprime les `.DS_Store` (périmètre staging uniquement, pas les disques).
7. **verify** — Contrôle qualité avant dispatch (NFO valide, poster + landscape présents, nommage correct) ; lecture seule.
8. **trailers** — Télécharge les bandes-annonces (optionnel, désactivé par défaut — nécessite `YOUTUBE_API_KEY`).
9. **dispatch** — Déplace les médias validés vers le bon disque de stockage (films = remplacement, séries = fusion, nouveau = disque le plus libre).

> **Note :** MediaElch reste disponible comme fallback manuel pour le scraping si l'API ne trouve pas le résultat (voir plus bas).

**Règle d'or :** pour chaque étape, lancez toujours `--dry-run` d'abord, vérifiez la sortie, puis relancez sans `--dry-run`.

---

## 1. Commandes (CLI)

Point d'entrée : `torrentmate <command>`. Les **flags globaux** se placent **avant** la sous-commande :
`-v/--verbose`, `-q/--quiet`, `--version`, `-c/--config PATH`, `-f/--format rich|plain|json`.
La plupart des commandes `library-*` acceptent aussi leur propre `-c/--config PATH` **après** la sous-commande.

### 1.1 Pipeline (`run` + étapes)

Chaque étape supporte `--dry-run` (prévisualisation, aucune écriture).

```bash
# Pipeline complet (ingest → … → dispatch)
torrentmate run
torrentmate run --dry-run              # prévisualiser sans modifier
```

Flags de `run` : `--dry-run`, `-i/--interactive`, `--skip-trailers`, `--continue-on-trailer-error`,
`--headless` (aucun subscriber, silencieux pour cron/CI), `--no-console` (désactive le Rich Live
mais garde les logs fichier + Telegram — utilisé par le watcher), `--trigger-reason TEXT`.

L'hôte et le port qBittorrent (utilisés par `ingest` / `torrents-list`) vivent dans
`config/torrent.json5` (`clients.qbittorrent.host` / `.port`) — seuls les identifiants (`QBIT_PASSWORD`, …) sont dans `.env`.

| Commande        | Rôle                                                                            | Flags notables                                                     |
| --------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `ingest`        | Copie les torrents terminés de qBittorrent vers le staging (ignore déjà-ingéré) | `--dry-run`                                                        |
| `sort`          | Trie dans les dossiers catégorie + sanitisation initiale                        | `--dry-run`                                                        |
| `clean`         | Re-nettoyage noms + dédoublonnage fuzzy (sous-étape de `process`)               | `--dry-run`                                                        |
| `scrape`        | Récupère métadonnées + artwork (TMDB/TVDB), écrit `.nfo`                        | `--dry-run`, `-i/--interactive`, `--movies-only`, `--tvshows-only` |
| `cleanup`       | Supprime les dossiers vides (sous-étape de `process`)                           | `--dry-run`                                                        |
| `enforce`       | Sanitise noms, valide structure, supprime `.DS_Store` (staging)                 | `--dry-run`                                                        |
| `verify`        | Contrôle qualité avant dispatch (lecture seule)                                 | `--dry-run`, `--movies-only`, `--tvshows-only`                     |
| `dispatch`      | Déplace les médias validés vers les disques de stockage                         | `--dry-run`                                                        |
| `process`       | Composite : `clean` + `scrape` + `cleanup` (étapes 3–5)                         | `--dry-run`, `-i/--interactive`                                    |
| `torrents-list` | Liste les torrents terminés de qBittorrent (exit 2 si client injoignable)       | —                                                                  |

### 1.2 Bibliothèque — indexeur & maintenance (`library-*`)

La quasi-totalité des commandes de correction sont **dry-run par défaut ; utilisez `--apply` pour écrire**.
Les commandes de correction acceptent aussi `--db PATH`.

**Indexeur / scan :**

```bash
torrentmate library-index                    # scan complet dans .data/library.db (défaut : mode full, 2 passes)
torrentmate library-index --mode quick       # rapide (Merkle + dir-mtime)
torrentmate library-index --mode full --disk Disk1   # rebuild complet d'un disque
torrentmate library-index --rebuild          # repart de zéro (quarantaine l'ancienne DB)
torrentmate library-scan                     # alias visible de `library-index --mode full`
torrentmate library-init-canonical           # bootstrap canonical_provider depuis les NFO (one-shot)
torrentmate library-status                   # résumé du dernier scan-run (lecture seule)
```

Flags de `library-index` : `--mode full|quick|incremental|enrich`, `--disk TEXT`, `--budget INT`,
`--no-budget`, `--backfill-streams`, `--dry-run`, `--wait-for-lock INT`, `--confirm-bulk-change`, `--rebuild`.

**Vérification / réparation / réconciliation :**

```bash
torrentmate library-verify                   # re-stat les fichiers indexés, enqueue les écarts (--no-enqueue = audit)
torrentmate library-repair                   # draine la file de réparation (--budget INT, défaut 60)
torrentmate library-reconcile                # détecte les divergences index ↔ FS (lecture seule par défaut)
torrentmate library-ghost-audit              # audite les dirents fantômes NTFS/macFUSE (--disk)
torrentmate library-relink --apply           # relie les media_file sans release_id
```

`library-reconcile` : `--scope merkle|dispatch_path|enrich|release|season|item|path_missing` (répétable),
`--read-only`, `--dry-run`, `--enqueue-repairs` (écriture opt-in).

**Nettoyage / correction (dry-run par défaut, `--apply`) :**

```bash
torrentmate library-clean --apply            # supprime .actors/, dossiers vides, junk (--only actors|empty|junk|release|orphans)
torrentmate library-fix-canonical-provider --apply  # répare la dérive canonical_provider
torrentmate library-fix-nfo --apply          # tronque les NFO malformés (URL en fin) — écrit un .nfo.bak
torrentmate library-fix-orphan-files --apply # relie les media_file orphelins (release_id NULL)
torrentmate library-fix-season-counts --apply # répare la dérive season.episode_count
torrentmate library-dedup-titles --apply     # dédoublonne les media_item jumeaux NFD/NFC
torrentmate library-validate                 # valide conformité NFO/artwork/nommage (--fix --apply, --from-index)
torrentmate library-gc                        # purge les vieilles lignes index_outbox (--older-than-days, défaut 30)
```

**Analyse / requête :**

```bash
torrentmate library-analyze                  # résumé codec/audio/sous-titres (nécessite un enrich préalable)
torrentmate library-recommend                # recommandations de re-téléchargement → library_recommendations.json
torrentmate library-rescrape                 # re-scrape ciblé (--only nfo|artwork|episodes)
torrentmate library-report                   # stats + rapport de santé (lecture seule)
torrentmate library-doctor                   # contrôles de santé sur la DB live (exit ≠ 0 si WARN/FAIL)
torrentmate library-search "<query>"         # requête flex-attr (ex: nfo_status:invalid, year:>=2020)
torrentmate library-show <item_id>           # détail d'un item
torrentmate library-backfill-ids             # backfill des IDs croisés + notes (TMDB/TVDB/OMDb)
```

`library-search` : `field:value`, `-field:value`, `year:>=2020` ; `--limit INT` (défaut 50) ; exit 2 sur champ inconnu.
`library-backfill-ids` : `--show TEXT`, `--ids-only`, `--ratings-only`, `--dry-run` (prérequis : `library-init-canonical` + clés API dans `.env`).
Pointeurs `.env` : `OMDB_API_KEY` est requis pour le backfill des notes (`library-backfill-ids --ratings-only`) ; `TRAKT_CLIENT_ID` active `library-recommend`.

### 1.3 Acquisition (follow / grab / seed / cross-seed / watch)

État persisté dans `acquire.db` ; jobs planifiés via PM2. Cadences (heure locale, `ecosystem.config.js`) :
`personalscraper-index-enrich` dim. 04:30 · `personalscraper-backfill-ids` dim. 05:00 ·
`personalscraper-follow-detect` 03:00 (quotidien) · `personalscraper-grab` 03:20 + 15:20 ·
`personalscraper-health-check` horaire (:15) — en plus des daemons `personalscraper-watch`,
`torrentmate-web` (8710), `torrentmate-web-staging` (`web --port 8711`) et `torrentmate-autodeploy` (poll 60s).

**Suivi de séries — follow → detect → grab :**

```bash
torrentmate follow add --tvdb 12345          # suivre une série (idempotent ; --tvdb préféré, sinon --tmdb / --imdb ; --title optionnel)
torrentmate follow list                       # lister les séries suivies (--all inclut les inactives)
torrentmate follow remove --tvdb 12345        # soft-unfollow (active=False, historique conservé ; ou --id)
torrentmate follow detect                     # enqueue les épisodes diffusés-mais-absents comme "wanted" (--dry-run, --series ID|title)
torrentmate grab                              # cherche sur les trackers "{titre} SxxEyy", filtre l'épisode exact, classe, ajoute le meilleur à qBittorrent
torrentmate grab --dry-run                     # prévisualiser sans ajouter (-n/--limit N)
```

**Tagging seed-pure** (pour que le watcher fasse du cross-seed au lieu d'ingérer) :

```bash
torrentmate seed mark <INFO_HASH>            # applique le tag seed-pure
torrentmate seed unmark <INFO_HASH>          # retire le tag seed-pure
torrentmate seed list                         # liste les torrents terminés tagués seed-pure (lecture seule)
```

**Cross-seeding :**

```bash
torrentmate cross-seed --sweep               # balayage throttlé du back-catalogue
torrentmate cross-seed --hash <INFO_HASH>    # un seul torrent (spawné par le watcher à la complétion)
```

`--sweep` et `--hash` sont mutuellement exclusifs (exit 2 sur mauvaise combinaison) ; no-op si `cross_seed.enabled=false`.

**Watcher (daemon PM2) :**

```bash
torrentmate watch                            # poll qBittorrent chaque cycle, spawne `run --no-console` sur nouvelle complétion ; aucune option CLI
torrentmate watch-now                         # écrit le sentinel watch.trigger → run immédiat au prochain poll (persiste si daemon down)
```

Config dans `config/watch_seed.json5` : `watch.enabled`, `poll_interval_s`, `debounce_s` (défaut 900s),
`safety_net_hours` (défaut 24h — garantit un run minimum par jour). Pour les torrents tagués `seed_pure`,
le watcher lance `cross-seed --hash` au lieu d'un run pipeline.

```bash
# Gestion du daemon
pm2 status personalscraper-watch
pm2 logs personalscraper-watch
pm2 stop personalscraper-watch
```

### 1.4 Interface web (daemon PM2)

```bash
torrentmate web                              # démarre l'app FastAPI TorrentMate (SPA + REST /api/* + /ws/events)
torrentmate web --host 0.0.0.0 --port 8710   # host/port (défaut : config.web.port = 8710, staging = 8711)
torrentmate web set-password                 # génère WEB_PASSWORD_HASH (scrypt) + WEB_JWT_SECRET si absent ; affiche les clés
torrentmate web set-password --write         # upsert atomique dans le .env racine (après confirmation)
```

Config dans `config/web.json5` ; secrets `WEB_PASSWORD_HASH` / `WEB_JWT_SECRET` dans l'environnement.
Voir la section **Interface web** plus bas pour l'usage complet.

### 1.5 Santé

```bash
torrentmate health-check                     # moniteur local proactif (job PM2 horaire)
```

Vérifie la vivacité du watch-daemon (vrai pid OS, pas le shim pyenv), les lignes de log récentes
`level=error`, et un `pipeline.lock` bloqué ; envoie une alerte Telegram unique en cas d'anomalie.
Exit 0 si sain / 1 si anomalie. Lecture seule + fail-soft, sans flag.

### 1.6 Meta : info / init-config / trailers

```bash
torrentmate info                             # version, chemins de config, statut des disques (respecte --format)
torrentmate info providers                    # snapshot circuit-breaker par provider (exit 1 sur RegistryConfigError)
torrentmate init-config                       # bootstrap config/ depuis config.example/ (--example, --output, --yes, --force, --dry-run)
torrentmate config migrate-category --from <id> --to <id>   # réécrit media_item.category_id lors d'un renommage
```

**Trailers** (parent désactivé par défaut ; nécessite `YOUTUBE_API_KEY`). Sous-commandes partageant
`--disk`, `--category`, `--since YYYY-MM-DD`, `--level show|season|both`, `--season INT` :

```bash
torrentmate trailers scan                    # liste les items sans bande-annonce (lecture seule ; --limit, --no-refresh)
torrentmate trailers download                # télécharge les BA manquantes (TMDB /videos → YouTube → yt-dlp ; placement Plex)
torrentmate trailers audit                   # audit 4-checks (existence/taille/extension/--deep lisibilité) — exit 0/2/4
torrentmate trailers purge                   # supprime les BA orphelines (--dry-run, --include-state)
```

**Prérequis global :** fichier `.env` configuré avec les credentials des services. Voir `.env.example`.

### 1.7 Cibles Make (développement)

```bash
make lint     # ruff + mypy + check_logging (invisible à ruff/mypy) — zéro erreur
make test     # suite complète (test-unit / test-integration / test-cov aussi disponibles)
make check    # lint + test-cov (cible du phase-gate ; test-cov désélectionne ~161 tests vs `make test`)
```

Autres : `make gate` (= check), `format`, `install-dev`, `clean`, `version`, `cli-coverage-check`,
`update-ytdlp`, `perf-rebaseline`, `openapi`.

> Détail complet de chaque commande : `docs/reference/commands.md`.

---

## 2. Disques de stockage

### 2.1 Configuration multi-disques NTFS / macFUSE

- **4 disques de stockage**, tous formatés **NTFS**, montés via **macFUSE** (driver famille ntfs-3g) en **USB**.
  Points de montage : `/Volumes/Disk1/medias` … `/Volumes/Disk4/medias`.
- Tous les disques n'acceptent pas toutes les catégories (voir la table dans `docs/reference/storage.md`) :

  | Disque    | Catégories acceptées                                                                                     |
  | --------- | -------------------------------------------------------------------------------------------------------- |
  | **Disk1** | toutes (films, animations, documentaires, livres audio, séries, animes, spectacles, théâtres, émissions) |
  | **Disk2** | séries, séries animes uniquement                                                                         |
  | **Disk3** | films, animations, documentaires, séries, animes-docs, spectacles, théâtres, émissions                   |
  | **Disk4** | films, films animations, séries, séries animations, séries documentaires                                 |

- Un disque est **éligible** pour un nouvel item seulement s'il est (a) monté, (b) accepte la catégorie
  cible, et (c) satisfait la formule d'espace libre (ci-dessous).

### 2.2 Contraintes NTFS-via-macFUSE (opérationnel)

- **Pas de permissions Unix** — `chmod`/`chown`/`chgrp` sont des no-ops ou EPERM ; tous les fichiers
  apparaissent `rwxrwxrwx`, propriété de l'utilisateur qui monte.
- **rsync doit dépouiller perms/times** : le dispatcher utilise
  `-a --no-perms --no-owner --no-group --no-times --omit-dir-times --inplace --partial --exclude=.DS_Store --exclude=._*`
  (un simple `rsync -a` échoue avec « Operation not permitted »). Ce préfixe est figé dans
  `_fs_capability.py::_NTFS_RSYNC_FLAGS`.
- **Flags de montage recommandés** (le scanner WARN s'ils manquent, sans abandonner) :
  `noatime`, `noappledouble`, `noapplexattr`, `defer_permissions`, `allow_other`.
- Le filesystem est auto-détecté via `probe_mount` (mémoïsé pour la durée de vie du process via `lru_cache` ; les « 10s » sont le timeout du shell-out `mount`, pas un TTL de cache) ; un `DiskConfig.fs_type` explicite
  l'emporte (ex. forcer `hfsplus`). Un disque démonté / non-Darwin retombe sur la capability restrictive
  `unknown` (traitée comme NTFS).

### 2.3 Règle d'espace disque (choix de la cible pour un NOUVEL item)

Formule de seuil unifiée :

```
free_space_gb >= max(min_free_gb, item_size_gb * 1.5)
```

Le `Dispatcher` choisit le disque cible via `conf.resolver.pick_disk_for()` ; `get_disk_status()`
retourne un `DiskStatus` avec `free_space_gb`.

### 2.4 Règles de déplacement (dispatch)

Le routage est inline dans `process()` — `dispatch_movie()` vs `dispatch_tvshow()` :

- **Films → REMPLACEMENT.** Catégories `movies`, `movies_animation`, `movies_documentary`, `standup`,
  `theater` : si un dossier du même nom existe déjà sur un disque, il est **remplacé** par la version du staging.
- **Séries → FUSION.** Catégories `tv_shows`, `tv_shows_animation`, `tv_shows_documentary`, `anime`,
  `tv_programs` : si le dossier existe déjà, les nouveaux fichiers d'épisodes y sont **fusionnés**,
  remplaçant les épisodes déjà présents.
- **Nouveau média (aucun dossier existant nulle part) → disque le plus libre.** Déplacement vers le disque
  éligible ayant le **plus d'espace libre**.

**Correspondance « existe déjà »** résolue contre l'indexeur (`library.db`) en trois passes :

1. Nom de dossier normalisé exact.
2. **ID du provider canonique** — le `<uniqueid>` du NFO de l'item staging (TVDB pour les séries, TMDB
   pour les films, même séparation de familles que le scraping) comparé à l'`external_ids_json` de l'entrée
   sur disque. Capture un titre présent sous un **nom différent** (titre localisé / mauvaise année, ex.
   `Rick et Morty (2006)` vs `Rick and Morty (2013)`, tous deux TVDB `275274`) → traité comme le **même**
   item et fusionné/remplacé, pas dupliqué.
3. Nom fuzzy (fallback quand `external_ids_json` est vide).

La passe par ID de provider ne surcharge jamais un match exact et ne traverse jamais les familles de
providers. En fusion/remplacement, le **dossier sur disque garde son propre nom** (casse/orthographe conservées).

### 2.5 Layout des sous-dossiers de staging

Configuré dans `config/patterns.json5` sous `staging_dirs` (NON codé en dur, NON suivi par git). Chaque
entrée : `{id, name, file_type}`. Le nom du dossier sur disque = `f"{id:03d}-{name.upper()}"`
(`personalscraper/conf/staging.py::folder_name`).

| id  | name    | file_type       | Dossier       |
| --- | ------- | --------------- | ------------- |
| 1   | movies  | movie           | `001-MOVIES`  |
| 2   | tvshows | tvshow          | `002-TVSHOWS` |
| 3   | ebooks  | ebook           | `003-EBOOKS`  |
| 4   | audio   | audio           | `004-AUDIO`   |
| 5   | apps    | app             | `005-APPS`    |
| 6   | android | app             | `006-ANDROID` |
| 97  | temp    | (role `ingest`) | `097-TEMP`    |
| 98  | autres  | other           | `098-AUTRES`  |

- Exactement **une** entrée doit déclarer `role: "ingest"` — le point d'entrée des nouveaux
  téléchargements (ici `097-TEMP`).
- La racine du staging est `paths.staging_dir` (dans `config/paths.json5`, hors dépôt par défaut).
  FileMate reflète ces mappings de noms de dossiers dans `~/dev/FileMate/.env` — à garder synchronisé
  si le nommage des dossiers change.

### 2.6 Sécurité des chemins

- Les chemins de stockage/staging contiennent des espaces (`/Volumes/Disk1/medias`) — **toujours mettre
  les chemins entre guillemets** dans le terminal.
- Le filesystem macOS est insensible à la casse : `git mv FILE.md file.md` échoue ; utiliser un renommage
  intermédiaire (`git mv FILE.md tmp.md && git mv tmp.md file.md`).

```bash
# Espace disque
df -h /Volumes/Disk{1,2,3,4}
```

---

## 3. Nommage

### 3.1 IDs de catégorie (11 natifs)

`movies`, `movies_animation`, `movies_documentary`, `tv_shows`, `tv_shows_animation`,
`tv_shows_documentary`, `anime`, `audiobooks`, `standup`, `theater`, `tv_programs`.
(IDs personnalisés possibles via `custom_categories`.) Chaque ID mappe vers un `folder_name` dans
`config/categories.json5`. Plusieurs IDs peuvent partager un `folder_name` pour fusionner dans le même
dossier physique.

- **Famille films** (REMPLACEMENT au dispatch) : `movies`, `movies_animation`, `movies_documentary`,
  `standup`, `theater`.
- **Famille séries** (FUSION au dispatch) : `tv_shows`, `tv_shows_animation`, `tv_shows_documentary`,
  `anime`, `tv_programs`.
- Ordre de classification : `category_rules` (premier match gagne) → `anime_rule` (genre TMDB 16 +
  origin_country JP → `anime`) → `genre_mapping` (par provider) → défauts (`movies` / `tv_shows`).

### 3.2 Nommage des films

Pattern `movie_dir = "{Title} ({Year})"`. Convention artwork MediaElch (chaque fichier suffixé par le
basename) :

```
Titre du Film (Année)/
  Titre du Film.mkv
  Titre du Film.nfo
  Titre du Film-poster.jpg    Titre du Film-fanart.jpg    Titre du Film-banner.jpg
  Titre du Film-clearlogo.png Titre du Film-clearart.png  Titre du Film-discart.png
  Titre du Film-landscape.jpg
  .actors/
```

### 3.3 Nommage des séries

Convention artwork canonique Kodi (noms au niveau série à la racine, `seasonNN-*` par saison) :

```
Nom de la Série (Année)/
  tvshow.nfo
  poster.jpg  fanart.jpg  banner.jpg  clearlogo.png ...
  season01-poster.jpg    (season{Season:02d}-poster / -fanart / -banner / -landscape)
  .actors/
  Saison 01/
    S01E01 - Titre de l'Episode.mkv
    S01E01 - Titre de l'Episode.nfo
    S01E01 - Titre de l'Episode-thumb.jpg
  Saison 02/
    ...
```

- Dossiers de saison en **français** : `Saison {Season:02d}` (`Saison 01`, `Saison 02`).
- Fichier d'épisode : `S{Season:02d}E{Episode:02d} - {EpisodeTitle}` (+ `.nfo`, `-thumb.jpg`).
- Flux de création : le **sorter** crée `Nom de la Série/` (sans année) ; le **scraper** renomme en
  `Nom de la Série (Année)/` après matching API (idempotent).

**Season-pack / multi-épisodes** (un seul fichier vidéo couvrant toute une saison — forme Kodi
`S01E01-E02`), vérifié dans `naming_patterns.py` :

```
episode_video_range = "S{Season:02d}E{EpisodeStart:02d}-E{EpisodeEnd:02d} - {EpisodeTitle}"
```

ex. `S01E01-E10 - ...` (avec `episode_nfo_range` et `episode_thumb_range` correspondants).

### 3.4 Sanitisation des noms de fichiers

`sanitize_filename()` (`personalscraper/text_utils.py`) retire `<>:"/\|?*` et normalise l'espace
insécable U+00A0 → espace normal. Appliqué dans `NamingPatterns.format()` (tous les noms artwork/NFO)
et dans le `clean_name` du scraper (renommage de dossiers). Obligatoire car les titres TMDB portent des
`:` et des espaces insécables typographiques français (ex. `Spirale : L'Héritage de Saw`) illégaux/
problématiques sur NTFS.

### 3.5 Deux conventions d'artwork (à reconnaître toutes deux)

- **Films** → suffixe MediaElch : `<Titre>-poster.jpg`, `<Titre>-fanart.jpg`.
- **Séries** → canonique Kodi à la racine série : `poster.jpg`, `fanart.jpg`, `tvshow.nfo` ; variantes
  par saison `seasonNN-poster.jpg`.

Les confondre est la première source de faux positifs « artwork manquant ». `_inventory_artwork`
(`indexer/scanner/_modes/enrich.py`) accepte les deux.

### 3.6 Placement des bandes-annonces (conforme Plex)

- **Films** (à plat, même dossier) : `{media_dir}/{media_name}-trailer.{ext}` →
  `Fight Club (1999)/Fight Club (1999)-trailer.mp4`.
- **Série niveau show** (sous-dossier `Trailers/` requis) : `{show_dir}/Trailers/{show_name}.{ext}`.
- **Série niveau saison** (opt-in) : `{show_dir}/Saison {NN}/Trailers/{show_name} - Saison {NN}.{ext}`.
- Extensions acceptées, par priorité : `.mp4`, `.mkv`, `.webm`.

### 3.7 Extensions vidéo gérées (pipeline-wide)

`.mp4 .mkv .avi .mov .wmv .flv .mpg .mpeg .m4v .webm .ts .m2ts .mts .3gp .vob .ogv .rmvb`

---

## 4. Interface web — TorrentMate

**TorrentMate** est l'application ; **personalscraper** est le nom de code (le moteur Python synchrone).
Le frontend est **TorrentMateUI**. La vague S1 (`tm-shell`, ticket #158) livre le socle : un daemon FastAPI
headless sert la SPA React derrière Caddy, avec une API REST, un flux d'événements temps réel via WebSocket,
et une PWA installable.

### 4.1 Accès

| Rôle    | URL                                    | Port |
| ------- | -------------------------------------- | ---- |
| Prod    | `https://tm.iznogoudatall.xyz`         | 8710 |
| Staging | `https://tm-staging.iznogoudatall.xyz` | 8711 |

Les deux se distinguent au logo/bandeau (**prod = logo ambre**, **staging = logo cyan** + bandeau) ; le
nom « TorrentMate » reste identique sur les deux.

### 4.2 Connexion (login)

- **Utilisateur unique** — le nom d'utilisateur est dans `config/web.json5` (`web.username`, défaut `izno`).
- Le mot de passe est stocké comme hash scrypt dans `WEB_PASSWORD_HASH`, généré par
  `torrentmate web set-password`. Le secret de session JWT est `WEB_JWT_SECRET`.
- La session est un JWT HS256 posé dans le cookie **`tm_session`** (`HttpOnly; SameSite=Strict`,
  `Secure` en prod ; `Max-Age` = `session_ttl_hours * 3600`, défaut 720h = 30 jours).
- Rate-limit de login : 5 échecs / 60s → `429`. Un `WEB_JWT_SECRET` vide ou un `WEB_PASSWORD_HASH`
  manquant → le login renvoie `401` (fail-closed, jamais `500`).

```bash
# Configurer le mot de passe (one-time)
torrentmate web set-password           # affiche WEB_PASSWORD_HASH + WEB_JWT_SECRET
torrentmate web set-password --write   # écrit directement dans le .env racine
```

### 4.3 Tableau de bord + flux d'événements live

- La SPA est servie par le daemon (`/api/*` REST + `/ws/events` WebSocket).
- L'**EventBus** in-process est pontée vers le process web via **Redis Streams** (replay possible) :
  le producteur `RedisEventPublisher` (`personalscraper/subscribers/redis_stream.py`) `XADD` chaque
  événement dans le stream `personalscraper:events` (fail-soft : Redis down → warn une fois, drop les
  événements, ne bloque jamais le pipeline). Câblé (gated sur `web.enabled`) dans `run`, `watch` et les
  jobs d'acquisition.
- Le **relay WebSocket** (`GET /ws/events`, authentifié par cookie) diffuse chaque nouvelle entrée à toutes
  les sockets connectées. À la connexion : `{"type":"ws.hello",...}`, puis par événement
  `{"id":"<stream-id>","type":"<EventClass>","data":{…}}`, avec un keep-alive `{"type":"ws.ping"}` toutes les
  30s. Reconnexion avec replay via `?last_id=<id>`.

### 4.4 Installer la PWA

TorrentMate est une **Progressive Web App installable**, mobile-first (Android, iOS/iPadOS, desktop).

- **Android / desktop** : un bouton in-app « Installer TorrentMate » apparaît (capture de
  `beforeinstallprompt` ; les refus sont mémorisés dans `localStorage`).
- **iOS / iPadOS** : Safari hors mode standalone est détecté → feuille d'instructions native
  « Partager → Sur l'écran d'accueil ».
- **Mise à jour automatique** : le service worker vérifie les mises à jour au chargement, au
  `visibilitychange`, et toutes les 15 min ; `/api/version` est comparé au commit embarqué — un écart
  force la mise à jour → toast « Nouvelle version installée — rechargement… » → un seul rechargement
  automatique. Aucun client obsolète.

### 4.5 Configuration (`config/web.json5`)

```json5
web: {
  enabled: true,
  host: "127.0.0.1",
  port: 8710,                  // le clone staging surcharge à 8711
  username: "izno",
  redis_url: "redis://127.0.0.1:6379/0",
  stream_key: "personalscraper:events",
  stream_maxlen: 10000,
  session_ttl_hours: 720,      // 30 jours
  cookie_secure: true,         // false pour le dev local sans HTTPS
  dev_mode: false,             // true = démarre sans SPA buildée (proxy Vite dev)
}
```

Secrets `.env` : **`WEB_PASSWORD_HASH`** (`scrypt$N$r$p$salt$hash`, via `torrentmate web set-password`)
et **`WEB_JWT_SECRET`** (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).

### 4.6 Lancer en local (développement)

```bash
# 1. Secrets (one-time)
torrentmate web set-password

# 2. Builder la SPA (npm run build → frontend/dist/, sortie Vite par défaut)
cd frontend && npm ci && npm run build && cd ..
# Puis recopier le build vers le dossier servi (ou lancer ./scripts/deploy.sh qui le fait) :
rsync -a --delete frontend/dist/ personalscraper/web/static/

# 3. Lancer le daemon web (foreground)
torrentmate web
```

`torrentmate web` refuse de démarrer si `static/index.html` est absent et `web.dev_mode=false`
(évite de servir une app à moitié déployée). Dev frontend avec HMR : `cd frontend && npm run dev`
(Vite proxie `/api` + `/ws` vers `:8710`). Pour le dev local sans HTTPS, mettre `web.cookie_secure: false`.

### 4.7 Déploiement prod / staging

Deux clones de déploiement (modèle KanbanMate « push to deploy »), chacun avec son propre venv et sa
propre copie de `.env`, tous deux pointant `PERSONALSCRAPER_CONFIG=/Users/izno/dev/PersonalScraper/config`
(config réelle — S1 est en lecture seule, donc staging sur données réelles est sûr).

| Rôle    | Clone                   | Suit      | App PM2                   | Venv                         |
| ------- | ----------------------- | --------- | ------------------------- | ---------------------------- |
| Prod    | `~/deploy/torrentmate`  | `main`    | `torrentmate-web`         | `~/deploy/torrentmate-venv`  |
| Staging | `~/staging/torrentmate` | `staging` | `torrentmate-web-staging` | `~/staging/torrentmate-venv` |

- **Push `main` → prod se déploie ; push `staging` → staging se déploie.** L'app PM2
  `torrentmate-autodeploy` (`scripts/autodeploy-poll.sh`, boucle 60s) fetch, avance, puis lance
  `scripts/deploy.sh` (prod) ou `scripts/deploy-staging.sh` (staging).
- Chaque deploy : `npm ci && npm run build` → `rsync` vers `personalscraper/web/static/` → stamp
  `BUILD_COMMIT` → `pip install -e .` dans le venv → `pm2 startOrRestart … --update-env` → health-check
  `curl 127.0.0.1:<port>/api/health` == 200.
- **Caddy** (`/opt/homebrew/etc/Caddyfile`, appliqué manuellement par l'opérateur) : deux blocs
  `import tls_config` + `reverse_proxy localhost:8710` (prod) / `localhost:8711` (staging). Le proxying
  WebSocket est natif ; pas de basicauth Caddy (l'app gère son propre auth JWT-cookie).

> Référence complète : `docs/reference/web-ui.md`.

---

## 5. Scraping des métadonnées

### 5.1 Automatique (recommandé) — `torrentmate scrape`

Le scraping est automatisé via les APIs TMDB et TVDB :

```bash
torrentmate scrape              # scrape tous les médias (films + séries)
torrentmate scrape --dry-run    # prévisualiser
```

Produit : fichiers `.nfo` (XML Kodi), posters, fanarts, banners, et renomme les épisodes au format
`S01E01 - Titre.mkv`.

### 5.2 Fallback manuel — MediaElch

Si l'API ne trouve pas un résultat, MediaElch (application de bureau GUI) peut être utilisé manuellement :

1. Ouvrir MediaElch, charger le dossier de staging des films ou des séries (ex. `001-MOVIES/` ou `002-TVSHOWS/`).
2. Lancer la recherche (TMDb/TheTVDB).
3. Télécharger poster, fanart, banner, etc.
4. Sauvegarder → génère le fichier `.nfo`.

**Un media est prêt à déplacer quand il a au minimum :** un fichier vidéo + un fichier `.nfo`.

---

## 6. Tests

```bash
# Tests unitaires (rapide)
make test                               # ou : python -m pytest -v

# Tests E2E torrents (MANUEL — nécessite qBittorrent actif)
python -m pytest -m e2e_torrent -v -s

# Tests E2E roundtrip (MANUEL — nécessite clés API TMDB/TVDB)
python -m pytest -m roundtrip -v -s

# Tests réseau (MANUEL)
python -m pytest -m network -v -s
TRAILER_INTEGRATION_TESTS=1 python -m pytest -m network -v -s

# Autres marqueurs
python -m pytest -m slow -v -s
python -m pytest -m darwin_only -v -s
```

**Marqueurs disponibles :** `e2e`, `roundtrip`, `e2e_torrent`, `e2e_idempotence`, `network`, `slow`, `darwin_only`.

**Important :** les tests E2E et réseau ne sont **jamais** lancés par `make test` — ils nécessitent un
lancement manuel explicite avec `-m <marqueur>`. Ils téléchargent de vrais torrents depuis les fichiers
`.torrent` dans `assets/torrents/`, appellent les APIs TMDB/TVDB, et nettoient tout à la fin. Le dispatch
tourne toujours en dry-run (les disques de stockage ne sont jamais modifiés).

---

## 7. Structure des dossiers (repo)

```
<repo>/
├── personalscraper/     Package Python (CLI)
│   ├── ingest/          qBittorrent → dossier ingest (ex. 097-TEMP/)
│   ├── sorter/          guessit + strategies → dossiers catégorie
│   ├── process/         reclean, dedup, cleanup
│   ├── scraper/         TMDB/TVDB matching, NFO, artwork
│   ├── enforce/         Règles de conformité (nommage, structure)
│   ├── verify/          Contrôle qualité renforcé
│   ├── dispatch/        rsync vers disques configurés
│   ├── trailers/        Téléchargement bandes-annonces (yt-dlp)
│   ├── indexer/         Index SQLite des disques (scan, query, drift)
│   ├── web/             App FastAPI TorrentMate (SPA + REST + WebSocket)
│   ├── subscribers/     Subscribers EventBus (Redis stream, Telegram…)
│   ├── conf/            Modèles Pydantic + loader JSON5
│   ├── commands/        Groupes de commandes Typer
│   ├── pipeline.py      Orchestrateur séquentiel des étapes
│   └── pipeline_steps.py Registre des étapes du pipeline
├── frontend/            TorrentMateUI (Vite + React + TS)
├── tests/               Tests unitaires + E2E
└── assets/torrents/     Fichiers .torrent pour tests E2E
```

Les dossiers de staging se trouvent dans le dossier défini par `paths.staging_dir` dans `config/paths.json5`.

---

## Notes importantes

- **Toujours `--dry-run` d'abord** — pour chaque étape pipeline (ingest/sort/process/verify/dispatch),
  prévisualiser, vérifier la sortie, puis lancer sans `--dry-run`.
- **Espaces dans les chemins** — toujours mettre les chemins entre guillemets dans le terminal :
  `"/Volumes/Disk1/medias"`.
- **Séparation stricte des providers** — TVDB primaire pour les séries, TMDB pour les films ; jamais de
  contamination croisée entre familles lors de la correspondance dispatch / dedup.
