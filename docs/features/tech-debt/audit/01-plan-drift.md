# Item 1 — Étude des dérives des plans (cross-feature)

**Périmètre** : les 3 dernières features mergées sur `main` : `event-bus` (v0.14.0), `test-coverage` (v0.12.0), `provider-ids` (v0.15.0).
**Date** : 2026-05-21
**Méthode** : lecture comparée DESIGN.md / ACCEPTANCE.md / plan/ / IMPLEMENTATION.md / DEVIATIONS.md de chaque archive, croisement avec les findings de l'audit pipeline-monitor récent.

## 0. Définition de "dérive"

Une **dérive de plan** est un écart entre :

- **Ce que le plan annonce livrer** (DESIGN, ACCEPTANCE, phases du plan)
- **Ce que le code livre réellement** au moment du merge

Une dérive n'est PAS forcément une faute : un scope expansion documenté, un report explicite avec trace écrite, ou un consolidation justifiée sont des évolutions saines. Le problème commence quand l'écart est **invisible dans l'historique** ou **caché derrière un ✅ trompeur**.

## 1. Observations par feature

### 1.1 — `event-bus` (PR #22, v0.14.0)

**Discipline du DESIGN** : exceptionnellement stricte — section `## NO DEFERRAL — MANDATORY` en tête. Liste des out-of-scope claire (cross-process events, pipeline.py → package).

**Dérives observées** :

- Une note IMPLEMENTATION ligne 83 : "scanner/\_orchestrator.py would also touch hot paths and is deferred to a follow-up issue" — dérive **non prévue au DESIGN**, apparue en cours, jamais ouverte en issue trackable.
- **PR review cycle 1 + cycle 2** ont remonté 17+ findings (W1–W3 critiques + I1–I14 importants). Le bug systémique W1 « bus-detached emit sites » a échappé à toutes les phases. Symptôme : le code shippait des events sans bus attaché à plusieurs endroits (`trailers/step.py:75`, `library_index_command`, etc.).
- L'IMPLEMENTATION note ouvertement : « Step CLI commands silently drop events: design did not specify per-step subscriber wiring; only `personalscraper run` is the operator-facing entry. » — **le DESIGN était incomplet sur la transversalité du wiring**.

**Bilan event-bus** : la discipline « no deferral » a fonctionné pour le scope déclaré, mais le DESIGN n'a pas anticipé la dimension transversale (qui appelle quel emit avec quel bus). C'est la review qui a rattrapé.

### 1.2 — `test-coverage` (PR #20, v0.12.0)

**Discipline du DESIGN** : exemplaire — Non-Goals explicites (per-module thresholds différés), justifiés. Concept de `deferred_promotion` formalisé dans `audit_design_coverage.py` (catégorie d'attente officielle avec date d'expiration).

**Dérives observées** :

- **Bump consolidé** : le plan prévoyait `80 → 82 → 85 → 87 → 90` distribué sur phases 6–9. Au commit `71c8926` les bumps cycle par cycle ont été remplacés par un saut unique 80 → 90 en fin de feature. **Dérive notée dans le plan rescaled (`1dc7eac`) et dans IMPLEMENTATION** — trace complète. Sain.
- Baseline coverage mesurée à 80.48 % au lieu de 44 % planifié. Recalibrage immédiat, documenté. Sain.
- Aucune note « deferred » non-tracée. Aucun cycle PR-review listé.

**Bilan test-coverage** : la feature qui dérive le mieux du panel. Méthode : tout est tracé dans IMPLEMENTATION + le plan lui-même évolue dans des commits explicites. Le concept `deferred_promotion` mérite d'être étudié comme modèle.

### 1.3 — `provider-ids` (PR #23, v0.15.0)

**Discipline du DESIGN** : très ambitieuse, 15 phases gatées.

**Dérives observées** (déjà documentées dans l'audit pipeline-monitor) :

- **ACCEPTANCE #3** (`personalscraper indexer --backfill-ids` walks library) : ✅ ticé. **Code** : driver `run_backfill_ids` existe, mais **aucun Typer command** ne l'expose. L'opérateur ne peut pas l'appeler.
- **ACCEPTANCE #6** (monolithic Protocols droppés) : ✅ ticé. **Code** : `MetadataProvider` et `TorrentClientFull` toujours présents (`api/metadata/_base.py:267`, `api/torrent/_contracts.py:124`), toujours testés.
- **ACCEPTANCE #4** (DB schema unifié) : ✅ ticé. **Code** : write-side correct, mais le **library scanner** n'écrivait jamais `external_ids_json` / `ratings_json` / `canonical_provider` jusqu'à la session pipeline-monitor (P7 fixé en cours de PR).
- **DEV #2 fix** (Acceptance #1) : ✅ ticé. **Code** : tv_service path fixé, mais `library/rescraper._rescrape_episodes` portait toujours le même bug structurel (corrigé en session).
- **DEVIATIONS.md** de provider-ids : "Aucun écart" sur les phases 11, 13, 14 alors que l'audit a démontré le contraire. L'observateur a vérifié plan-vs-code phase par phase mais **pas l'invariant transverse** « plus aucun monolithique Protocol ne survit ».
- **Commit `192bad3`** : sujet = "TrackerRegistry priority_by_media_type override" — a aussi **droppé silencieusement** `MetadataEpisodeScrapingPolicy` + son wiring. Scope expansion non-signalée.

**Bilan provider-ids** : ACCEPTANCE devenue "phases gated" plutôt que "feature complete". Les ✅ sont des proxies de "tests verts à la phase X", pas des "objectif livré à la merge".

## 2. Patterns récurrents identifiés

| #      | Pattern                                                              | Origines                                       | Risque                                                                 |
| ------ | -------------------------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------- |
| **P1** | ACCEPTANCE rédigée en prose, sans commande shell vérifiable          | provider-ids                                   | Items ✅ qui mentent (3 sur 10)                                        |
| **P2** | Invariants transverses non-grep en fin de feature                    | provider-ids (monolithic Protocols)            | DEVIATIONS dit OK alors que l'objectif global n'est pas atteint        |
| **P3** | Scope expansion silencieuse dans un commit                           | provider-ids (192bad3 a dropped policy schema) | Régression invisible, pas de signal au reviewer                        |
| **P4** | Plan "consolidé" en cours de route (sain si tracé)                   | test-coverage (80→90 d'un coup)                | Devient un anti-pattern si le plan modifié n'est PAS commit séparément |
| **P5** | Bugs cachés derrière des tests verts (couvre code, pas comportement) | provider-ids DEV #2, library scanner P7        | Tests unitaires + lint passent, feature reste cassée                   |
| **P6** | Cross-feature debt invisible (un caller oublié à la migration)       | provider-ids (library/recommender legacy IDs)  | Code mort coexiste avec API nouvelle                                   |
| **P7** | Différé non-tracé (note dans IMPLEMENTATION sans issue)              | event-bus (scanner/\_orchestrator deferred)    | Disparait du radar à la merge suivante                                 |
| **P8** | DESIGN incomplet sur dimension transversale                          | event-bus (per-step bus wiring)                | Bug systémique trouvé seulement en PR review                           |

## 3. Causes racines (synthèse)

1. **L'ACCEPTANCE n'est pas exécutable.** Prose libre, validation = "phase gate green". Aucune commande shell ne re-vérifie l'objectif final. **C'est la cause la plus structurante.**

2. **Pas de verify-invariant final.** En fin de feature, aucun grep transverse vérifiant « interdit que X existe encore » ou « tout objet Y doit avoir Z ». Le DEVIATIONS observe les diffs sub-phase, jamais l'état global.

3. **Pas d'integration test pipeline-end-to-end.** Chaque feature teste ses unités, mais aucune ne teste le comportement assemblé "scrape → scan → verify → dispatch". Tous les bugs majeurs trouvés en pipeline-monitor passaient les unit tests.

4. **Pas de cross-caller-grep avant claim "API supprimée".** On déclare « drop » sans `rg -t py` systématique sur les call sites.

5. **L'observateur DEVIATIONS surveille plan-vs-code, pas objectif-vs-code.** Un sous-objectif « atteint en respectant le plan » mais qui ne contribue pas à l'objectif déclaré dans DESIGN/ACCEPTANCE n'est pas flaggé.

6. **Le scope d'un commit n'est pas borné par son sujet.** Un commit "X" peut toucher Y sans signal. Pas de hook qui vérifie que le scope du diff matche le scope du sujet.

7. **Les PR-review-toolkit cycles trouvent les bugs structurels TARDIVEMENT.** Pour `event-bus`, 17+ findings remontés en cycle 1 — ils auraient dû être trouvés en sous-phase. Le mécanisme de detection arrive après que le code soit "fini".

## 4. Ce qui fonctionne bien (à préserver)

- **`test-coverage`** comme modèle : Non-Goals explicites, déférés trackés en catégorie typée (`deferred_promotion`), plan re-versionné dans commits dédiés.
- **`event-bus` discipline NO DEFERRAL** : la posture "aucun différé tacite" a évité plusieurs dérives.
- **DEVIATIONS.md** : l'idée d'un observateur séparé qui trace les écarts est bonne — il faut juste lui donner les bons points de regard (objectif vs code, pas plan vs code).
- **PR-review-toolkit + multi-agent** : a rattrapé les bugs critiques. À garder, à durcir en amont (déplacer en cours de phase plutôt qu'à la fin).

## 5. Implications pour la feature `tech-debt`

Sans entrer dans le design (item 14), les leviers à activer :

- **ACCEPTANCE exécutable obligatoire** : chaque critère doit être une commande shell que le reviewer peut lancer. C'est ce que la draft proposait déjà (phase 2.2). À consolider en règle universelle, pas spécifique à tech-debt.
- **`verify-invariants` step en fin de chaque phase** : grep transverse documenté dans le plan (« no `tmdb_id` column reference », « no `class MetadataProvider` », « zero `os.environ.get` not in `.env.example` »).
- **Integration test "pipeline E2E sur fixture"** comme nouvelle baseline obligatoire (déjà dans draft 3.6).
- **Cross-caller-grep dans les checklists de sous-phase** : avant tout claim "supprimé/migré", un `rg -t py <symbol>` est joint au commit.
- **Hook côté commit** qui vérifie que le diff ne touche pas de fichier hors du scope annoncé par le sujet du commit (futur, pas tech-debt).
- **L'observateur DEVIATIONS surveille un set d'invariants déclarés** dans le DESIGN, pas juste le plan.

## 6. Output

Ce rapport est la base de réflexion pour les items 11–14 (analyse critique + brainstorm + challenge du design tech-debt). Les patterns P1 à P8 et les 7 causes racines doivent rester en mémoire active.
