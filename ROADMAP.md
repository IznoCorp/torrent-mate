# ROADMAP — PersonalScraper

> Future ideas. Chaque item passe par son propre brainstorming avant implémentation.
> **Priorité** : **P1** (haute — débloque, à faire tôt) → **P3** (stretch).
> **Vague** : ordre de construction dépendance-correct (voir « Plan de construction »).
> Le travail **shippé n'est pas tracké ici** — voir `CHANGELOG.md` et `docs/archive/features/`.
> Restructuré le **2026-06-01** (brainstorm trackers/ratio/suivi + refacto-prép, analyse
> multi-agents). `lib-fold` déjà shippé → retiré.

> ⚠️ **Les références au code sont des INDICES datés (2026-06-01), pas des contrats.** Chemins,
> noms de méthodes/classes, capacités décrites, mentions « shippé » : le code évolue. Re-vérifier
> l'état réel **au moment de prendre une vague** et mettre à jour l'entrée concernée. Cette roadmap
> décrit l'**intention** (quoi / pourquoi), pas le design.

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
partagé** : un **cœur de téléchargement** (RP5) au-dessus d'un client torrent capable
d'**ajouter** et **tagger** (RP1), d'une **config par tracker** (RP2), d'une **persistance
d'acquisition** (RP3) et d'un **catalogue d'events** (RP4). On pose ces fondations avant tout.

---

## 🏛 Architecture cible (intention)

> Vers quoi la roadmap **converge**. Niveau intention — **pas un design**. Chaque item sert cette
> cible plutôt que de s'empiler. (Issu de la revue d'archi multi-agents, 2026-06-02.)

- **Un lobe `acquire/` de premier niveau** — package pair de `ingest`/`sort`/`dispatch`/`indexer`,
  home de l'orchestrateur, du service d'acquisition, de Follow, Ratio, Seed-Safety et du Watcher.
  Il dépend **vers le bas** des ports `api/` (tracker, torrent, transport) + de son store
  `acquire.db`, et **n'importe jamais** les packages de triage.
- **Un seul seam triage ↔ acquisition** — tout le contact se réduit au **tag seed-pur /
  contenu-utile** (champ `tags`, RP1) : l'acquisition l'écrit, le triage le lit et skippe, le
  Watcher (qui remplace le cron 3 h) consomme le même contrat. Aucun autre couplage.
- **State partitionné, autorités uniques** — `library.db` reste l'autorité **single-writer** du
  *possédé* (lue en SELECT-only à travers la frontière par le prédicat d'ownership, RP6) ;
  `acquire.db` possède le *désiré / obligation* sous sa propre discipline single-writer. **Une
  seule** autorité d'espace libre, lue par dispatch (owner de fait), maintenance et l'arbitre O3.
- **Composition root unique** — un seul site de construction du contexte applicatif, étendu d'**une**
  poignée d'acquisition (+ le registre de trackers), jamais N champs (sinon le contexte gelé dérive
  en service-locator).
- **Contrôle direct, EventBus observe-only** — l'acquisition s'orchestre en appels directs
  top-down ; l'EventBus porte **un** catalogue d'events que SUPERVISE (Telegram + read-models
  Web UI) consomme ; les actions d'écriture Web UI passent par la **même autorité de déclenchement**
  (lock pipeline) que le Watcher.
- **Direction d'import garantie** — le garde-fou de layering est étendu pour imposer que `acquire/`
  dépende vers le bas, jamais l'inverse (RP-layer).

---

## 🧊 Décisions gelées (brainstorm 2026-06-01)

| # | Décision | Choix retenu |
|---|----------|--------------|
| **Q1** | Détection « nouvel épisode » (suivi séries) | **Calendrier-déclencheur** : on poll les dates de diffusion (TVDB/TMDB) → quand l'air date est passée, l'épisode entre dans une file `wanted` → recherche **répétée** sur les trackers jusqu'à le trouver (les trackers sont en retard sur la diffusion). |
| **cadence** | Fréquence de recherche des `wanted` | **Backoff par paliers, configurable** (défaut global + override par série) : 🔥 Hot 0–72 h → ~toutes les 2 h ; 🌤 Warm 3–14 j → 1×/jour ; ❄️ Cold 14–30 j → 1×/semaine ; ⛔ cutoff 30 j → stop + notif Telegram. |
| **Q2** | Mesure du ratio par tracker | **Cascade** : endpoint API tracker en priorité **→ fallback agrégation qBittorrent locale** (somme up/down par host) si le tracker n'expose pas son ratio. Détection de capacité façon registry. |
| **Q3** | Séquencement trackers + radar freeleech | **Spike d'étude d'API → torr9 → digitalcore**. Radar freeleech **R1 conditionnel** : seulement si un tracker expose une API d'énumération de fenêtres ; sinon R1 se réduit à la récolte par recherche (déjà shippée). |
| **Q4** | Frontière de téléchargement du `.torrent` | **PersonalScraper fetch + POST** : on télécharge le `.torrent` (auth gérée) puis on POST le fichier à qBittorrent ; **exception magnet** pour les liens sans auth. Le 401 reste observable/routable (vs qBit qui ne sait pas ré-authentifier un jeton expiré). |

---

## 🗺️ Plan de construction — 7 vagues

Index d'exécution dépendance-correct. `RPx` = refacto-prép (voir section dédiée) ; les codes
`Sx/Dx/Ox/Vx/Cx/R1` = sous-features (voir catalogue). Détail riche dans le **Catalogue** plus bas.

### Vague 1 — Feuilles + amorce des fondations
- **LaCale Deprecation** `[P1]` — désactiver + flag `deprecated` + tests skip.
- **RP1** `[P1, prérequis]` — protocole d'écriture torrent (ajout/catégorie/limite) + tags sur l'item torrent + Transmission fail-fast. **Pin Q4 ici.**
- **RP1a** `[P1, prérequis]` — frontière fetch (PersonalScraper fetch+POST, exception magnet).
- **RP2** `[P1, parallèle]` — config économie par tracker (politique de ratio + secret d'annonce) ; **raye le non-goal « no new config schema »**.
- **Name-keyed matching E1** `[P2]` — rattrapage par nom quand le numéro d'épisode est absent (mode 1) + flag non bloquant si nom/numéro divergent franchement, le numéro restant la clé (mode 2). Léger, dans le triage.
- **architecture.md Multi-Filesystem cleanup** `[P3, doc]` — pointeur mort (shippé).

### Vague 2 — Persistance / events + composition root + package `acquire/` + shell de supervision
- **RP3** `[P1, parallèle]` — store `acquire.db` (séparé de `library.db`) : suivies + `wanted` + obligations + état ratio ; single-writer partitionné ; autorité de suppression *fail-open* (qui décide vs qui exécute).
- **RP3a** `[P2, prérequis]` — modèle de domaine **« item désiré »** partagé (Follow/Ratio/Renouvellement/E2), contrat d'entrée de l'orchestrateur. Vit dans `acquire/`.
- **RP4** `[P1, parallèle]` — catalogue d'events d'acquisition + subscriber Telegram (muet) ; **enregistrer le module producteur dans le hub eager-import**.
- **RP5a** `[P1, prérequis]` — câbler le registre de trackers dans le composition root + **factory config-driven + validation au boot** à parité avec metadata.
- **RP5c** `[P1, prérequis]` — package **`acquire/`** de premier niveau (home orchestrateur/Follow/Ratio/Seed-Safety/Watcher) + **une seule poignée** au composition root.
- **RP-layer** `[P2, parallèle]` — étendre le garde-fou de layering pour la direction d'import de `acquire/`.
- **Web UI S1** `[P2]` — shell + auth + WebSocket + container headless.
- **Verify V1** `[P2]` — registre de checks + 2 protocoles (check pré-dispatch sur chemin + check de lignes médiathèque).
- **Additional Trackers — spike** `[P2]` — étude d'API (Q3), dépend de RP2 seulement.

### Vague 3 — Le cœur « grab » + le garde-fou
- **RP5b** `[P1, prérequis]` — cœur de grab partagé (orchestrateur + service d'acquisition) au-dessus de RP5a. **Gate de l'épopée.** Contient l'étage **dédup cross-tracker pré-ranking**.
- **Seed Safety O1** `[P2]` — tag « seed-pur » + skip à travers `ingest`/`sort`/`process` ; **définit le contrat de skip que le Watcher (vague 4) consommera**.
- **Seed Safety O2** `[P2]` — politique d'obligation de seed au-dessus de l'autorité de suppression (RP3).
- **RP6** `[P2, parallèle]` — prédicat « je possède déjà » dans la couche de requête de l'indexer.
- **RP7** `[P2, parallèle]` — cycle de vie auth tracker + fraîcheur du grab (event d'échec d'auth).
- **RP9** `[P2, prérequis]` — capacité de poll des dates de diffusion sur un *ensemble* (après Q1).
- **Additional Trackers — torr9** `[P2]` — premier tracker, après RP7 (auth).
- **Freeleech R1** `[P3, conditionnel]` — découverte de fenêtres (seulement si API d'énumération ; sinon récolte par recherche).

### Vague 4 — Acquisition headline + déclencheur de supervision
- **Follow D1** `[P2]` — store + CRUD de la liste suivie.
- **Follow D2** `[P2]` — détection calendrier-d'abord (RP9) + file `wanted` + cadence backoff + ownership (RP6).
- **Follow D3** `[P2]` — grab via le cœur partagé (RP5b) : dédup cross-tracker + re-résolution URL (RP7) + fetch (RP1a) + tag « contenu utile » (O1).
- **Watcher Service** `[P2]` — remplace le cron ; **décommission du cron 3 h dans le même changement** (pas de double-ingestion) ; consomme le contrat de skip seed-pur d'O1 ; **autorité de déclenchement unique** (lock pipeline) — Watcher, cron-remplacement et actions Web UI ne sont pas des writers parallèles.

### Vague 5 — Politique ratio + reste de l'orchestration
- **Ratio C1** `[P3]` — mesure par tracker (Q2 : API→fallback qBit, lit le plafond par tracker de RP2) + boucle de grab vers la cible.
- **Seed Safety O3** `[P2]` — arbitre de budget disque global (**précédence : le vrai média gagne**). **Une seule** autorité d'espace libre lue par dispatch (owner de fait) / maintenance / O3 — pas trois calculs. Précède C2.
- **Ratio C2** `[P3]` — rotation/LRU (respecte O2, bornée par O3).
- **Ratio C3** `[P3]` — mode hybride « contenu utile » (taggé via O1).
- **Seed Safety O4** `[P2]` — events + caps de bande passante (par torrent **et** global).
- **Verify V2** `[P2]` — CLI granulaire (`verify --check nfo_validity`).
- **Correction name-keyed E2** `[P3]` — re-scrape par nom depuis le download d'origine (re-téléchargé si parti) quand une mauvaise numérotation est constatée dans Plex. Dépend du cœur de grab (RP5b) + trackers.
- **Additional Trackers — digitalcore** `[P2]` — second tracker (après torr9).

### Vague 6 — Surfaces de supervision sur l'acquisition désormais vivante
- **Web UI S2** `[P2]` — pipeline control + logs + history.
- **Web UI S3** `[P2]` — maintenance dashboard.
- **Web UI S4** `[P2]` — éditeur de config. ⚠️ « reload sûr » dépend d'un reload qui n'existe que pour la config providers (RP8, vague 7) : soit borner S4 à ce périmètre, soit anticiper un seam de reload plus large.
- **Web UI S5** `[P2]` — scraping interactif. ⚠️ requiert un seam **pause/reprise-sur-décision-humaine** que le pipeline batch n'a pas — à anticiper comme prérequis structurel.
- **Web UI S6** `[P2]` — registry + health (**fusionne Registry Consumer**) ; inclut **S6.0 — geler le statut registry en additif-only AVANT d'exposer le panneau**.
- **Web UI S7** `[P2]` — pages acquisition/watcher (sur les events RP4).
- **Verify V3** `[P2]` — panneau Web UI par check (sur V1).

### Vague 7 — Déferrals registry + dette + stretch
- **RP8** `[P3, prérequis]` — primitive unique de re-priorisation live (drain + swap atomique).
- **Active Health Scoring — cœur réseau** `[P3]` — au-dessus de RP8.
- **Active Health Scoring — slice ratio** `[P3]` — lit l'état Ratio (après C1).
- **Hot-Swap Provider Config** `[P3]` — au-dessus de RP8.
- **Tech-Debt Round 2** `[P3]`.
- **Follow D4** `[P2→P3]` — règles d'override par critère + profils qualité par série + cron.
- **Renouvellement médiathèque** `[P3]` — déclencheur d'auto-download sourcé des recommandations.
- **LLM Pipeline Assistant** `[P3]`.

---

## 🧱 Refacto-prep (préparation du terrain)

> Nouvelles features de **préparation du terrain**, motivées par des manques **constatés** dans le
> code (indices datés, à re-vérifier). On les pose avant les features d'acquisition pour ne pas
> bâtir sur du sable.

| Code | Prio | Type | Quoi (intention) | Prépare |
|------|------|------|------------------|---------|
| **RP1** | P1 | prérequis | Le client torrent sait piloter un torrent existant (pause/reprise/suppression, état de seed) mais **ne sait pas en AJOUTER un**. Le modèle d'item porte déjà une catégorie mais **pas de tags**. Ajouter un **protocole d'écriture** (ajout + catégorisation + limites) + un champ tags ; le client Transmission doit **refuser de démarrer s'il ne sait pas ajouter** (fail-fast). Pin Q4. | Orchestration, Follow, Ratio, Watcher, Trackers |
| **RP1a** | P1 | prérequis | Certains trackers exigent une auth pour récupérer le `.torrent` → si qBittorrent le fetch lui-même il peut se prendre un 401. PersonalScraper fetch le `.torrent` (auth gérée) puis POST le fichier ; **exception magnet** (lien sans auth). | Follow, Ratio, Orchestration |
| **RP2** | P1 | parallèle | La config par tracker ne porte aujourd'hui que l'**activation**. Lui ajouter l'**économie par tracker** (politique de ratio + secret d'annonce/passkey) **avant torr9/digitalcore**. Le non-goal « no new config schema » des Additional Trackers est **rayé**. | Ratio, Trackers, Follow, Orchestration |
| **RP3** | P1 | parallèle | Pas de persistance d'acquisition aujourd'hui. Créer un **store dédié** (`acquire.db`, **fichier séparé de `library.db`**) : séries suivies + file `wanted` + obligations de seed + état ratio. Entre dans le **modèle de State-ownership** (single-writer), **autorité d'écriture partitionnée** (follow / seed-safety / ratio). L'**autorité UNIQUE de suppression** est définie vs les deleters FS existants (maintenance/disk_cleaner) et l'arbitre O3 — **qui décide vs qui exécute** — en **fail-open** (store absent → ne bloque jamais le nettoyage). | Follow, Orchestration, Ratio |
| **RP3a** | P2 | prérequis | Nommer **une fois** le **modèle de domaine partagé « item désiré »** (épisode/film/release + profil qualité + critères de source ; série suivie ; entrée `wanted` ; obligation de seed), réutilisé par Follow, Ratio, Renouvellement et E2, et consommé comme **contrat d'entrée de l'orchestrateur** (RP5b). Évite que chaque feature réinvente « la chose que je veux » (même piège que les events épars). Vit dans `acquire/`. Vocabulaire partagé, pas de schéma. | Follow, Ratio, Renouvellement, E2 |
| **RP4** | P1 | parallèle | Aucun event d'acquisition aujourd'hui. Les définir **une fois** (catalogue unique) + un subscriber Telegram, muet jusqu'aux vagues 4–5. ⚠️ Le module producteur doit être **enregistré dans le hub eager-import des events** (+ compteur de catalogue), sinon le round-trip d'enveloppe drope silencieusement les events cross-process / Web UI (casse S7 + Telegram). | Orchestration, Freeleech, Watcher, Follow, Ratio, Web UI |
| **RP5a** | P1 | prérequis | Le registre de trackers existe mais **n'est pas câblé dans le contexte applicatif runtime**. Le câbler ; **absorbe le besoin de conteneur d'injection** (le contexte porte le registre). ⚠️ Câbler exige aussi une **construction pilotée par config + validation au boot à parité** avec le registre metadata (aujourd'hui le constructeur prend un dict pré-bâti ; ni factory ni validation côté tracker) — pour éviter une 2e voie divergente. Prérequis de RP5b. | RP5b, Follow, Ratio, Watcher |
| **RP5b** | P1 | prérequis | Pas de **cœur de grab partagé**. Créer un **orchestrateur de téléchargement + service d'acquisition** au-dessus de RP5a, **dans le package `acquire/`** (RP5c). **Gate de l'épopée** — Ratio C1 et Follow D3 partagent ce cœur. Contient l'étage **dédup cross-tracker pré-ranking** (c'est le job de l'orchestrateur ; D3 ne fait qu'y référer). | Orchestration, Follow, Ratio, Watcher |
| **RP5c** | P1 | prérequis | **Donner un home + un seam d'injection au lobe acquisition** : un package **`acquire/` de premier niveau** (pair de ingest/sort/dispatch/indexer) hébergeant orchestrateur, service d'acquisition, Follow, Ratio, Seed-Safety, Watcher ; dépend des ports `api/` + `acquire.db`, **jamais** du triage. Injecté au composition root unique via **une seule poignée** (pas N champs → l'AppContext gelé ne dérive pas en service-locator). Étend RP5a au-delà du seul registre. Intention, pas de layout de classes. | Orchestration, Follow, Ratio, Seed-Safety, Watcher |
| **RP6** | P2 | parallèle | Prédicat « je possède déjà » indéfini. L'ajouter dans la **couche de requête de l'indexer** (PAS dans le service films, déjà trop gros — voir Tech-Debt Round 2). | Follow, Ratio |
| **RP7** | P2 | parallèle | Jetons d'auth à durée courte ; le circuit breaker ne réagit pas aux 4xx. **Re-résoudre l'URL juste avant l'ajout** du torrent, et émettre un **event d'échec d'auth tracker**. Avec RP1a le 401 est observable. | Follow, Ratio, Trackers, Active Health |
| **RP8** | P3 | prérequis | Hot-Swap **et** Active Health veulent **muter l'ordre du chain à chaud** : une seule **primitive sûre** (drain + swap atomique). | Active Health, Hot-Swap |
| **RP9** | P2 | prérequis | Aujourd'hui le fetch d'épisodes se fait **série par série** ; un **poll des dates de diffusion sur un ENSEMBLE** de séries est une capacité neuve à ajouter. Résoudre Q1 d'abord. | Follow |
| **RP-layer** | P2 | parallèle | Quand `acquire/` atterrit, **étendre le garde-fou de layering** pour imposer sa direction d'import : `acquire/` → bas (`api`/`core`/`conf` + `acquire.db`), **jamais** l'inverse ; le pipeline le compose, lui n'importe pas le pipeline. (Au passage, l'énumération actuelle omet `insights`/`maintenance`/`enforce`/`process`.) Énoncer l'invariant, pas le test. | acquire/ (tout le lobe) |

---

## 📦 Catalogue des features (détail)

### — Acquisition —

#### TVShow Follow & Auto-Download System (D1–D4)

> Refondu 2026-06-01 : le **suivi de séries** est la feature principale ; l'ancien
> « Auto-Download System » (abonnement + recherche multi-trackers) **fusionne dedans** comme
> volets. Découpé en 4 sous-features (+ le renouvellement médiathèque sorti en item standalone).

Téléchargement automatique des nouveaux épisodes / saisons des séries d'une **liste suivie**,
recherche sur **tous les trackers actifs**, choix du **meilleur torrent** (filtres durs + score).

- **D1 — Liste + CRUD** : store de séries suivies, **liste manuelle** (ajouter/retirer),
  indépendante de la médiathèque — on peut suivre une série pas encore possédée.
- **D2 — Détection** : **calendrier-d'abord** (Q1) — on poll les air dates → file `wanted` →
  recherche tracker répétée selon la **cadence backoff** (Hot/Warm/Cold/cutoff, configurable
  globale + par série). Ownership via RP6 (ne pas chercher ce qu'on possède déjà).
- **D3 — Grab (cœur partagé)** : via le cœur de grab (RP5b).
  - **Filtres durs (éliminatoires)** : piste audio requise (VF/VOSTFR), qualité mini (≥1080p)…
  - **Score pondéré** sur les survivants : seeders, freeleech/économie tracker, source, codec, taille.
  - **Dédup cross-tracker AVANT le ranking** (porté par l'orchestrateur, RP5b) : le scoring traite
    un résultat à la fois → on regroupe par `info_hash`, on choisit la meilleure provenance, on
    passe **un** représentant à l'étage de ranking.
  - Re-résolution d'URL (RP7) + fetch (RP1a) + tag « contenu utile » (O1) pour ingestion normale.
- **D4 — Overrides & profils** : règles par critère (studio, réalisateur, franchise, titre, IMDB
  ID) + **profils qualité par série** (anime VOSTFR vs série VF) + cron. (Le renouvellement
  médiathèque a été sorti en item standalone — voir plus bas.)

**Depends on** : RP1, RP1a, RP2, RP3, RP5a/RP5b, RP6, RP7, RP9 ; trackers actifs ; l'étage de ranking (shippé).

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

**Depends on** : RP1, RP1a, RP2, RP3, RP5a/RP5b, RP6 ; Seed Safety O1/O2/O3 ; Freeleech R1 (bonus) ; l'étage de ranking.

#### Download Orchestration & Seed Safety (O1–O4)

> **Couche partagée** (P2) entre les modules qui téléchargent et le client torrent / le triage.
> Sans elle, le seed-pur polluerait la médiathèque et les obligations de seed seraient violées.

- **O1 — Tag « seed-pur » + skip** : marquage porté par le modèle d'item (catégorie + tags, via
  RP1) ; **skip à toutes les étapes du pipeline** (`ingest`/`sort`/`process`). **Définit le
  contrat de skip que le Watcher consommera** (vague 4). Les grabs « contenu utile » sont au
  contraire taggés pour ingestion normale. **Garde-fou anti-pollution médiathèque.**
- **O2 — Obligation de seed / anti-HnR** : politique au-dessus de l'autorité de suppression (RP3)
  — aucun module ne supprime/arrête un torrent avant le seedtime mini du tracker (évite les pénalités HnR).
- **O3 — Arbitre de budget disque global** : applique les quotas (dont le plafond par tracker de
  C1) ; **précédence : le dispatch du vrai média gagne toujours**, l'arbitre ne réserve que
  l'espace non réclamé ; **une seule autorité d'espace libre** que dispatch (**owner de fait
  aujourd'hui**), maintenance et l'arbitre lisent — l'arbitre ne duplique pas le calcul et ne plonge
  pas dans les internes disque de dispatch. Relié au sous-système de maintenance.
- **O4 — Events + caps** : events de download (via RP4) + **caps de bande passante par torrent
  ET globaux**.

**Depends on** : RP1, RP3, RP4 ; client torrent (qBittorrent) ; notifier Telegram ; sous-système de maintenance (shippé).
**Cadre/bloque** : Watcher, Ratio, TVShow Follow.

#### Additional Trackers (spike → torr9 → digitalcore)

> Remonté P3 → P2 le 2026-06-01 (LaCale tombe → besoin de sources actives). Séquencement Q3.

Implémenter deux nouveaux providers de tracker suivant le protocole de client tracker existant,
sur l'infra de transport HTTP unifiée. **Spike d'étude d'API d'abord** (Torznab/RSS/REST, samples
réels, doc de référence par tracker), **puis torr9, puis digitalcore**.

- Deux providers plug-compatibles avec le registre de trackers + le moteur de ranking.
- Capter l'économie par tracker (freeleech, bonus, seedtime mini, passkey) → **via le schéma RP2**.
- Activation via le mécanisme d'activation de providers existant.
- Détecter si le tracker expose une **API d'énumération de fenêtres freeleech** → gate R1 (Q3).

**Non-goals** : nouveaux critères de ranking (le moteur les supporte déjà).
**Depends on** : RP2 (schéma config), RP7 (auth). ⚠️ L'ancien non-goal « no new config schema » est **rayé** (RP2).
**Ordre** : spike en vague 2 (dépend de RP2) ; torr9 en vague 3 (après RP7) ; digitalcore en vague 5.

#### Freeleech Radar (R1) — conditionnel

> Module **transverse** partagé par Ratio et Follow. **La plomberie par-résultat est déjà
> shippée** (marqueur freeleech + bonus de ranking). Le seul net-new = la **découverte proactive
> de fenêtres**.

- **R1** : event de fenêtre freeleech + découverte de fenêtres — **seulement si ≥1 tracker expose
  une API d'énumération** (sinon R1 se réduit à la récolte par recherche déjà shippée). Ratio en
  fait sa priorité n°1 (gain de ratio à coût nul) ; Follow s'en sert comme critère de score.

**Depends on** : Additional Trackers (spike Q3), Event Bus (shippé).

#### Watcher Service

Remplace le déclencheur cron par un service temps-réel.

- Surveille l'état qBittorrent ou le répertoire `complete/` ; déclenche `personalscraper run`.
- **Ignore les torrents taggés « seed-pur »** (consomme le contrat défini par O1).
- **Décommission du cron 3 h au cutover** (sinon double-ingestion) — mention canonique de la cadence cron.
- **Autorité de déclenchement unique** : Watcher, ex-cron et actions Web UI (S2 start/kill) passent par le **même lock pipeline** — pas de writer parallèle.

**Depends on** : Event Bus (shippé), Pipeline Observer Protocol (shippé), Seed Safety O1.

### — Supervise —

#### Web Management UI (S1–S7)

Interface web pour piloter/superviser tout le projet. Découpée en 7 sous-features.

- **S1** — shell + auth + WebSocket + container headless (**à faire en premier**).
- **S2** — pipeline control : start/pause/resume/kill (`ingest`/`sort`/`process`/`dispatch`), logs live, status, history.
- **S3** — maintenance dashboard : disque/espace libre par disque, orphelins (préfixe temporaire), locks, santé index, historique des runs.
- **S4** — éditeur de config visuel avec validation de schéma + reload sûr. ⚠️ Le « reload sûr » dépend d'un mécanisme de reload qui n'existe aujourd'hui que pour la config providers (RP8, vague 7) : soit S4 borne son reload à ce périmètre, soit un seam de reload plus large est anticipé.
- **S5** — scraping interactif : points de décision manuels (matches ambigus TMDB/TVDB, picks multi-résultats, arbitrage fuzzy, override titre/année/saison). ⚠️ Requiert un seam **pause/reprise-sur-décision-humaine** que le pipeline batch n'a pas aujourd'hui — à anticiper comme prérequis structurel.
- **S6** — registry + health (**fusionne l'ancien « Web UI Registry Consumer »**) : WebSocket sur
  les events registry (fallback / épuisement / capacité verrouillée / fan-out / boot), REST de
  lecture de l'état et des opérations du registry, panneau circuit + chain + latences.
  - **S6.0** — geler le statut registry en **additif-only AVANT** d'exposer le panneau (Active
    Health en vague 7 l'étend) : porteur explicite de ce prérequis.
- **S7** — pages acquisition/watcher (status, history, CRUD liste suivie, règles override) sur les events RP4.

**Architecture (à trancher en design)** : FastAPI/Flask+HTMX vs SPA+REST/WebSocket ; auth local-only vs basic ;
reverse-proxy friendly (sous-chemin derrière `iznogoudatall.xyz`). **Hors scope v1** : multi-user, contrôle d'agent distant, UX mobile.
**Depends on** : Pipeline Observer (shippé), Event Bus (shippé), RP4 (pour S7), statut/opérations du registry (shippé, pour S6).

### — Qualité / plateforme —

#### Verify Checker Plugin System (V1–V3)

Le checker de verify est aujourd'hui un **module monolithique** : ajouter un check impose d'éditer
le fichier. Le passer en **architecture de plugins** → checks testables, extensibles, découvrables
par la Web UI. Landing zone de l'ex-validateur de médiathèque.

- **V1** — registre de checks + **deux protocoles** : check **pré-dispatch** (porte sur un chemin)
  et check de **lignes de médiathèque** (ex-validateur), sous un seul registre. Chaque groupe
  existant (ex. : NFO, artwork, naming, stream, genre, taille, doublons vidéo) devient un plugin.
- **V2** — CLI granulaire : `personalscraper verify --check nfo_validity`.
- **V3** — panneau Web UI par check (liste, run individuel, résultats).

**Non-goals** : changer la logique des checks au-delà de l'extraction.

#### Active Health Scoring (Registry) — au-dessus de RP8

Passer du circuit breaker passif au **scoring de santé actif** : tâche de fond de monitoring par
provider (check périodique), **moyenne glissante** sur N checks, dé-priorisation dans le chain sous
un seuil (re-tenté à la fenêtre suivante) ; le statut du registry inclut le score. Mutation de
l'ordre du chain **via la primitive RP8**.

- **Slice ratio (brainstorm 2026-06-01)** : pour les providers tracker, intégrer l'état de ratio
  (proche de la limite → déprioriser) **en plus** de la santé réseau. Alimenté par Ratio C1 →
  **cette slice attend C1 (vague 5)**.

**Non-goals** : load-balancing actif, routage par région. **Risque** : budget des checks de santé à borner.
**Depends on** : Provider Registry (shippé), **RP8**, RP7 ; slice ratio ⇐ Ratio C1.

#### Hot-Swap Provider Configuration — au-dessus de RP8

Recharger la config des providers sur SIGHUP / changement de fichier **sans redémarrer**.

- File-watcher sur le fichier de config providers → validation → si PASS, **swap atomique via RP8**,
  drain 5 s, event de hot-swap.

**Non-goals** : hot-swap des IMPLÉMENTATIONS (config seulement), config distribuée.
**Depends on** : Provider Registry (shippé), validation de config (shippé), **RP8**.

#### Résolution d'épisode par nom (E1 + E2)

> Reframe 2026-06-02 : l'ex-« Reverse Episode Lookup » devient une feature **intégrée au pipeline**
> (plus un outil isolé). Le **nom d'épisode** sert de clé quand le numéro est absent ou faux — mais
> **le numéro reste la clé par défaut** et le nom (bruité : autre langue, mal écrit, absent) ne
> l'écrase **jamais** automatiquement.

Aujourd'hui un fichier TV sans SxxExx est **skippé silencieusement** (il reste en vrac à la racine
de la série). Cette feature le rattrape, et attaque aussi la cause des séries mal numérotées
(sources de scraping en désaccord, constaté après coup dans Plex). Le titre d'épisode se cherche
contre la liste d'épisodes **déjà récupérée** chez le provider au point de décision (donc léger).

**E1 — Name-keyed matching (intégré au triage, léger)** — modes 1 & 2 :
- **Mode 1 — fallback (numéro absent)** : matcher l'épisode par nom contre la liste déjà en mémoire
  (au lieu du skip actuel). Fuzzy + seuil de confiance : auto si franc, sinon on n'invente pas
  (skip / flag). Le nom est la clé car c'est le seul signal disponible.
- **Mode 2 — corroboration (numéro + nom présents)** : **non bloquant, le numéro reste la clé**. Si
  le match par nom est **franc** et **contredit fortement** le numéro, on **signale** (warning /
  check Verify / marqueur de revue) sans jamais écraser le numéro. But : repérer tôt une probable
  mauvaise numérotation. Un nom faible / étranger / mal écrit est **ignoré** (pas de pénalité).

**E2 — Correction par re-scrape name-keyed (manuel, lourd)** — mode 3 :
- Quand une mauvaise numérotation est **constatée dans Plex**, on déclenche (par série) un
  re-scraping **name-keyed depuis le download d'origine**. Si le torrent n'est plus là, on le
  **re-télécharge** (via le cœur de grab + trackers). La version corrigée remplace la mauvaise
  (règles de move TV : merge/replace).
- Réutilise le moteur de E1. **Dépend de la stack d'acquisition** → atterrit tard (vague 5).
- ⚠️ **Question ouverte (design)** : re-télécharger ne récupère les noms que si une release
  **nommée par titres** existe (beaucoup ne mettent que SxxExx). À creuser au design de E2.

**Déclencheur E2** : commande manuelle par série (l'humain constate dans Plex). Une CLI du style
`resolve-episodes` survit donc, mais branchée sur le **même moteur** (E1) — elle n'est plus « hors
pipeline », elle partage la logique intégrée.

**Depends on**
- **E1** : matching d'épisodes + modèle de confiance (shippé) — la liste d'épisodes est déjà en
  mémoire au point de décision ; aucune dépendance au socle d'acquisition.
- **E2** : E1 + cœur de grab (RP5b) + trackers actifs + re-download (RP1/RP1a).

#### Tech-Debt Round 2 (`tech-debt-2`)

> Status (indice 2026-05-28) : pas de crise god-module aiguë.

- Extraire le **service films** (le plus gros module, proche du plafond dur) le long du seam dedup/rename/orphan-unlink.
- Décider la politique de garde-fou pour les `__init__.py` : le check de taille les exclut tous, ce qui masque quelques gros package-inits (ex. registre metadata, scanner indexer).
- Sweep large : code mort, `TODO`/`FIXME`/`HACK`, `type: ignore`/`pragma: no cover`, `except` larges, magic values, skips/`xfail` expirés.

**Non-goals** : changements de comportement (déplacements structurels seulement).

#### architecture.md Multi-Filesystem cleanup `[doc]`

Section « Multi-Filesystem » encore marquée *planned* alors que **déjà shippée** — seul pointeur
mort restant. Nettoyage doc.

#### LLM Pipeline Assistant (idée, gardée pour la fin)

Connecter un LLM (local/distant) comme assistant d'arbitrage pour les points à décision humaine
(matches ambigus, post-mortem d'erreurs, incohérences). RAG sur la médiathèque + corrections
utilisateur — jamais de fine-tuning, jamais autonome, toujours en validation. Volontairement simple.

Vision/questions ouvertes : `docs/superpowers/roadmap/llm-assistant/brainstorming.md`.
**Brainstorming entamé** (2026-05-11/12) : principes posés, cas d'usage cadrés, stack pressenti
(MCP + sqlite-vec + Ollama + Open WebUI), 3 questions ouvertes. Reprendre via `/brainstorming`.

#### Renouvellement médiathèque (acquisition trigger)

> Sorti de Follow D4 le 2026-06-01 : ce n'est pas une règle d'override mais un **déclencheur
> d'acquisition distinct**, sourcé des recommandations médiathèque.

Brancher la **liste de recommandations** de la médiathèque sur l'auto-download pour renouveler /
compléter le fonds (remplacer des versions, combler des manques). Réutilise le cœur de grab (RP5b)
et le prédicat de possession (RP6).

**Depends on** : RP5b (cœur de grab), RP6 (ownership), recommandations médiathèque (shippé). Lit **P3**.

### — Dépréciations —

#### LaCale Deprecation

LaCale n'existe plus. On **conserve tout le code** (référence pour les futurs trackers) mais on le
marque **déprécié**.

- **Désactivation** via le mécanisme d'activation de providers (retiré du registry actif / de l'ordre de préférence).
- **Flag `deprecated`** dans le provider LaCale (`api/tracker/lacale.py`) + warning au boot s'il est activé.
- **Tests/fixtures** marqués `skip` (raison documentée), gardés. Doc de référence LaCale conservée.
- **CHANGELOG** : entrée « Deprecated ».

**Non-goals** : suppression du code, du doc ou des fixtures.

---

## 🔀 Journal des fusions & reclassements (2026-06-01)

Issu du brainstorm multi-agents (analyse ancrée sur le code, critique adverse appliquée) :

**Fusions**
- **Web UI Registry Consumer** → page **Web UI S6** (zéro backend indépendant ; statut/opérations shippés en 0.16.0).
- **Dependency Injection Container** → **RP5a** (le contexte applicatif doit porter le registre de trackers — c'est le seam RP5a).
- **Plomberie par-résultat du Freeleech Radar** → déjà shippée ; seul survivant net-new = **R1** (découverte de fenêtres).
- **Events d'acquisition épars** → **RP4** (un seul catalogue).
- **Mutation Active Health + swap Hot-Swap** → **primitive RP8 unique** (les deux mutent l'ordre du chain à chaud).
- **Validateur de médiathèque** → 2e protocole dans **Verify V1**.

**Découpes** (features trop grosses → spec-sized)
- Web Management UI → **S1–S7** · TVShow Follow → **D1–D4** · Seed Safety → **O1–O4** · Verify → **V1–V3** · Ratio → **C1–C3** · Freeleech → **R1**.
- (Coherence pass) **RP5 → RP5a + RP5b** (câblage registre/DI vs cœur de grab) · **Renouvellement médiathèque** sorti de D4 en item standalone.

**Ajouts de cohérence** (sinon la boucle ne tourne pas)
- Dédup cross-tracker **pré-ranking** (dans RP5b/D3) · précédence disque réel > seed-pur (O3) ·
  décommission cron 3 h au cutover Watcher · versionnage du statut registry avant S6 (S6.0).

**Reclassements**
- `lib-fold` (shippé en 0.19.0) **retiré**. · LaCale → P1. · torr9+digitalcore P3 → P2. · DI Container → absorbé RP5a.

**Reporté (non retenu ce tour-ci)** : confort — bootstrap liste depuis l'indexer, pages Web UI ratio dédiées.

**Coherence pass (2026-06-01)** : roadmap rendue moins dépendante du code (références = indices
datés, pas des contrats) ; découpe/ordre revérifiés ; 1 fix d'ordre dur (torr9 W2→W3, dépendait de
RP7) ; sans zèle (sur-découpes refusées).

**Reframe Reverse Episode Lookup → Résolution d'épisode par nom (2026-06-02)** : d'outil isolé
manuel à feature **intégrée au pipeline**. Découpée en **E1** (name-keyed matching, modes
fallback + corroboration non bloquante, vague 1 — le numéro reste la clé par défaut) et **E2**
(correction par re-scrape name-keyed depuis le download d'origine / re-download, vague 5, dépend du
cœur de grab + trackers). Principe figé : le nom (bruité) ne supplante jamais le numéro
automatiquement ; il sert de fallback (numéro absent) ou de signal mou (numéro présent).

**Architecture pass (2026-06-02)** : revue d'archi multi-agents ancrée code. Verdict — la roadmap
**pense archi** (RP partagés posés avant les features, fusions qui réduisent la surface, ordre =
layering, state ownership raisonné), pas de l'empilage. Manque majeur corrigé : **l'altitude du lobe
acquisition**. Ajouts : section **🏛 Architecture cible** + **RP5c** (package `acquire/` + seam
d'injection unique), **RP3a** (modèle de domaine « item désiré » partagé), **RP-layer** (garde-fou
de direction d'import) ; précisions **RP3** (ownership/partition `acquire.db`, suppression
décide-vs-exécute), **RP5a** (factory config + validation au boot), **RP4** (enregistrement
eager-import des events), **O3** (autorité unique d'espace libre, dispatch owner de fait) ; notes de
dépendance **S4/S5** (seams reload + pause/reprise) et **Watcher** (autorité de déclenchement unique).

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
