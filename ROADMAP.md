# ROADMAP — PersonalScraper

> Future ideas. Chaque item passe par son propre brainstorming avant implémentation.
> **Priorité** : **P1** (haute — débloque, à faire tôt) → **P3** (stretch).
> **Vague** : ordre de construction dépendance-correct (voir « Plan de construction »).
> Le travail **shippé n'est pas tracké ici** — voir `CHANGELOG.md` et `docs/archive/features/`.
> Restructuré le **2026-06-01** (brainstorm trackers/ratio/suivi + refacto-prép, analyse
> multi-agents ancrée sur le code réel). `lib-fold` shippé en 0.19.0 → retiré.

---

## 🎯 Vision — la boucle fermée

Système auto-hébergé en **boucle fermée** :

```
ACQUIRE ──▶ TRIAGE ──▶ STORE & INDEX ──▶ SEED / RATIO ──▶ SUPERVISE
(suivi séries     (pipeline rename/    (disques +        (ratio sain sur   (Web UI +
 + auto-download   clean/scrape/        indexer DB)        trackers privés)  Telegram)
 trackers privés)  dispatch existant)                                        │
        ▲──────────────────────────────────────────────────────────────────┘
```

Les nouvelles features (acquisition, ratio, seed-safety) reposent toutes sur **un socle
partagé** : un `DownloadOrchestrator` (RP5) au-dessus d'un client torrent capable d'**ajouter**
et **tagger** (RP1), d'une **config par tracker** (RP2), d'une **persistance d'acquisition**
(`acquire.db`, RP3) et d'un **catalogue d'events** (RP4). On pose ces fondations avant tout.

---

## 🧊 Décisions gelées (brainstorm 2026-06-01)

| # | Décision | Choix retenu |
|---|----------|--------------|
| **Q1** | Détection « nouvel épisode » (suivi séries) | **Calendrier-déclencheur** : RP9 poll les dates de diffusion (TVDB/TMDB) → quand l'air date est passée, l'épisode entre dans une file `wanted` (acquire.db) → recherche **répétée** sur les trackers jusqu'à le trouver (les trackers sont en retard sur la diffusion). |
| **cadence** | Fréquence de recherche des `wanted` | **Backoff par paliers, configurable** (défaut global + override par série) : 🔥 Hot 0–72 h → ~toutes les 2 h ; 🌤 Warm 3–14 j → 1×/jour ; ❄️ Cold 14–30 j → 1×/semaine ; ⛔ cutoff 30 j → stop + notif Telegram. |
| **Q2** | Mesure du ratio par tracker | **Cascade** : endpoint API tracker en priorité **→ fallback agrégation qBittorrent locale** (somme up/down par host) si le tracker n'expose pas son ratio. Capability detection façon registry. |
| **Q3** | Séquencement trackers + radar freeleech | **Spike d'étude d'API → torr9 → digitalcore**. Radar freeleech **R1 conditionnel** : seulement si un tracker expose une API d'énumération de fenêtres ; sinon R1 se réduit à la récolte par recherche (déjà shippée). |
| **Q4** | Frontière de téléchargement du `.torrent` | **PersonalScraper fetch + POST** : on télécharge le `.torrent` (auth gérée) puis on POST le fichier à qBittorrent ; **exception magnet** pour les liens sans auth. Le 401 reste observable/routable (vs qBit qui ne sait pas ré-authentifier un JWT expiré). |

---

## 🗺️ Plan de construction — 7 vagues

Index d'exécution dépendance-correct. `RPx` = refacto-prép (voir section dédiée) ; les codes
`Sx/Dx/Ox/Vx/Cx/R1` = sous-features (voir catalogue). Détail riche dans le **Catalogue** plus bas.

### Vague 1 — Feuilles + amorce des fondations
- **LaCale Deprecation** `[P1]` — désactiver + flag `deprecated` + tests skip.
- **RP1** `[P1, prérequis]` — protocoles d'écriture torrent (`add`/catégorie/limite) + tags `TorrentItem` + Transmission fail-fast. **Pin Q4 ici.**
- **RP1a** `[P1, prérequis]` — frontière fetch (PersonalScraper fetch+POST, exception magnet).
- **RP2** `[P1, parallèle]` — config économie par tracker (`RatioPolicy` + `announce_passkey`) ; **raye le non-goal « no new config schema »**.
- **Reverse Episode Lookup** `[P2]` — autonome, ne dépend que du registry shippé.
- **architecture.md Multi-Filesystem cleanup** `[P3, doc]` — pointeur mort (shippé 0.18.0).

### Vague 2 — Persistance / events + shell de supervision + P2 indépendants
- **RP3** `[P1, parallèle]` — `acquire.db` (`FollowedSeriesRepo` + `SeedObligationRepo` + `may_remove` autorité unique de suppression, *fail-open*).
- **RP4** `[P1, parallèle]` — catalogue d'events d'acquisition + subscriber Telegram (muet jusqu'aux vagues 4–5).
- **Web UI S1** `[P2]` — shell + auth + WebSocket + container headless.
- **Verify V1** `[P2]` — `CheckRegistry` + 2 protocoles (`PreDispatchCheck` Path + `LibraryCheck` entrée).
- **Additional Trackers — spike + torr9** `[P2]` — étude API (Q3), puis torr9 sur le schéma RP2.

### Vague 3 — Le cœur « grab » + le garde-fou
- **RP5** `[P1, prérequis]` — `DownloadOrchestrator` + `AcquisitionService` (câble `TrackerRegistry` dans AppContext ; **absorbe le DI Container**). **Gate de l'épopée.** Contient l'étage **dédup cross-tracker pré-ranking**.
- **Seed Safety O1** `[P2]` — tag « seed-pur » + skip à travers `ingest`/`sort`/`process` + skip Watcher + patch cron 3 h.
- **Seed Safety O2** `[P2]` — politique d'obligation de seed au-dessus de `may_remove` (RP3).
- **RP6** `[P2, parallèle]` — prédicat « je possède déjà » dans `indexer/query.py`.
- **RP7** `[P2, parallèle]` — cycle de vie auth tracker + fraîcheur du grab (`TrackerAuthFailed`).
- **RP9** `[P2, prérequis]` — capability poll des dates de diffusion sur un *set* (après Q1).
- **Freeleech R1** `[P3, conditionnel]` — découverte de fenêtres (seulement si API d'énumération ; sinon récolte par recherche).

### Vague 4 — Acquisition headline + déclencheur de supervision
- **Follow D1** `[P2]` — store + CRUD de la liste suivie (`acquire.db`).
- **Follow D2** `[P2]` — détection calendrier-d'abord (RP9) + file `wanted` + cadence backoff + ownership (RP6).
- **Follow D3** `[P2]` — grab via le cœur partagé (RP5) : dédup cross-tracker + re-résolution URL (RP7) + fetch (RP1a) + tag « contenu utile » (O1).
- **Watcher Service** `[P2]` — remplace le cron ; **décommission du cron 3 h dans le même changement** (pas de double-ingestion).

### Vague 5 — Politique ratio + reste de l'orchestration
- **Ratio C1** `[P3]` — mesure par tracker (Q2 : API→fallback qBit) + boucle de grab vers la cible.
- **Seed Safety O3** `[P2]` — arbitre de budget disque global (**précédence : le vrai média gagne**).
- **Ratio C2** `[P3]` — rotation/LRU (respecte O2, bornée par O3).
- **Ratio C3** `[P3]` — mode hybride « contenu utile » (taggé via O1).
- **Seed Safety O4** `[P2]` — events + caps de bande passante (par torrent **et** global).
- **Verify V2** `[P2]` — CLI granulaire (`verify --check nfo_validity`).
- **Additional Trackers — digitalcore** `[P2]` — second tracker (après torr9).

### Vague 6 — Surfaces de supervision sur l'acquisition désormais vivante
- **Web UI S2** `[P2]` — pipeline control + logs + history.
- **Web UI S3** `[P2]` — maintenance dashboard.
- **Web UI S4** `[P2]` — éditeur de config.
- **Web UI S5** `[P2]` — scraping interactif.
- **Web UI S6** `[P2]` — registry + health (**fusionne Registry Consumer** ; `registry.status()` versionné additif-only).
- **Web UI S7** `[P2]` — pages acquisition/watcher (sur les events RP4).
- **Verify V3** `[P2]` — panneau Web UI par check (sur V1).

### Vague 7 — Déferrals registry + dette + stretch
- **RP8** `[P3, prérequis]` — primitive unique de re-priorisation live (drain + swap atomique).
- **Active Health Scoring — cœur réseau** `[P3]` — au-dessus de RP8.
- **Active Health Scoring — slice ratio** `[P3]` — lit l'état Ratio (après C1).
- **Hot-Swap Provider Config** `[P3]` — au-dessus de RP8.
- **Tech-Debt Round 2** `[P3]`.
- **Follow D4** `[P2→P3]` — overrides + profils qualité par série + cron + renouvellement médiathèque.
- **LLM Pipeline Assistant** `[P3]`.

---

## 🧱 Refacto-prep (RP1–RP9)

> Nouvelles features de **préparation du terrain**, ancrées sur des manques **vérifiés** dans le
> code. On les pose avant les features d'acquisition pour ne pas bâtir sur du sable.

| Code | Prio | Type | Quoi (constat code) | Prépare |
|------|------|------|---------------------|---------|
| **RP1** | P1 | prérequis | `api/_contracts.py` n'a **pas de `add`** ; `TorrentItem` **sans tags** (`qbittorrent.py:259`). Ajouter adder/categorizer/limiter + tags ; **Transmission asserte `TorrentAdder` au démarrage** (fail-fast). Pin Q4. | Orchestration, Follow, Ratio, Watcher, Trackers |
| **RP1a** | P1 | prérequis | JWT lacale / apikey c411 peuvent **401 si qBit fetch lui-même**. → PersonalScraper fetch le `.torrent` puis POST le fichier ; exception magnet sans auth. | Follow, Ratio, Orchestration |
| **RP2** | P1 | parallèle | `TrackerProviderConfig` n'a que `enabled`. Ajouter `RatioPolicy` + `announce_passkey`. **Rayer le non-goal « no new config schema »** des Additional Trackers avant torr9/digitalcore. | Ratio, Trackers, Follow, Orchestration |
| **RP3** | P1 | parallèle | Pas de persistance d'acquisition. Créer `acquire.db` : `FollowedSeriesRepo` + `SeedObligationRepo` + **`may_remove` autorité unique de suppression**, *fail-open* si absent (ne bloque pas `disk_cleaner`). | Follow, Orchestration, Ratio |
| **RP4** | P1 | parallèle | Aucun event d'acquisition. Les définir **une fois** (sous-classes de `Event`) + mapping subscriber Telegram. Muet jusqu'aux vagues 4–5. | Orchestration, Freeleech, Watcher, Follow, Ratio, Web UI |
| **RP5** | P1 | prérequis | `TrackerRegistry` **jamais instancié hors tests** ; AppContext ne le porte pas. Créer `DownloadOrchestrator` + `AcquisitionService` (cœur de grab partagé) ; **absorbe le DI Container**. Gate de l'épopée — Ratio C1 et Follow D3 partagent ce cœur. | Orchestration, Follow, Ratio, Watcher |
| **RP6** | P2 | parallèle | Prédicat « je possède déjà » indéfini. Ajouter `owns_episode` / `owns_movie_at_quality` dans `indexer/query.py` (**pas** `movie_service.py` à 975 LOC). | Follow, Ratio |
| **RP7** | P2 | parallèle | Tokens courts ; le breaker ignore les 4xx. Re-résoudre l'URL avant `add`, émettre `TrackerAuthFailed`. Avec RP1a le 401 est observable. | Follow, Ratio, Trackers, Active Health |
| **RP8** | P3 | prérequis | Hot-Swap **et** Active Health veulent **muter l'ordre du chain à chaud** : une seule primitive sûre (drain + swap atomique). | Active Health, Hot-Swap |
| **RP9** | P2 | prérequis | `chain(EpisodeFetcher)` fetch par série ; un **poll de dates sur un *set*** est neuf. Ajouter `poll_recent_episodes`. Résoudre Q1 d'abord. | Follow |

---

## 📦 Catalogue des features (détail)

### — Acquisition —

#### TVShow Follow & Auto-Download System (D1–D4)

> Refondu 2026-06-01 : le **suivi de séries** est la feature principale ; l'ancien
> « Auto-Download System » (abonnement + recherche multi-trackers + renouvellement) **fusionne
> dedans** comme volets. Découpé en 4 sous-features.

Téléchargement automatique des nouveaux épisodes / saisons des séries d'une **liste suivie**,
recherche sur **tous les trackers actifs**, choix du **meilleur torrent** (filtres durs + score).

- **D1 — Liste + CRUD** : store de séries suivies dans `acquire.db` (`FollowedSeriesRepo`),
  **liste manuelle** (ajouter/retirer), indépendante de la médiathèque.
- **D2 — Détection** : **calendrier-d'abord** (Q1) — RP9 poll les air dates → file `wanted` →
  recherche tracker répétée selon la **cadence backoff** (Hot/Warm/Cold/cutoff, configurable
  globale + par série). Ownership via RP6 (ne pas chercher ce qu'on possède déjà).
- **D3 — Grab (cœur partagé)** : via `DownloadOrchestrator` (RP5).
  - **Filtres durs (éliminatoires)** : piste audio requise (VF/VOSTFR), qualité mini (≥1080p)…
  - **Score pondéré** sur les survivants : seeders, freeleech/économie tracker, source, codec, taille.
  - **Dédup cross-tracker AVANT le ranking** : `_ranking` traite 1 résultat à la fois → on
    regroupe par `info_hash`, on choisit la meilleure provenance, on passe **un** représentant à `score_result`.
  - Re-résolution d'URL (RP7) + fetch (RP1a) + tag « contenu utile » (O1) pour ingestion normale.
- **D4 — Overrides & extras** : règles par critère (studio, réalisateur, franchise, titre, IMDB ID),
  **profils qualité par série** (anime VOSTFR vs série VF), cron, **renouvellement médiathèque**
  (brancher la liste de recommandations sur l'auto-download).

**Depends on** : RP1, RP1a, RP2, RP3, RP5, RP6, RP7, RP9 ; trackers actifs ; `_ranking.py` (shippé).

#### Ratio Management Module (C1–C3)

> Télécharge les torrents les plus **propices au partage** pour faire monter le ratio,
> **tracker par tracker**. Distinct du suivi (on télécharge **pour seeder**) mais modes coexistants.
> Reste **P3** : c'est de la **politique** au-dessus du socle P2.

- **C1 — Mesure + boucle** : ratio par tracker en **cascade** (Q2 : endpoint API → fallback
  agrégation qBit locale). Boucle de grab tant que `ratio < cible` **et** `disque < plafond`
  (config par tracker via RP2).
- **C2 — Rotation/LRU** : suppression jamais avant le **seedtime mini** (politique O2), puis
  **rotation LRU par rentabilité** quand le quota est plein, bornée par l'arbitre disque (O3).
- **C3 — Hybride contenu-utile** : si un torrent à bon swarm correspond à du contenu voulu
  (wishlist/médiathèque, via RP6), on le **garde** (taggé « contenu utile » via O1) au lieu de le jeter.

Critères « propice au partage » : freeleech (priorité, voir R1), ratio seeders/leechers, taille,
fraîcheur, vélocité du swarm.

**Depends on** : RP1, RP1a, RP2, RP3, RP5, RP6 ; Seed Safety O1/O2/O3 ; Freeleech R1 (bonus) ; `_ranking.py`.

#### Download Orchestration & Seed Safety (O1–O4)

> **Couche partagée** (P2) entre les modules qui téléchargent et le client torrent / le triage.
> Sans elle, le seed-pur polluerait la médiathèque et les obligations de seed seraient violées.

- **O1 — Tag « seed-pur » + skip** : catégorie/tag qBittorrent dédiée ; **skip à travers
  `ingest`/`sort`/`process`** ET skip Watcher ; **patch du cron 3 h**. Les grabs « contenu
  utile » sont taggés pour ingestion normale. **Garde-fou anti-pollution médiathèque.**
- **O2 — Obligation de seed / anti-HnR** : politique au-dessus de `may_remove` (RP3) — aucun
  module ne supprime/arrête un torrent avant le seedtime mini du tracker (évite les pénalités HnR).
- **O3 — Arbitre de budget disque global** : applique les quotas (dont le plafond par tracker de
  C1) ; **précédence : le dispatch du vrai média gagne toujours**, l'arbitre ne réserve que
  l'espace non réclamé ; une seule vue partagée de l'espace libre. Relié à `maintenance/`.
- **O4 — Events + caps** : events de download (via RP4) + **caps de bande passante par torrent
  ET globaux**.

**Depends on** : RP1, RP3, RP4 ; client torrent (qBittorrent) ; notifier Telegram ; `maintenance/` (shippé 0.19.0).
**Cadre/bloque** : Watcher, Ratio, TVShow Follow.

#### Additional Trackers (spike → torr9 → digitalcore)

> Remonté P3 → P2 le 2026-06-01 (LaCale tombe → besoin de sources actives). Séquencement Q3.

Implémenter `api/tracker/torr9.py` puis `api/tracker/digitalcore.py` suivant le protocole
`TrackerClient` (0.11.0). **Spike d'étude d'API d'abord** (Torznab/RSS/REST, samples réels,
docs `docs/reference/{torr9,digitalcore}-api.md`), puis torr9, puis digitalcore. Sur l'infra
`HttpTransport` unifiée.

- Deux providers `TrackerClient`, plug-compatibles avec `TrackerRegistry` + `rank()`.
- Capter l'économie par tracker (freeleech, bonus, seedtime mini, passkey) → **via le schéma RP2**.
- Activation via `ProviderActivation`.
- Détecter si le tracker expose une **API d'énumération de fenêtres freeleech** → gate R1 (Q3).

**Non-goals** : nouveaux critères de ranking (le moteur 0.11.0 les supporte déjà).
**Depends on** : RP2 (schéma config), RP7 (auth). ⚠️ L'ancien non-goal « no new config schema » est **rayé** (RP2).

#### Freeleech Radar (R1) — conditionnel

> Module **transverse** partagé par Ratio et Follow. **La plomberie par-résultat est déjà
> shippée** (`is_freeleech` / `FreeleechAware` / bonus `_ranking`). Le seul net-new = la
> **découverte proactive de fenêtres**.

- **R1** : `FreeleechWindowDetected` sur l'Event Bus + découverte de fenêtres — **seulement si
  ≥1 tracker expose une API d'énumération** (sinon R1 se réduit à la récolte par recherche déjà
  shippée). Ratio en fait sa priorité n°1 (gain de ratio à coût nul) ; Follow s'en sert comme
  critère de score.

**Depends on** : Additional Trackers (spike Q3), Event Bus (shippé).

#### Watcher Service

Remplace le déclencheur cron par un service temps-réel.

- Surveille l'état qBittorrent ou le répertoire `complete/` ; déclenche `personalscraper run`.
- **Ignore les torrents taggés « seed-pur »** (contrat O1).
- **Décommission du cron 3 h dans le même changement** (sinon double-ingestion).

**Depends on** : Event Bus (shippé 0.14.0), Pipeline Observer Protocol (shippé 0.13.0), Seed Safety O1.

### — Supervise —

#### Web Management UI (S1–S7)

Interface web pour piloter/superviser tout le projet. Découpée en 7 sous-features.

- **S1** — shell + auth + WebSocket + container headless (**à faire en premier**).
- **S2** — pipeline control : start/pause/resume/kill (`ingest`/`sort`/`process`/`dispatch`), logs live, status, history.
- **S3** — maintenance dashboard : disque/espace libre par disque, orphelins (`_tmp_*`), locks, santé index, historique des runs.
- **S4** — éditeur de config visuel (`config/`) avec validation de schéma + reload sûr.
- **S5** — scraping interactif : points de décision manuels (matches ambigus TMDB/TVDB, picks multi-résultats, arbitrage fuzzy, override titre/année/saison).
- **S6** — registry + health (**fusionne l'ancien « Web UI Registry Consumer »**) : WebSocket sur
  `ProviderFallbackTriggered`/`ProviderExhaustedEvent`/`LockedCapabilityUnresolved`/`RegistryFanOutCompleted`/`RegistryBootValidated`,
  REST `GET /api/registry/{status,operations}`, panneau état circuit + chain + latences fan_out.
  ⚠️ **`registry.status()` versionné additif-only** avant S6 (Active Health en vague 7 l'étend).
- **S7** — pages acquisition/watcher (status, history, CRUD liste suivie, règles override) sur les events RP4.

**Architecture (à trancher en design)** : FastAPI/Flask+HTMX vs SPA+REST/WebSocket ; auth local-only vs basic ;
reverse-proxy friendly (sous-chemin derrière `iznogoudatall.xyz`). **Hors scope v1** : multi-user, contrôle d'agent distant, UX mobile.
**Depends on** : Pipeline Observer (0.13.0), Event Bus (0.14.0), RP4 (pour S7), `registry.status()`/`operations()` (0.16.0, pour S6).

### — Qualité / plateforme —

#### Verify Checker Plugin System (V1–V3)

`verify/checker.py` (822 LOC) est monolithique. Architecture en plugins → checks testables,
extensibles, découvrables par la Web UI. Landing zone de l'ex-`library/validator.py`.

- **V1** — `CheckRegistry` + **deux protocoles** : `PreDispatchCheck` (porte sur `Path`) et
  `LibraryCheck` (valide des lignes, ex-`library_checks.py`) sous un seul registre. Chaque groupe
  existant (NFO, artwork, naming, stream, genre, taille, `no_duplicate_videos`) devient un plugin sous `verify/checks/`.
- **V2** — CLI granulaire : `personalscraper verify --check nfo_validity`.
- **V3** — panneau Web UI par check (liste, run individuel, résultats).

**Non-goals** : changer la logique des checks au-delà de l'extraction.

#### Active Health Scoring (Registry) — au-dessus de RP8

Passer du circuit breaker passif au scoring de santé actif (ping périodique + fenêtre glissante +
dé-priorisation). Mutation de l'ordre du chain **via la primitive RP8**.

- `ProviderHealthMonitor` (tâche de fond AppContext) ; `health_check() -> bool` par provider ;
  EWMA sur N checks ; `chain()` skip sous seuil (re-tenté à la fenêtre suivante) ; `registry.status()` inclut le score.
- **Slice ratio (brainstorm 2026-06-01)** : pour les providers tracker, intégrer l'état de ratio
  (proche de la limite → déprioriser) **en plus** de la santé réseau. Alimenté par Ratio C1 →
  **cette slice attend C1 (vague 5)**.

**Non-goals** : load-balancing actif, routage par région. **Risque** : budget `health_check` à borner.
**Depends on** : Provider Registry (0.16.0), ProviderObserver, **RP8**, RP7 ; slice ratio ⇐ Ratio C1.

#### Hot-Swap Provider Configuration — au-dessus de RP8

Recharger `ProvidersConfig` sur SIGHUP / changement de fichier sans redémarrer.

- File-watcher sur `config/providers.json5` → `validate_config()` → si PASS, **swap atomique via RP8**
  (`_index` + `_priority_for_chain` + `_circuit_breakers`), drain 5 s, event `RegistryHotSwapped`.

**Non-goals** : hot-swap des IMPLÉMENTATIONS (config seulement), config distribuée.
**Depends on** : Provider Registry (0.16.0), `validate_config()` (0.16.0), **RP8**.

#### Reverse Episode Lookup (Standalone)

Trouver SXXEXX pour des épisodes sans numéro via reverse scraping TVDB (fallback TMDB/autres).
Commande autonome, manuelle.

- **Input** : fichier sans SXXEXX (`The Return of the King.mkv`).
- **Reverse** : nettoyer le nom → chercher le titre d'épisode dans TVDB (série déjà identifiée) → `airedSeason`/`airedEpisodeNumber`.
- **Fallback cascade** : TVDB langue scrap → TVDB langue fallback → TMDB → autres.
- **Output** : renommer en `SXXEXX - Episode Name.ext` pour le pipeline standard.
- **CLI** : `personalscraper resolve-episodes <path>` — hors pipeline auto.
- Inspiré de `TVDBNameToNum.py.bak`.

**Depends on** : Provider Registry (0.16.0). _(Vague 1 : autonome, ne touche pas au socle d'acquisition.)_

#### Tech-Debt Round 2 (`tech-debt-2`)

> Status (vérifié 2026-05-28) : pas de crise god-module. `check-module-size.py` exit 0.

- Extraire `scraper/movie_service.py` (954 non-blank, 46 lignes du plafond dur) le long du seam dedup/rename/orphan-unlink.
- Décider la politique de garde-fou `__init__.py` (le check exclut tous les `__init__.py` — masque `api/metadata/registry/__init__.py` à 689 et `indexer/scanner/__init__.py` à 621).
- Sweep large : code mort, `TODO`/`FIXME`/`HACK`, `type: ignore`/`pragma: no cover`, `except` larges, magic values, skips/`xfail` expirés.

**Non-goals** : changements de comportement (déplacements structurels seulement).

#### architecture.md Multi-Filesystem cleanup `[doc]`

Section « Multi-Filesystem » encore marquée *planned* alors que shippée 0.18.0 — seul pointeur
mort restant (la critique « lib-fold encore en P1 » était fausse, lib-fold retiré). Nettoyage doc.

#### LLM Pipeline Assistant (idée, gardée pour la fin)

Connecter un LLM (local/distant) comme assistant d'arbitrage pour les points à décision humaine
(matches ambigus, post-mortem d'erreurs, incohérences). RAG sur la médiathèque + corrections
utilisateur — jamais de fine-tuning, jamais autonome, toujours en validation. Volontairement simple.

Vision/questions ouvertes : `docs/superpowers/roadmap/llm-assistant/brainstorming.md`.
**Brainstorming entamé** (2026-05-11/12) : principes posés, cas d'usage cadrés, stack pressenti
(MCP + sqlite-vec + Ollama + Open WebUI), 3 questions ouvertes. Reprendre via `/brainstorming`.

### — Dépréciations —

#### LaCale Deprecation

LaCale n'existe plus. On **conserve tout le code** (référence pour les futurs trackers) mais on le
marque **déprécié**.

- **Désactivation** via `ProviderActivation` (retiré du registry actif / de l'ordre de préférence).
- **Flag `deprecated`** dans `api/tracker/lacale.py` + warning au boot s'il est activé.
- **Tests/fixtures** marqués `skip` (raison documentée), gardés. `docs/reference/lacale-api.md` conservé.
- **CHANGELOG** : entrée « Deprecated ».

**Non-goals** : suppression du code, du doc ou des fixtures.

---

## 🔀 Journal des fusions & reclassements (2026-06-01)

Issu du brainstorm multi-agents (analyse ancrée sur le code, critique adverse appliquée) :

**Fusions**
- **Web UI Registry Consumer** → page **Web UI S6** (zéro backend indépendant ; `status/operations` shippés 0.16.0).
- **Dependency Injection Container** → **RP5** (le `ServiceContainer`/AppContext doit porter `TrackerRegistry` — c'est le seam RP5).
- **Plomberie par-résultat du Freeleech Radar** → déjà shippée ; seul survivant net-new = **R1** (découverte de fenêtres).
- **Events d'acquisition épars** → **RP4** (un seul catalogue).
- **Mutation Active Health + swap Hot-Swap** → **primitive RP8 unique** (les deux mutent l'ordre du chain à chaud).
- **`verify/library_checks.py`** → 2e protocole dans **Verify V1**.

**Découpes** (features trop grosses → spec-sized)
- Web Management UI → **S1–S7** · TVShow Follow → **D1–D4** · Seed Safety → **O1–O4** · Verify → **V1–V3** · Ratio → **C1–C3** · Freeleech → **R1**.

**Ajouts de cohérence** (sinon la boucle ne tourne pas)
- Dédup cross-tracker **pré-ranking** (dans RP5/D3) · précédence disque réel > seed-pur (O3) ·
  décommission cron 3 h au cutover Watcher · versionnage `registry.status()` avant S6 · cleanup doc Multi-Filesystem.

**Reclassements**
- `lib-fold` (shippé 0.19.0) **retiré**. · LaCale → P1. · torr9+digitalcore P3 → P2. · DI Container → absorbé RP5.

**Reporté (non retenu ce tour-ci)** : confort — bootstrap liste depuis l'indexer, ~~profils qualité par série~~ (intégré à D4), pages Web UI ratio dédiées.

---

## 📜 Journal — demande d'origine (verbatim, 2026-06-01)

- LaCale n'est plus, déprécié, garder le code.
- 2 nouveaux trackers : https://torr9.net/ et https://digitalcore.club/
- Module de gestion du ratio (téléchargement automatique des torrents les plus propices au
  partage afin d'augmenter le ratio). Gestion tracker par tracker.
- Module de suivi tvshows (téléchargement automatique des nouveaux épisodes / nouvelles saisons
  d'une série, parmi une liste de séries suivies) ; recherche sur tous les trackers et choix du
  meilleur torrent selon plusieurs critères (ratio, qualité, piste audio…).

Puis : « on pense aussi architecture en ajoutant des features de refacto si nécessaire pour
préparer le terrain » → RP1–RP9. Le détail raffiné vit dans le Catalogue + le Plan de construction ci-dessus.
