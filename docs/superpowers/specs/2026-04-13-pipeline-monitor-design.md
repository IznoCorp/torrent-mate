# Pipeline Monitor — Design Spec

## Overview

A skill (`/pipeline-monitor`) and 7 agents that orchestrate, monitor, and verify the `personalscraper` pipeline execution step-by-step with real-time feedback, a persistent BUG LIST, and automated debugging.

## Architecture

### Components

- **Skill `/pipeline-monitor`** — Chef d'orchestre. Gère le workflow complet.
- **3 agents techniques** — Lancés après chaque step :
  - `pipeline-orphan-hunter` — tmp dirs, lock files, dossiers vides, résidus sur les 4 disques
  - `pipeline-state-validator` — cohérence fichiers d'état vs filesystem
  - `pipeline-output-analyzer` — warnings, erreurs silencieuses, timings anormaux
- **4 agents métier** — Lancés après leur step respectif :
  - `pipeline-ingest-checker` — après INGEST
  - `pipeline-sort-checker` — après SORT
  - `pipeline-scrape-checker` — après SCRAPE (inclut process)
  - `pipeline-dispatch-checker` — après DISPATCH

### Flow

```
User → /pipeline-monitor (skill)
         │
         ├─ GATE 0: Pré-analyse
         │    ├─ Inventaire qBit (connexion, torrents, états)
         │    ├─ État staging (001-MOVIES, 002-TVSHOWS, 097-TEMP)
         │    ├─ État tracker (ingested_torrents.json)
         │    ├─ Espace disque (SSD + Disk1-4)
         │    ├─ Rapport prévisionnel → affiché à l'utilisateur
         │    ├─ Créer BUG LIST markdown
         │    └─ Créer Tasks miroir
         │
         ├─ Pour chaque step (ingest, sort, process, verify, dispatch):
         │    ├─ Lancer `personalscraper -v <step>` (FOREGROUND, timeout 600s)
         │    ├─ Afficher output + analyse à l'utilisateur
         │    ├─ Si erreur critique → STOP → protocole nettoyage
         │    ├─ Lancer agents en parallèle:
         │    │    ├─ orphan-hunter
         │    │    ├─ state-validator
         │    │    ├─ output-analyzer
         │    │    └─ <step>-checker (agent métier du step)
         │    ├─ Agréger rapports → BUG LIST
         │    ├─ Afficher résumé step à l'utilisateur
         │    └─ GATE N: valider toutes les conditions avant step suivant
         │
         ├─ GATE 6: Analyse finale post-pipeline
         └─ Phase traitement: chaque item BUG LIST → /systematic-debugging
```

## Pipeline Steps (step-by-step, pas monolithique)

| #   | Commande                      | Agents techniques                               | Agent métier     |
| --- | ----------------------------- | ----------------------------------------------- | ---------------- |
| 1   | `personalscraper -v ingest`   | orphan-hunter, state-validator, output-analyzer | ingest-checker   |
| 2   | `personalscraper -v sort`     | orphan-hunter, state-validator, output-analyzer | sort-checker     |
| 3   | `personalscraper -v process`  | orphan-hunter, state-validator, output-analyzer | scrape-checker   |
| 4   | `personalscraper -v verify`   | orphan-hunter, state-validator, output-analyzer | —                |
| 5   | `personalscraper -v dispatch` | orphan-hunter, state-validator, output-analyzer | dispatch-checker |

## BUG LIST

### Double persistance

1. **Fichier markdown** : `docs/pipeline-runs/YYYY-MM-DD-HHhMM-pipeline-run.md` — persiste après la conversation, suivi d'avancement, permet de reprendre
2. **Tasks** : miroir numéroté (#1, #2...) — suivi temps réel dans le terminal

### Structure markdown

```markdown
# Pipeline Run — YYYY-MM-DD HHhMM

## Status: EN COURS | TERMINÉ | STOPPÉ (erreur critique)

## Pré-analyse

- Torrents à ingérer: X
- Médias en staging: X films, X séries
- Espace disque: ...
- Résultat attendu: ...

## Exécution

### INGEST — OK | ERREUR | SKIPPED

- Durée: Xs
- Résultat: X copiés, X skippés, X erreurs
- Vérifié par: ingest-checker, orphan-hunter, state-validator, output-analyzer

### SORT — ...

(même structure par step)

## BUG LIST

| #   | Catégorie    | Sévérité | Step     | Description            | Status    |
| --- | ------------ | -------- | -------- | ---------------------- | --------- |
| 1   | bug          | critique | INGEST   | IP bannie qBit         | TRAITÉ    |
| 2   | amélioration | mineur   | DISPATCH | Pas de circuit breaker | À TRAITER |

## Traitement

### #1 — IP bannie qBit

- Diagnostic: ...
- Fix: ...
- Status: TRAITÉ
```

### Catégories et sévérités

- **Catégories** : `bug`, `anomalie`, `amélioration`, `erreur`
- **Sévérités** : `critique` (stop pipeline), `moyen`, `mineur`
- **Status** : `À TRAITER`, `EN COURS`, `TRAITÉ`, `NON REPRODUCTIBLE`, `CONNU`

## Agents — Spécifications détaillées

### Agents techniques (après chaque step)

#### `pipeline-orphan-hunter`

- Scanne 097-TEMP, 001-MOVIES, 002-TVSHOWS pour `_tmp_*` dirs
- Scanne `/Volumes/Disk{1,2,3,4}/medias/` pour `_tmp_dispatch_*`
- Vérifie `.personalscraper/pipeline.lock` (stale = orphan)
- Détecte dossiers vides dans les catégories
- Retourne : liste des orphelins (chemin, taille, date)

#### `pipeline-state-validator`

- Lit `ingested_torrents.json` et vérifie que chaque entrée correspond à un dossier réel en staging ou déjà dispatché
- Lit `media_index.json` et vérifie la cohérence avec les disques
- Vérifie que `pipeline.lock` n'existe pas (ou est stale après un crash)
- Retourne : liste des incohérences état/filesystem

#### `pipeline-output-analyzer`

- Reçoit la sortie console brute du step
- Cherche : lignes `error`, `warning`, tracebacks, `skip` inattendus
- Détecte les timings anormaux (step trop long ou trop court)
- Retourne : liste des anomalies (ligne, contexte, sévérité)

### Agents métier (après leur step uniquement)

#### `pipeline-ingest-checker` (après INGEST)

- Connecte à qBit, liste tous les torrents completed
- Pour chaque torrent : vérifie qu'il est soit dans le tracker (déjà traité), soit dans 097-TEMP (fraîchement copié)
- Vérifie intégrité des copies (tailles correspondent)
- Détecte les torrents oubliés (dans qBit completed mais ni trackés ni copiés)
- Retourne : liste des problèmes d'ingestion

#### `pipeline-sort-checker` (après SORT)

- Vérifie que 097-TEMP est vide (gate condition)
- Pour chaque item trié : vérifie qu'il est dans le bon dossier catégorie (film → 001-MOVIES, série → 002-TVSHOWS, etc.)
- Détecte les doublons (même média dans TEMP et dans catégorie)
- Retourne : liste des problèmes de tri

#### `pipeline-scrape-checker` (après PROCESS)

- Pour chaque dossier dans 001-MOVIES :
  - NFO existe, XML valide, `<uniqueid>` non-vide
  - Titre NFO correspond au nom de dossier
  - Artwork minimum : poster + landscape
- Pour chaque dossier dans 002-TVSHOWS :
  - `tvshow.nfo` existe, XML valide
  - Structure `Saison XX/` présente
  - Artwork minimum : poster + landscape
- Retourne : liste des problèmes de scraping

#### `pipeline-dispatch-checker` (après DISPATCH)

- Pour chaque média dispatché :
  - Arrivé sur le bon disque, dans la bonne catégorie
  - Séries : merge correct (pas de dossier dupliqué)
  - Films : remplacement correct (pas d'ancienne version restante)
- Scanne les 4 disques pour `_tmp_dispatch_*`
- Vérifie que le staging a été vidé des items dispatchés
- Retourne : liste des problèmes de dispatch

## Gates obligatoires

Chaque gate est une checklist. Si un item échoue → on n'avance pas.

### GATE 0 — Pré-analyse complète

- [ ] Inventaire qBit fait (connexion OK, liste des torrents)
- [ ] État staging documenté (contenu 001-MOVIES, 002-TVSHOWS, 097-TEMP)
- [ ] État tracker lu (ingested_torrents.json)
- [ ] Espace disque vérifié (SSD staging + 4 disques destination)
- [ ] Rapport prévisionnel affiché à l'utilisateur
- [ ] BUG LIST markdown créée
- [ ] Tasks miroir créées

### GATE 1 — Post-INGEST

- [ ] Commande terminée
- [ ] Output affiché et analysé
- [ ] 3 agents techniques lancés ET résultats reçus
- [ ] Agent ingest-checker lancé ET résultat reçu
- [ ] Rapports agrégés dans BUG LIST
- [ ] Markdown mis à jour (section INGEST)
- [ ] Tasks mises à jour
- [ ] Aucune erreur critique

### GATE 2 — Post-SORT

- [ ] Commande terminée
- [ ] Output affiché et analysé
- [ ] 3 agents techniques lancés ET résultats reçus
- [ ] Agent sort-checker lancé ET résultat reçu
- [ ] 097-TEMP vérifié
- [ ] Rapports agrégés dans BUG LIST
- [ ] Markdown mis à jour (section SORT)
- [ ] Tasks mises à jour
- [ ] Aucune erreur critique

### GATE 3 — Post-PROCESS

- [ ] Commande terminée
- [ ] Output affiché et analysé
- [ ] 3 agents techniques lancés ET résultats reçus
- [ ] Agent scrape-checker lancé ET résultat reçu
- [ ] Rapports agrégés dans BUG LIST
- [ ] Markdown mis à jour (section PROCESS)
- [ ] Tasks mises à jour
- [ ] Aucune erreur critique

### GATE 4 — Post-VERIFY

- [ ] Commande terminée
- [ ] Output affiché et analysé
- [ ] 3 agents techniques lancés ET résultats reçus
- [ ] Rapports agrégés dans BUG LIST
- [ ] Markdown mis à jour (section VERIFY)
- [ ] Tasks mises à jour
- [ ] Aucune erreur critique
- [ ] Nombre d'erreurs verify acceptable (sinon demander à l'utilisateur)

### GATE 5 — Post-DISPATCH

- [ ] Commande terminée
- [ ] Output affiché et analysé
- [ ] 3 agents techniques lancés ET résultats reçus
- [ ] Agent dispatch-checker lancé ET résultat reçu
- [ ] Rapports agrégés dans BUG LIST
- [ ] Markdown mis à jour (section DISPATCH)
- [ ] Tasks mises à jour

### GATE 6 — Post-pipeline

- [ ] Analyse finale complète rédigée
- [ ] BUG LIST markdown complètement remplie
- [ ] Toutes les Tasks miroir à jour
- [ ] Markdown sauvegardé

### Enforcement

La skill maintient un état `gates_passed = {0: false, 1: false, ..., 6: false}`. Avant chaque step, elle vérifie que la gate précédente est `true`. Si tentative de sauter une gate → ERREUR et STOP.

## Protocole d'erreur critique

### Définition d'erreur critique (= STOP immédiat)

- 2 erreurs identiques consécutives (systémique)
- `Operation not permitted` / `Permission denied`
- `Forbidden403Error` / IP bannie
- `No space left on device`
- Toute erreur qui pourrait corrompre des données

### Protocole STOP

1. Kill le process en cours
2. Afficher l'erreur à l'utilisateur
3. Ajouter à la BUG LIST (sévérité: critique)
4. Lancer les 3 agents techniques en parallèle
5. Agréger les rapports
6. Nettoyage automatique :
   - Supprimer les `_tmp_*` trouvés par orphan-hunter
   - Supprimer le `pipeline.lock` stale
   - NE PAS toucher aux fichiers médias (seulement tmp/orphelins)
7. Mettre à jour la BUG LIST
8. Passer à la phase traitement

### Règle de nettoyage

Ne supprimer que les fichiers clairement temporaires (`_tmp_*`, `.lock`). Tout fichier média = demander confirmation à l'utilisateur.

## Phase de traitement

Après gate 6 (ou après STOP + nettoyage) :

```
Pour chaque item BUG LIST (status = À TRAITER):
  1. Status → EN COURS (markdown + task)
  2. Invoquer /systematic-debugging:
     - Description du problème
     - Step concerné
     - Output console pertinent
     - Contexte (fichiers, chemins, état)
  3. Récupérer diagnostic + fix
  4. Appliquer le fix si c'est du code
  5. Mettre à jour markdown (section Traitement #N)
  6. Status → TRAITÉ (markdown + task)

  GATE entre chaque item:
  - [ ] Item précédent a un status final
  - [ ] Markdown mis à jour
  - [ ] Task mise à jour
```

### Items non-code

- Pas de `/systematic-debugging`
- Documenter la suggestion dans le markdown
- Marquer `CONNU` avec une recommandation

### Fin du workflow

- Résumé final : X traités, X connus, X non reproductibles
- Commit du markdown BUG LIST
- Si fichiers code modifiés → `python -m pytest -x -q`

## Contraintes techniques

- **JAMAIS de background** pour `personalscraper` (hook `block_background_pipeline.py` l'enforce)
- **FOREGROUND** avec `timeout=600000` (10 min max par step)
- **Output affiché** entre chaque step — pas d'analyse post-mortem
- **Limitations connues** : pas de streaming temps réel dans Bash, mais le step-by-step compense — contrôle total entre chaque étape
