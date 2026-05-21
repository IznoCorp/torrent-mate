# Phase 7 — Matrix v2.1 + agents matrix-aware

**Effort** : 1-2 jours
**Theme** : sync matrix avec les events réels du pipeline + agents matrix-aware par défaut.

**Note** : ce travail se fait sur le repo `.claude/` (branche `personal-scraper`), pas sur
personalscraper directement. Le checkout `.claude/` est un sous-repo séparé.

## Gate

- Phase 6 commited (docs reference comprehensive)
- Tous les events nouveaux (Phase 1-5) sont stabilisés et observables

## Sub-phases

### 7.1 Matrix v2.1 — intégrer les 12 events coverage gaps (MUST-15 / SH-24)

**Site** : `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md`

**Header** : `**Matrix version**: 2.1`

**Events à ajouter** (DESIGN_CONFORM patterns) :

- §SORT :
  - `tracker_dest_path_pruned`
  - `sort_tracker_pruned`
- §PROCESS:clean :
  - `repair_root_duplicate_replaced`
  - `repair_root_duplicate_would_replace`
  - `repair_root_duplicate_replace_failed`
- §PROCESS:scrape :
  - `nfo_valid action=repaired`
  - `movies_start count=N`
  - `movies_done errors=N scraped=N skipped=N unmatched=N`
  - `tvshows_start count=N`
  - `tvshows_done errors=N scraped=N skipped=N unmatched=N`
  - `repair_episode_moved dest=... season_dir=... source=...`
  - `episode_sibling_deleted path=...`
  - `season_dir_exists directory=...`
  - `episode_would_rename dest=... source=...`
  - `repair_episodes_organized count=N show=...`
- §ENFORCE :
  - `enforce.orphan_episode_moved dst=... src=...`
  - `enforce_sanitize_action action=deleted_ds_store`
  - `enforce_structure_fix fix=... item=...`
- §VERIFY :
  - `verify_item_done status=valid checks_passed=N/N` (post Phase 3.1)
  - `verify_item_done status=blocked errors=[...]`

**Sections à modifier** :

- §PROCESS:scrape : documenter `episode_unmatched_no_rename` puis handoff ENFORCE (corrige
  contradiction note prose item 5 finding output-analyzer)
- §VERIFY : retirer le doute "Hyp. A vs B" — DEV #6 résolu en Phase 3.1, events sont sur
  stdout (INFO) ET sur EventBus
- §3.4 library-reconcile : supprimer la mention `--dry-run` (corrige DEV #10), mentionner
  `--read-only` / `--enqueue-repairs` aliases

**Commit** (sur `.claude/` repo) : `docs(pipeline-monitor): matrix v2.1 — 12 events coverage
gaps + VERIFY events + library-reconcile flag clarif (MUST-15, DEV #6, DEV #8, DEV #10)`

### 7.2 Skill version bump (MUST-15)

**Site** : `.claude/skills/pipeline-monitor/SKILL.md`

- Frontmatter : `version: 2.1`, `matrix_version: "2.1"`
- Assertion au boot : `MATRIX_VERSION = "2.1"` — refus si matrix != 2.1

**Commit** : `feat(pipeline-monitor): skill v2.1 — matrix v2.1 binding`

### 7.3 Agents matrix-aware par défaut (CL-A item 6 R / S / T)

**Sites** : `.claude/agents/pipeline-orphan-hunter.md`, `pipeline-state-validator.md`,
`pipeline-scrape-checker.md`, `pipeline-sort-checker.md`, `pipeline-ingest-checker.md`,
`pipeline-dispatch-checker.md`, `pipeline-output-analyzer.md`

**Pour chaque agent**, ajouter dans la `description` (ou un fichier shared) :

> "AVANT toute classification, lire `references/design-conformity-matrix.md` v2.1. Pour chaque
> finding, identifier si une row matrix le couvre comme DESIGN_CONFORM. Si oui → 'Design
> Conformity Check' section (informational only). Sinon → DEVIATION LIST. NE JAMAIS classifier
> un état design-conform comme bug."

**Sites spécifiques** :

- **pipeline-orphan-hunter** : ajouter explicitement "Files in 097-TEMP between INGEST and SORT
  are DESIGN_CONFORM ; `.DS_Store` is cosmetic macOS (mineur)."
- **pipeline-state-validator** : ajouter "ALWAYS verify FS via Bash + ls/stat. NEVER infer FS
  state from log messages." (corrige DEV #3 specifically)

**Commit** : `feat(pipeline-monitor): agents matrix-aware default + state-validator FS-truth (DEV #2, DEV #3)`

### 7.4 Skill auto-detect missing matrix agents (CL-U item 6 alternative à DEV #1)

**Site** : `.claude/skills/pipeline-monitor/SKILL.md` PHASE 0

**Implementation** : au start de la skill, après MATRIX_VERSION assertion, vérifier que les 4
agents matrix-aware existent dans la liste available agents. Si l'un manque → STOP avec message :

> "Matrix-aware agent <name> not discoverable. Run `/plugins-reload` and re-invoke the skill,
> or fall back to general-purpose substitution (degraded mode)."

**Commit** : `feat(pipeline-monitor): auto-detect missing matrix agents at boot (DEV #1)`

### 7.5 CHANGELOG v2.1

**Site** : `.claude/skills/pipeline-monitor/CHANGELOG.md`

**Entry** :

```markdown
## v2.1 — 2026-MM-DD

Matrix + skill enrichment from tech-debt 0.16.0 audit.

### Matrix v2.1 changes

- 12 new events documented (SORT, PROCESS:clean/scrape, ENFORCE, VERIFY)
- DEV #10 library-reconcile flag clarif
- VERIFY observability gap resolved (Phase 3.1 personalscraper)

### Skill v2.1 changes

- MATRIX_VERSION assertion = "2.1"
- Auto-detect missing matrix-aware agents (DEV #1)
- Agent prompts default matrix-aware (DEV #2)
- pipeline-state-validator FS-truth rule (DEV #3)
```

**Commit** : `docs(pipeline-monitor): CHANGELOG v2.1`

## Phase 7 Gate

- [ ] 7.1 matrix v2.1 commit, 12 events documented
- [ ] 7.2 skill SKILL.md v2.1 + assertion
- [ ] 7.3 agents matrix-aware default + state-validator FS-truth
- [ ] 7.4 auto-detect missing agents
- [ ] 7.5 CHANGELOG updated
- [ ] Skill invocation sur personalscraper post-Phase 6 produit DEVIATION LIST = 0 (modulo
      operational items)

**Phase gate commit** (sur `.claude/`) : `chore(pipeline-monitor): phase 7 gate — matrix v2.1`
