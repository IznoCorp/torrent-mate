# DESIGN — reswitch : auto-bascule d'une release bloquée + seeders renforcés dans le score

**Codename** : `reswitch` · **Type** : `feat` · **Bump** : minor (0.64.0 → 0.65.0)
**Ticket** : #342 · **Merge** : auto

## Demande opérateur (mots exacts)

> « Re-grab (tenter une autre release) si un torrent est bloqué et ne démarre pas,
> automatiquement on doit changer de release. De plus le nombre de seeder doit influer
> sur le score d'une release pour favoriser les releases les plus seeder. »

Contexte terrain : STSNW S03E09/E10 sont marqués « En attente de sources » alors que des
sources existent sur C411 / Tr4ker. Cause racine vérifiée (session précédente) : le swarm
est **injoignable** (tracker annonce 8 seeds, 0 connecté) — ce n'est PAS un bug de recherche.
Une release peut donc être _grabée_ puis rester bloquée à 0 % : il faut alors **basculer
automatiquement sur une autre release**, et **biaiser le choix vers les releases les mieux
seedées** en amont.

## Constitution produit (CONTRAIGNANT)

Sert `docs/reference/product-intent.md` :

- **§2 (véridicité des acquisitions)** : un item « en cours d'acquisition » qui ne progresse
  jamais est un mensonge silencieux ; le système DOIT réagir (basculer) et le DIRE.
- **§méthode** : pas de « conforme » sans run daté exécuté ; réaction jamais silencieuse.

## État des lieux (audit code — ancres réelles)

- **Seeders déjà dans le score** : `config/ranking.json5:16-26` — `field:"seeders"`, `weight:1`,
  seuils `0→0, 5→5, 20→10, 100→20`. Moteur générique `api/tracker/_ranking.py:69` lit
  `r.seeders`. Plancher `min_seeders:1` (`ranking.json5:40`) écarte les 0-seed. ⇒ la demande A
  est un **renforcement**, pas un ajout.
- **`TrackerResult.seeders` / `.leechers`** : `api/tracker/_base.py:100-101`, parsés par tous
  les trackers (torznab/lacale/c411).
- **Grab** : `acquire/orchestrator.py:626` `GrabOrchestrator.grab()` → `add()` (`:744`) →
  `_persist_success` (`_grab_pass.py:217`) → `mark_grabbed(id, info_hash)` (`:274`).
- **Garde d'idempotence** : `_grab_pass.py:114` — un item `grabbed`/`grabbed_hash != None` n'est
  **jamais** re-claimé. C'est le point à débloquer pour rebasculer.
- **Stall observé mais AUCUN acteur** : `web/acquisition/downloads.py:44` mappe `stalledDL →
"stalled"` (affichage seul). `qbittorrent.py:753 _torrent_item` ne lit **que**
  `progress/state/ratio/error_reason` — **pas** `num_complete`/seeds connectés ⇒ « swarm mort »
  non observable aujourd'hui.
- **Requeue sur ABSENCE seulement** : `reconcile.py:162` `requeue_missing` si le hash a disparu
  du client — un torrent présent-mais-bloqué n'est PAS requeué.
- **`rank()` sans exclusion** : `_ranking.py:33` n'a pas de paramètre « exclure ce hash » ; le
  runner-up n'est pas persisté ⇒ rebasculer impose de re-chercher + re-ranker en **excluant**
  les hashes déjà tentés. Cet ensemble d'exclusion est la pièce manquante.

## Approche (5 phases)

### Phase 1 — Seeders renforcés (demande A)

`config/ranking.json5` + `config.example/ranking.json5` : monter le poids seeders (1 → **2**) et
affiner les seuils (`0→0, 1→3, 5→8, 20→14, 50→18, 100→22`) pour que, à qualité égale, une release
bien seedée l'emporte nettement, sans dominer la résolution (max seeders 2×22=44 vs résolution
4×20=80). `min_seeders:1` conservé (écarte les 0-seed morts). Test : à qualité égale, la release
la mieux seedée sort en tête ; un delta de seeders franchit un écart de codec mais pas un saut de
résolution.

### Phase 2 — Observabilité du swarm

`api/torrent/_base.py TorrentItem` : ajouter `swarm_seeds: int | None` (= `num_complete` qBit,
seeds connus du tracker) — champ optionnel, rétro-compatible. `qbittorrent.py:753 _torrent_item`
le renseigne depuis le payload `torrents/info` (déjà présent). Helper pur de classification
`classify_stall(item, grabbed_age_s, *, thresholds) -> StallVerdict` (`healthy` |
`stalled_recoverable` | `stalled_dead`) : `stalled_dead` = état `stalled`/`stalledDL` **ET**
progress 0 **ET** (`swarm_seeds == 0` **OU** âge > seuil dur). Tests unitaires exhaustifs (matrice
état × progress × swarm × âge).

### Phase 3 — Mémoire des hashes tentés + exclusion au ranking

Migration indexer/acquire : colonne `tried_hashes_json` (liste JSON) sur la table `wanted`
(`acquire/domain.py` + store). Méthodes store `append_tried_hash(id, hash)` /
`list_tried_hashes(id)`. `rank()` / `rank_candidates()` (`_ranking.py` / `orchestrator.py:262`)
gagnent un paramètre `exclude_hashes: frozenset[str] = frozenset()` appliqué avant le tri. Le
chemin grab passe `list_tried_hashes(item.id)` en exclusion. Tests : un hash exclu n'est jamais
choisi ; rétro-compat (défaut vide = comportement actuel).

### Phase 4 — Acteur de rebascule

Nouvelle passe `reswitch_stalled(store, client, config, now)` (dans `acquire/reconcile.py` ou un
module dédié `acquire/_reswitch.py`) invoquée dans la cadence acquisition (là où `reconcile`
tourne) : pour chaque item `grabbed`, lire l'état qBit ; si `classify_stall == stalled_dead` :

1. `append_tried_hash(id, grabbed_hash)`, 2) supprimer le torrent mort du client (`delete`), 3)
   `requeue` l'item (clear `grabbed_hash`, statut → `pending`, en **conservant** `tried_hashes`),
2. émettre `GrabReswitched(media_ref, old_hash, reason)`. La passe grab suivante re-cherche, ranke
   en excluant `tried_hashes`, et grabe une **autre** release. Garde-fou : si toutes les releases
   sont exclues → `en_attente` avec raison « toutes les sources tentées ont échoué » (jamais un
   mensonge). Tests : stalled_dead ⇒ requeue + hash mémorisé + event ; healthy ⇒ intact ;
   plus-de-release ⇒ en_attente honnête.

### Phase 5 — Surfaçage UI + events + ACC

Catalogue d'events (`GrabReswitched`) ; la carte d'acquisition affiche la raison de bascule
(« Source bloquée — bascule vers une autre release ») et le nb de tentatives. `make openapi` si un
modèle web change. ACC exécutables + preuve Chrome 390 px + `make check` + déploiement.

## Non-buts

- Pas de refonte du moteur de ranking (on ajuste config + un paramètre d'exclusion).
- Pas de nouvelle UI de réglage du score (c'est #18, QualityProfile éditable — feature distincte).
- Pas de détection « swarm lent mais vivant » comme motif de bascule (seul `stalled_dead` bascule ;
  un swarm vivant qui télécharge lentement est laissé tranquille).

## ACCEPTANCE (commandes exécutables)

- **ACC-01 (A)** — test ranking : à qualité égale, `rank()` place la release 100-seeds avant la
  1-seed ; commande `python -m pytest tests/tracker/test_ranking_seeders.py -q`.
- **ACC-02 (Phase 2)** — `classify_stall` : matrice couverte ; `stalled + 0% + swarm_seeds==0` ⇒
  `stalled_dead`. `python -m pytest tests/.../test_classify_stall.py -q`.
- **ACC-03 (Phase 3)** — `rank(..., exclude_hashes={h})` n'émet jamais `h` ; store round-trip
  `append/list_tried_hashes`. Migration appliquée (colonne présente).
- **ACC-04 (Phase 4)** — passe reswitch : un item `grabbed` stalled_dead ⇒ requeue + hash mémorisé
  - `GrabReswitched` émis ; plus-de-release ⇒ `en_attente` honnête. Test d'intégration.
- **ACC-05** — `make check` vert, `make openapi` sans dérive, preuve Chrome 390 px si UI touchée,
  déploiement prod (BUILD_COMMIT + health 200).

## Phases (indicatif — `/implement:plan` fait foi)

1. Seeders renforcés (config + test).
2. Observabilité swarm (`TorrentItem.swarm_seeds` + `classify_stall`).
3. Mémoire hashes tentés + exclusion ranking (migration + store + `rank` param).
4. Acteur de rebascule (`reswitch_stalled` + event + garde-fou honnête).
5. Surfaçage UI + events + ACC + déploiement.
