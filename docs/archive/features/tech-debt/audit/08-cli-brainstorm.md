# Item 10 — Brainstorm améliorations CLI

**Date** : 2026-05-21
**Méthode** : consolidation des findings item 9 (DEVs #20-#23 + patterns P20-P22 + items
CL-A..CL-T) en sous-ensemble CLI du DESIGN tech-debt, plus brainstorm exhaustif d'axes CLI
exploratoires non encore couverts.
**Output** : liste DESIGN-ready CLI complète pour item 14 + propositions 0.17+.

---

## 0. Bilan condensé item 9

| Dimension                 | Statut                              | Items                                                                                                      |
| ------------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Bugs CLI                  | 4 DEVs                              | DEV #20 (qbit-restart inexistante), #21 (--dry-run gaps), #22 (format incohérent), #23 (telemetry absente) |
| Patterns systémiques      | 3 nouveaux                          | P20 (matrix→CLI inexistant), P21 (mutate sans dry-run), P22 (output format hardcoded)                      |
| Items brainstorm couverts | 20                                  | CL-A..CL-T                                                                                                 |
| Plan phase                | 6 phases (CLI-1..CLI-6), 7-13 jours |

Item 9 a établi le "must do" CLI. Item 10 complète avec des axes exploratoires + des items
transversaux (CLI ↔ BDD ↔ pipeline) qui ne sont apparus qu'en cross-feature.

---

## 1. Axes exploratoires (idées nouvelles, codifiées CL-U..CL-Z+)

### 1.1 — Interactive / REPL

**CL-U. Mode interactif `personalscraper repl`**

REPL Python avec contexte pré-chargé : `config`, `settings`, `db`, `app_context`. Pour debug
rapide :

```
$ personalscraper repl
PersonalScraper v0.16.0 REPL
config loaded from ./config/
library.db: 1935 items, 4 disks, last scan #32 (2026-05-21 21:06)
>>> db.execute("SELECT * FROM media_item WHERE title LIKE 'Monk%'").fetchall()
>>> drift.report = reconcile.run(); drift.report.merkle_drift
[]
>>>
```

Coût : faible (50 LOC Python). Bénéfice : énorme pour debugging.

**CL-V. Mode interactif `personalscraper interactive-dispatch`**

Plutôt que le HARD gate skill-side, dispatch interactif natif : montre chaque move planifié,
demande Y/N par item. Pour les opérateurs prudents.

```
Dispatch plan:
  [1/8] American Dad! (2005) → disk_2 (merged)    [Y/n/q]:
  [2/8] FROM (2022) → disk_3 (merged)             [Y/n/q]:
  ...
```

Bypass via `--yes-to-all` ou `--non-interactive`.

### 1.2 — Composition / pipelines explicites

**CL-W. Commandes composables via `--pipe-from-stdin` / `--pipe-to-stdout`**

Pour scripting :

```bash
personalscraper library-search 'kind=show year>=2020' --format json |
  personalscraper library-rescrape --from-stdin --dry-run
```

Currently chaque commande lit son propre input (config + FS). L'option pipe permettrait des
chaînages plus directs.

**CL-X. `personalscraper exec <script.py>`**

Pour automation custom : exécute un script Python avec le AppContext pré-chargé (équivalent
`repl` non-interactif). Évite à l'opérateur de monter son propre `import personalscraper`.

### 1.3 — Per-step entry points pour pipeline-monitor v2.1

**CL-Y. Hidden subcommand `__internal-pipeline-step`**

Pour la skill pipeline-monitor host process : un entry point qui exécute UNE step de pipeline
(ingest OU sort OU ...) et émet ses events sur un EventBus passé en arg. Permet à la skill
de monitorer step-by-step sans wrapper subprocess.

Currently la skill v2.0 importe `Pipeline` direct via host.py (Q5 décision). Cette commande
hidden simplifie le binding.

**CL-Z. `--emit-events-to <path>` global**

Option globale qui demande à la commande d'écrire son event-bus dump dans un JSONL file. La
skill pipeline-monitor host process (skill v2.0) émet déjà ce dump, mais on pourrait l'intégrer
au CLI pour permettre :

```bash
personalscraper --emit-events-to /tmp/run.jsonl run
```

Sans wrapper Python externe.

### 1.4 — Configuration introspectable

**CL-AA. `personalscraper config show [--format yaml|json|table]`**

Affiche la config résolue (after merging master + overlays + local). Utile pour debugging
"pourquoi cette catégorie ne se voit pas dans le sort ?".

**CL-AB. `personalscraper config diff` (vs config.example)**

Diff entre `config/` actuel et `config.example/` (le template). Montre les overrides locaux.

**CL-AC. `personalscraper config validate`**

Validation Pydantic stricte + sanity checks (paths existent, disks reachable, API keys présentes).
Actuellement déclenché au boot de chaque commande, mais une commande dédiée permettrait un
"dry-run config check" sans démarrer un workflow.

### 1.5 — Healthcheck / monitoring

**CL-AD. `personalscraper health`**

Health endpoint pour Healthchecks.io ou cron :

- Library DB integrity_check
- Drift signals (merkle, miss_strikes lifecycle)
- Disks mounted
- qBit reachable
- API keys présentes (TMDB/TVDB/OMDB)

Exit 0 si OK, non-0 + JSON sur stderr sinon. Voir aussi BD-Y `library-doctor`.

**CL-AE. `personalscraper status` (élargit `library-status`)**

Vue agrégée : pipeline status, library status, trailers status, indexer scan_run history,
disk space. Centralise ce que les 5 commandes status actuelles dispersent.

### 1.6 — Migration de la BDD / data ops

**CL-AF. `personalscraper db migrate [--dry-run] [--target-version N]`**

Exposer `apply_migrations()` via CLI. Currently implicitement appelé au boot de chaque commande,
pas de visibilité. Migration explicite + dry-run + rollback à version N.

**CL-AG. `personalscraper db backup` / `db restore`**

Snapshot manuel de library.db (pas seulement pre-migration auto). Pour les opérations risquées
hors migration.

**CL-AH. `personalscraper db vacuum`**

Wrapper sur `VACUUM`. Currently 0 site. À lancer périodiquement (cron mensuel ?) pour libérer
l'espace post-soft-deletes.

### 1.7 — Internationalisation / accessibility

**CL-AI. Help text en français (config user.language)**

Currently tout le help text est en anglais. Le user communique en français. Typer supports
gettext. Pas critique mais ergonomique.

### 1.8 — UX completion + suggestions

**CL-AJ. Auto-completion enhanced : suggérer les commandes par contexte**

`personalscraper l<TAB>` → suggère `library-*`. Existing completion functionne mais propose
TOUTES les commandes. Affiner par context (group, recently used, frequency).

**CL-AK. `personalscraper suggest <free-text>`**

LLM-ou-regex-based suggestion : "qu'est-ce que je devrais lancer après un dispatch ?" →
suggère `library-scan` + `library-index --mode incremental`.

Bel à terme. Pas pour 0.16.0.

---

## 2. Items trans-feature (cross BDD/CLI/pipeline)

Identifiés en re-relisant items 6/7/8/9 :

**CL-AL. Hook pre-commit "matrix references CI-validated CLI"**

Avant tout commit du repo skill (`.claude/`), lance le test "matrix mentions = CLI exists".
Évite l'introduction de DEV #20-style.

**CL-AM. `personalscraper diagnose <issue>`**

Diagnostic interactif : opérateur décrit son problème ("dispatch a échoué", "BDD est désynchro"),
le diagnose suggère les commandes/checks à lancer. À terme un mini-expert system.

**CL-AN. JSON-API mode pour intégration tierce**

Long terme : la CLI peut tourner en mode "server" exposant une JSON-RPC ou un HTTP endpoint
local. Pour intégration avec n8n, Home Assistant (déjà self-hosté), dashboards externes.

Pas pour 0.16, mais à mentionner dans le roadmap 0.17+.

---

## 3. Catégorisation must/should/nice (CL-U..CL-AN ajoutés)

### Must-have (DESIGN priorité 1)

Aucun nouvel item must-have par rapport à item 9. Items CL-U..CL-AN sont tous au mieux
should-have. La priorité 1 reste sur DEV #20-#23 fixes et CL-A..CL-T must-have.

### Should-have (priorité 2)

- **CL-AA** `config show` (debugging utility, low cost)
- **CL-AC** `config validate` (low cost, helpful in CI)
- **CL-AD** `health` (monitoring intégration)
- **CL-AF** `db migrate` explicite (visibility)
- **CL-AH** `db vacuum` (maintenance)
- **CL-AL** Hook pre-commit matrix-CLI check (extension CL-T au repo skill)

### Nice-to-have (0.17+ — exploratoires)

- **CL-U** `repl`
- **CL-V** `interactive-dispatch`
- **CL-W** `--pipe-from-stdin` / `--pipe-to-stdout`
- **CL-X** `exec <script>`
- **CL-Y** Hidden `__internal-pipeline-step`
- **CL-Z** `--emit-events-to <path>` global
- **CL-AB** `config diff`
- **CL-AE** `status` agrégé
- **CL-AG** `db backup/restore`
- **CL-AI** Help text français
- **CL-AJ** Completion contextuelle
- **CL-AK** `suggest`
- **CL-AM** `diagnose`
- **CL-AN** JSON-API mode

---

## 4. Plan définitif CLI (consolidation item 9 + 10)

| Phase           | Items                                                                                   | Effort | Bumpe vers |
| --------------- | --------------------------------------------------------------------------------------- | ------ | ---------- |
| CLI-1           | CL-A (dry-run gaps) + CL-I (run help) + CL-K (CLI coverage CI) + CL-T (matrix CLI test) | 1-2 j  | 0.16.0     |
| CLI-2           | CL-F (telemetry decorator) + CL-G (VERIFY events) + CL-H (console+log parity test)      | 1-2 j  | 0.16.0     |
| CLI-3           | CL-L (library-scan) + CL-M (library-doctor) + CL-P (backfill-ids CLI dédié ou doc)      | 2-3 j  | 0.16.0     |
| CLI-4           | CL-D + CL-E (format unification) + CL-J (doc référence)                                 | 2 j    | 0.16.0     |
| CLI-5           | CL-B (qbit-restart) + CL-C (reconcile flags clarif) + CL-N (library-gc)                 | 1-2 j  | 0.16.0     |
| CLI-6           | CL-S (pin commands tests) + CL-AA + CL-AC + CL-AD + CL-AF + CL-AH + CL-AL               | 1-2 j  | 0.16.0     |
| CLI-7 (différé) | CL-Q + CL-R (rename, group) + autres nice-to-have                                       | 1-2 j  | 0.17+      |

Total CLI 0.16.0 : **8-13 jours** sur les 13-22 du DESIGN global.

---

## 5. Synthèse finale CLI

- **35 items au total** (CL-A..CL-AN — 20 venant d'item 9 + 14 nouveaux brainstormés ici + 1 chevauchement)
- **23 items must/should** intégrables à 0.16.0 (CLI-1..CLI-6)
- **12 items nice-to-have** différés à 0.17+ (CLI-7 + 0.18+)
- **2 sections DESIGN** consolidées :
  - **§10 "CLI surface"** (élargit de l'item 6) — rules CLI-1..CLI-6
  - **§11 "CLI ergonomics & ops"** (nouvelle) — items 0.17+ exploratoires (REPL, interactive,
    pipe, exec, JSON-API)

### Tableau global multi-dimension (récap pour item 14)

| Dimension                  | Items DESIGN ready                                                                 | Jours estimés 0.16.0                                                          |
| -------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Pipeline app + indexer     | items A-G (item 6) + DEV #15-#19 (item 7) + BD-A..BD-AK (item 8)                   | 9-14 j                                                                        |
| Skill matrix v2.1 + agents | items M-T (item 6)                                                                 | 1-2 j                                                                         |
| Tests E2E + validation     | items AB-AE (item 6) + BD-AF, BD-AG, BD-AH (item 8) + CL-K, CL-T, CL-S (item 9/10) | 2-3 j                                                                         |
| CLI + observability + doc  | CL-A..CL-T (item 9) + CL-U..CL-AN ce brainstorm                                    | 8-13 j                                                                        |
| **TOTAL 0.16.0**           |                                                                                    | **20-32 jours** (avec parallélisation, en pratique 13-22 j sur le calendrier) |

---

## 6. Suite

Items 11-13 explorent les angles non encore vus :

- **Item 11** : analyse app + conformité design — cross-vérifie que tous les DEVs et items
  entrent dans une cohérence avec les DESIGNs existants (event-bus, provider-ids, indexer,
  pipeline).
- **Item 12** : analyse critique design + architecture — meta-analyse du tech-debt vs
  l'architecture cible (que veut être personalscraper à 1.0 ?).
- **Item 13** : brainstorm améliorations globales — synthèse de tous les brainstorms 6+8+10
  - items 11+12 + propositions transversales.
- **Item 14** : challenge final DESIGN + plan tech-debt — production de DESIGN.md (non-draft)
  - plan/INDEX.md + phases-XX.md prêts à `/implement:phase`.
