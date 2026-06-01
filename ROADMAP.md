# ROADMAP — PersonalScraper

> Future ideas. Each item gets its own brainstorming session before implementation.
> Priority scale: **P1** (high — unblocks major features, do next) → **P3** (stretch — nice to have, no urgency).
> Shipped work is **not** tracked here — see `CHANGELOG.md` and `docs/archive/features/`.

---

## P1 — High Priority (do next, unblocks major features)

### P1 — LaCale Deprecation

> Ex-stub (a), 2026-06-01.

LaCale n'existe plus en tant que tracker. On **conserve tout le code** mais on le marque
**déprécié** plutôt que de le supprimer (réactivation possible, valeur de référence pour
l'implémentation des futurs trackers — voir P2 Additional Trackers).

**Portée**

- **Désactivation** : retirer LaCale de l'ordre de préférence / du registry actif via le
  mécanisme `ProviderActivation` existant (config) — il ne participe plus aux recherches.
- **Flag `deprecated` explicite** dans le provider (`api/tracker/lacale.py`), avec warning
  au boot s'il est malgré tout activé en config.
- **Tests/fixtures** : marqués `skip` avec raison documentée (deprecated) — gardés dans
  l'arbo, non exécutés. `docs/reference/lacale-api.md` + samples conservés.
- **CHANGELOG** : entrée « Deprecated » signalant le retrait du tracker.

**Non-goals** : suppression du code, du doc de référence ou des fixtures.

> _`lib-fold` (Library / Indexer Consolidation) shippé en 0.19.0 (2026-06-01) — retiré de la
> roadmap conformément à « shipped work is not tracked here ». Détails : `CHANGELOG.md`._

---

## P2 — Medium Priority (important but not blocking)

### P2 — Web Management UI

Web-based graphical interface to pilot and supervise the whole project from a browser.

- **Pipeline control**: start / pause / resume / kill each step (`ingest`, `sort`, `process`, `dispatch`), view live logs, step status, and per-run history.
- **Configuration editor**: visual editor for `config/` (paths, categories, disks, thresholds, patterns) with schema validation and safe reload — no shell required.
- **Maintenance dashboard**: disk usage / free space per disk, orphan files (`_tmp_ingest_*`, `_tmp_dispatch_*`), stale locks, library index health, pipeline-runs history.
- **Interactive scraping**: front-end for the manual-decision points currently handled via MediaElch / CLI prompts — ambiguous TMDB/TVDB matches, multi-result picks, low-fuzzy-score arbitration, manual override of detected title/year/season.
- **Future-ready**: UI shell designed to host pages for upcoming roadmap items, notably:
  - **Auto-Download System** — tracker search, format preferences, subscription list CRUD, override rules editor
  - **Watcher Service** — live watcher status, trigger history
  - **Library Indexer** — browse/search indexed media, trigger re-scan, view stale entries
  - **YoutubeTrailerScraper Integration** — missing-trailer queue, per-item scrape trigger
- **Architecture pointers** (to decide during brainstorm): FastAPI / Flask + HTMX vs. SPA (Vue/React) + REST/WebSocket; auth (local-only vs. basic auth); reverse-proxy friendly (sub-path deploy behind `iznogoudatall.xyz`).
- **Out of scope (v1)**: multi-user, remote-agent control, mobile-specific UX.

**Depends on:** Pipeline Observer Protocol (shipped v0.13.0), Event Bus (shipped v0.14.0), Third-Party API Consumer Unification (shipped v0.11.0). Prerequisite: `arch-cleanup-2` (Event contract + envelope `schema_version`) — shipped v0.17.0 (#28).

### P2 — TVShow Follow & Auto-Download System

> Refondu le 2026-06-01 : le **suivi de séries** (ex-stub (d)) devient la feature
> principale ; l'ancien « Auto-Download System » (abonnement + recherche multi-trackers
> + renouvellement médiathèque) **fusionne dedans** comme volets de la même feature.

Pipeline de téléchargement automatique de torrents avec intégration API tracker, piloté
par une **liste de séries suivies**.

**Suivi de séries (volet principal)**

- **Liste manuelle** de séries suivies, gérée en CRUD (ajouter / retirer), indépendante
  de la médiathèque — on peut suivre une série pas encore possédée.
- **Détection des nouveautés** : nouveaux épisodes et nouvelles saisons des séries suivies.
- **Recherche multi-trackers** : on cherche sur **tous** les trackers actifs.
- **Sélection du meilleur torrent — filtres durs + score** :
  - **Filtres durs (éliminatoires)** : non négociables, ex. piste audio requise (VF/VOSTFR),
    qualité mini (ex. ≥ 1080p). Un torrent qui ne passe pas est écarté d'office.
  - **Score pondéré** sur les survivants pour départager : seeders, freeleech / économie
    de ratio du tracker, source, codec, taille…
  - Réutilise le moteur de ranking `api/tracker/_ranking.py`.
- **Déduplication** vs ce qui est déjà en médiathèque (indexer DB) — ne pas re-télécharger.

**Volets hérités de l'ex-Auto-Download System**

- Formats : format préféré + formats de repli.
- Vérifs cron des nouveaux épisodes (planification).
- Recherche multi-trackers avec ordre de préférence.
- Branchement de la liste de recommandations médiathèque sur l'auto-download (renouvellement).
- Règles d'override par critère : studio, réalisateur, franchise, titre, IMDB ID.

**À affiner en design** (pas maintenant)

- Source « nouvel épisode dispo » : calendrier TVDB/TMDB vs détection par recherche tracker.
- Langue / piste audio voulue par série (filtre dur global vs par série).
- Réglage des poids du score, et articulation avec le module de ratio (c) (un grab peut
  servir le suivi ET le ratio).

**Depends on:** Third-Party API Consumer Unification (shipped v0.11.0), Provider Registry
(shipped v0.16.0), trackers actifs (P2 — Additional Trackers), client torrent (qBittorrent),
**P2 — Download Orchestration & Seed Safety** (tag « contenu utile » pour ingestion +
anti-HnR), **P3 — Freeleech Radar** (critère de score).

### P2 — Additional Trackers (torr9 + digitalcore)

> Remonté de P3 → P2 le 2026-06-01 : avec la dépréciation de LaCale (voir entrée (a)),
> il faut des sources actives. Débloque l'Auto-Download System, le module de ratio (c) et
> le suivi de séries (d), qui ont tous besoin de plusieurs trackers vivants.

Implement `api/tracker/torr9.py` and `api/tracker/digitalcore.py` following the
`TrackerClient` Protocol established in 0.11.0. Study each tracker's API
(Torznab/RSS/REST), capture real-response samples, write reference docs in
`docs/reference/torr9-api.md` and `docs/reference/digitalcore-api.md`, then
implement using the unified `HttpTransport` infrastructure.

**Goals**

- Two new `TrackerClient` providers, plug-compatible with the existing
  `TrackerRegistry` and `rank()` engine.
- Reference docs + sample fixtures so future updates can replay against
  captured responses.
- Activation through the existing `ProviderActivation` mechanism — no new
  config schema.
- Capture per-tracker ratio-economy specifics (freeleech markers, bonus,
  min seedtime, passkey) — feeds the ratio module (c) and the tvshow ranking (d).

**Non-goals**

- New ranking criteria (the engine landed in 0.11.0 already supports
  arbitrary providers).
- Auto-Download System integration — that lands in its own P2 feature.

**Depends on**: Third-Party API Consumer Unification (shipped v0.11.0).

### P2 — Download Orchestration & Seed Safety

> Issu du brainstorm 2026-06-01. **Couche partagée** dont dépendent le module de ratio (c),
> le suivi de séries (d) et le Watcher Service. Sans elle, le seed-pur du ratio polluerait
> la médiathèque et les obligations de seed des trackers privés seraient violées.

Couche transverse entre les modules qui téléchargent (ratio, suivi) et le client torrent /
le pipeline de triage. Trois responsabilités :

- **Tag « seed-pur » / catégorisation des downloads.** Tout torrent grabbé pour le seul
  ratio (c) reçoit une catégorie/tag qBittorrent dédiée. Le **Watcher Service ignore ces
  torrents** (pas de `personalscraper run` déclenché) et le triage ne les voit jamais. Les
  grabs « contenu utile » (suivi (d), mode hybride de (c)) sont au contraire taggés pour
  ingestion normale. **C'est le garde-fou anti-pollution médiathèque.**
- **Suivi des obligations de seed / anti-HnR.** Registre par torrent du seedtime mini exigé
  par le tracker source ; aucun module ne peut supprimer/arrêter un torrent avant échéance.
  Évite les pénalités hit-and-run des trackers privés. Partagé par (c) et (d).
- **Arbitre de budget disque global.** Médiathèque et seed-pur se disputent le disque : un
  arbitre central applique les quotas (dont le plafond par tracker de (c)) et garantit que
  le seed jetable n'affame jamais le vrai stockage. À relier au module `maintenance/`.

- **Notifications** (via le notifier Telegram existant) : centralise les événements de
  download — nouvel épisode grabbé, cible ratio atteinte/en danger, obligation de seed
  proche de l'échéance, suppression seed-pur effectuée.

**Depends on:** client torrent (qBittorrent, shipped), notifier Telegram (shipped),
`maintenance/` (shipped en 0.19.0 via lib-fold). **Bloque (ou cadre) :** Watcher Service,
Ratio Module (c), TVShow Follow (d).

### P2 — Watcher Service

Replace cron-based pipeline trigger with a real-time watcher service.

- Service that watches either qBittorrent state or the `complete/` directory.
- Triggers `personalscraper run` automatically on new downloads.
- **Doit ignorer les torrents taggés « seed-pur »** (voir P2 — Download Orchestration &
  Seed Safety) : ne jamais déclencher `personalscraper run` sur un grab de ratio jetable.
- More responsive than the current 3am daily cron.

**Depends on:** Event Bus (shipped v0.14.0), Pipeline Observer Protocol (shipped v0.13.0). Prerequisite: `arch-cleanup-2` (cross-process event envelope) — shipped v0.17.0 (#28). Tagging contract: **P2 — Download Orchestration & Seed Safety**.

### P2 — Verify Checker Plugin System

`verify/checker.py` (822 LOC, 713 non-blank) is a monolithic file containing all pre-dispatch validation checks. Adding a new check (e.g., a new media type, a new quality rule) requires modifying the file directly. A plugin architecture makes checks independently testable, extensible, and discoverable by the Web UI. This is also the landing zone for `library/validator.py` (see `lib-fold`).

**Goals**

- `Check` Protocol: `severity: Severity`, `category: str`, `check(item: Path, config: Config) -> CheckResult`.
- `CheckRegistry` — checks auto-register via a decorator or entry point.
- Each existing check group (NFO validity, artwork presence, naming conventions, stream details, genre categorization, file size, the Phase 30 `no_duplicate_videos` movie check) becomes its own plugin file under `verify/checks/`.
- Web UI can list available checks, run them individually, and display per-check results.
- CLI gets `personalscraper verify --check nfo_validity` granular invocation.

**Non-goals**

- Changing existing check logic beyond the extraction itself.

### P2 — Reverse Episode Lookup (Standalone)

Find SXXEXX for episodes missing season/episode numbers via reverse scraping on TVDB (TMDB/other fallback). Standalone command invoked manually when needed.

- **Input**: a video file named without SXXEXX (e.g. `The Return of the King.mkv`).
- **Reverse lookup**: clean the filename → search the episode name in TVDB (within the already-identified series) → retrieve `airedSeason` and `airedEpisodeNumber`.
- **Cascading fallback**: TVDB in scraping language → TVDB in fallback language → TMDB → other scrapers.
- **Output**: rename the file to `SXXEXX - Episode Name.ext` so it flows through the standard pipeline.
- **CLI**: `personalscraper resolve-episodes <path>` — standalone, not integrated into the automated pipeline.
- **Codebase**: inspired by the `TVDBNameToNum.py.bak` script (interactive TVDB v3 interface, name cleaning/normalization, fuzzy matching).

**Depends on:** Provider Registry (shipped v0.16.0) for clean provider fallback.

### P2 — Web UI Registry Consumer

**Source**: registry feature DESIGN §11 deferral (recorded in Phase 12 of the registry feature).

**Goal**: Expose ProviderRegistry status + operations to the Web Management UI (P2 above). Surface live provider eligibility, circuit state, fallback history, fan_out attempted lists.

**Dependencies**:

- Web Management UI scaffolding (P2 above).
- `registry.status()` + `registry.operations()` (shipped v0.16.0 — Provider Registry feature).
- Prerequisite: `arch-cleanup-2` (registry events on the base `Event` contract for WebSocket streaming) — shipped v0.17.0 (#28).

**Scope**:

- WebSocket subscription to `ProviderFallbackTriggered`, `ProviderExhaustedEvent`, `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated` events.
- REST endpoint `GET /api/registry/status` returning the dict from `registry.status()`.
- REST endpoint `GET /api/registry/operations` returning the dict from `registry.operations()`.
- UI panel: per-provider circuit state, per-capability priority chain, fan_out latency aggregates.

**Non-goals**:

- Hot-swap (separate ROADMAP entry — see P3 Hot-Swap).
- Provider configuration editing via UI (config file is source-of-truth; UI is read-only).

**Estimated effort**: 1 sprint (5 days) after Web Management UI scaffolding lands.

---

## P3 — Stretch (nice to have, lower urgency)

### P3 — Ratio Management Module

> Ex-stub (c), 2026-06-01.

Téléchargement automatique des torrents les plus propices au partage pour faire monter
le ratio, **tracker par tracker** (chaque tracker a son passkey, ses règles et sa propre
économie de ratio : freeleech, bonus, seedtime mini…). Distinct du suivi de séries /
Auto-Download : ici on télécharge **pour seeder**, pas pour alimenter la médiathèque —
mais les deux modes coexistent (« hybride » ci-dessous).

**Mode de fonctionnement — hybride**

- **Seed pur (jetable)** : grab des torrents qui seedent le mieux (freeleech, gros swarm,
  beaucoup de leechers) indépendamment du contenu, pour le seul ratio.
- **Contenu utile** : si un torrent à bon swarm correspond à du contenu voulu (wishlist /
  complément médiathèque), on le **garde** au lieu de le jeter. Le ratio devient un bonus.

**Pilotage — par tracker, double contrainte**

- **Cible de ratio** (ex. 1.5) : tant que ratio < cible, le module grab ; au-dessus, pause.
- **Plafond disque** (ex. 50 Go) : on grab tant que ratio < cible **sans** dépasser le quota.
- Config indépendante par tracker (cible + quota + seedtime mini propres à chacun).

**Suppression / rotation (contenu jetable) — combiné**

- Jamais avant le **seedtime mini** du tracker (respect des règles).
- Ensuite **rotation LRU par rentabilité** : quand le quota disque est plein, on retire le
  torrent le moins rentable (swarm faible / déjà bien seedé) pour faire de la place.

**À affiner en design** (pas maintenant)

- Critères de « propice au partage » : freeleech, ratio seeders/leechers, taille, fraîcheur,
  vélocité du swarm.
- Intégration client torrent (qBittorrent déjà présent — API, catégories/tags dédiés ratio).
- Mesure du ratio courant par tracker (scrape page profil vs API tracker).
- Garde-fous : ne jamais re-télécharger du contenu déjà en médiathèque ; limites de
  bande passante ; cap nombre de torrents actifs.

**Depends on**: trackers actifs (P2 — Additional Trackers), client torrent (qBittorrent,
shipped), **P2 — Download Orchestration & Seed Safety** (tag seed-pur + anti-HnR + budget
disque), **P3 — Freeleech Radar** (priorité n°1 des grabs). Réutilise le moteur de ranking
`api/tracker/_ranking.py`.

### P3 — Freeleech Radar

> Issu du brainstorm 2026-06-01. Petit module **transverse**, partagé par le module de
> ratio (c) et le suivi de séries (d).

Détecte les fenêtres **freeleech** (et bonus/upload multiplié) sur tous les trackers actifs
et expose l'info aux consommateurs :

- Le **module de ratio (c)** en fait sa priorité n°1 : un grab freeleech = gain de ratio à
  coût nul (rien décompté en download).
- Le **suivi de séries (d)** s'en sert comme critère de score (à qualité/piste égales,
  préférer la source freeleech).

**À affiner** : détection par tracker (flag dans la réponse de recherche vs page dédiée vs
annonce), fraîcheur/expiration de la fenêtre, event `FreeleechWindowDetected` sur l'Event Bus
pour notification (voir Seed Safety).

**Depends on**: trackers actifs (P2 — Additional Trackers), Event Bus (shipped v0.14.0).

### P3 — Tech-Debt Round 2 (`tech-debt-2`)

> Design: `docs/features/tech-debt-2/DESIGN.md` _(to be written)_. Source analysis: `docs/analysis/03-god-modules-debt-audit.md` + a forthcoming broad debt sweep.

**Status correction (verified 2026-05-28, HEAD `79b345d8`):** the god-module "crisis" the older
ROADMAP described **no longer exists**. `python3 scripts/check-module-size.py` exits **0** (no
hard-block breach); only **two** files exceed the 800 non-blank soft-warn ceiling:
`scraper/movie_service.py` (**954** non-blank — grew from 927 via the Phase 30 orphan-unlink fix,
now 46 lines from the 1000 hard ceiling) and `library/scanner.py` (**855** non-blank, removed by
`lib-fold`). The previously-listed offenders are all under ceiling now: `indexer/scanner/__init__.py`
621, `trailers/state.py` 767, `trailers/cli.py` 698, `indexer/db.py` 588. `scraper/tmdb_client.py`
no longer exists (split into `api/metadata/tmdb.py` + `api/metadata/_tmdb_parsers.py`).

**Real blind spot:** `check-module-size.py` excludes **all** `__init__.py` files (line 22/37),
hiding two facade modules carrying heavy logic: `api/metadata/registry/__init__.py` (689 non-blank —
the largest module by this metric) and `indexer/scanner/__init__.py` (621). The guardrail policy is
the decision to make.

**Goals**

- Extract `scraper/movie_service.py` along its dedup/rename/orphan-unlink seam to get it back under 800 and away from the hard ceiling.
- Decide and implement the `__init__.py` guardrail policy (count facade modules, or enforce re-exports-only).
- Run a broad debt sweep (dead code, `TODO`/`FIXME`/`HACK`, `type: ignore` / `pragma: no cover` debt, broad `except`, magic values, test skips / `xfail` / `skip_audit` expiries) and fold the actionable items into the design.

**Non-goals**

- Behaviour changes during extraction — structural moves only.

### P3 — LLM Pipeline Assistant (idée, gardée pour la fin)

Connecter un LLM (local et/ou distant) comme assistant d'arbitrage pour les
points du pipeline qui requièrent aujourd'hui une décision humaine (matches
ambigus TMDB/TVDB, post-mortem d'erreurs, détection d'incohérences). L'IA
s'imprègne de la médiathèque existante et apprend des corrections utilisateur
via RAG — jamais de fine-tuning, jamais autonome, toujours en validation.
Principe directeur : feature volontairement simple à implémenter.

Vision et questions ouvertes (document vivant, pas de plan technique) :
`docs/superpowers/roadmap/llm-assistant/brainstorming.md`

**Brainstorming déjà entamé** (2026-05-11/12) : principes directeurs posés,
cas d'usage cadrés (pipeline + médiathèque), stack pressenti identifié
(MCP server + sqlite-vec + Ollama + Open WebUI compatible), 3 questions
ouvertes restantes (log de corrections, indexation initiale, confidentialité
backend distant). Reprendre la prochaine session via `/brainstorming` sur ce
document — pas besoin de repartir de zéro.

### P3 — Dependency Injection Container

Components directly instantiate their dependencies (e.g., `Scraper.__init__` creates its own `TMDBClient`, `TVDBClient`, `NFOGenerator`, `ArtworkDownloader`). This makes testing harder (requires monkeypatching) and blocks the Web UI from swapping real implementations for mocks. May be partly absorbed by `arch-cleanup-2` if a `ServiceContainer` lands there first.

**Goals**

- Lightweight DI container (no framework — a simple `AppContext` dataclass or `ServiceContainer` with factory functions).
- All domain services accept their dependencies via `__init__`, never create them internally.
- CLI wiring creates the production container; tests create a test container; Web UI creates a headless container.

**Non-goals**

- Runtime service hot-swap.
- Full-blown DI framework (no `dependency-injector`, no decorator-based injection).

### P3 — Active Health Scoring (Registry)

**Source**: registry feature DESIGN §11 deferral (recorded in Phase 12 of the registry feature).

**Goal**: Move from passive circuit breaker (per-call failure threshold) to active health scoring (periodic ping + rolling window + provider de-prioritization).

**Dependencies**:

- Provider Registry framework (shipped v0.16.0).
- ProviderObserver protocol (already defined for circuit transitions).

**Scope**:

- New `ProviderHealthMonitor` running as a background AppContext-scoped task.
- Each provider exposes `health_check() -> bool` (cheap synthetic call).
- Rolling window of last N health checks, exponentially-weighted moving average.
- `chain()` consults health score: providers below threshold are skipped (not removed — re-attempted on next health window).
- `registry.status()` includes per-provider health score.
- **Économie de ratio dans le score (brainstorm 2026-06-01)** : pour les providers tracker,
  intégrer l'état de ratio (proche de la limite tracker → déprioriser) en plus de la santé
  réseau. Un tracker où ton ratio est en danger est temporairement écarté des recherches
  d'auto-download/suivi. Alimenté par le module de ratio (c).

**Non-goals**:

- Active load balancing.
- Per-region provider routing.

**Risk**: health_check budget for each provider must be defined to avoid quota burn.

**Estimated effort**: 1 sprint (5 days).

### P3 — Hot-Swap Provider Configuration

**Source**: registry feature DESIGN §11 deferral (recorded in Phase 12 of the registry feature).

**Goal**: Reload `ProvidersConfig` on SIGHUP or config-file change without restarting the process. Currently registry is constructed once at AppContext init; config changes require restart.

**Dependencies**:

- Provider Registry framework (shipped v0.16.0).
- `validate_config()` (shipped v0.16.0, used at boot — re-usable for hot reload).

**Scope**:

- File-watcher on `config/providers.json5` (using `watchdog` or polling).
- On change: call `validate_config()` → if PASS, atomically swap `ProviderRegistry._index` + `_priority_for_chain` + `_circuit_breakers`.
- Drain in-flight calls before swap (5 s grace period).
- Emit new event `RegistryHotSwapped(...)` with diff summary.

**Non-goals**:

- Hot-swap of provider IMPLEMENTATIONS (only config). Adding a new provider class still requires restart.
- Distributed config (single-process only).

**Risk**: Race conditions on circuit breaker state during swap. Mitigate with explicit drain protocol.

**Estimated effort**: 2 sprints (10 days).

---

## Journal — ajouts 2026-06-01 (résolus)

Quatre demandes ajoutées puis raffinées en mini-brainstorm, désormais classées :

- **(a) Dépréciation LaCale** → **P1 — LaCale Deprecation** (section P1).
- **(b) Nouveaux trackers torr9 + digitalcore** → fusionné dans **P2 — Additional Trackers**
  (remonté de P3 → P2).
- **(c) Module de ratio** → **P3 — Ratio Management Module** (section P3).
- **(d) Suivi de séries** → devenu le volet principal de **P2 — TVShow Follow &
  Auto-Download System** (a absorbé l'ancien Auto-Download System).

Brainstorm phase 3 — nouvelles entrées dérivées (glu d'intégration + synergies) :

- **Glu critique** → **P2 — Download Orchestration & Seed Safety** (tag seed-pur ignoré par
  le Watcher/triage, suivi anti-HnR des obligations de seed, arbitre de budget disque
  global, + notifications Telegram).
- **Radar freeleech** → **P3 — Freeleech Radar** (transverse, partagé par (c) et (d)).
- **Économie tracker → health** → bullet ajouté à **P3 — Active Health Scoring**.
- *(Reporté : confort 7-8-9 — bootstrap liste depuis indexer, profils qualité par série,
  pages Web UI ratio + CRUD liste. Non retenu ce tour-ci.)*

Demande utilisateur d'origine (verbatim) :

- LaCale n'est plus, déprécié, garder le code.
- 2 nouveaux trackers : https://torr9.net/ et https://digitalcore.club/
- Module de gestion du ratio (téléchargement automatique des torrents les plus propices
  au partage afin d'augmenter le ratio). Gestion tracker par tracker.
- Module de suivi tvshows (téléchargement automatique des nouveaux épisodes / nouvelles
  saisons d'une série, parmi une liste de séries suivies) ; recherche sur tous les
  trackers et choix du meilleur torrent selon plusieurs critères (ratio, qualité, piste
  audio…).

Le détail raffiné vit désormais dans les entrées P1/P2/P3 listées ci-dessus.
