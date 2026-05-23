# Phase 7 — Matrix v2.1 + agents matrix-aware

> **⚠ MANUAL EXECUTION REQUIRED — NOT for `/implement:phase`** (same as Phase 0)
>
> Cette phase commit sur le repo **`.claude/`** (branche `personal-scraper`), DISTINCT du repo
> `personalscraper/` (branche `fix/tech-debt`) où s'exécutent Phases 1-6 + 8-9. `/implement:phase`
> ne sait pas faire cross-repo. Procédure manuelle similaire à Phase 0 :
>
> ```bash
> cd /Users/izno/dev/PersonnalScaper/.claude
> git checkout personal-scraper
> # Implémenter sub-phases 7.1-7.4 via Edit/Write dans la conversation
> # Commits avec scope (pipeline-monitor)
> cd /Users/izno/dev/PersonnalScaper  # retour pour Phase 8
> ```

**Effort** : 1-2 jours
**Theme** : sync matrix avec les events réels du pipeline + agents matrix-aware par défaut.

## Coverage matrix

| Item                     | Sub-phase | Source pattern |
| ------------------------ | --------- | -------------- |
| MUST-15 / SH-24 / DEV #8 | 7.1       | P6             |
| (matrix version bump)    | 7.2       | P6             |
| DEV #2 + DEV #3          | 7.3       | P9             |
| (CHANGELOG)              | 7.4       | (doc)          |

**Note** : DEV #1 (skill auto-detect missing agents, ancien 7.4) a été **promu en Phase 0.1**
(`phase-00-skill-safety.md`) — il doit être shipped AVANT toutes les autres phases pour que
le monitoring `pipeline-monitor` v2.0 soit pleinement opérationnel pendant Phases 1-8.

DESIGN sections impacted : §12 doc conformity (matrix is reference doc).
Note : DEV #10 (library-reconcile --dry-run inexistant) closed dans 7.1 par matrix update.
DEV #6 (VERIFY events) closed par Phase 3.1 (events désormais émis → matrix peut les documenter).

**Note** : ce travail se fait sur le repo `.claude/` (branche `personal-scraper`), pas sur
personalscraper directement. Le checkout `.claude/` est un sous-repo séparé.

## Gate

- **READ FIRST** : `docs/features/tech-debt/AGENT_BRIEFING.md`
- Phase 6 commited (docs reference comprehensive)
- Tous les events nouveaux (Phase 1-5) sont stabilisés et observables
- **Note** : Phase 7 commit sur `.claude/` branche `personal-scraper` (cross-repo, comme Phase 0). Voir AGENT_BRIEFING §3 — `/implement:phase` ne sait pas le faire, exécution manuelle requise

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

### 7.4 CHANGELOG v2.1

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
- Auto-detect missing matrix-aware agents (DEV #1) — shipped earlier in Phase 0.1
- Agent prompts default matrix-aware (DEV #2)
- pipeline-state-validator FS-truth rule (DEV #3)
```

**Commit** : `docs(pipeline-monitor): CHANGELOG v2.1`

## Phase 7 Gate

- [x] 7.1 matrix v2.1 commit, **18 events** documented (audit gap audit found 18, not 12 — `cd47026`)
- [x] 7.2 skill SKILL.md v2.1 + assertion (`30360ef`)
- [x] 7.3 agents matrix-aware default + state-validator FS-truth (`4f9d598`)
- [x] 7.4 CHANGELOG updated (auto-detect DEV #1 already shipped in Phase 0.1) (`a1eb322`)
- [x] Parent repo personalscraper unchanged during cross-repo dispatch (clean separation)

**Phase 7 commits** (sur `.claude/personal-scraper`) :

- `cd47026` matrix v2.1 + 18 events
- `30360ef` skill v2.1 binding
- `4f9d598` 7 agents matrix-aware + state-validator FS-truth
- `a1eb322` CHANGELOG v2.1

**Phase gate commit** (sur le parent personalscraper, marquant le sync) :
`45b37bf chore(tech-debt): phase 7 gate — matrix v2.1 cross-repo (ACC-30/31/32 ✅)`
