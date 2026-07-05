# Configuration

Guide de configuration — overlays `config/` et credentials `.env` pour **TorrentMate**.

> Pour les règles de fusion des overlays (ordre, `ConfigConflictError`, `local.json5`
> last-wins) et l'appartenance des clés fichier par fichier, voir
> [docs/reference/config-overlay-layout.md](docs/reference/config-overlay-layout.md).
> Le décompte à jour est **18 overlays + 1 master `config.json5` = 19 fichiers de
> config au total** (le doc de référence peut encore mentionner un chiffre antérieur).

**Deux sources de configuration :**

- **`config/`** — 19 fichiers JSON5 (chemins, disques, catégories, patterns, seuils,
  providers, torrent, tracker, ranking, notify, trailers, indexeur, acquire, watch,
  web…). Créé via `torrentmate init-config` depuis `config.example/`.
- **`.env`** — **uniquement** les credentials (clés API, mots de passe, tokens, secrets
  web). Template : `.env.example`. Le modèle `_StrictModel` (`extra="forbid"`) empêche
  tout secret de se glisser par erreur dans un overlay.

> Voir aussi : [INSTALLATION.md](INSTALLATION.md) (installation) | [MANUAL.md](MANUAL.md) (utilisation)

## Mise en place

```bash
# 1. Créer la configuration (copie config.example/ → config/)
torrentmate init-config

# 2. Configurer les credentials
cp .env.example .env
# Éditer .env pour renseigner les clés API et secrets
```

Le fichier `.env` est chargé automatiquement via
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) (chemin
résolu relativement au package, pas au CWD). Il contient **uniquement** les secrets.
Toute la configuration structurelle est dans `config/`.

> **Ne jamais commiter `.env` ni `config/`** — ils sont dans `.gitignore`. Utiliser
> `.env.example` et `config.example/` comme templates de référence.

> **Pré-1.0** : `config_version` vaut `1`. Pas de script de migration ni de
> rétro-compatibilité — la config, la BDD et les NFO évoluent en même temps que le code
> sur l'unique instance.

---

## Le minimum pour démarrer

Pour un premier run fonctionnel, seuls ces éléments sont **obligatoires** :

| Source                  | Clé                                               | Pourquoi                            |
| ----------------------- | ------------------------------------------------- | ----------------------------------- |
| `config/paths.json5`    | `torrent_complete_dir`, `staging_dir`             | Points d'entrée/sortie du pipeline  |
| `config/disks.json5`    | au moins 1 disque (`id`, `path`, `categories`)    | Destinations de stockage            |
| `config/patterns.json5` | `staging_dirs` avec exactement 1 `role: "ingest"` | Point d'entrée des téléchargements  |
| `.env`                  | `TMDB_API_KEY` + `TVDB_API_KEY`                   | Scrape films (TMDB) + séries (TVDB) |
| `.env`                  | `QBIT_USERNAME` + `QBIT_PASSWORD`                 | Client torrent actif (qBittorrent)  |

Tout le reste (trackers, trailers, notifications, indexeur, acquire, cross-seed, web UI,
OMDb/Trakt) est **optionnel** — le pipeline démarre sans, chaque brique manquante est
simplement désactivée (`provider_disabled` journalisé, jamais de crash).

---

## Structure des overlays `config/`

### `config.json5` (master)

| Clé              | Type      | Défaut | Rôle                                                |
| ---------------- | --------- | ------ | --------------------------------------------------- |
| `config_version` | int       | `1`    | Version de schéma pour migrations futures           |
| `overlays`       | list[str] | —      | Liste ordonnée des overlays fusionnés (18 fichiers) |

Les overlays sont fusionnés **dans cet ordre exact** ; deux overlays ne peuvent pas
partager une même clé top-level (sinon `ConfigConflictError`). Un `local.json5`
optionnel (gitignoré) est fusionné en dernier, last-wins, sans erreur de conflit — pour
surcharger une clé sur une machine donnée sans toucher aux overlays versionnés. (Le clone
de staging, lui, ne passe **pas** par `local.json5` : il partage la config de prod via
`PERSONALSCRAPER_CONFIG` et fixe son port avec le flag CLI `web --port 8711` de PM2 —
voir `ecosystem.config.js`.)

### Overlay → clés top-level possédées

| Overlay            | Clé(s) top-level                                                                   |
| ------------------ | ---------------------------------------------------------------------------------- |
| `paths.json5`      | `paths`                                                                            |
| `disks.json5`      | `disks`                                                                            |
| `categories.json5` | `custom_categories`, `categories`, `category_rules`, `anime_rule`, `genre_mapping` |
| `patterns.json5`   | `staging_dirs`                                                                     |
| `encoding.json5`   | `library`                                                                          |
| `scraper.json5`    | `scraper`, `ingest`, `fuzzy_match` (+ `sort`, `process_clean` par défaut)          |
| `trailers.json5`   | `trailers`                                                                         |
| `indexer.json5`    | `indexer`                                                                          |
| `acquire.json5`    | `acquire`                                                                          |
| `thresholds.json5` | `thresholds`                                                                       |
| `metadata.json5`   | `metadata`                                                                         |
| `providers.json5`  | `providers`                                                                        |
| `torrent.json5`    | `torrent`                                                                          |
| `tracker.json5`    | `tracker`                                                                          |
| `ranking.json5`    | `ranking`                                                                          |
| `notify.json5`     | `notify`                                                                           |
| `watch_seed.json5` | `cross_seed`, `watch`                                                              |
| `web.json5`        | `web`                                                                              |

---

## Chemins — `paths.json5`

Bloc `paths`. **Attention aux espaces** dans les chemins (json5 les accepte sans quoting,
mais tout appel shell qui consomme ces chemins doit les entourer de guillemets).

| Clé                    | Type | Défaut                    | Rôle                                                |
| ---------------------- | ---- | ------------------------- | --------------------------------------------------- |
| `torrent_complete_dir` | Path | **requis**                | Dossier où qBittorrent dépose les torrents terminés |
| `staging_dir`          | Path | **requis** (`./staging/`) | Zone de staging intermédiaire avant dispatch        |
| `data_dir`             | Path | `./.data`                 | État du pipeline (index, locks, analyses)           |

- Les chemins relatifs se résolvent **contre la racine du projet** (`config_dir.parent`),
  pas contre le CWD ; ils doivent être absolus après `init-config`.
- L'arborescence de staging est créée automatiquement au premier lancement.
- Chemins dérivés auto-remplis si non définis : `indexer.db_path` → `data_dir/library.db`,
  `acquire.db_path` → `data_dir/acquire.db`, `trailers.state_file` → `data_dir/trailers_state.json`.

---

## Disques — `disks.json5`

`disks: list[DiskConfig]` (au moins 1 entrée).

| Clé          | Type                                                                  | Défaut     | Rôle                                                         |
| ------------ | --------------------------------------------------------------------- | ---------- | ------------------------------------------------------------ |
| `id`         | str (`^[a-z][a-z0-9_]*$`)                                             | **requis** | Identifiant libre, unique ; utilisé par `--disk` et les logs |
| `path`       | Path                                                                  | **requis** | Chemin monté absolu                                          |
| `categories` | list[str] (≥1)                                                        | **requis** | IDs de catégories acceptés sur ce disque                     |
| `fs_type`    | `ntfs_macfuse`\|`apfs`\|`hfsplus`\|`exfat`\|`ext4`\|`unknown`\|`null` | `null`     | Type de FS ; `null` = auto-détection via FsProbe             |

> Une faute de frappe dans `fs_type` (`ntfs`, `APFS`…) lève une `ValidationError` — pas de
> dégradation silencieuse.

---

## Catégories — `categories.json5`

**11 catégories builtin** : `movies`, `movies_animation`, `movies_documentary`,
`tv_shows`, `tv_shows_animation`, `tv_shows_documentary`, `anime`, `audiobooks`,
`standup`, `theater`, `tv_programs`.

- **`custom_categories: list[str]`** (défaut `[]`) — IDs supplémentaires, chacun matchant
  `^[a-z][a-z0-9_]*$` et sans collision avec un builtin.
- **`categories: dict[str, CategoryConfig]`** (défaut `{}`) — par ID : `folder_name`
  (requis, nom du dossier sur disque), `aliases` (list[str], labels acceptés par
  `--category`). Sans entrée, le label par défaut = l'ID avec `_` → espace.
- **`category_rules: list[CategoryRule]`** (défaut `[]`) — règles évaluées dans l'ordre,
  premier match gagne, **avant** `genre_mapping`. Exactement un champ `match_*` par règle :
  `path_contains`, `path_regex`, `title_regex`, `tmdb_genre_contains`, `tmdb_keyword`
  (list, match si ≥1 présent). Plus `applies_to` (`movie`\|`tv`\|`both`, défaut `both`) et
  `category` (requis, résultat).
- **`anime_rule: AnimeRule`** (TMDB n'a pas de genre « Anime ») : `enabled` (`true`),
  `requires_genre_id` (`16` = Animation TMDB), `requires_origin_country` (`["JP"]`),
  `maps_to` (`anime`), `applies_to` (`tv`).
- **`genre_mapping: GenreMapping`** — `genre_id` → `category_id` par provider :
  `tmdb_movies`, `tmdb_tv`, `tvdb` (dict[int,str], défaut `{}`), plus
  `default_movies_category` (`movies`) et `default_tv_category` (`tv_shows`).

> Tous les IDs de catégorie référencés (clés `categories`, `disks`, valeurs
> `genre_mapping`, `anime_rule.maps_to`, `category_rules.category`) doivent appartenir à
> l'ensemble connu (builtins + `custom_categories`) — validé au chargement.

---

## Disposition du staging — `patterns.json5`

`staging_dirs: list[StagingDirConfig]` (**requis**). Nom du dossier sur disque =
`f"{id:03d}-{name.upper()}"`.

| Champ       | Type                             | Défaut | Rôle                                                              |
| ----------- | -------------------------------- | ------ | ----------------------------------------------------------------- |
| `id`        | int [0–999]                      | requis | Préfixe numérique, unique                                         |
| `name`      | str (`^[a-z0-9]+(-[a-z0-9]+)*$`) | requis | Label kebab-case, mis en majuscules pour le dossier               |
| `file_type` | str\|null                        | `null` | Membre FileType : `movie`,`tvshow`,`ebook`,`audio`,`app`,`other`  |
| `role`      | `ingest`\|null                   | `null` | Seul `ingest` est défini ; **exactement une** entrée doit l'avoir |

> L'entrée `ingest` est le point d'entrée des nouveaux téléchargements. Exemple template :
> `1-movies`, `2-tvshows`, `3-ebooks`, `4-audio`, `5-apps`, `6-android`,
> `97-temp` (role `ingest`), `98-autres`.

---

## Préférences bibliothèque / encodage — `encoding.json5`

Bloc `library`.

**`library.video` (VideoPrefs) :**

| Clé                    | Type      | Défaut              | Rôle                              |
| ---------------------- | --------- | ------------------- | --------------------------------- |
| `preferred_codec`      | str       | `hevc`              | Codec cible des recommandations   |
| `fallback_codecs`      | list[str] | `["av1"]`           | Codecs acceptables (non signalés) |
| `rejected_codecs`      | list[str] | `["mpeg2","mpeg4"]` | Codecs toujours signalés          |
| `preferred_resolution` | str       | `1080p`             | Résolution cible                  |
| `max_size_movie_gb`    | float     | `4.0`               | Taille max d'un fichier film (Go) |
| `max_size_episode_gb`  | float     | `2.0`               | Taille max d'un épisode (Go)      |

> Validateur : les codecs préférés + fallback doivent être disjoints des rejetés.

- **`library.audio.profile_priority: list[str]`** — défaut `["multi","vf","vostfr","vo"]`.
- **`library.subtitles.required_languages: list[str]`** — défaut `["fra"]` (codes ISO 639-2/T ; erreur si absents).
- **`library.encoding_rules: list[EncodingRule]`** (défaut `[]`) — surcharges par média :
  `criteria` (au moins un de `genre`/`title`/`tmdb_id`) + au moins une cible parmi
  `resolution`, `codec`, `max_size_gb`.

---

## Scraper / ingest / fuzzy — `scraper.json5`

**`scraper` (ScraperConfig)** — langues des requêtes API :

| Clé                    | Défaut    | Rôle                                                                 |
| ---------------------- | --------- | -------------------------------------------------------------------- |
| `language`             | `fr-FR`   | Langue principale (BCP-47 côté TMDB ; converti en interne pour TVDB) |
| `fallback_language`    | `en-US`   | Repli quand la traduction principale manque                          |
| `prefer_local_title`   | `true`    | Préférer le titre dans la langue configurée pour le nommage          |
| `episode_default_name` | `Episode` | Préfixe d'un titre d'épisode synthétique (→ « Episode 8 »)           |
| `artwork_language`     | `en`      | Langue préférée pour les artworks (ISO 639-1)                        |

**`ingest.min_ratio: float`** — défaut `0.0` (désactivé). Ratio de seeding minimum pour
l'éligibilité à l'ingest.

**`fuzzy_match` (FuzzyMatchConfig) :**

| Clé                     | Défaut | Rôle                                                   |
| ----------------------- | ------ | ------------------------------------------------------ |
| `min_length_ratio`      | `0.67` | Rejet si `len(court)/len(long)` en dessous de ce seuil |
| `short_title_length`    | `10`   | Frontière titres courts/longs                          |
| `short_title_threshold` | `95.0` | Score WRatio requis pour les titres courts             |
| `long_title_threshold`  | `90.0` | Score WRatio requis pour les titres longs              |

**Défaut-only (valides mais absents du template) :**

- `sort.verify_seed_pure: bool` — défaut `false`. **Appliqué** si `true` (torrents
  terminés taggés seed-pure exclus du sort).
- `process_clean.verify_seed_pure: bool` — défaut `false`. **Réservé** — `true` lève une
  `ValueError` (garde côté clean volontairement non implémentée).

> Le format suit la convention `{langue}-{PAYS}` : `fr-FR`, `en-US`, `de-DE`, `es-ES`,
> `ja-JP`. Les défauts conviennent à une bibliothèque francophone.

---

## Seuils d'espace + circuit breaker — `thresholds.json5`

| Clé                         | Défaut | Rôle                                                           |
| --------------------------- | ------ | -------------------------------------------------------------- |
| `min_free_space_staging_gb` | `20`   | Espace libre min (Go) sur le disque de staging avant ingest    |
| `min_free_space_disk_gb`    | `100`  | Espace libre min (Go) sur un disque de stockage avant dispatch |
| `circuit_breaker_threshold` | `5`    | Erreurs API consécutives avant ouverture du circuit            |
| `circuit_breaker_cooldown`  | `300`  | Secondes avant re-tentative après ouverture                    |

> **Formule de dispatch** : un disque est éligible si
> `free_space_gb >= max(min_free_gb, item_size_gb * 1.5)` — marge garantie même pour les
> gros fichiers.

**Circuit breaker** — protège des pannes durables TMDB/TVDB :

- **CLOSED** (normal) : les appels passent, les 5xx/timeout/connexion sont comptés.
- **OPEN** (après N erreurs) : échec immédiat (`CircuitOpenError`), bascule sur le provider
  alternatif (TMDB↔TVDB).
- **HALF_OPEN** (après cooldown) : un seul appel test — succès → CLOSED, échec → OPEN.

> Le circuit ne compte PAS les 429 (rate limit, gérés par tenacity) ni les 4xx (erreurs client).

---

## Métadonnées — `metadata.json5`

Bloc `metadata`.

- **`metadata.providers: dict[str, {enabled: bool}]`** — template : `tmdb=true`,
  `tvdb=true`, `omdb=false`, `imdb=false`, `rotten_tomatoes=false`, `trakt=false`. Les
  credentials passent par `.env` (`TMDB_API_KEY`, `TVDB_API_KEY`, `OMDB_API_KEY` pour les
  façades omdb/imdb/rotten_tomatoes, `TRAKT_CLIENT_ID`).
- **`metadata.priorities` (MetadataPriorities)** — chaque champ est `dict[str,int]`
  (plus petit = prioritaire), défaut `{}` : `movie_scraping` (template `tmdb:1,tvdb:2`),
  `series_scraping` (`tvdb:1,tmdb:2`), `episode_scraping` (`tvdb:1,tmdb:2`),
  `recommendations` (`trakt:1,omdb:2`), `notations` (`imdb:1,rotten_tomatoes:2,omdb:3,trakt:4`).
- **`metadata.defaults`** : `language` (`fr-FR`), `fallback_language` (`en-US`),
  `prefer_local_title` (`true`).
- **`metadata.episode_scraping_policy`** (défaut-only) : `lock_to_series_provider`
  (`true` — épisodes récupérés uniquement chez le provider qui a matché la série),
  `allow_synthetic_rename_on_unmatched` (`false` — sinon les fichiers dont la
  saison/épisode est absente du provider verrouillé restent à la racine avec leur nom brut).
- **`metadata.season_pack_policy`** (défaut-only) — gestion des « Intégrale » mono-fichier :
  `enabled` (`true`), `markers` (défaut `["integrale","integral","complete","complet",
"coffret","full.season","full season","season.pack","season pack"]`, insensible aux
  accents/casse).

---

## Registre des providers — `providers.json5`

Bloc `providers`, indexé par nom de Protocole de capacité → `dict[provider, entier > 0]`
(plus petit = prioritaire). `extra="forbid"` ; priorités dupliquées dans une même section
= erreur. Toutes les sections défaut `{}`.

| Section                  | Valeur template                                         |
| ------------------------ | ------------------------------------------------------- |
| `Searchable`             | `{tvdb:1, tmdb:2}`                                      |
| `MovieDetailsProvider`   | `{tmdb:1, tvdb:2}`                                      |
| `TvDetailsProvider`      | `{tvdb:1, tmdb:2}`                                      |
| `EpisodeFetcher`         | `{tvdb:1, tmdb:2}`                                      |
| `RatingProvider`         | `{}` (ajouter imdb/rotten_tomatoes avec `OMDB_API_KEY`) |
| `ArtworkProvider`        | `{tmdb:1, tvdb:2}`                                      |
| `KeywordProvider`        | `{}` (nécessite un pont IDCrossRef)                     |
| `VideoProvider`          | `{tmdb:1, tvdb:2}`                                      |
| `RecommendationProvider` | `{}` (seul trakt)                                       |
| `IDValidator`            | `{}` (seul imdb/OMDb)                                   |
| `IDCrossRef`             | `{}` (seul imdb/OMDb)                                   |

---

## Clients torrent — `torrent.json5`

Bloc `torrent`.

| Clé       | Type                          | Défaut (template)    | Rôle                           |
| --------- | ----------------------------- | -------------------- | ------------------------------ |
| `active`  | str                           | `""` (`qbittorrent`) | Nom de l'UNIQUE client utilisé |
| `clients` | dict[str, TorrentClientEntry] | `{}`                 | Config par client              |

Par client : `enabled` (défaut `true`), `host` (défaut `localhost`), `port` (défaut
`8080`). Template : `qbittorrent {enabled:true, localhost:8080}`,
`transmission {enabled:false, localhost:9091}`. **Credentials via `.env`** :
`QBIT_USERNAME`/`QBIT_PASSWORD`, `TRANSMISSION_USERNAME`/`TRANSMISSION_PASSWORD`.

> Host + port sont **canoniques dans `config/torrent.json5`** ; seuls les credentials vont
> dans `.env`. (`QBIT_HOST`/`QBIT_PORT` existent encore comme champs `Settings` pour
> rétro-compat, mais la valeur consommée est celle de `torrent.json5`.)

---

## Trackers — `tracker.json5`

Bloc `tracker`.

| Clé                      | Type                             | Défaut (template)                  | Rôle                                  |
| ------------------------ | -------------------------------- | ---------------------------------- | ------------------------------------- |
| `providers`              | dict[str, TrackerProviderConfig] | `{}` (lacale, c411, torr9)         | Config par tracker                    |
| `priority`               | list[str]                        | `[]` (`["lacale","c411","torr9"]`) | Ordre de fallback                     |
| `priority_by_media_type` | dict[str, list[str]]             | `{}`                               | Surcharge par type de média (validée) |
| `max_total_results`      | int                              | `50`                               | Cap global de résultats               |
| `max_per_tracker`        | int                              | `30`                               | Cap par tracker                       |
| `timeout_per_tracker`    | int                              | `15`                               | Timeout HTTP par tracker (s)          |

Par provider (TrackerProviderConfig) : `enabled` (défaut `false`), `cross_seed`
(`false`), `enrich_seeders` (`false`), `enrich_seeders_top_k` (`10`), `economy`
(TrackerEconomyConfig\|null, `null`).

**TrackerEconomyConfig** (bloc optionnel) : `target_ratio` (requis), `min_ratio` (`1.0`),
`min_seed_time` (requis ; durées humanisées `72h`/`3d` → secondes), `hit_and_run_grace`
(`0`, humanisé). Validé : `target_ratio ≥ min_ratio`, valeurs finies et ≥0.

**Credentials `.env`** (gating) : `LACALE_API_KEY`, `C411_API_KEY`,
`TORR9_USERNAME`+`TORR9_PASSWORD`. Passkeys optionnels **non-gating** : `LACALE_PASSKEY`,
`C411_PASSKEY`, `TORR9_PASSKEY`.

---

## Ranking — `ranking.json5`

Bloc `ranking`.

| Clé           | Type                   | Défaut                          | Rôle                         |
| ------------- | ---------------------- | ------------------------------- | ---------------------------- |
| `criteria`    | list[RankingCriterion] | `[]`                            | Critères de scoring ordonnés |
| `bonuses`     | RankingBonuses         | `{freeleech:10, silverleech:5}` | Points bonus                 |
| `min_seeders` | int                    | `1`                             | Seeders min pour être retenu |

`RankingCriterion` : `field` (requis), `weight` (`1.0`), `values` (dict[str,int]\|null),
`thresholds` (list[ThresholdEntry]\|null), `prefer` (`higher`\|`lower`\|null).
`ThresholdEntry` : `at` (int ; tailles octets type `"1GB"` parsées via ByteSize), `score`.
Le template couvre resolution (w4), codec (w3), format (w2), audio (w2), source (w2),
seeders (w1, thresholds), size (w1, byte-size thresholds).

---

## Notifications — `notify.json5`

Bloc `notify`.

| Clé                      | Type              | Défaut                | Rôle                                                    |
| ------------------------ | ----------------- | --------------------- | ------------------------------------------------------- |
| `telegram`               | `{enabled: bool}` | `{enabled:false}`     | Bot Telegram (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) |
| `healthchecks`           | `{enabled: bool}` | `{enabled:false}`     | Ping Healthchecks (`HEALTHCHECK_URL`)                   |
| `acquire_notify_enabled` | bool              | `false` (défaut-only) | Autorise le subscriber d'acquisition muté à notifier    |

---

## Trailers — `trailers.json5`

Bloc `trailers`.

| Clé                       | Type             | Défaut                                  | Rôle                                                      |
| ------------------------- | ---------------- | --------------------------------------- | --------------------------------------------------------- |
| `enabled`                 | bool             | `false`                                 | Interrupteur maître                                       |
| `languages`               | list[str] (≥1)   | `["fr-FR","en-US"]`                     | Langues de recherche vidéo TMDB (ordonnées)               |
| `search_query_format`     | str              | `"{title} {year} bande annonce"`        | Requête YouTube si TMDB vide (`{title}`,`{year}`)         |
| `state_file`              | str\|null        | `null` → `data_dir/trailers_state.json` | État par item média                                       |
| `retry_after_days`        | list[int≥0] (≥1) | `[1,7,30]`                              | Back-off après un échec                                   |
| `fallback_youtube_search` | bool             | `true`                                  | Sur échec URL TMDB, alt recherche YouTube + 1 re-download |

**Réglages avancés (essentiellement défaut-only) :**

- `filters` : `min_file_size_bytes` (`102400`), `max_filesize_mb` (`500`),
  `allowed_extensions` (`["mp4","mkv","webm"]`).
- `circuit_breakers` : `tmdb_videos` (`errors_threshold:5, cooldown_sec:1800`),
  `youtube` (`5, 3600`).
- `youtube_api` : `daily_quota_units` (`10000`), `search_list_cost_units` (`100`).
- `ytdlp` : `format` (`bestvideo[height<=1080]+bestaudio/best[height<=1080]`),
  `socket_timeout_sec` (`30`), `retries` (`3`).
- `step.max_duration_sec` (`1800`), `pipeline` (`skip:false`, `continue_on_error:false`),
  `seasons.enabled` (`false`), `library_check` (`movies:false`, `tv_shows:true`).

> Placement conforme Plex : films à plat, séries dans un sous-dossier `Trailers/`.
> **ffmpeg requis sur le PATH** pour le download yt-dlp.

---

## Indexeur — `indexer.json5`

Bloc `indexer`.

| Clé       | Type       | Défaut                         | Rôle                                                                                                |
| --------- | ---------- | ------------------------------ | --------------------------------------------------------------------------------------------------- |
| `db_path` | Path\|null | `null` → `data_dir/library.db` | BDD SQLite. Rejetée sur mount WAL-unsafe (ntfs_macfuse/unknown, ou sous `/Volumes/` non détectable) |

**`indexer.scan` (IndexerScanConfig) :**

| Clé                             | Défaut (template)      | Rôle                                                      |
| ------------------------------- | ---------------------- | --------------------------------------------------------- |
| `budget_seconds`                | `1800`                 | Cap de temps dur par run de scan                          |
| `checkpoint_every_n_files`      | `100`                  | Granularité de reprise après crash                        |
| `max_workers_total`             | `4` (template `2`)     | Workers parallèles max (plafonné au nb de disques montés) |
| `n_strikes_for_softdelete`      | `3`                    | Scans manqués avant `deleted_at`                          |
| `read_rate_mb_per_sec`          | `null` (template `80`) | Throttle IO MB/s ; `null` = illimité                      |
| `drop_indexes_during_full_scan` | `true`                 | Drop/rebuild des index non-PK sur cold scan               |
| `paranoia_window_seconds`       | `86400`                | Fenêtre de recheck outbox récent en mode quick ; 0 = off  |

- `indexer.drift.merkle_delta_freeze_threshold` (0–1, défaut `0.50`) — halte le scan si le
  delta Merkle dépasse ce seuil (garde bulk-restore) ; `1.0` = désactivé.
- `indexer.spotlight.use_when_available` (défaut `true`) — délègue la détection de
  changement à Spotlight (APFS uniquement).
- `indexer.log.deleted_item_retention_days` (défaut `365`) — jours avant purge dure des tombstones.
- `indexer.post_dispatch_maintenance.enabled` (défaut `true`) — scan+relink+fix-season-counts
  auto par disque après tout dispatch ayant déplacé ≥1 item.

---

## Acquire — `acquire.json5`

Bloc `acquire`.

| Clé       | Type          | Défaut                         | Rôle                                                      |
| --------- | ------------- | ------------------------------ | --------------------------------------------------------- |
| `db_path` | Path\|null    | `null` → `data_dir/acquire.db` | BDD SQLite acquire (même rejet WAL-unsafe que l'indexeur) |
| `cadence` | CadenceConfig | tiers canoniques               | Politique de re-recherche Hot/Warm/Cold                   |

**`acquire.cadence` (CadenceConfig) :**

- `tiers: list[CadenceTierConfig]` — défaut Hot `{max_age_hours:72, interval_minutes:120}`,
  Warm `{336, 1440}`, Cold `{720, 10080}`. Chaque tier : `max_age_hours`, `interval_minutes`.
- `cutoff_days` — défaut `30`. Âge où un item wanted est abandonné.
- Validé : tiers non vides, valeurs >0, `max_age_hours` strictement croissant,
  `cutoff_days*24 ≥ max_age_hours du dernier tier`.

---

## Watch / cross-seed — `watch_seed.json5`

**`cross_seed` (CrossSeedConfig) :**

| Clé                            | Type          | Défaut  | Rôle                                                  |
| ------------------------------ | ------------- | ------- | ----------------------------------------------------- |
| `enabled`                      | bool          | `false` | Kill-switch de toute activité cross-seed              |
| `max_searches_per_day`         | int≥1         | `250`   | Quota journalier des recherches back-catalog          |
| `min_delay_between_searches_s` | int≥5         | `30`    | Throttle entre deux recherches                        |
| `exclude_recent_search_days`   | int≥1         | `3`     | Ignore les info_hashes cherchés < N jours             |
| `verify_timeout_s`             | int [30–7200] | `900`   | Attente max du recheck client d'un cross-seed injecté |

**`watch` (WatchConfig)** — daemon watcher (piloté par PM2) :

| Clé                | Type           | Défaut  | Rôle                                                      |
| ------------------ | -------------- | ------- | --------------------------------------------------------- |
| `enabled`          | bool           | `false` | Kill-switch du daemon                                     |
| `poll_interval_s`  | int [10–3600]  | `60`    | Secondes entre deux cycles de poll                        |
| `debounce_s`       | int [60–86400] | `900`   | Fenêtre calme après un déclenchement de pipeline          |
| `safety_net_hours` | int [1–168]    | `24`    | Déclenche un run filet de sécurité si aucun succès en N h |

> Le filet de sécurité (`safety_net_hours`, défaut 24h) garantit un run au maximum toutes
> les 24h même sans nouveau torrent — cohérent avec un check Healthchecks à période 1 jour.

---

## Web UI TorrentMate — `web.json5`

Bloc `web`. Sert l'interface web TorrentMate (`torrentmate web`).

| Clé                 | Type | Défaut                     | Rôle                                                                                                      |
| ------------------- | ---- | -------------------------- | --------------------------------------------------------------------------------------------------------- |
| `enabled`           | bool | `true`                     | Kill-switch ; si `false`, `torrentmate web` s'arrête aussitôt                                             |
| `host`              | str  | `127.0.0.1`                | Adresse de bind uvicorn                                                                                   |
| `port`              | int  | `8710`                     | Port TCP uvicorn (clone staging → `8711` via le flag CLI `web --port 8711` de PM2, `ecosystem.config.js`) |
| `username`          | str  | `izno`                     | Nom d'utilisateur de connexion (mono-utilisateur)                                                         |
| `redis_url`         | str  | `redis://127.0.0.1:6379/0` | URL Redis pour le relais d'événements                                                                     |
| `stream_key`        | str  | `personalscraper:events`   | Clé du Redis Stream de publication d'événements                                                           |
| `stream_maxlen`     | int  | `10000`                    | Nb max d'entrées conservées dans le Stream                                                                |
| `session_ttl_hours` | int  | `720` (30 j)               | Durée de vie du cookie de session JWT (heures)                                                            |
| `cookie_secure`     | bool | `true`                     | Flag Secure sur le cookie de session (nécessite HTTPS)                                                    |
| `dev_mode`          | bool | `false`                    | Si `true`, démarre sans SPA buildé (proxy Vite dev)                                                       |

> Les secrets de la web UI sont dans `.env` : `WEB_PASSWORD_HASH` (hash scrypt) et
> `WEB_JWT_SECRET` (secret HS256). Voir la section credentials ci-dessous.

---

# Credentials — `.env`

Les secrets se chargent via `pydantic-settings` (`Settings` dans
`personalscraper/config.py`), plus les credentials d'activation des trackers/providers via
`os.environ` à travers `PROVIDER_CREDS` / `PROVIDER_OPTIONAL_SECRETS`
(`personalscraper/api/_activation.py`). **Un provider n'est activé que si son toggle config
est `enabled: true` ET que ses credentials requis sont présents** ; un credential manquant
journalise `provider_disabled` et saute le provider (jamais de crash).

> **Masquage** : `qbit_password`, `tmdb_api_key`, `tvdb_api_key`, `youtube_api_key`,
> `telegram_bot_token`, `healthcheck_url`, `web_password_hash`, `web_jwt_secret` sont
> `<masked>` dans les repr/tracebacks.

---

## 1. Métadonnées (TVDB / TMDB / OMDB / Trakt)

| Variable           | Requis                           | Défaut | Rôle                                                                                                                                           |
| ------------------ | -------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `TVDB_API_KEY`     | **Requis** pour le scrape séries | `""`   | Clé TheTVDB (« Negotiated Contract ») — provider TV primaire                                                                                   |
| `TMDB_API_KEY`     | **Requis** pour le scrape films  | `""`   | Clé TMDB (Bearer token) — films + fallback/info séries                                                                                         |
| `OMDB_API_KEY`     | Optionnel                        | `""`   | Active le backfill de notes OMDb/IMDb/Rotten Tomatoes. Une clé alimente les 3 façades. Vide = backfill notes ignoré                            |
| `OMDB_DAILY_LIMIT` | Optionnel                        | `1000` | **Réservé** — présent (commenté) dans `.env.example` mais **non consommé au runtime actuellement** (aucun code ne le lit dans l'environnement) |
| `TRAKT_CLIENT_ID`  | Optionnel                        | `""`   | Auth app-only (header `trakt-api-key`). Active RecommendationProvider + Searchable/Details/notations/related/trending                          |

**Comment obtenir chaque clé :**

- **TVDB** — Créer un compte sur [thetvdb.com](https://thetvdb.com/auth/register), puis
  générer une clé de type **Negotiated Contract** (gratuit usage perso) sur
  [thetvdb.com/api-information](https://thetvdb.com/api-information) (ou
  Dashboard > Account > API Keys). Le pipeline s'authentifie avec `{"apikey": "..."}`
  uniquement, sans champ `pin`. Codes langue à 3 lettres (`fra`,`eng`), convertis
  automatiquement depuis `fr-FR`.
- **TMDB** — Créer un compte sur [themoviedb.org](https://www.themoviedb.org/signup), puis
  Settings > API ([lien](https://www.themoviedb.org/settings/api)) > Create > Developer.
  Copier la **API Key (v3 auth)**. Rate limit ~40 req/10 s, retries gérés par tenacity.
- **OMDb** — Demander une clé gratuite sur
  [omdbapi.com/apikey.aspx](http://www.omdbapi.com/apikey.aspx) (1000 req/jour), valider par
  email.
- **Trakt** — Créer une app sur
  [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications), copier le **Client
  ID** (le Client Secret OAuth est volontairement hors scope).

```ini
TMDB_API_KEY=abcdef1234567890abcdef1234567890
TVDB_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# Optionnels
OMDB_API_KEY=xxxxxxxx
# OMDB_DAILY_LIMIT=1000
TRAKT_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 2. Clients torrent (qBittorrent / Transmission)

| Variable                | Requis                                 | Défaut  | Rôle                                             |
| ----------------------- | -------------------------------------- | ------- | ------------------------------------------------ |
| `QBIT_USERNAME`         | Requis pour activer qBittorrent        | `admin` | Login Web API qBittorrent                        |
| `QBIT_PASSWORD`         | Requis pour activer qBittorrent        | `""`    | Mot de passe Web API (**masqué**)                |
| `TRANSMISSION_USERNAME` | Requis si `transmission.enabled: true` | (aucun) | User RPC Transmission (absent de `.env.example`) |
| `TRANSMISSION_PASSWORD` | Requis si `transmission.enabled: true` | (aucun) | Mot de passe RPC Transmission                    |

**Comment obtenir :** dans qBittorrent, Options > Web UI (user par défaut `admin`, définir
le mot de passe). Pour Transmission : settings > Remote/RPC auth.

> Host + port ne vont PAS dans `.env` — ils sont dans `config/torrent.json5`
> (`clients.qbittorrent.host/.port`, `transmission.host/.port`). Seuls les credentials ici.

```ini
QBIT_USERNAME=admin
QBIT_PASSWORD=mon_mot_de_passe
```

---

## 3. Trackers (LaCale / C411 / torr9)

Les clés API sont **gating** (une clé manquante désactive le tracker) ; les passkeys sont
**optionnels et non-gating** (jamais désactivants — usage seeding Vague-5 à venir).

| Variable         | Tracker | Requis                     | Rôle                                                          |
| ---------------- | ------- | -------------------------- | ------------------------------------------------------------- |
| `LACALE_API_KEY` | LaCale  | Requis pour activer LaCale | Clé API de recherche (distincte du passkey announce)          |
| `LACALE_PASSKEY` | LaCale  | Optionnel (non-gating)     | Passkey announce BitTorrent (commenté dans `.env.example`)    |
| `C411_API_KEY`   | C411    | Requis pour activer C411   | Clé API de recherche                                          |
| `C411_PASSKEY`   | C411    | Optionnel (non-gating)     | Passkey announce (commenté dans `.env.example`)               |
| `TORR9_USERNAME` | torr9   | Requis pour activer torr9  | Login (tracker style JWT)                                     |
| `TORR9_PASSWORD` | torr9   | Requis pour activer torr9  | Mot de passe                                                  |
| `TORR9_PASSKEY`  | torr9   | Optionnel (non-gating)     | Passkey RSS freeleech (documenté dans `config/tracker.json5`) |

> Ces clés proviennent de votre compte sur chaque tracker (page API/profil). Elles ne sont
> lues que si le tracker est `enabled: true` dans `config/tracker.json5`.

> **Absentes du template `.env.example`** (comme `TRANSMISSION_USERNAME`) : `LACALE_API_KEY`,
> `C411_API_KEY`, `TORR9_USERNAME`, `TORR9_PASSWORD`, `TORR9_PASSKEY` — à ajouter manuellement
> au `.env`. (Seuls `LACALE_PASSKEY` / `C411_PASSKEY` figurent, commentés, dans le template.)

---

## 4. Notifications (Telegram / Healthchecks)

| Variable             | Requis                         | Défaut | Rôle                                                          |
| -------------------- | ------------------------------ | ------ | ------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | Optionnel (les 2 pour activer) | `""`   | Token du bot (**masqué**)                                     |
| `TELEGRAM_CHAT_ID`   | Optionnel (les 2 pour activer) | `""`   | ID du chat/utilisateur cible                                  |
| `HEALTHCHECK_URL`    | Optionnel                      | `""`   | URL de ping Healthchecks (auth-in-URL, **masqué**, fail-soft) |

**Telegram :**

1. Chercher **@BotFather** sur Telegram, envoyer `/newbot`, choisir nom + username →
   BotFather retourne un token type `123456789:ABCDef...`.
2. Envoyer un message au bot, puis ouvrir
   `https://api.telegram.org/bot<TOKEN>/getUpdates` et lire `"chat":{"id": ...}` (ou
   utiliser @userinfobot). Pour un groupe, l'ID est négatif (ex `-1001234567890`).

**Healthchecks :** créer un compte sur [healthchecks.io](https://healthchecks.io) (ou
instance auto-hébergée), créer un check (Period 1 day, Grace 1 hour), copier l'URL de ping.
Le pipeline pinge au début (`/start`), au succès, et à l'échec (`/fail`).

```ini
TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz
TELEGRAM_CHAT_ID=123456789
HEALTHCHECK_URL=https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## 5. Trailers (YouTube Data API + cookies + ffmpeg)

> **ffmpeg requis sur le PATH** (`brew install ffmpeg` / `apt-get install ffmpeg`) — pas
> une variable d'env, mais une dépendance runtime dure de la feature trailers.

| Variable                       | Requis    | Défaut | Rôle                                                                                                                                               |
| ------------------------------ | --------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `YOUTUBE_API_KEY`              | Optionnel | `""`   | Clé YouTube Data API v3 (**masquée**). Vide → fallback yt-dlp `ytsearch1` (plus lent, sans quota). 100 unités par `search.list`, quota 10 000/jour |
| `YOUTUBE_COOKIES_FILE`         | Optionnel | `""`   | Fichier `cookies.txt` Netscape (Option A — stockage APFS natif, mode `600`)                                                                        |
| `YOUTUBE_COOKIES_FROM_BROWSER` | Optionnel | `""`   | Extraction live d'un profil (Option B — `firefox`,`chrome`,`chromium`,`edge`,`opera`,`brave`,`safari`)                                             |

Clé API : [Google Cloud Console](https://console.developers.google.com/apis/api/youtube.googleapis.com).

```ini
YOUTUBE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# YOUTUBE_COOKIES_FILE=/path/to/cookies.txt
# YOUTUBE_COOKIES_FROM_BROWSER=firefox
```

---

## 6. Web UI TorrentMate

| Variable            | Requis                         | Défaut | Génération                                                                                                   |
| ------------------- | ------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------ |
| `WEB_PASSWORD_HASH` | Requis pour activer l'auth web | `""`   | Hash scrypt (`scrypt$N$r$p$salt$hash`, **masqué**). Généré par `torrentmate web set-password`                |
| `WEB_JWT_SECRET`    | Requis pour activer l'auth web | `""`   | Secret HS256 des JWT de session (**masqué**). `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

```bash
# Générer le hash de mot de passe (écrit WEB_PASSWORD_HASH pour vous)
torrentmate web set-password

# Générer le secret JWT
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```ini
WEB_PASSWORD_HASH=scrypt$16384$8$1$...$...
WEB_JWT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> Les réglages non-secrets de la web UI (host, port, redis_url, TTL de session…) sont dans
> `config/web.json5`, pas ici.

---

## 7. Divers

| Variable                       | Requis    | Défaut | Rôle                                                                                                                                           |
| ------------------------------ | --------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `LIBRARY_ANALYZER_MAX_WORKERS` | Optionnel | `4`    | **Réservé** — présent (commenté) dans `.env.example` mais **non consommé au runtime actuellement** (aucun code ne le lit dans l'environnement) |

---

## Exemple complet

### `.env` (credentials uniquement)

```ini
# ── qBittorrent (host/port → config/torrent.json5) ──
QBIT_USERNAME=admin
QBIT_PASSWORD=mon_mot_de_passe

# ── TMDB / TVDB (requis pour le scrape) ─────────────
TMDB_API_KEY=abcdef1234567890abcdef1234567890
TVDB_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# ── Backfill notes / IDs (optionnel) ────────────────
OMDB_API_KEY=xxxxxxxx
TRAKT_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Trackers (optionnel, gating si enabled) ─────────
# LACALE_API_KEY=...
# C411_API_KEY=...
# TORR9_USERNAME=...
# TORR9_PASSWORD=...

# ── Notifications (optionnel) ───────────────────────
TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz
TELEGRAM_CHAT_ID=123456789
HEALTHCHECK_URL=https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# ── Trailers (optionnel, ffmpeg requis) ─────────────
YOUTUBE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# YOUTUBE_COOKIES_FROM_BROWSER=firefox

# ── Web UI TorrentMate (optionnel) ──────────────────
WEB_PASSWORD_HASH=scrypt$16384$8$1$...$...
WEB_JWT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### `config/thresholds.json5`

```json5
{
  min_free_space_staging_gb: 20,
  min_free_space_disk_gb: 100,
  circuit_breaker_threshold: 5,
  circuit_breaker_cooldown: 300,
}
```

### `config/scraper.json5` (extrait)

```json5
{
  scraper: {
    language: "fr-FR",
    fallback_language: "en-US",
    prefer_local_title: true,
    episode_default_name: "Episode",
    artwork_language: "en",
  },
  ingest: { min_ratio: 0.0 },
  fuzzy_match: {
    min_length_ratio: 0.67,
    short_title_length: 10,
    short_title_threshold: 95.0,
    long_title_threshold: 90.0,
  },
}
```

---

## Dépannage

### Le pipeline ne trouve pas le `.env`

Le fichier `.env` doit être à la racine du projet.

```bash
ls -la "/path/to/torrent-mate/.env"
```

### Les clés API ne fonctionnent pas

```bash
# TMDB
curl --connect-timeout 10 --max-time 30 \
  "https://api.themoviedb.org/3/movie/550?api_key=VOTRE_CLE" | python -m json.tool

# TVDB (authentification)
curl --connect-timeout 10 --max-time 30 -X POST "https://api4.thetvdb.com/v4/login" \
  -H "Content-Type: application/json" \
  -d '{"apikey": "VOTRE_CLE"}' | python -m json.tool
```

### qBittorrent refuse la connexion

1. Vérifier que l'interface Web est activée (Preferences > Web UI).
2. Vérifier le host/port dans `config/torrent.json5` :
   `curl --connect-timeout 10 --max-time 30 -s http://localhost:8080/api/v2/app/version`
3. « Unauthorized » : vérifier `QBIT_USERNAME`/`QBIT_PASSWORD` dans `.env`.
4. Timeout : vérifier que qBittorrent tourne (`pgrep -l qbittorrent`).

### Un provider/tracker est ignoré

Un `provider_disabled` dans les logs = toggle `enabled: false` dans l'overlay concerné, ou
credential requis absent du `.env`. Vérifier les deux (toggle + credential) — l'activation
exige les deux.
