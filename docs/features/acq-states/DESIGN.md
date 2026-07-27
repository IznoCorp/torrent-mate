# DESIGN — acq-states : états d'acquisition véridiques

**Codename**: `acq-states`
**Ticket**: #319
**Commit type**: `feat`
**SemVer bump**: minor — 0.54.1 → 0.55.0
**Constitution**: §5 (Acquisitions), §6 (Disponibilité des actions), NE-DOIT-PAS-1 (mentir),
NE-DOIT-PAS-5 (échec silencieux), NE-DOIT-PAS-7 (second mécanisme), NE-DOIT-PAS-8
(maltraiter les dépendances).

---

## 1. Incident fondateur

Série _Furious_ (TVDB 468000) ajoutée le 2026-07-27 à 09:18:50 par le formulaire d'ajout
manuel par ID. L'interface affiche **« À jour »** alors que ses 3 épisodes diffusés ne sont
ni téléchargés ni en médiathèque, et sa carte n'a pas de poster.

État en base au moment de l'incident : `followed_series` id=10 → **0 `aired_episode`,
0 `wanted`**, `poster_url`/`overview`/`year` à `NULL`.

### Preuve que la chaîne d'acquisition était saine

Recherche C411 réelle, avec la requête exacte que `build_search_query` produit :

| Requête          | Résultats bruts | Après `filter_to_episode` |
| ---------------- | --------------- | ------------------------- |
| `Furious S01E01` | 13              | 4                         |
| `Furious S01E02` | 12              | 4                         |
| `Furious S01E03` | 12              | 4                         |

Tracker, filtrage et ranking fonctionnaient. **Il ne manquait que les lignes `wanted`.**
Confirmé a posteriori : un `detect --series 10` suivi d'un `grab --followed-id 10` a récupéré
les 3 épisodes (1080p MULTi, conformes au profil), et le pipeline 264 les a dispatchés en
médiathèque avec NFO et artwork complets.

---

## 2. Causes racines

### RC1 — Aucune amorce à la création d'un suivi

`POST /api/acquisition/followed` insère la ligne et s'arrête. Le catalogue diffusé
(`aired_episode`) et la file `wanted` ne sont écrits **que** par la passe `detect`
(cron 03:00). Furious ajouté à 09:18 → dernière passe 03:00 → catalogue vide toute la journée.

Conséquence directe : le clic « Rechercher » de l'opérateur à 09:19:09 a lancé
`grab --followed-id 10` (rc=0), lequel ne travaille que sur `wanted.list_pending()` →
_« No pending wanted items »_ → **succès silencieux** (NE-DOIT-PAS-5).

### RC2 — Deux sources de vérité qui se contredisent

`personalscraper/web/models/acquisition.py:99-104` — la carte :

```python
if self.aired_count is None:      # aucun catalogue en cache
    if self.wanted_grabbed > 0: return "acquiring"
    if self.wanted_pending > 0: return "pending"
    return "up_to_date"           # ← 0 wanted ⇒ « à jour »
```

`personalscraper/web/acquisition/completeness.py:110-116` — le panneau de détail :

```python
else:                              # cache vide
    aired = poll_aired([followed], registry, today=date.today())   # repli LIVE
```

La carte lit le cache (vide → « À jour »), le panneau de détail tombe en repli sur un poll
live (3 épisodes → tous `manquant`). Les logs prod confirment que
`GET /api/acquisition/followed/10/completeness` a bien été appelé à 09:19 :
**l'application se contredisait à l'écran**. Violation NE-DOIT-PAS-1.

### RC3 — Le poster n'est jamais enrichi côté serveur

`frontend/src/components/acquisition/FollowedPanel.tsx:159` — ajout manuel par ID TVDB :

```ts
const body: CreateFollowRequest = { tvdb_id: tvdb, kind: "show" };
if (title.trim()) body.title = title.trim(); // ni poster, ni overview, ni year
```

Côté serveur, `_write_follow_metadata` sort immédiatement quand les trois sont nuls. Le poster
ne provient **que** du candidat de recherche envoyé par le client. Or TVDB expose 6 posters
pour la série 468000 et `/search` renvoie l'URL : l'information était disponible, elle n'a
jamais été demandée. Contraste : Star City, ajouté via la recherche, a bien son poster.

Aggravant : après dispatch, la médiathèque contient `poster.jpg` pour Furious, mais la carte
d'acquisition reste sans poster — les deux champs sont indépendants et rien ne les réconcilie.

---

## 3. Le modèle d'états

### 3.1 Les cinq états (arbitrage opérateur 2026-07-27)

| État                       | Définition                                              |
| -------------------------- | ------------------------------------------------------- |
| **À jour**                 | Épisode diffusé **et** présent en médiathèque           |
| **En attente**             | Diffusé, recherche **conclue**, aucun candidat prenable |
| **À récupérer**            | Diffusé, candidat prenable connu, pas encore téléchargé |
| **En cours d'acquisition** | Téléchargé (ou en cours), pas encore en médiathèque     |
| **Non vérifié**            | Diffusé, **aucune recherche conclue** à ce jour         |

« Non vérifié » est le 5ᵉ état explicitement retenu par l'opérateur : c'est le seul qui rend
structurellement impossible le bug de l'incident, en interdisant d'affirmer sans savoir.

### 3.2 « Prenable » — définition retenue

Arbitrage opérateur : **prenable = survit aux filtres éliminatoires**, c'est-à-dire au moins
un résultat qui passe `filter_to_episode` **et** `apply_hard_filters` **et** le seuil
`min_seeders`.

État actuel de la configuration (les 10 suivis ont `quality_profile_json = NULL`, donc défauts
partout) — ce qui **rejette** réellement :

- **3D (SBS / Over-Under)** — `exclude_3d = True`, seul rejet de profil réellement actif ;
- `min_seeders = 1` — écarte les swarms morts ;
- `filter_to_episode` — écarte les autres épisodes et les packs de saison ;
- identité TMDB contradictoire — no-op sur C411 (pas de `tmdb_id` dans les résultats).

Ce qui n'**ordonne** que (jamais éliminatoire) : résolution (1080p 20 > 720p 12 > 2160p 8),
codec, format, audio, source, seeders, taille, bonus freeleech.

Le profil n'est donc pas restrictif : il prend le meilleur disponible et n'exclut que la 3D.
Retenir « prenable » plutôt que « n'importe quel résultat » ne restreint quasiment rien en
pratique — cela empêche seulement « À récupérer » de promettre du 3D-seulement, du 0-seeder ou
du pack-de-saison que le moteur ne prendra jamais.

### 3.3 Panne ≠ absence (invariant central)

L'orchestrateur distingue déjà ses issues. La correspondance est **non négociable** :

| Issue orchestrateur         | État dérivé            | Justification                     |
| --------------------------- | ---------------------- | --------------------------------- |
| `no_candidates`             | En attente             | recherche propre, zéro résultat   |
| `no_matching_episode`       | En attente             | seulement packs / autres épisodes |
| `all_filtered`              | En attente             | tout violait le profil dur        |
| candidat retenu, non ajouté | À récupérer            | prenable connu, pas encore pris   |
| `grabbed`                   | En cours d'acquisition | torrent ajouté                    |
| en médiathèque              | À jour                 | possession vérifiée               |
| `trackers_unavailable`      | **Non vérifié**        | panne — pas une absence           |
| `circuit_open`              | **Non vérifié**        | panne — pas une absence           |
| `no_seeders`                | **Non vérifié**        | swarm mort ≠ conclusion           |

Une panne tracker rapportée comme « En attente » serait exactement le mensonge de l'incident,
déplacé d'un cran. Une recherche qui n'a pas conclu laisse l'état à « Non vérifié ».

---

## 4. Décisions d'architecture

### D1 — Persistance : colonnes sur `wanted` (arbitrage opérateur)

La table `wanted` porte déjà `last_search_at` et `attempts` — c'est exactement là que la
recherche a lieu. On y ajoute le **résultat** de la dernière recherche.

Migration `acquire.db` :

```sql
ALTER TABLE wanted ADD COLUMN last_search_outcome TEXT;    -- l'issue orchestrateur, NULL = jamais cherché
ALTER TABLE wanted ADD COLUMN last_search_found INTEGER;   -- nb de candidats PRENABLES, NULL = inconnu
```

`last_search_outcome` stocke l'issue nommée (`no_candidates`, `all_filtered`,
`trackers_unavailable`, …), pas un booléen : c'est ce qui permet de distinguer panne et
absence, et de diagnostiquer sans relire les logs.

Rejeté : table de disponibilité dédiée — clé dupliquée et nettoyage à prévoir, sans bénéfice
tant que chaque épisode diffusé non possédé a sa ligne `wanted` (garanti par l'amorce D2).

### D2 — Amorce à la création : 201 + run visible (arbitrage opérateur)

`POST /api/acquisition/followed` répond **201 immédiatement**, puis enfile **un run d'amorce**
pour ce suivi (catalogue + file `wanted` + première recherche) via **l'autorité de
déclenchement existante** — le même lock et le même runner que les autres actions
(NE-DOIT-PAS-7 : jamais un second mécanisme).

Pendant le run, la carte affiche **« Vérification en cours »**, pas un état deviné. Conforme
au §6 : l'action s'exécute ou s'enfile **visiblement**.

Rejeté : detect synchrone dans le POST (bloque l'ajout sur des appels providers) ; tout
synchrone (bloque plusieurs secondes **et** frappe les trackers depuis le chemin web).

### D3 — Source unique de vérité pour le catalogue

RC2 vient de deux chemins de lecture divergents. La correction est structurelle : **la carte
et le panneau de détail lisent la même source**, par la même fonction.

Le repli `poll_aired` live de `compute_completeness` est **supprimé** : avec l'amorce D2, un
suivi a toujours son catalogue peu après sa création, et un repli live qui contredit la carte
est précisément le défaut à éliminer. Catalogue absent ⇒ **« Non vérifié »**, jamais un état
deviné ni un poll divergent.

### D4 — Enrichissement serveur des métadonnées de carte

`create_follow` enrichit **côté serveur**, quel que soit le chemin d'ajout : quand le client
n'a pas fourni poster/overview/year, le serveur les récupère lui-même via le registry
(l'information existe — TVDB expose 6 posters pour 468000).

Le formulaire d'ajout par ID reste inchangé côté client : c'est le serveur qui devient
responsable, ce qui ferme la classe de bug entière plutôt qu'un seul chemin.

---

## 5. Périmètre

1. Migration `acquire.db` : `last_search_outcome` + `last_search_found` sur `wanted`.
2. L'orchestrateur persiste l'issue de chaque recherche (tous les chemins de sortie).
3. Dérivation serveur des 5 états — **source unique**, l'UI ne re-dérive rien.
4. Amorce à la création du suivi via l'autorité de déclenchement existante (D2).
5. Suppression du repli `poll_aired` divergent dans `compute_completeness` (D3).
6. Enrichissement serveur poster/overview/year (D4).
7. UI : libellés français des 5 états, épisode par épisode groupé par saison (§5).
8. Tests de régression, un par cause racine.

## 6. Critères d'acceptation (exécutables)

| ID     | Critère                                                                                                                                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ACC-01 | Un suivi fraîchement créé n'affiche **jamais** « À jour » — l'état est « Vérification en cours » puis un état dérivé de faits. Reproduit l'incident Furious. |
| ACC-02 | Catalogue absent ⇒ « Non vérifié », jamais « À jour ». Test direct sur la dérivation.                                                                        |
| ACC-03 | Carte et panneau de détail s'accordent toujours : mêmes faits, même source. Test qui échoue sur le code actuel.                                              |
| ACC-04 | Une panne tracker (`trackers_unavailable`, `circuit_open`) laisse « Non vérifié », jamais « En attente ».                                                    |
| ACC-05 | Un épisode dont tous les candidats sont 3D / 0-seeder / packs ⇒ « En attente », jamais « À récupérer ».                                                      |
| ACC-06 | Un suivi ajouté par ID TVDB seul obtient poster + overview + year côté serveur. Reproduit RC3.                                                               |
| ACC-07 | `scripts/check-acquisition-coherence.py` à zéro anomalie.                                                                                                    |
| ACC-08 | Aucun appel tracker déclenché par le rendu d'une carte ou d'un panneau (NE-DOIT-PAS-8).                                                                      |

## 7. Hors périmètre

- Refonte du ranking ou des poids du profil qualité (2160p bas reste un ouvert assumé).
- Profils qualité par série (`quality_profile_json` reste `NULL` partout) — c'est le ticket
  #193 [D4].
- Le cas _Top Chef Le Concours Parallèle_ (aucune donnée épisode chez les providers) reste un
  ouvert assumé de l'opérateur.
