# ACCEPTANCE — `spine-truth` (déroulé exécuté 2026-08-05, après déploiement)

§méthode règle 2 : « aucun verdict *conforme* sans déroulé réel en prod avec preuve datée ».
Tout ce qui suit a été exécuté sur les **bases réelles** (`~/dev/PersonalScraper/.data/`,
partagées entre dev / prod / staging), depuis le checkout de déploiement
`~/deploy/torrentmate` et son venv, après merge de la PR #399.

## Déploiement

```
[2026-08-05 09:10:34] /Users/izno/deploy/torrentmate : main a avancé 821009d7 -> 1a717ef7 — déploiement
```

`GET /api/version` servi par prod, cache PWA busté (`unregistered: 0, cachesDeleted: 0`) :

```json
{"version": "0.80.0", "build_commit": "1a717ef756e3302170333a6e2121ede9d84b97d2"}
```

`personalscraper-watch` — que l'autodeploy ne redémarre pas — relancé explicitement après
vérification qu'il était inactif (aucun `pipeline.lock`, `COUNT(*) FROM pipeline_run WHERE
ended_at IS NULL` = 0, aucun processus enfant). Nouveau pid 71705 à 09:14:57, boot propre.

## ACC-01 — la migration 015 est appliquée sur la base réelle

```
PRAGMA user_version;                     → 15
sqlite_master(staging_provenance).kind   → CHECK (kind IN ('movie', 'episode', 'season'))
index                                    → idx_provenance_current_path
                                           idx_provenance_resolution_state
```

Snapshot de sécurité écrit par le moteur de migration : `acquire.db.pre-migration-15.bak`.

## ACC-02 — le garde-fou CRIE sur l'état fautif (avant réparation)

```
$ python scripts/check-acquisition-coherence.py
❌ [SPINE_ROW_MISSING] Rooster S01E10 (wanted #47): grabbed_hash c67e36c69c4a… has no
   staging_provenance row — the grab's provenance write never landed …
   … (57 lignes)
57 anomalies — 57 error, 0 warning, 0 info (57 counted).
```

**57**, soit exactement les 57 parcours perdus. C'est ce que la règle aurait affiché le
2026-08-02 au lieu des quatre jours de silence.

## ACC-03 — l'état est réparé (§13)

Sauvegarde préalable : `acquire.db.pre-backfill-spine-truth.bak`.

```
$ python scripts/backfill-provenance-spine.py --apply
…
f04708468f3c… season   Batman: Caped Crusader        → dispatched /Volumes/Disk1/medias/series/Batman Caped Crusader (2024)
62c207c827a8… season   L'Attentat du vol Pan Am 103  → dispatched /Volumes/Disk1/medias/series/The Bombing of Pan Am 103 (2025)
d412a66379ec… season   American Dad!                 → grabbed    — (atterrissage non prouvé)
9f27cc907299… season   American Dad!                 → grabbed    — (atterrissage non prouvé)

rebuilt 57 journey(s) — 55 dispatched, 2 stopped at grabbed.
```

Les deux `grabbed` sont les packs American Dad encore en vol (`wanted.status='grabbed'`) :
aucun atterrissage à prouver, donc aucun atterrissage écrit.

État de la spine, avant → après :

| | avant | après |
| --- | --- | --- |
| `dispatched` | 1 | **56** |
| `grabbed` | 0 | **2** |
| par kind | `movie` 1 | `episode` 47 · `movie` 5 · **`season` 6** |

## ACC-04 — le garde-fou est SILENCIEUX après réparation

```
$ python scripts/check-acquisition-coherence.py ; echo $?
0 anomalies — 0 error, 0 warning, 0 info (0 counted).
0
```

Second garde-fou, inchangé :

```
$ python scripts/check-media-complete.py
❌ INCOMPLETE  [tv] Top Chef Le Concours Parallèle (2026)
1 checked, 1 incomplete.
```

C'est l'**ouvert assumé connu** (aucune donnée d'épisode chez les fournisseurs : TVDB 475278
= 0 épisode, TMDB 315820 = 404), pas une régression de cette feature.

## ACC-05 — §13 à l'écran, et §12 à 390 px

Vue d'ensemble chargée dans une iframe **390 px** same-origin sur
`https://tm.iznogoudatall.xyz` (le viewport Chrome est épinglé à 1440), service-worker
désenregistré et caches vidés au préalable — bundle servi `assets/index-C3vdZ7hQ.js`.

| Tuile | Valeur | Lien | `display` de l'ancre | L'ancre couvre la carte | Hauteur |
| --- | --- | --- | --- | --- | --- |
| En vol | 2 | `/acquisition?tab=parcours` | `block` | oui (124×171 = 124×171) | 124 |
| Bloqués | 0 | `/acquisition?tab=parcours` | `block` | oui | 124 |
| En attente de résolution | 0 | `/medias` | `block` | oui | 125 |
| **Dispatchés** | **56** | — | — | — | 125 |

```
docScrollW = 386   docClientW = 386   →  aucun débordement horizontal
heightsByRow = {196: [124,124], 332: [125,125]}   →  chaque rangée est régulière
```

« Dispatchés » affiche **56** là où l'opérateur lisait **1**. La tuile entière est la cible
tactile, les quatre tuiles s'alignent, rien ne déborde à la largeur d'un téléphone.

## Ouvert (non introduit par cette feature)

- **Top Chef Le Concours Parallèle** reste incomplet — aucune donnée d'épisode côté
  fournisseurs. Ouvert assumé par l'opérateur, rappelé ici pour qu'il ne soit pas relu
  comme une régression.
- Les deux packs **American Dad** sont reconstruits en `grabbed` : leur `wanted` est encore
  ouvert. Leur parcours se complétera par le chemin normal, désormais corrigé — c'est le
  premier cas réel qui éprouvera la corrélation par `info_hash` de bout en bout.
