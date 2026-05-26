# Item 3 — Brainstorm MAJ skill pipeline-monitor

**Date** : 2026-05-21
**Méthode** : brainstorm exhaustif sans filtre puis catégorisation et priorisation. Nourri par les items 1 (dérives des plans) et 2 (carto pipeline).
**Output** : specification fonctionnelle pour l'item 4 (implémentation de la skill).

---

## 0. Diagnostic actuel de la skill

### Ce que la skill fait bien

- **Paradigm "design-conformity, not bug-hunting"** : la classification en 4 catégories (DESIGN_CONFORM / DESIGN_DEVIATION / TOOLING_BUG / OPERATIONAL) est solide. Évite l'inflation du DEVIATION LIST.
- **`design-conformity-matrix.md`** : principe d'une matrice de référence consultée AVANT classification — bonne idée.
- **HARD GATE C dispatch** : protection forte contre dispatch accidentel. Confirmation littérale uniquement.
- **DEVIATION LIST structurée** : Catégorie × Sévérité × Step × Description × Status.
- **Multi-agent verification** : 3 agents techniques (orphan-hunter, state-validator, output-analyzer) + 1 business agent par step.
- **STOP PROTOCOL explicite** : 8 triggers nommés (`Forbidden403Error`, `No space left`, `rsync invalid argument`, etc.).
- **Run markdown** : chaque exécution produit un journal `docs/pipeline-runs/{date}-pipeline-run.md`.

### Ce qu'elle ne fait pas (ou mal)

- **Matrix incomplète** : ne couvre que 5 étapes (ingest/sort/process/verify/dispatch) alors que le pipeline en produit 9 StepReports (manque enforce + trailers ; process pas décomposé).
- **Aucune référence aux flux connexes** : library-index, library-rescrape, library-reconcile, trailers — pas dans le matrix.
- **Pré-run recovery jamais documentée** : `_recover_from_previous_run` exécute 3 actions importantes avant INGEST, la skill ne le mentionne pas.
- **Pas d'invariants transverses vérifiables** : la skill ne propose pas de checks "grep transverse" en fin de pipeline (ex: zéro `_tmp_dispatch_*` sur tous disks, zéro stale lock, zéro orphan dans la BDD).
- **Agents fragiles** : pipeline-state-validator, pipeline-orphan-hunter, etc. — leurs prompts ne savent rien du matrix réel et émettent parfois des faux positifs (vu pendant la run du 2026-05-18).
- **Pas de subscriber EventBus** : la skill pourrait écouter les events directement via subscriber temporaire, mais elle scrappe les logs stdout via grep.
- **Aucune validation que le code = matrix** : si le code change (nouvelle phase, nouveau event), la skill ne le remarque pas. Le matrix peut devenir stale silencieusement.
- **Pas d'historique inter-runs** : chaque run produit un markdown isolé. Pas de diff "tendance" / "régression depuis le run précédent".
- **STOP PROTOCOL trop tardif sur certains cas** : le boot Pydantic failure (`extra_forbidden`) n'est pas un trigger STOP — il bloque tout sans diagnostic.
- **Aucun mode "headless"** : la skill demande des `<options>` interactifs à chaque step. Cron / batch impossible.
- **Pas de mode "dry-run" de la skill elle-même** : impossible de tester le matrix sans lancer un vrai pipeline.

---

## 1. Idées d'amélioration par dimension

Brainstorm exhaustif. Pas de filtre — toutes les idées entrent.

### 1.1 Matrix (référence design-conformity-matrix.md)

**A. Étendre le matrix aux 9 StepReports**

- Décomposer la section PROCESS en `clean` / `scrape` / `cleanup` (3 sections séparées avec leurs propres outputs normaux / déviations)
- Ajouter une section **`enforce`** complète (file_sanitizer + structure_validator + coherence_checker)
- Ajouter une section **`trailers`** complète (scan / download / verify / purge sous-commandes + bloquant-vs-non-bloquant)

**B. Ajouter sections "flux connexes"**

- `library-index` (5 ScanMode + backfill_ids hors enum)
- `library-rescrape` (vu son DEV #2 vector encore vivant)
- `library-reconcile` + `library-repair` (cycle de vie de la repair_queue)
- `trailers` sub-commands (scan / download / verify / purge)

**C. Ajouter section "Pré-run recovery"**

- `_tmp_dispatch_*` cleanup sur tous disks
- qBit auth lockout expiry (>1h)
- `.ingest_tmp_*` cleanup en staging
- Outputs normaux : `recovered=N artifacts` info log

**D. Ajouter section "Invariants transverses"** (nouveau concept)

- Liste de checks `grep` à effectuer EN FIN de pipeline complet (pas par step)
- Exemples : zéro `_tmp_*` orphans, zéro stale `pipeline.lock`, zéro `scan_run` running > 6h, zéro `media_item.dispatch_path` qui n'existe plus sur disque

**E. Matrix versionable**

- Header `**Matrix version**: 1.2` qui doit matcher un champ dans la skill (assertion at start)
- Évite que la skill et le matrix dérivent

**F. Matrix sourçable**

- Chaque entrée DESIGN_CONFORM cite un fichier:ligne du code source (pas juste une ref doc)
- Si la ligne change ou disparaît, le matrix est flaggé stale

**G. Matrix par version d'app**

- `design-conformity-matrix.md` versionné par release : matrix-0.15.0.md, matrix-0.16.0.md
- La skill choisit le matrix selon la version actuelle (lue depuis `personalscraper.__version__`)

### 1.2 Phases de la skill (GATE 0-6)

**H. Ajouter GATE -1 "Pre-pre-analysis"**

- Vérifier la sanité du repo avant de toucher au pipeline
- `personalscraper info` doit fonctionner (sinon STOP — config cassée)
- `make lint` doit être vert (sinon WARN — pipeline peut être boggué)
- Vérifier la cohérence skill ↔ matrix ↔ code via le mécanisme E/F/G ci-dessus

**I. GATE 0 enrichi**

- Inclure les 3 actions de pré-recovery (8.2 du rapport item 2) dans le forecast
- Forecast probabiliste : "97% de chances que INGEST soit no-op (matrix-based heuristic)"

**J. GATE 5 dispatch enrichi**

- Le HARD GATE C reste — mais ajouter un précheck pré-confirmation : "Top Chef Le Concours Parallèle laissé au root par Unmatched Episode Policy — est-ce normal pour toi ?" (interroger l'opérateur sur les DESIGN_CONFORM marginaux avant de dispatcher)

**K. GATE 6 post-pipeline enrichi**

- Run invariants transversaux (D ci-dessus)
- Diff avec le run précédent (régression / amélioration)
- Mise à jour automatique du matrix si nouveau DESIGN_CONFORM détecté

**L. Phase de Treatment (PHASE 4)**

- Actuellement : traite les items DEVIATION LIST séquentiellement, peut commit du code
- Risque : la skill commit du code dans le contexte d'un pipeline-monitor qui devrait être observationnel
- Idée : séparer "monitoring run" de "remediation run" — par défaut la skill ne commit RIEN, seulement rapporte. L'opérateur lance ensuite `/implement:feature` pour les fixes.

**M. Phase optionnelle "Re-run après fix"**

- Si l'utilisateur a corrigé un DEVIATION LIST item entre 2 runs, la skill devrait pouvoir vérifier que c'est résolu en relançant le step concerné isolément.

### 1.3 Agents (existants + nouveaux)

**Existants à durcir**

**N. `pipeline-orphan-hunter`** : prompt explicite sur les patterns d'orphans (`_tmp_*`, `*.lockout`, stale `*.lock`) — déjà OK probablement, à confirmer.

**O. `pipeline-state-validator`** : doit checker les disques avant de flagger un tracker entry comme orphan (bug historique #5).

**P. `pipeline-output-analyzer`** : reçoit le matrix en contexte pour classification. Actuellement il classe peut-être sans matrix.

**Q. `pipeline-dispatch-checker`** : reconciliation plan dry-run vs real run (déjà mentionné dans 2.4 de la skill).

**Nouveaux agents potentiels**

**R. `pipeline-event-monitor`** : subscribe au bus en parallèle de la run, capture en RAM tous les events émis, fait un diff avec le matrix (events attendus vs émis).

**S. `pipeline-invariant-checker`** : agent final qui exécute les checks transverses (zéro orphans, BDD cohérente, etc.) après GATE 6.

**T. `pipeline-bdd-validator`** : checks `personalscraper library-index` état + `library-reconcile` état + repair_queue + outbox. Tourne après dispatch.

**U. `pipeline-cli-coverage-checker`** : valide que chaque CLI command observée pendant la run est dans le matrix.

**V. `pipeline-matrix-stale-detector`** : compare le matrix au code (events réellement émis, étapes réellement exécutées) — flag les drifts.

**Repenser le calling pattern**

**W. Run agents pendant la step, pas après** : pour les étapes longues (PROCESS scrape qui re-scrape 7 shows × API calls), un agent qui tourne en parallèle et stream les findings au lieu d'attendre la fin.

**X. Limit budget par agent** : chaque agent a un budget de tokens — sinon une run produit trop de findings et explose le contexte de la skill principale.

**Y. Agent persona consistency** : tous les agents pipeline-\* utilisent le même "mode" de classification (matrix-aware). Aujourd'hui le prompt template varie.

### 1.4 Processus de classification

**Z. Pré-classification automatique via regex**

- Pour les outputs déterministes (`sort_fast_skip`, `ingest_complete dry_run=False errors=0 skipped=N success=0`), la skill applique le matrix sans agent — économie de tokens.

**AA. Classification par majority vote**

- Pour les findings ambigus, 2 agents indépendants classifient — si désaccord, escalade à l'opérateur.

**AB. Catégorie 5 : `KNOWN_LIMITATION`**

- Distinct de DESIGN_CONFORM (qui dit "c'est documenté + voulu") et de DEVIATION (qui dit "c'est anormal").
- Pour des comportements documentés comme NON-IDÉAL mais ACCEPTÉS pour la release courante. Ex: "library-recommender utilise legacy IDs, sera fixé en tech-debt 0.15.1".

**AC. Catégorie 6 : `ACCEPTANCE_FAIL`**

- Quand un comportement contredit explicitement un ✅ de l'ACCEPTANCE.md d'une feature mergée.
- Plus grave que DESIGN_DEVIATION : c'est une régression sur un claim public.

### 1.5 Invariants transverses à vérifier (alimente D + S)

**Filesystem**

- AD. Zéro `_tmp_dispatch_*` sur n'importe quel disk après run terminé
- AE. Zéro `_tmp_ingest_*` ou `.ingest_tmp_*` en staging après run
- AF. Zéro `pipeline.lock` si pas de pipeline en cours
- AG. Zéro NFO orphan dans Saison NN/ (`*.nfo` sans `*.mkv` parent)
- AH. Zéro `season-{NN}-poster.jpg` orphan
- AI. Aucun `Saison NN/` vide
- AJ. Aucun `.actors/` dir restant

**BDD**

- AK. Zéro `scan_run` running depuis > 6h
- AL. Zéro `media_item` sans `dispatch_path` flex attr
- AM. Zéro `media_item.dispatch_path` qui n'existe plus sur disque
- AN. Zéro `media_release` orphan (pas d'item lié)
- AO. Zéro `media_file` sans `release_id` lié
- AP. `season.episode_count` == `COUNT(episode WHERE season_id=)`
- AQ. `season.has_poster` cohérent avec FS
- AR. Zéro `repair_queue` pending depuis > 1 semaine

**Tracker**

- AS. Tout `ingested_torrents.json` entry sans `dest_path` AND fichier introuvable nulle part = orphan
- AT. Tout torrent qBit completed avec hash absent du tracker = ingest a raté

**Conf**

- AU. `personalscraper info` doit succeed (Pydantic strict OK)
- AV. Toute clé `os.environ.get(...)` doit avoir un correspondant dans `.env.example`

### 1.6 Observabilité de la skill elle-même

**AW. Skill emits its own events**

- Au bus EventBus, ou dans un canal séparé "skill.pipeline-monitor.\*"
- Permet de monitorer la skill (combien de temps elle prend, combien de findings par step, etc.)

**AX. Skill produit un score de qualité**

- "Conformity score" : (DESIGN_CONFORM observed / total observed) × 100
- Par step + global
- Permet de suivre la tendance run-on-run

**AY. Skill produit un changelog**

- Si le matrix a changé entre 2 runs, log de ce qui a changé
- Idem si la skill elle-même a changé (version bump)

**AZ. Skill log des décisions GATE**

- Audit trail de chaque GATE PASSED / FAILED avec horodatage
- Réutilisable pour audit ultérieur

### 1.7 Recovery / safe-fail

**BA. Skill checkpoint**

- Si le contexte explose pendant un run, la skill peut reprendre où elle en était (état serialisé entre les steps)
- Pas critique mais utile pour les longs runs

**BB. Skill produit toujours un `audit-report.md` même en STOP**

- Aujourd'hui : si STOP_PROTOCOL trigger, le markdown est partiellement rempli
- Améliorer : toujours produire un rapport complet "as-far-as-we-went"

**BC. Skill kill propre du subprocess**

- Si l'opérateur SIGINT, la skill doit kill proprement personalscraper (libérer le lock, etc.)
- Aujourd'hui : Bash run_in_background interdit, mais le foreground avec timeout n'est pas un kill propre.

### 1.8 Idées créatives / nice-to-have

**BD. Web dashboard pour le matrix**

- Browseable, searchable, lié aux file:line du code
- Auto-régénéré depuis le code + matrix
- Permet à l'opérateur de naviguer dans la matrice depuis le navigateur

**BE. "What-if" analyzer**

- Avant chaque step, propose : "Si tu lances ce step, voilà ce qui devrait se passer selon matrix"
- Plus pédagogique pour les nouveaux opérateurs

**BF. Auto-fix proposals**

- Pour chaque DEVIATION classifiée TOOLING_BUG (skill bug), proposer le fix dans le matrix ou la skill SKILL.md
- L'opérateur accepte → patch direct

**BG. Integration avec `/implement:feature`**

- Si la run produit des DEVIATIONS critiques, la skill propose de créer une feature suivi : "Lancer `/implement:feature` avec ces 3 critiques ?"

**BH. Matrix import/export**

- Format JSON / YAML / TOML pour le matrix (parsable)
- Permet aux agents et autres scripts de le consommer programmatiquement

**BI. Matrix lints**

- Linter spécifique pour `design-conformity-matrix.md` : valide la structure, les références, les sévérités

**BJ. "Pipeline simulation" mode**

- La skill peut simuler un run sans toucher au disque ni à la BDD
- Utile pour valider que le matrix est correct avant un run réel

**BK. Records des "weird outputs"**

- Toute observation NON_CLASSIFIÉE (pas dans matrix, pas évidente) est sauvée dans un "weird outputs log" pour étude ultérieure
- Source d'évolution du matrix

**BL. Cross-correlation avec audit `library-reconcile`**

- À la fin de la run, lance `library-reconcile --dry-run` et inclut les findings dans le rapport
- Peut révéler des drifts FS↔BDD que le pipeline n'a pas créés

**BM. Compare avec le précédent run**

- Si run précédent dans `docs/pipeline-runs/` existe, la skill calcule un diff
- "X nouveaux items dispatchés, Y nouveaux DEVIATIONS, Z items résolus"

**BN. Notification finale**

- Subscriber Telegram dédié à la skill (pas le pipeline lui-même)
- Envoie un récap court : "Run terminée. 0 critique, 2 majeurs, 5 mineurs. Voir docs/pipeline-runs/{date}.md"

**BO. Pre-commit hook qui vérifie le matrix**

- Si un commit touche le code du pipeline (ingest/sort/process/...), le hook vérifie que le matrix correspondant est aussi à jour ou flag warn
- Évite le drift latent

---

## 2. Catégorisation

### 2.1 — Must-have (corrige les bugs trouvés en items 1 + 2)

**Matrix**

- A. Étendre aux 9 StepReports
- B. Ajouter sections flux connexes
- C. Ajouter section pré-run recovery
- D. Ajouter section invariants transverses

**Phases**

- I. GATE 0 enrichi (pré-recovery)
- K. GATE 6 enrichi (invariants transverses)

**Agents**

- O. pipeline-state-validator check disks first
- P. pipeline-output-analyzer matrix-aware (assure que chaque agent reçoit le matrix)
- S. pipeline-invariant-checker (nouveau, exécute D)

**Classification**

- AC. Catégorie ACCEPTANCE_FAIL (pour les claims faussement ✅)

**Invariants concrets à coder**

- AD-AT : tous les invariants FS+BDD+Tracker+Conf

### 2.2 — Should-have (qualité + robustesse)

**Matrix**

- E. Matrix versionable + assertion at start
- F. Matrix sourçable (file:line refs)

**Phases**

- H. GATE -1 pré-pré-analysis
- L. Séparer monitoring de remediation

**Agents**

- R. pipeline-event-monitor (subscriber bus)
- T. pipeline-bdd-validator
- V. pipeline-matrix-stale-detector
- X. Limit budget par agent
- Y. Agent persona consistency

**Classification**

- Z. Pré-classification automatique via regex
- AB. Catégorie KNOWN_LIMITATION

**Observability**

- AX. Conformity score
- AZ. Audit trail GATE decisions

### 2.3 — Nice-to-have (extension future)

**Matrix**

- G. Matrix par version d'app
- BH. Matrix import/export JSON
- BI. Matrix lints

**Phases**

- J. GATE 5 ask about marginal DESIGN_CONFORM
- M. Re-run après fix

**Agents**

- U. pipeline-cli-coverage-checker
- W. Run agents pendant la step (streaming)
- AA. Majority vote classification

**Observability**

- AW. Skill events bus
- AY. Skill changelog
- BL. Cross-correlation library-reconcile

**Recovery**

- BA. Skill checkpoint
- BB. Always produce report even on STOP
- BC. Clean kill subprocess

**Créatif**

- BD. Web dashboard
- BE. What-if analyzer
- BF. Auto-fix proposals
- BG. Integration /implement:feature
- BJ. Pipeline simulation mode
- BK. Weird outputs log
- BM. Compare avec précédent run
- BN. Notification Telegram skill
- BO. Pre-commit hook matrix

---

## 3. Questions ouvertes à trancher avant l'item 4

| Q   | Question                                                 | Mes recommandations                                                                                             |
| --- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Q1  | Séparer "monitoring run" de "remediation run" (idée L) ? | OUI — la skill ne commit pas de code, juste rapporte. Évite confusion responsabilités.                          |
| Q2  | Matrix sourçable file:line (F) ou doc-only ?             | file:line — plus de drift latent, mais charge à maintenir. À chiffrer.                                          |
| Q3  | Matrix versionable (E) + assertion at start ?            | OUI — coût faible, prévient le drift catastrophique.                                                            |
| Q4  | Ajouter ACCEPTANCE_FAIL (AC) en plus de DEVIATION ?      | OUI — distingue régression-sur-claim d'écart-pas-claimé.                                                        |
| Q5  | pipeline-event-monitor subscribe au bus (R) ?            | OUI à terme, mais lourd. Voir si la lib subscribers existante peut héberger un "RunMonitorSubscriber" éphémère. |
| Q6  | Quels invariants critiques ABSOLUMENT pour la 0.15.1 ?   | AD-AF (orphans filesystem), AK (stale scan_run), AL-AM (BDD dispatch_path), AS-AT (tracker drift).              |
| Q7  | Quels nice-to-have report-ils en 0.16.0+ ?               | Tout BD-BO. À noter dans ROADMAP.                                                                               |
| Q8  | Skill kill propre subprocess (BC) — bloquant ?           | NON pour 0.15.1 — vérifier que `Bash(timeout=600000)` libère bien lock. Si oui, suffisant.                      |
| Q9  | Pré-classification regex (Z) ?                           | OUI — économie tokens importante sur les runs no-op.                                                            |
| Q10 | Categorie KNOWN_LIMITATION (AB) ?                        | OUI — explicit > implicit. Distinct de DESIGN_CONFORM.                                                          |

---

## 4. Décisions utilisateur (Q1-Q10)

Tranchées en session 2026-05-21.

| Q   | Sujet                             | Décision                                           | Conséquence pour l'item 4                                                                                 |
| --- | --------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Q1  | Séparer monitoring vs remediation | OUI mais via flag `--remediate` (OFF par défaut)   | Skill = lecture seule par défaut. `/pipeline-monitor --remediate` opt-in pour traiter DEVIATIONS.         |
| Q2  | Garder matrix synchro avec code   | Lazy auto-scan au start de la skill                | Skill grep chaque event nommé dans matrix. Zéro match → warning "matrix stale". Pas de file:line à coder. |
| Q3  | Versionner matrix + assertion     | OUI assertion stricte (block)                      | Header `**Matrix version**: X.Y` + `MATRIX_VERSION = "X.Y"` dans skill. Mismatch = STOP.                  |
| Q4  | Catégorie ACCEPTANCE_FAIL         | OUI ajouter                                        | Total 5 catégories : DESIGN_CONFORM / DESIGN_DEVIATION / ACCEPTANCE_FAIL / TOOLING_BUG / OPERATIONAL.     |
| Q5  | Capture events EventBus           | Lourd : wrapping process Python                    | Skill devient host. Import direct de `personalscraper.pipeline.Pipeline`. Subscriber EventBus attaché.    |
| Q6  | Invariants pour la 1ère version   | Tous les 19 (rien hors scope)                      | AD-AV implémentés en 1 fois.                                                                              |
| Q7  | Nice-to-have                      | BJ + BK + BL + BM inclus ; BD-BI + BN-BO repoussés | Simulation mode, weird outputs log, cross-correlation library-reconcile, compare précédent run.           |
| Q8  | SIGINT handler                    | OUI inter-step check + handler                     | ~20 lignes dans Pipeline (check `_shutdown_requested` entre steps) + handler dans skill.                  |
| Q9  | Pré-classification regex          | NON, tout passe par agent                          | Simplicité. Pas de regex à maintenir dans le matrix.                                                      |
| Q10 | Catégorie KNOWN_LIMITATION        | NON, 5 catégories suffisent                        | Les limitations connues restent en DESIGN_DEVIATION mineur avec status="connu".                           |

**Note SemVer** : user décision = "peu importe tant que le boulot est fait". Vu l'ampleur (wrapping process Python + matrix versionable + nouveaux agents + nouveaux invariants), un bump MINOR (0.15.0 → 0.16.0) est plus honnête qu'un PATCH. Décision finale dans le DESIGN final (item 14).

## 5. Output

Cette liste exhaustive (60+ idées codifiées A-BO) + les 10 décisions tranchées sont la **specification fonctionnelle** pour l'item 4 (implémentation skill).

L'item 4 prendra :

1. **Tous les must-have** (A, B, C, D, I, K, O, P, S, AC, AD-AT) → patch obligatoire
2. **Selected should-have** (E, F via Q2 lazy, H, L via Q1 flag, R via Q5 wrapping, T, V, X, Y, AX, AZ)
3. **Selected nice-to-have** (BJ, BK, BL, BM)
4. **SIGINT handler + wrapping process** (Q5 + Q8) — implique modifications dans `personalscraper/pipeline.py` (inter-step check)
5. **5 catégories** + ACCEPTANCE_FAIL formalisée dans le matrix (Q4)

L'item 4 sera donc plus ample que prévu initialement (impacte aussi `personalscraper/pipeline.py`). Découpage en sous-phases proposé au début de l'item 4.
