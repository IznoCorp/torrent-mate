# EPIC — Acquisition tracking spine (unified acquisition / pipeline / decisions / resolution)

**Vision (opérateur)** : une couche de suivi cohérente reliant _suivi des acquisitions
(film/série/épisode)_, _exécution de pipeline_, _décisions de scraping_, _médias en
attente de résolution_. Aujourd'hui ces 4 piliers **existent mais silotés** :

| Pilier                   | Store existant                                                   |
| ------------------------ | ---------------------------------------------------------------- |
| Acquisitions             | `acquire.db` — follows + wanted (statut par média/épisode)       |
| Exécution pipeline       | `library.db` — `pipeline_run` (kind/command/steps)               |
| Décisions scraping       | sous-système décisions (`web/routes/decisions`, decision writer) |
| En attente de résolution | `web/staging/read_model.py` (Flow Board « à résoudre »)          |

**Le manque** : rien ne relie _cette acquisition (grab) → ce run de pipeline → cette
décision → cet état de résolution_. L'épic construit la **colonne vertébrale
connective** (clé = `info_hash` + identité média) puis les vues/actions qui la
consomment.

## Principes gravés (tout l'épic)

- **Overlay advisory** : le filesystem + les stores existants restent la vérité ; le
  spine est un **indice réconcilié**, fail-soft. Registre vidé ⇒ comportement actuel.
- **Pas de fusion de bases** : `acquire.db` et `library.db` restent séparées ; on
  **joint à la lecture** par identité/hash. Zéro big-bang.
- **Additif** : chaque feature borne son périmètre, sa branche, sa PR, sa revue.

## Séquence des features

### F0 — Spine de provenance + #30 · `provenance` v1 (branche actuelle)

La table `staging_provenance` (per-hash, advisory) trace grab→ingest→sort→scrape→
dispatch, et porte la **clé connective** (`info_hash` + `media_ref`) sur laquelle
tout le reste joindra.

- Livre **#30** : identité déterministe au scrape (films **et** séries), en amont de
  l'inférence #29 (fallback). Renforce #28.
- Écritures best-effort aux étapes ; reconcile-prune (FS=vérité).
- **DESIGN** : `docs/archive/features/provenance/DESIGN.md`.
- _Ship : le socle + #30. Aucune UI. Valeur immédiate + fondation._

### F1 — Vue « parcours » unifiée (lecture) · feature suivante

Un endpoint + UI minimale qui **JOINT** provenance ↔ wanted (acquire.db) ↔
`pipeline_run` (library.db) ↔ décision ↔ état de résolution → **un** parcours par
acquisition (grabbed → téléchargé → ingéré → scrapé → dispatché → en médiathèque).

- Rend le pipeline **lisible** (product-intent §pipeline lisible).
- Read-only, aucun nouveau mécanisme d'écriture. Prouve la jointure tôt (validation).

### F2 — Intégration des décisions de scraping — **MIGRATE (choix opérateur)**

> Décision opérateur : on **migre** l'état de résolution sur le spine (pas un simple
> lien). L'intégration est profonde ; garde-fous obligatoires : revue adverse + tests
> anti-régression sur le flux décisions existant (ne rien casser).

Relier le sous-système décisions au spine : une décision prise sur un item de staging
met à jour son parcours ; « médias en attente de résolution » devient un **état
requêtable de première classe** sur le spine (plus une dérivation de read_model).

- Consolide le pilier « décisions » + « en attente de résolution » sur la colonne.

### F3 — Liaison run de pipeline ↔ acquisitions

Lier chaque `pipeline_run` aux acquisitions qu'il a traitées (quels grabs ont coulé
dans quel run) → « quel run a scrapé/dispatché ce média ? » devient répondable.

- Consolide le pilier « exécution pipeline » sur la colonne.

### F4 — Reprise / actions ciblées

Sur le spine : reprendre un item bloqué, re-scraper un grab précis, requeue par état
de parcours. Le registre devient le substrat des actions de maintenance ciblées.

### F5 — Dashboard « état de la machine » (capstone)

La vue web unifiée : acquisitions + pipeline + décisions + en-attente, une page,
consommant F0–F3. C'est l'aboutissement produit.

## Rationale de l'ordre

F0 est la fondation sur laquelle tout joint (à livrer en premier — borné, ship #30).
F1 prouve la jointure tôt (valeur + validation de l'archi). F2/F3 rapatrient les
piliers existants sur la colonne. F4/F5 sont les payoffs à forte valeur. Chaque
feature est indépendamment mergeable et laisse le système cohérent.

## Ce que l'épic ne fait PAS

- Ne fusionne pas `acquire.db` et `library.db`.
- Ne réécrit pas les sous-systèmes existants (décisions, pipeline_run, read_model) —
  il les **relie** ; leur rapatriement (F2/F3) est incrémental et fail-soft.
- Ne fait dépendre aucune correction de la présence/cohérence du spine.
