# acq-escalade — l'acquisition escalade vers le pack saison quand la recherche épisode échoue

**Date**: 2026-08-04 · **Codename**: `acq-escalade` · **Type**: fix · **Bump**: bugfix (0.78.0 → 0.78.1)

Diagnostic source, avec toutes les preuves d'observation live :
`docs/archive/analysis/2026-08-04-acquisition-season-escalation-diagnosis.md`.

**Nommage** — le document d'analyse nomme les défauts D1/D2/D3 et leurs correctifs F1/F2/F3.
Ce design nomme **le défaut et son correctif du même nom**, et ajoute D4 découvert ensuite :

| Ici | Analyse | Sujet |
|---|---|---|
| D1 | D1 / F1 | Escalade épisode→saison aveugle à l'échec de recherche |
| D2 | D2 / F2 | Panne partielle de tracker écrite comme une absence |
| D3 | D3 / F3 | Aucune passe déclenchée par l'action opérateur |
| D4 | *(découvert après)* | Scan post-dispatch émettant sur un bus jetable |

## 1. Problème

Une ligne épisode dont le torrent individuel n'existe pas sur les trackers est re-cherchée
jusqu'à **17 fois sur 20 jours** avec une requête qui ne peut pas aboutir, alors qu'un pack
saison couvrant est disponible immédiatement (65 à 710 seeders selon les cas). L'opérateur a
dû enfiler les saisons **à la main**, et ces lignes manuelles n'ont ensuite rien déclenché.

Quatre défauts distincts, tous validés par observation sur données live.

### D4 — le scan post-dispatch émet sur un bus jetable (le plus grave)

`personalscraper/dispatch/post_maintenance.py:190` construit un `EventBus()` **neuf** au lieu
de propager celui de l'appelant :

```python
rc = library_index_command(
    mode="incremental", disk=disk, no_budget=True,
    event_bus=EventBus(),          # bus neuf, zéro abonné
    config_path=resolve_config_path(),
)
```

`PostDispatchReconcileSubscriber` est abonné au bus **du processus** et écoute
`LibraryScanCompleted`. Le scan post-dispatch émet sur le bus jetable : le subscriber
n'entend jamais rien, et les lignes `wanted` possédées ne sont jamais fermées.

Preuve — run `completion` du 2026-08-04 03:40 (celui qui a livré les médias) :

```
03:46:47  post_maintenance_scan_start disk=disk_1
03:46:50  media_file indexés (Widow's Bay S01E08/E09, President Curtis S01E02)
03:46:50  indexer.scan.update_run_status id=337 ok
03:46:50  indexer.scan.update_run_status id=338 ok
03:46:51  indexer.scan.update_run_status id=339 ok
03:46:51  indexer.scan.update_run_status id=340 ok
03:46:51  step_finished step=dispatch
```

Quatre scans terminés, **zéro ligne `acquire.*` ou `reconcile` entre 03:44 et 03:50**.

Conséquence mesurée par le garde-fou exécutable du §méthode :

```
python scripts/check-acquisition-coherence.py   →  exit code 4
❌ [GRABBED_OWNED] House of the Dragon S03E07 (wanted #54)
❌ [GRABBED_OWNED] President Curtis S01E02   (wanted #55)
❌ [GRABBED_OWNED] Widow's Bay S01E08        (wanted #85)
❌ [GRABBED_OWNED] Widow's Bay S01E09        (wanted #86)
   status='grabbed' but the library already owns it (phantom in-flight)
```

C'est une violation de l'invariant projet « `event_bus` est un paramètre REQUIS partout,
jamais de défaut » — et le défaut est exactement ce qui a produit le bug.

### D2 — une panne partielle de tracker est écrite comme une absence définitive

`SearchOutcome.all_errored` (`acquire/_dedup.py:83`) n'est vrai que si **tous** les trackers
échouent. Avec deux trackers actifs, si l'un tombe et l'autre rend légitimement zéro, le jeu
vide part sur `no_candidates`, que la taxonomie (`orchestrator.py:797`) mappe sur
`("not_found", "no_candidates", 0)` — un verdict « 0 trouvé » persisté.

C'est une violation du contrat que le module s'est lui-même écrit :
`SearchVerdict.found` documente déjà *« None = not concluded (NEVER 0 on outage) »*.

Preuve — log `personalscraper-search-error.log`, passe de 03:10 :

```
03:10:30  api_error_body_unparsable provider=c411 status=429
          body='<error code="500" description="Rate limit exceeded..."/>'
          url='https://c411.org/api?apikey=<REDACTED>&t=tvsearch&q=Widow%27s+Bay+S01E10'
03:10:34  tracker_search_failed taxon=api tracker=c411
```

La ligne #87 a persisté `no_candidates` / `found=0`. La même requête rejouée à 14:00 rend
`raw=25, exact_episode=9`. Les releases existaient ; c411 était rate-limité.

### D1 — l'escalade épisode→saison est aveugle à l'échec de recherche

Deux chemins d'escalade existent, aucun ne lit l'échec de recherche.

**DETECT** (`detect.py:468-506`) — portes purement calendaires et de possession. Rejeu
verbatim de ces portes sur les données live :

```
f4  American Dad!           S15  owned=20/22 -> c:OWNED_MAJORITY(20/22)
f4  American Dad!           S17  owned=22/24 -> c:OWNED_MAJORITY(22/24)
f21 Widow's Bay             S1   owned=9/10  -> c:OWNED_MAJORITY(9/10)
f20 Batman: Caped Crusader  S2   owned=0/10  -> b:LAST_AIR_TOO_RECENT(2026-07-31)
```

La porte (c) `owned <= total/2` est **anti-corrélée au besoin** : plus on possède
d'épisodes, plus l'escalade est interdite — exactement la forme « il me manque 1–2 épisodes
qui n'existent qu'en pack ».

**SEARCH R2** (`_search_pass.py:139-146`) — la conversion n'est armée que sur
`verdict.outcome == "no_matching_episode"`, ce qui exige que la requête épisode ait ramené
des résultats bruts. Quand elle rend **zéro**, l'orchestrateur sort plus tôt sur
`no_candidates` (`orchestrator.py:676`) et R2 est inatteignable :

```
#5  'American Dad! S15E21'        raw=0 exact=0 -> no_candidates  R2_fires=False
#74 'Batman: Caped Crusader S02E01' raw=0 exact=0 -> no_candidates  R2_fires=False
```

Alors que la requête **saison** rend des packs sains (appels trackers réels) :

```
#88 'American Dad!' S15         expected=22 raw=4  kept=4   top seeders=65
#89 'American Dad!' S17         expected=24 raw=4  kept=4   top seeders=74
#90 'Batman: Caped Crusader' S2  expected=10 raw=1  kept=1   top seeders=178
#91 "Widow's Bay" S1            expected=10 raw=26 kept=11  top seeders=710
```

### D3 — aucune passe déclenchée par l'action opérateur

`grab_season` (`web/routes/acquisition.py:1046`) insère la ligne `pending` et absorbe les
épisodes, puis **ne déclenche rien**. Les crons sont `search 10 3,15` et `grab 20 3,15` :
une ligne créée à 12:36 attend 15:10. `create_follow` appelle pourtant déjà
`enqueue_prime_run` — `grab_season` est le seul point d'entrée opérateur oublié.

## 2. Ce que la constitution impose ici

- **§2 / §8** — l'interface ne doit jamais affirmer un progrès qui n'a pas lieu. Les quatre
  fantômes `GRABBED_OWNED` et les lignes « en cours d'acquisition » qui n'ont aucune passe
  programmée sont deux formes du même mensonge.
- **§5** — un déclenchement manuel **montre le run** : lancé → en cours → résultat chiffré.
  Un toast de succès sur un run mort est interdit.
- **§6** — une action opérateur légitime ne répond **jamais « occupé »** : elle s'exécute ou
  elle s'enfile **visiblement**. Le seul refus permis est l'idempotence. Patron de
  référence : la file resolve (202 systématique, step `queue`, pastille « En file »).
- **§méthode** — aucun verdict de conformité n'est recevable sans
  `scripts/check-acquisition-coherence.py` à **zéro anomalie**.

## 3. Décisions (arbitrées par l'opérateur)

| # | Décision | Retenu |
|---|---|---|
| A1 | Périmètre | D4 + D2 + D1 + D3 en une feature |
| A2 | Seuil d'escalade | **2 recherches conclues** (sens durci par D2) |
| A3 | Extraction `acquisition.py` | Commit séparé, comportement constant, avant F3 |
| A4 | Garde-fou cohérence | Critère ACCEPTANCE **bloquant** (exit 0) |
| A5 | Où vit la sonde saison | Search pass (là où vit le verdict) |
| A6 | Portes DETECT | Inchangées — deux déclencheurs distincts coexistent |
| A7 | Forme du déclencheur D3 | Réutiliser `enqueue_prime_run` |

## 4. Conception

### 4.1 D4 — propager le bus (phase 1)

`event_bus` devient un paramètre **requis** (jamais `| None`, jamais de défaut) traversant :

```
maybe_run_post_dispatch_maintenance(config, results, *, event_bus, …)
  → run_post_dispatch_maintenance(config, disks, *, event_bus, …)
    → _scan_disk_incremental(config, disk, *, event_bus)
      → library_index_command(…, event_bus=event_bus)
```

Trois appelants, tous avec un bus en portée :

| Appelant | Bus |
|---|---|
| `pipeline_steps.py:377` (DispatchStep) | `ctx.app.event_bus` |
| `commands/pipeline.py:425` (CLI dispatch) | le bus déjà utilisé ligne 394 |
| `commands/library/audit.py:538` (CLI audit) | bus du boundary |

Requis et non optionnel : un défaut permettrait au bug de revenir silencieusement, et c'est
la règle du projet pour tout site d'émission.

### 4.2 D2 — `trackers_degraded` (phase 2)

Dans `orchestrator.py`, avant la sortie `no_candidates` :

```
results vide ET outcome.trackers_errored > 0 ET NOT all_errored
   → exit_path "trackers_degraded"
   → ("retryable", "trackers_degraded", None)
```

`found=None` (jamais 0) et **l'essai n'est pas consommé**.

`claim_for_search` (`_wanted_store.py:170`) stampe `attempts = attempts + 1` **atomiquement
avec** la transition vers `searching`, donc avant que le verdict soit connu. Le non-consommé
se fait donc par **remboursement explicite** : une méthode de store dédiée
(`refund_search_attempt(wanted_id)`) décrémente l'essai en même temps qu'elle repose le
statut à `pending`, dans la même transaction que le reste du chemin retryable. Un
remboursement ne descend jamais `attempts` sous 0.

Conséquence voulue : `attempts` cesse de compter les pannes et devient un compteur de
recherches **conclues** — ce qui rend A2 lisible sans nouvelle colonne ni migration.

**Précision nécessaire** : `claim_for_grab` incrémente lui aussi `attempts`. Le compteur
n'est donc pas « nombre de recherches » dans l'absolu. Ce n'est pas un problème pour D1 :
une ligne affamée ne devient jamais `available`, donc jamais `grabbed` — sur ce chemin
`attempts` ne compte que des claims de recherche. La condition de D1 (§4.3) est de toute
façon conjointe à un verdict de recherche not_found, ce qui exclut les lignes ayant abouti.

`all_errored` (tous les trackers tombés) reste inchangé sur `trackers_unavailable`.

### 4.3 D1 — escalade armée sur l'évidence (phase 3)

Dans le search pass, en extension de R2 :

```
SI verdict.outcome ∈ {no_candidates, no_matching_episode}
   ET item.kind == "episode"
   ET item.attempts >= 2                       (recherches CONCLUES, cf. 4.2)
   ET toute la saison est diffusée              (aired catalog, aucun épisode futur)
   ET (followed_id, season) pas déjà sondé dans CETTE passe
ALORS sonder une requête saison
   SI filter_to_season rend un pack couvrant
      → _enqueue_season_from_conversion(...)    (helper existant, réutilisé tel quel)
      → émettre SeasonEscalatedAfterEpisodeFailures
   SINON verdict ordinaire, la ligne épisode reste vivante
```

Le helper `_enqueue_season_from_conversion` est réutilisable **sans modification** : ses
paramètres `raw_results` et `season_packs` sont déclarés mais jamais lus dans son corps —
il ne fait qu'enfiler la saison et absorber les épisodes.

**Bornage du coût.** Mémoïsation par `(followed_id, season)` **dans une même passe** : au
plus une sonde saison par saison et par passe, soit ≤ 2 appels trackers par jour pour une
saison qui famine. Sans cela, dix épisodes affamés déclencheraient dix sondes identiques.

**Pourquoi le search pass et pas detect (A5)** : le verdict d'échec y vit déjà, R2 y vit
déjà, et la cadence y rythme déjà les appels trackers. Detect est une passe de poll
catalogue ; y placer une recherche tracker mélangerait deux responsabilités.

**Pourquoi ne pas assouplir DETECT (A6)** : les deux déclencheurs ont des sémantiques
distinctes — DETECT planifie (« la saison est finie et j'en possède peu → prendre le pack »),
D1 répare (« la route épisode échoue de façon prouvée → prendre le pack »). Relâcher la
porte (c) ferait prendre des packs saison alors que la route épisode fonctionne.

### 4.4 D3 — l'action opérateur déclenche (phases 4 et 5)

**Phase 4 — extraction (A3).** La route season-grab sort de `acquisition.py` (995/1000
lignes non vides, plafond dur à 1000) vers un sous-module dédié. Comportement strictement
constant, tests verts, commit isolé pour que la revue puisse vérifier que rien ne change.

**Phase 5 — câblage.** `grab_season` appelle `enqueue_prime_run(config.indexer.db_path,
followed_id)` après création de la ligne, exactement comme `create_follow`. Conformément au
**§6** : 202 + état « En file », **jamais** de 409 ; le seul refus reste l'idempotence (même
action, même cible, déjà en cours), déjà portée par la garde existante.

`prime` (detect → search → grab) est réutilisé plutôt que d'ajouter une sixième commande
runner : il existe, il est conforme §6, il porte la garde d'idempotence, et son poll
catalogue supplémentaire est borné à un seul suivi.

Tout changement de signature de route impose `make openapi` + fichiers régénérés commités.

### 4.5 Événements

Les deux événements émis aujourd'hui par le helper (`WantedEnqueued`,
`SeasonAbsorbedEpisodes`) ne disent pas **pourquoi** l'absorption a lieu. Nouvel événement :

```
SeasonEscalatedAfterEpisodeFailures(
    season_wanted_id, media_ref, season,
    trigger_outcome,          # no_candidates | no_matching_episode
    starved_episode_ids,      # les épisodes qui ont motivé l'escalade
)
```

Il permet à l'UI de dire « les épisodes n'existent pas séparément, je prends le pack de la
saison » (§2, libellé français clair) plutôt qu'une absorption muette.

`trackers_degraded` doit remonter comme « recherche non concluante — tracker indisponible »,
jamais « rien trouvé ».

## 5. Hors périmètre

- **Assouplir les portes de DETECT** — A6, deux déclencheurs distincts.
- **Le bug ouvert « l'année collée aux requêtes TV »** (`torznab.py:346`) — défaut connu,
  indépendant, non touché ici.
- **Toute refonte de la cadence** — Hot/Warm/Cold et `cutoff_days: 30` restent inchangés.

## 6. Stratégie de test (écrits AVANT l'implémentation, A4)

**D4**
- Un subscriber espion abonné au bus du processus **reçoit** `LibraryScanCompleted` émis par
  le scan post-dispatch (échoue aujourd'hui).
- `maybe_run_post_dispatch_maintenance` sans `event_bus` est une **erreur de typage/appel** —
  le paramètre est requis.
- Régression bout-en-bout : dispatch d'un épisode possédé ⇒ la ligne `grabbed` passe `done`.

**D2**
- 1 tracker sur 2 en erreur + 0 résultat ⇒ `("retryable", "trackers_degraded", None)`, et
  `attempts` **inchangé de bout en bout** (claim +1 puis remboursement −1), la ligne
  revenant `pending`.
- Remboursement sur une ligne à `attempts == 0` ⇒ reste 0, jamais négatif.
- 0 tracker en erreur + 0 résultat ⇒ inchangé `("not_found", "no_candidates", 0)`.
- Tous les trackers en erreur ⇒ inchangé `trackers_unavailable`.

**D1**
- `no_candidates` + `attempts >= 2` + saison entièrement diffusée + pack couvrant ⇒ saison
  enfilée, épisodes absorbés, `SeasonEscalatedAfterEpisodeFailures` émis.
- Sous le seuil ⇒ aucune escalade et **aucun appel tracker supplémentaire**.
- Saison non entièrement diffusée ⇒ aucune escalade.
- Sonde sans pack couvrant ⇒ la ligne épisode garde son verdict et reste vivante.
- Deux épisodes affamés de la même saison dans une même passe ⇒ **une seule** sonde.
- Régression nommée : American Dad! S15E21 — requête épisode 0 résultat, requête saison
  4 packs ⇒ escalade.

**D3**
- La route crée la ligne **et** enfile un run ; réponse 202.
- Chemin `reused` (ligne saison vivante déjà présente) ⇒ pas de double enfilement.
- Action déjà en cours sur la même cible ⇒ idempotence, **jamais** 409 sur une action
  légitime (§6).
- Rôle staging ⇒ 403 inchangé (`require_not_staging`).

**Extraction (phase 4)** — la suite complète passe avant et après, sans modification de test :
c'est la preuve du comportement constant.

## 7. ACCEPTANCE

Chaque critère est une commande exécutable avec sa sortie attendue documentée.

| ID | Commande | Attendu |
|---|---|---|
| ACC-01 | `python scripts/check-acquisition-coherence.py` | exit 0, zéro anomalie (**bloquant**) |
| ACC-02 | `make lint` | 0 erreur |
| ACC-03 | `make test` | 0 failed, 0 error |
| ACC-04 | `make check` | vert (dont module-size : `acquisition.py` < 1000) |
| ACC-05 | `python scripts/check-module-size.py` | `acquisition.py` absent des findings BLOCK |
| ACC-06 | `make openapi && git diff --exit-code` | aucun drift |
| ACC-07 | Run daté prouvant l'escalade sur une saison affamée réelle | saison enfilée + épisodes absorbés |

ACC-07 exige un déroulé réel daté — pas une prose (§méthode : « aucun "conforme" sans un run
exécuté daté »).

## 8. Ordre des phases

| Phase | Contenu | Pourquoi cet ordre |
|---|---|---|
| 1 | D4 — propagation du bus | Masque l'effet de tout le reste ; les fantômes actuels sont dus à lui |
| 2 | D2 — `trackers_degraded` | Change la sémantique d'`attempts` dont dépend la phase 3 |
| 3 | D1 — escalade sur évidence | Le cœur du bug rapporté |
| 4 | Extraction `acquisition.py` | Dégage la marge sous le plafond, comportement constant |
| 5 | D3 — déclenchement + événement | Dépend de la marge dégagée en phase 4 |
