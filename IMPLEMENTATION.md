# Implementation Progress — acq-states

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Acquisitions — états véridiques (disponibilité tracker) + amorce du suivi + poster serveur
**Type**: feat
**Version bump**: 0.54.1 → 0.55.0 (minor)
**Branch**: feat/acq-states
**Ticket**: #319 — claimed (session locale, heartbeat actif)
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/acq-states/DESIGN.md
**Master plan**: `docs/features/acq-states/plan/INDEX.md`

## Contexte

Incident fondateur : la série _Furious_ (TVDB 468000), ajoutée le 2026-07-27, affichait
« À jour » avec 3 épisodes diffusés absents de la médiathèque, et sans poster.

Trois causes racines établies avec preuves (détail dans le DESIGN) :

- **RC1** — `POST /followed` n'amorce ni catalogue ni file `wanted` ; seul le cron `detect`
  de 03:00 le fait → le « Rechercher » manuel est un succès silencieux.
- **RC2** — la carte et le panneau de détail lisent **deux sources divergentes** : cache vide
  → « À jour » côté carte, repli `poll_aired` live → 3 épisodes `manquant` côté détail.
- **RC3** — aucun enrichissement serveur du poster ; il ne vient que du candidat de recherche
  envoyé par le client, donc jamais par le formulaire d'ajout par ID.

L'incident lui-même a été résolu manuellement le 2026-07-27 (`detect` + `grab` + pipeline 264) :
les 3 épisodes sont en médiathèque. Cette feature corrige les causes, pas le symptôme.

## Décisions opérateur (2026-07-27)

| Sujet             | Décision                                                                               |
| ----------------- | -------------------------------------------------------------------------------------- |
| Modèle d'états    | 5 états — À jour / En attente / À récupérer / En cours d'acquisition / **Non vérifié** |
| « Disponible »    | = **candidat réellement prenable** (survit aux filtres éliminatoires)                  |
| Persistance       | colonnes sur `wanted` (`last_search_outcome`, `last_search_found`)                     |
| Amorce            | 201 immédiat + run d'amorce **visible** via l'autorité de déclenchement existante      |
| Fichier `VERSION` | **supprimé** — mort et désynchronisé (0.48.0 vs 0.54.1 réel)                           |
| Merge             | auto                                                                                   |

**Arbitrage complémentaire (2026-07-27, après relecture du plan initial)** — recherche et
récupération deviennent **deux opérations distinctes** : sans cette séparation, « À récupérer »
ne durerait que quelques millisecondes à l'intérieur d'un appel de fonction. Trois passes
(`detect` → `search` → `grab`), le grab reste **automatique** à la passe suivante, avec un
bouton « Récupérer maintenant » pour ne pas attendre. Le grab **refait sa propre recherche**
plutôt que de réutiliser le candidat mémorisé (choix opérateur) : le surcoût tracker reste
borné parce que le grab ne parcourt que les items déjà connus disponibles.

## Phases

| #   | Phase                                    | File                                                                                         | Status |
| --- | ---------------------------------------- | -------------------------------------------------------------------------------------------- | ------ |
| 1   | Socle de persistance (migration + store) | [phase-01-persistence.md](docs/features/acq-states/plan/phase-01-persistence.md)             | [x]    |
| 2   | Séparation search / grab dans le moteur  | [phase-02-search-grab-split.md](docs/features/acq-states/plan/phase-02-search-grab-split.md) | [x]    |
| 3   | Commande `search` + ordonnancement       | [phase-03-search-command.md](docs/features/acq-states/plan/phase-03-search-command.md)       | [x]    |
| 4   | Dérivation serveur des 5 états           | [phase-04-state-derivation.md](docs/features/acq-states/plan/phase-04-state-derivation.md)   | [x]    |
| 5   | Fin des sources divergentes              | [phase-05-single-source.md](docs/features/acq-states/plan/phase-05-single-source.md)         | [x]    |
| 6   | Amorce à la création du suivi            | [phase-06-follow-priming.md](docs/features/acq-states/plan/phase-06-follow-priming.md)       | [x]    |
| 7   | Enrichissement serveur des métadonnées   | [phase-07-server-metadata.md](docs/features/acq-states/plan/phase-07-server-metadata.md)     | [x]    |
| 8   | UI — 5 états + Récupérer maintenant      | [phase-08-ui-states.md](docs/features/acq-states/plan/phase-08-ui-states.md)                 | [x]    |
| 9   | Garde-fous et acceptation                | [phase-09-guardrails-acc.md](docs/features/acq-states/plan/phase-09-guardrails-acc.md)       | [x]    |

## ACC — vérification exécutée (2026-07-27, session dev)

Commande globale : `python3 -m pytest tests/unit/web/routes/test_create_follow_priming.py
tests/unit/web/acquisition/test_states.py tests/unit/web/acquisition/test_source_agreement.py
tests/acquire/test_search_verdicts.py tests/acquire/test_search_pass.py
tests/acquire/test_grab_pass.py tests/unit/web/test_no_tracker_call_on_read.py -q`
→ **84 passed**.

| ID     | Verdict | Preuve exécutée                                                                                                                                                                             |
| ------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ACC-01 | ✅      | `test_create_follow_priming.py` 4/4 — 201 + run prime + `verification_en_cours`                                                                                                             |
| ACC-02 | ✅      | `test_states.py::test_empty_catalog_is_never_up_to_date` (mutation-vérifié en phase 4)                                                                                                      |
| ACC-03 | ✅      | `test_source_agreement.py` 12/12 — mêmes faits, même dérivation, règle open-rows-latest partagée                                                                                            |
| ACC-04 | ✅      | matrice verdicts : chaque outcome INCONCLUSIVE ⇒ `non_verifie`, found=None jamais 0                                                                                                         |
| ACC-05 | ✅      | exit-paths orchestrateur : 3D-only/0-seed/packs ⇒ `all_filtered`/`no_seeders`/`no_matching_episode`                                                                                         |
| ACC-06 | ✅ réel | backfill exécuté sur la base réelle : `SELECT COUNT(*) … poster_url IS NULL` → **0** sur 10 suivis                                                                                          |
| ACC-07 | ⏸ défér | 4 anomalies `SEARCHED_WITHOUT_VERDICT` = lignes héritées du moteur pré-verdict (prod sur main) ; se résorbent à la 1re passe `search` post-déploiement — re-exercice post-merge obligatoire |
| ACC-08 | ✅      | `test_no_tracker_call_on_read.py` — 3 couches instrumentées, 0 appel sur GET followed + completeness                                                                                        |
| ACC-09 | ✅ +⏸   | `test_search_pass_adds_no_torrent` ; re-exercice réel post-déploiement (passe 03:10)                                                                                                        |
| ACC-10 | ✅      | `test_grab_reverts_to_pending_when_the_torrent_vanished` — revert honnête + verdict enregistré                                                                                              |
| ACC-11 | ✅      | `test_grab_only_walks_available_items` + `test_grab_pass_never_walks_pending…` (mutation-vérifié)                                                                                           |
| ACC-12 | ⏸ défér | bouton « Récupérer maintenant » — vérification Chrome sur staging post-déploiement (+ preuve 390 px)                                                                                        |

Protocole critère-différé (feature-lifecycle.md) : ACC-07, ACC-09 (volet réel) et ACC-12
sont ré-exercés post-merge sur l'environnement déployé, avant clôture du ticket #319.

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

All phases done — `/implement:feature-pr` (gate + push + PR + CI), puis re-exercice ACC différés post-déploiement.
