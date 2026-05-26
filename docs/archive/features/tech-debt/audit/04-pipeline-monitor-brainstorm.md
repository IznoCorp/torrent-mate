# Item 6 — Brainstorm améliorations suite au pipeline-monitor v2.0

**Date** : 2026-05-21
**Méthode** : brainstorm exhaustif post-run, structuré autour des 12 DEVIATIONs détectées
en item 5 + 2 DEVIATIONs supplémentaires révélées en validation post-fix. Catégorisation,
identification de patterns systémiques, traduction en items pour le DESIGN final tech-debt
(item 14).
**Output** : liste d'items pour le DESIGN, classés par dimension et priorité.

---

## 0. Bilan factuel du run 2026-05-21 17h16

### Ce qui a fonctionné comme prévu

- **HARD gate DISPATCH (rule 11 zero-tolerance)** : la skill a bloqué le real-dispatch
  dès qu'une DEVIATION CRITIQUE est apparue dans la liste. L'opérateur a pu choisir
  d'arrêter et de traiter DEV #9 avant tout déplacement de média. Comportement attendu.
- **Dry-run-first** (rule 10) : a permis d'observer la sémantique inversée de
  `repair_root_duplicate` AVANT toute destruction de fichier (le dry-run a logué
  `would_remove` au lieu de `would_replace`). Le user a immédiatement signalé
  l'inversion à partir du dry-run, économisant une perte de donnée potentielle.
- **Classification matrix-aware** : les agents techniques + business ont bien séparé
  DESIGN_CONFORM (ex: case-insensitive matching FROM/From) des vraies DEVIATIONs.
  Le DEVIATION LIST n'a pas été inflaté par des comportements normaux.
- **Pré-recovery preview** (GATE 0) : a démontré que la pipeline démarrait dans un
  état propre (zéro `_tmp_dispatch_*`, pas de stale lock, pas de lockout qBit). Utile.
- **Run markdown comme journal** : trace persistante des décisions et findings — a
  permis de remettre du contexte après compact + de tracer les fixes post-run.

### Ce qui n'a pas fonctionné

- **Les 4 nouveaux agents matrix v2.0 sont indécouvrables** dans la session courante
  (DEV #1). Fichiers présents sur disque, frontmatter conforme, mais le harness
  Claude Code charge la liste d'agents au boot. Conséquence : PHASE 0 stale-detector
  skip, PHASE 3 dégradée (substituts general-purpose). Critique.
- **`pipeline-orphan-hunter` a classifié comme CRITIQUE un état parfaitement normal**
  (fichier en 097-TEMP entre INGEST et SORT). Le prompt de l'agent n'est pas
  matrix-aware par défaut. DEV #2.
- **`pipeline-state-validator` a affirmé "No .DS_Store found"** alors que 10
  fichiers `.DS_Store` survivaient dans le staging. Inféré depuis logs au lieu
  de vérifier le FS. DEV #3.
- **VERIFY n'émet AUCUN event INFO sur stdout** (même avec `-v`). La matrix v2.0
  référence des events qui ne sortent jamais — soit ils sont sur EventBus only
  (la matrix doit le dire), soit ils ont été droppés. DEV #6, à trancher.
- **`personalscraper run --help`** liste 5 steps (ingest → sort → process → verify
  → dispatch) mais le pipeline en a 9 StepReports (ENFORCE et TRAILERS observés
  en cours d'exécution). Doc rot. DEV #7.
- **Matrix v2.0 et SKILL.md référencent `library-reconcile --dry-run`** qui n'existe
  pas dans le CLI. DEV #10.
- **~12 events émis par le pipeline ne sont pas documentés dans matrix v2.0** :
  `tracker_dest_path_pruned`, `sort_tracker_pruned`, `repair_root_duplicate_*`,
  `nfo_valid action=repaired`, `movies_start/done`, `tvshows_start/done`,
  `enforce.orphan_episode_moved`, `enforce_sanitize_action`, `enforce_structure_fix`.
  Coverage gaps. DEV #8.

### Ce qui a été corrigé hors-scope item 5 (priorité absolue user)

| DEV | Sévérité | Description                                            | Commit    |
| --- | -------- | ------------------------------------------------------ | --------- |
| #9  | CRITIQUE | `repair_root_duplicate` inversé — keep fresh root copy | `268cbee` |
| #11 | MAJEUR   | `compute_merkle_root` sort key tuple complet           | `29c4953` |
| #13 | CRITIQUE | `_recreate_indexes` C5 race idempotent                 | `fc39f77` |
| #14 | MAJEUR   | `_build_disk_fingerprints` oshash filter alignment     | `3993487` |

DEV #11 → #13 → #14 forment une **chaîne de découverte** : chaque fix a révélé le
suivant. Pattern significatif (voir §2 patterns).

---

## 1. Récap DEVIATIONs au format complet

| #   | Catégorie        | Sévérité | Step    | Statut        | Implication DESIGN tech-debt                                                              |
| --- | ---------------- | -------- | ------- | ------------- | ----------------------------------------------------------------------------------------- |
| 1   | TOOLING_BUG      | critique | skill   | OUVERT        | Agent discovery hot-reload OU skill auto-detect missing agents                            |
| 2   | TOOLING_BUG      | mineur   | INGEST  | OUVERT        | Agent prompts matrix-aware par défaut (orphan-hunter, state-validator)                    |
| 3   | TOOLING_BUG      | mineur   | ENFORCE | OUVERT        | Agent state-validator : verify FS, jamais inférer des logs                                |
| 4   | DESIGN_DEVIATION | mineur   | ENFORCE | À INVESTIGUER | Documenter ou élargir le scope du cleanup `.DS_Store`                                     |
| 5   | DESIGN_DEVIATION | mineur   | PROCESS | À INVESTIGUER | Counter `tvshows_done.scraped` incohérent avec summary `Scrape: N OK` (repair non compté) |
| 6   | DESIGN_DEVIATION | majeur?  | VERIFY  | À INVESTIGUER | VERIFY events INFO absents stdout — trancher hyp. A (EventBus) ou B (droppés)             |
| 7   | DESIGN_DEVIATION | mineur   | CLI doc | OUVERT        | `personalscraper run --help` doit lister 9 steps réels (ou refléter la composition)       |
| 8   | COVERAGE_GAP     | mineur   | matrix  | OUVERT        | Matrix v2.1 doit intégrer ~12 events observés ce run                                      |
| 9   | DESIGN_DEVIATION | CRITIQUE | PROCESS | TRAITÉ        | (validation : on doit avoir un test E2E `data-loss-on-redownload` permanent)              |
| 10  | TOOLING_BUG      | mineur   | skill   | OUVERT        | Skill/matrix doivent référencer uniquement des flags CLI existants — check au start       |
| 11  | DESIGN_DEVIATION | majeur   | GATE 7  | TRAITÉ        | (à étendre : audit "tous les usages de sort sur path_id non-unique")                      |
| 12  | DESIGN_DEVIATION | mineur   | GATE 7  | À INVESTIGUER | 7191 files_without_release : item 7 BDD audit                                             |
| 13  | DESIGN_DEVIATION | CRITIQUE | indexer | TRAITÉ        | (Pattern C5 race : tous les DDL idempotents par défaut?)                                  |
| 14  | DESIGN_DEVIATION | majeur   | indexer | TRAITÉ        | (Pattern : aligner toutes les queries qui partagent un set sémantique)                    |

Total : **8 ouvertes / 6 traitées**.

---

## 2. Patterns systémiques identifiés

### P1 — Convergence multiple queries, divergence latente

Le merkle pipeline a 4 sites de lecture des fingerprints (`_build_disk_fingerprints`,
`_sample_fresh_fingerprints`, `_finalize_disk_after_walk`, `detect_merkle_drift`).
Deux d'entre eux filtrent `oshash IS NOT NULL`, deux non. Aucun test ne vérifiait
que les 4 produisaient le même résultat sur le même état. DEV #14.

**Cause racine** : pas de contrat unique pour "ce qu'est l'ensemble des fingerprints
d'un disque". Chaque site a écrit sa propre query.

**Pattern probable ailleurs** : toute fonction "query SQL inline" partagée entre
plusieurs sites métier. Candidats à auditer :

- `release_linker` (joins media_file → media_release → media_item) — 5+ sites
- `dispatch_path` lookups (item_attribute) — scanner + reconcile + dispatch
- `tracker entry lookups` (ingested_torrents.json) — ingest + sort + dispatch

→ **Item DESIGN** : pour chaque "set sémantique" partagé, extraire une fonction
unique. Si plusieurs queries doivent coexister, un test pin que `set(query_A) ==
set(query_B)` sur un dataset.

### P2 — Chaîne de découverte cachée par fix superficiel

DEV #11 (merkle algo) a masqué DEV #13 (C5 race), qui a masqué DEV #14 (oshash
filter divergence). Chaque fix a permis au suivant de devenir observable.
Sans la validation "library-reconcile post-fix doit donner drift=0", on aurait
mergé un fix incomplet.

**Cause racine** : un fix qui passe ses propres tests unitaires est jugé complet.
La validation à l'usage (E2E) n'est pas systématique.

**Conséquence** : le commit `29c4953` (DEV #11) ne valide pas le scénario complet
"library-index → library-reconcile drift=0". Seuls les tests unitaires sur
`compute_merkle_root` ont été lancés. Le bug latent (#13, #14) n'aurait pas été
détecté sans le user mandant explicitement la validation.

→ **Item DESIGN** : pour chaque feature touchant un pipeline E2E, un test
d'intégration qui exerce le flow complet jusqu'à la commande de validation
"officielle" (ici `library-reconcile`). Pas seulement les tests unitaires.

### P3 — DDL non-idempotent au croisement de la concurrence

DEV #13 = `CREATE INDEX` sans `IF NOT EXISTS` quand N workers concurrents
recréent le même index. Le pattern "drop puis recreate" est valide en
mono-worker, casse en multi-worker.

**Cause racine** : `_drop_secondary_indexes` + `_recreate_indexes` ont été
écrits avant le passage en multi-worker, jamais relus avec la concurrence
en tête.

**Pattern probable ailleurs** : tout SQL DDL dans le scanner / library / dispatch.
Candidats à grepper :

```bash
rg -n "CREATE\s+(UNIQUE\s+)?INDEX\s+(?!IF NOT EXISTS)" --type py --type sql personalscraper/
rg -n "DROP\s+(TABLE|INDEX|VIEW)\s+(?!IF EXISTS)" --type py personalscraper/
rg -n "conn\.execute\([\"']CREATE" --type py personalscraper/
```

→ **Item DESIGN** : audit "tous les DDL doivent être IF [NOT] EXISTS", règle
documentée. Hook lint custom possible (regex sur les fichiers SQL/PY).

### P4 — Sémantique inversée non-pinned par test

DEV #9 = `repair_root_duplicate` inversait la sémantique design (keep new vs
keep old). Existed depuis au moins 2026-05-07 (date des anciens fichiers). Aucun
test ne pinnait la sémantique attendue. Le user n'a découvert l'inversion qu'en
observant un dry-run.

**Cause racine** : les tests existants asseyaient le comportement OBSERVÉ
(buggy), pas le comportement DÉSIGNÉ. `test_dry_run_logs_but_does_not_delete`
asserte `dup.exists()` après dry-run — vérifie l'effet de bord, pas l'intention.

**Pattern probable** : toute logique "anti-duplicate" / "merge vs replace" /
"conflict resolution" sans contrat utilisateur explicite documenté.

Candidats à grepper / auditer :

- `personalscraper/sorter/` — déduplication d'items 097-TEMP
- `personalscraper/scraper/existing_validator.py` — autres `_repair_*` (`_repair_movie_dir`, `_repair_tvshow_dir`)
- `personalscraper/library/scanner.py` — déduplication des media_file (release linker)
- `personalscraper/dispatch/` — règles replace/merge/moved

→ **Item DESIGN** : chaque opération destructive (`unlink`, `rmtree`, `replace`)
doit avoir un docstring qui précise le contrat utilisateur ("KEEP new / KEEP
old / PROMPT operator") + un test qui pin ce contrat. Audit transversal des
unlink/replace/delete dans le codebase.

### P5 — Stockage stale invisible aux invariants pre-refresh

DEV #11 fix invalidait tous les `disk.merkle_root` stockés. `library-reconcile`
les a flaggés (drift = 4 disks), mais la skill v2.0 n'avait pas anticipé ce
scénario "fix algo → reconcile en transition" — interprétait la drift comme
"app bug" plutôt que "invalidation post-fix attendue".

**Cause racine** : pas de notion de "version d'algo" stockée à côté du hash. Si
l'algo change, on ne peut pas distinguer "drift par mutation" de "drift par
algo update".

**Pattern probable** : tout cache / hash / fingerprint stocké en BDD sans tag
de version.

- `disk.merkle_root` (xxh3_64) — pas de version
- `media_file.oshash` (OpenSubtitles hash) — pas de version, peut évoluer
- `media_file.xxh3_partial`, `xxh3_full` — same
- `path.dir_mtime_ns` — pas de format de version, mais simple

→ **Item DESIGN** : pour chaque hash/fingerprint stocké, ajouter une colonne
`*_algo_version` (TEXT, ex: "xxh3_64-v1") ou un tag implicite via migration
SQL. Mismatch = recompute, pas drift.

### P6 — Coverage gap matrix vs code-emit

12 events émis par le pipeline ne sont pas dans matrix v2.0. La skill `lazy
auto-scan` (PHASE 0) était censée détecter ce gap, mais elle n'a pas tourné
(DEV #1 agents indécouvrables).

**Cause racine** : la matrix est rédigée à la main à partir d'observations
de runs précédents. Tout event introduit par un nouveau code path qui n'a pas
été tourné en pipeline-monitor reste invisible.

**Pattern** : feature drift entre code (truth) et matrix (representation). Le
fix DEV #1 (agent discovery) + un `pipeline-matrix-stale-detector` qui tourne
au boot de la skill = filet de sécurité.

→ **Item DESIGN** : génération automatique d'un "events catalog" depuis le code
(`rg -t py "log\.info\(\"(\w+)\"" personalscraper/`) comparé à la matrix.
Diff = warning à la session pipeline-monitor.

### P7 — VERIFY silencieux : observabilité asymétrique

VERIFY est le seul step à n'émettre aucun event INFO sur stdout (DEV #6). Les
autres steps (INGEST/SORT/PROCESS/ENFORCE/DISPATCH) sont chacun verbeux. Cette
asymétrie casse les agents matrix-aware qui s'attendent à un certain pattern de
ligne par step.

**Cause racine** : VERIFY a été écrit avec un rendering Typer rich (texte
formaté en tableau) plutôt qu'avec des events structurés. Le rich rendering ne
passe pas par structlog.

**Pattern** : autres commandes susceptibles d'avoir le même style : `info`,
`torrents-list`, `library-status`, `library-show`, `library-search`. Toutes ces
commandes affichent un rendu utilisateur, pas un log technique.

→ **Item DESIGN** : tracer la frontière "user output" (Typer rich) vs
"telemetry" (structlog) pour chaque commande. Une commande peut avoir les 2,
mais l'observabilité de la skill repose sur la telemetry.

### P8 — Doc rot CLI vs implémentation

`personalscraper run --help` omet ENFORCE et TRAILERS, qui s'exécutent
clairement (observés dans le run). DEV #7. Doc rédigée à la main, jamais
re-synchronisée quand de nouveaux steps ont été ajoutés.

**Pattern** : toutes les chaînes de docstring qui énumèrent une liste de steps,
phases, modes, providers, etc.

Candidats :

- `run --help`
- `library-index --help` modes énumération (full/quick/incremental/enrich/backfill-ids)
- `--scope` choices dans `library-reconcile`
- chaque docstring de classe qui liste les attributs

→ **Item DESIGN** : règle "pas de duplication entre docstring et code". Le help
text doit se baser sur l'énumération du code (introspection). Audit possible.

---

## 3. Improvement ideas par dimension

Brainstorm exhaustif, pas de filtre. Codifié A-Z.

### 3.1 — Pipeline app (personalscraper/)

**A. Audit transversal des opérations destructives (`unlink`, `rmtree`, `move`)**

Lister toutes les `f.unlink()`, `shutil.rmtree`, `os.remove`, `Path.replace` du
codebase + leur docstring contrat. Identifier celles sans test pin.

```bash
rg -n "\.(unlink|rmtree|remove)\(|shutil\.(rmtree|move)" --type py personalscraper/ | wc -l
```

→ Issue DESIGN : pour chaque site, "keep-policy" documentée + test pin.

**B. Audit transversal des DDL non-idempotents**

```bash
rg -n "CREATE\s+(UNIQUE\s+)?INDEX(?!\s+IF\s+NOT\s+EXISTS)" --type py --type sql personalscraper/
rg -n "DROP\s+(TABLE|INDEX|VIEW)(?!\s+IF\s+EXISTS)" --type py personalscraper/
```

→ Tous les DDL = idempotent par défaut. Règle dans CLAUDE.md / lint rule.

**C. Audit transversal des "set sémantiques" partagés**

Pour chaque triplet `(table, conditions)` ré-utilisé dans 2+ sites Python,
extraire une fonction unique.

Candidats prioritaires :

- "fingerprints d'un disque" : 4 sites (DEV #14)
- "items dispatchés sur un disque" : scanner + reconcile + library-status
- "torrents trackés non-dispatchés" : ingest + dispatch + state validator

**D. Audit version-tag des fingerprints/hashes en BDD**

Pour `disk.merkle_root`, `media_file.oshash`, `xxh3_*` : ajouter `*_algo_version`.

**E. Compteurs cohérents PROCESS:scrape**

`tvshows_done.scraped + skipped + unmatched` doit toujours égaler le summary
`Scrape: N OK / M skipped / X errors`. DEV #5. Probablement un test unitaire
suffit.

**F. Sémantique `repair_root_duplicate` à l'audit annuel**

Le DEV #9 est traité, mais le pattern "scrape supprime des fichiers utilisateur"
devrait apparaître dans un audit annuel ou un changelog flag. Idée : tag commit
`destructive: yes` pour tout commit qui supprime des fichiers utilisateur.

**G. `Top Chef France` folder transient — investiguer**

Observé pendant la validation : un folder `002-TVSHOWS/Top Chef France/` créé
par sort (S17E11/S17E12) a disparu post-process. Mergé dans `Top Chef (2010)/`
ou supprimé ? Au minimum un event log "show_folder_consolidated" ou similaire
pour traçabilité.

### 3.2 — Indexer / BDD (item 7 territoire)

**H. 7191 files_without_release (DEV #12)**

- 6655 sidecars (.jpg/.nfo/.png/.mp3 dans .actors/) = design-conform
- 496 video files orphans (mkv/avi/mp4) : Monk .actors, Pokemon, Squid Game .actors, Avez-vous déjà vu

→ Item 7 : reconcile-enqueue-repairs pour soft-delete les sidecars indésirables

- investigation des 496 vrais orphans (re-scan ? release linker bug ?).

**I. PRAGMA validation au démarrage**

Skill / library-status / library-index : vérifier `PRAGMA integrity_check = 'ok'`

- `PRAGMA journal_mode = 'wal'` à chaque start. Currently fait nulle part.

**J. scan_run lifecycle robust**

scan_run #27 (full failed) a laissé 143k files re-stat (last_verified_at bumped)
sans completer le merkle update. Le `_finalize_disk_after_walk` n'est pas appelé
si la scan failed. → quand un scan plante, le state est "fingerprints touched

- merkle stale" sans recovery automatic.

→ Idée : `repair_queue` reçoit un item `recompute_merkle_root` quand scan_run
échoue, traité par `library-repair`. Ou : retry policy au boot suivant.

**K. Outbox drain visible**

`index_outbox` drain est silencieux (`drain_complete applied=0 deduped=0 ...`).
Quand des entrées s'y accumulent (133 rows toutes "done" actuellement), elles
restent. Politique de pruning ? GC ?

**L. Provider-IDs columns 0/1935 unpopulated**

`canonical_provider` + `external_ids_json` + `ratings_json` sont NULL/empty sur
l'intégralité de library.db. Le backfill n'a jamais tourné. ACCEPTANCE #4
provider-ids non-testable contre cette BDD.

→ Item 7 : un `library-index --mode backfill-ids` à intégrer dans le cron ou
documenter "à lancer une fois après merge provider-ids".

### 3.3 — Skill pipeline-monitor (matrix v2.1)

**M. Matrix v2.1 — intégrer les 12 events coverage gaps**

Nouveaux events à documenter avec leur classification DESIGN_CONFORM :

- SORT : `tracker_dest_path_pruned`, `sort_tracker_pruned`
- PROCESS:clean : `repair_root_duplicate_replaced/would_replace/replace_failed`
- PROCESS:scrape : `nfo_valid action=repaired`, `movies_start/done`, `tvshows_start/done`, `repair_episode_moved`, `episode_sibling_deleted`, `season_dir_exists`, `episode_would_rename`, `repair_episodes_organized`
- ENFORCE : `enforce.orphan_episode_moved`, `enforce_sanitize_action action=deleted_ds_store`, `enforce_structure_fix`

**N. Matrix v2.1 — corriger DEV #10**

Supprimer toute mention de `library-reconcile --dry-run` (flag inexistant). La
commande est read-only par défaut.

**O. Matrix v2.1 — documenter le handoff PROCESS → ENFORCE**

`episode_unmatched_no_rename` (warning PROCESS) laisse un fichier au root.
ENFORCE le déplace dans `Saison NN/` via `enforce.orphan_episode_moved`. Mais
VERIFY peut quand même bloquer si le fichier n'est pas renommé canoniquement.
→ Triangle PROCESS / ENFORCE / VERIFY à formaliser.

**P. Matrix v2.1 — invariant nouveau : N=N counters**

Pour chaque step :

- `summary_OK_count == sum(per-section OK)` (catch DEV #5 type)
- `summary_skipped_count == sum(per-section skipped)`
- Si mismatch → DESIGN_DEVIATION mineur "counter asymmetry"

**Q. Matrix v2.1 — section VERIFY**

Si DEV #6 confirme hypothèse A (events sur EventBus, pas stdout), la matrix doit
documenter "VERIFY est observable UNIQUEMENT via EventBus dump (pipeline-monitor
host mode) — fallback subprocess mode ne le voit pas".

### 3.4 — Agents pipeline-\* (matrix v2.0)

**R. Agent prompts matrix-aware par défaut (DEV #2, #3)**

Chaque agent (orphan-hunter, state-validator, scrape-checker, etc.) doit avoir,
en frontmatter ou dans sa première instruction :

> "AVANT toute classification, lire `references/design-conformity-matrix.md` v2.0.
> Pour chaque finding, identifier si une row matrix le couvre comme DESIGN_CONFORM.
> Si oui → 'Design Conformity Check' section (informational). Sinon → DEVIATION LIST."

Currently la skill passe ce directive au prompt à chaque invocation. Idée : le
mettre dans les agents eux-mêmes (frontmatter `description` ou un fichier
`references/` partagé).

**S. State-validator : FS source of truth, jamais inférer de logs (DEV #3)**

Modifier le prompt : "Pour toute affirmation FS (existence de fichier, taille,
mtime, absence), TOUJOURS faire un check FS direct (Bash + ls/stat/find). NE
JAMAIS inférer depuis un log."

**T. Orphan-hunter : matrix-loaded list of "expected residuals"**

Currently il flag tout `.DS_Store` comme mineur. Matrix devrait dire
"`.DS_Store` est cosmétique macOS, ENFORCE en supprime, mais sa survie hors
097-TEMP est DESIGN*CONFORM". Idem pour les `\_tmp_dispatch*\*` (qui sont en fait
pré-recovery'd).

**U. Auto-discover agents au start de la skill (DEV #1)**

Si les 4 agents matrix-aware sont absents de la liste available, soit :

- A. STOP avec message "rerun the session after `/plugins-reload`"
- B. Fallback transparent à `general-purpose` avec le prompt agent intégré

Option A est plus safe (force l'opérateur à corriger). Option B permet une
session dégradée.

### 3.5 — Observability / Skill telemetry

**V. Skill events bus**

Chaque transition de phase (PHASE 0 done, GATE 1 done, etc.) émise comme event
structuré (JSON line). Permettrait des dashboards plus tard.

**W. Skill compare avec précédent run**

PHASE 3.5 actuelle (BM en matrix v2.0). Pas implémenté dans ce run. Item à
livrer.

**X. Weird-outputs log persistant**

Currently un fichier par run. Idée : un `weird-outputs.json` cumulé qui suit
"event vu N fois, jamais documenté dans matrix" — devient un signal pour matrix
v2.X enrichment.

### 3.6 — CLI / documentation

**Y. `run --help` source-of-truth introspection (DEV #7)**

Liste des steps générée depuis le code (`Pipeline.STEPS` ou similaire), pas
hardcodée dans le help text. Si nouveau step ajouté, help update auto.

**Z. CLI flag existence-check au start de la skill (DEV #10)**

Au boot, la skill vérifie que chaque commande CLI référencée dans matrix/SKILL.md
existe (`personalscraper <cmd> --help` exit 0). Mismatch → warning.

**AA. Per-command observability stamp**

Chaque commande CLI emet 1 event `cli.invoke.{command} args={...}` au start.
Permettrait un audit "qui a appelé quoi quand" + un compteur d'usage.

### 3.7 — Tests / régression

**AB. Test E2E pipeline → reconcile drift=0**

Test d'intégration : full pipeline run sur fixture → library-index → library-reconcile.
Assert `merkle_drift == 0`, `release_orphans == 0`, etc. Aurait attrapé DEV #11

- #13 + #14 en CI avant la merge.

**AC. Test E2E "re-ingest scenario"**

Reproduit le scénario DEV #9 : ingest → sort → process. Le file SxxExx déjà en
Saison NN/ doit être REMPLACÉ par la nouvelle version, pas l'inverse. Currently
test unitaire `test_root_duplicate_replaces_existing_file_real_run` mais pas
E2E (passe par tout le pipeline).

**AD. Test concurrence library-index**

Test d'intégration multi-worker (au moins 2 workers fictifs sur 1 DB temp)
exerçant la séquence drop+recreate indexes. Aurait attrapé DEV #13.

### 3.8 — Process / méthode

**AE. Règle "validation à l'usage" après chaque fix**

Pour chaque fix touchant un flux pipeline / BDD, exécuter la commande de validation
"officielle" (library-reconcile, run pipeline, etc.) avant claim "TRAITÉ".

**AF. Règle "patterns audit après chaque DEV critique"**

Quand un DEV CRITIQUE est trouvé, faire un audit transversal "ce pattern existe-t-il
ailleurs ?" avant fix. DEV #11 a triggé l'audit (a révélé #14). Bonne pratique
à formaliser.

**AG. Matrix update obligatoire à chaque DEV traité**

Si un DEV introduit un nouveau comportement / event / classification, la matrix
v2.X doit l'enregistrer dans le même commit. Currently les fixes #9-#14 n'ont
pas bumped la matrix.

---

## 4. Catégorisation des idées (must-have / should-have / nice-to-have)

### Must-have (bloquant pour merge tech-debt)

- **C** Audit "set sémantique" partagé (P1 — DEV #14)
- **R** Agent prompts matrix-aware par défaut (DEV #2, #3)
- **U** Skill auto-detect missing matrix-aware agents (DEV #1)
- **AB** Test E2E pipeline → library-reconcile drift=0 (P2 — DEV #11/13/14)
- **AC** Test E2E re-ingest scenario (DEV #9)
- **AE** Règle "validation à l'usage" après chaque fix (P2)
- **M** Matrix v2.1 — 12 events coverage gaps (DEV #8)
- **N** Matrix v2.1 — corriger flag --dry-run inexistant (DEV #10)
- **L** Document `--mode backfill-ids` ou intégrer au cron (provider-ids ACCEPTANCE #4)

### Should-have (DESIGN priorité 2)

- **A** Audit destructive operations
- **B** Audit DDL non-idempotents (généralisation P3)
- **D** Hash version-tag (P5)
- **E** Compteurs cohérents step (DEV #5)
- **H** Soft-delete sidecars indésirables (DEV #12 / item 7)
- **I** PRAGMA validation au boot
- **J** scan_run failed → repair_queue (P3 / DEV #13 chain)
- **O** Matrix v2.1 — handoff PROCESS → ENFORCE → VERIFY documenté
- **P** Matrix v2.1 — invariant N=N counters
- **Q** Matrix v2.1 — VERIFY observability frontière
- **S** State-validator : FS truth (DEV #3 spec)
- **T** Orphan-hunter : matrix-loaded expected residuals (DEV #4)
- **Y** `run --help` introspection (DEV #7)
- **Z** CLI flag existence-check (DEV #10 généralisation)
- **AD** Test concurrence library-index (DEV #13)
- **AF** Pattern audit obligatoire post-CRITIQUE
- **AG** Matrix update obligatoire post-DEV

### Nice-to-have (DESIGN priorité 3 / 0.16+)

- **F** Tag commit `destructive: yes`
- **G** "Top Chef France" investigation
- **K** index_outbox GC policy
- **V** Skill events bus
- **W** Compare avec run précédent (déjà en matrix v2.0 §3.5 mais non implémenté)
- **X** Weird-outputs log persistant cumulé
- **AA** Per-command observability stamp

---

## 5. Patterns récurrents → causes structurelles → leviers DESIGN

| #       | Pattern                                       | Cause racine                                | Levier DESIGN tech-debt                      |
| ------- | --------------------------------------------- | ------------------------------------------- | -------------------------------------------- |
| **P1**  | 4 queries SQL inline divergent (DEV #14)      | Pas de fonction unique par "set sémantique" | C + tests "set_A == set_B" sur dataset       |
| **P2**  | Chaîne de découverte cachée (DEV #11→#13→#14) | Validation à l'usage non systématique       | AB + AC + AE                                 |
| **P3**  | DDL non-idempotent + concurrence (DEV #13)    | Code écrit avant multi-worker               | B + AD                                       |
| **P4**  | Sémantique inversée non pinned (DEV #9)       | Tests assoient l'OBSERVÉ, pas le DÉSIGNÉ    | AC + audit unlinks (A)                       |
| **P5**  | Hash sans version tag (DEV #11)               | Pas de schema migration pour algo changes   | D                                            |
| **P6**  | Coverage gap matrix vs code-emit (DEV #8)     | Matrix rédigée à la main                    | M + auto-stale-detector ressuscité (U)       |
| **P7**  | Observabilité asymétrique (DEV #6 VERIFY)     | rich rendering vs structlog                 | Q + frontière documentée                     |
| **P8**  | Doc rot CLI vs implementation (DEV #7)        | Docstring hardcodée                         | Y + Z                                        |
| **P9**  | Agents non matrix-aware (DEV #2, #3)          | Prompts globaux non spécialisés             | R + S + T                                    |
| **P10** | Agent discovery non hot-reloadable (DEV #1)   | Harness Claude Code charge au boot          | U + documentation "rerun after agent change" |

---

## 6. Conclusion — implications pour le DESIGN tech-debt (item 14)

L'item 14 (challenge final DESIGN + plan tech-debt) doit intégrer :

### Sections nouvelles à prévoir dans DESIGN.md

1. **Section "Invariants codebase" (P1, P5)** : règles transversales documentées —
   chaque "set sémantique" a une fonction unique ; chaque hash/fingerprint stocké
   a un tag de version.

2. **Section "DDL idempotence" (P3)** : règle universelle `CREATE INDEX IF NOT
EXISTS` + audit script + lint rule custom.

3. **Section "Destructive operations contract" (P4)** : règle "chaque unlink/replace
   doit avoir un docstring contrat + test pin sémantique".

4. **Section "Validation à l'usage" (P2)** : pour chaque fix touchant pipeline /
   BDD / indexer, un test E2E qui exerce le scénario complet. + `library-reconcile`
   en CI obligatoire.

5. **Section "Matrix lifecycle" (P6, P10)** : workflow obligatoire — chaque PR
   qui ajoute un event/step met à jour matrix.md dans le même commit. Hook ou
   CI check.

6. **Section "Observability frontière" (P7)** : tracer Typer rich (user output)
   vs structlog (telemetry). Chaque step pipeline DOIT émettre au moins un event
   structuré observable.

7. **Section "Doc-as-code" (P8)** : pas de duplication entre docstring et code.
   Generation auto depuis introspection ou tests pin la cohérence.

8. **Section "Skill v2.1+" (P9, P10)** : agents matrix-aware par défaut + auto-
   detect missing agents au start.

### Plan phases pour item 14

L'item 14 transformera ce brainstorm en plan ordonné. Estimation grossière :

- **Phase 1** : Matrix v2.1 (M, N, O, P, Q) + skill telemetry (U, V) — 1-2 jours
- **Phase 2** : Tests E2E (AB, AC, AD) + règle validation à l'usage (AE) — 2-3 jours
- **Phase 3** : Audits transversaux (A, B, C) + leur fix associé — 3-5 jours
- **Phase 4** : Hash version-tag (D) + scan_run resilience (J) + provider-IDs backfill (L) — 2-3 jours
- **Phase 5** : Doc-as-code (Y, Z) + observability frontière (Q approfondi) — 1-2 jours
- **Phase 6** : Agents matrix-aware (R, S, T) + auto-detect (U) — 1-2 jours
- **Phase 7** : Nice-to-haves (F, G, K, V, W, X, AA) — selon temps

Total grossier : **10-17 jours de travail**, bumpe vers 0.16.0 (minor) selon
SemVer (nouvelles règles + nouveaux tests, sans breaking change).

### Mémoire active à conserver

Patterns P1-P10 doivent rester en mémoire active pendant l'item 14. Tout DESIGN
qui ne traite pas explicitement chacun de ces patterns est incomplet.

---

## 7. Suite

- Item 7 : Check BDD complet — DEV #12 (7191 files_without_release) + audit
  structurel + cohérence post-fix DEV #11/14.
- Item 8 : Brainstorm BDD améliorations — alimenté par item 7 + items L, H, I,
  J, K du brainstorm actuel.
- Item 9 : Analyse commandes CLI — DEV #7, #10 + scope élargi (chaque commande
  CLI sa propre check d'usage, son own help text introspecté, etc.).
- Item 10 : Brainstorm CLI improvements.
- Item 11–13 : analyses conformité / critique design / synthèse.
- Item 14 : DESIGN final → reprend tout, classe en phases définitives.

Cet item 6 est la base de réflexion pour la dimension "pipeline + skill" du
DESIGN. Les dimensions BDD (items 7-8) et CLI (items 9-10) compléteront avant
le challenge final.
