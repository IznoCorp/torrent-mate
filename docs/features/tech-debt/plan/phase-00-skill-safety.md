# Phase 0 — Pre-Foundations: Skill safety net (DEV #1)

> **⚠ MANUAL EXECUTION REQUIRED — NOT for `/implement:phase`**
>
> Cette phase commit sur le repo **`.claude/`** (branche `personal-scraper`), DISTINCT du repo
> `personalscraper/` (branche `fix/tech-debt`) où s'exécutent Phases 1-9. La skill
> `/implement:phase` + `/implement:sub-phase` opère sur UN seul repo (le current working dir),
> ne sait pas faire de cross-repo dispatch. Tenter `/implement:phase` ici échouera ou commitera
> au mauvais endroit.
>
> **Procédure manuelle** (opérateur ou agent inline en main session) :
>
> ```bash
> # 1. Switch context vers .claude/ branche personal-scraper
> cd /Users/izno/dev/PersonnalScaper/.claude
> git checkout personal-scraper
> git status  # doit être clean
>
> # 2. Implémenter sub-phase 0.1 ci-dessous (édition SKILL.md PHASE 0 + --degraded-mode)
> #    via Edit/Write tools dans la conversation
>
> # 3. Commit avec scope (pipeline-monitor) — voir convention en 0.1
> # 4. Vérifier que le grep MATRIX_AGENTS_MISSING retourne ≥1 match dans SKILL.md
>
> # 5. Revenir au repo personalscraper pour Phase 1+
> cd /Users/izno/dev/PersonnalScaper
> ```
>
> **Une fois Phase 0 commitée sur `.claude/`**, retourner sur `personalscraper/fix/tech-debt`
> et lancer `/implement:phase` qui démarrera Phase 1.

**Effort** : 0.5 jour
**Theme** : restaurer le filet de sécurité `pipeline-monitor` v2.0 AVANT toute autre phase, afin
que les Phases 1-8 personalscraper bénéficient du monitoring matrix-aware complet (host.py
EventBus mode + 4 agents matrix-aware).

**Promu depuis Phase 7.4** : la décision opérateur (2026-05-22) est de promouvoir DEV #1 en
sub-phase pré-foundations pour éviter que les 8 phases personalscraper tournent en fallback
subprocess mode comme le run 2026-05-21.

## Coverage matrix

| Item   | Sub-phase | Source pattern |
| ------ | --------- | -------------- |
| DEV #1 | 0.1       | P10            |

DESIGN sections impacted : §12 doc conformity (skill is reference for monitoring).

**Note repo** : ce travail se fait UNIQUEMENT sur le repo `.claude/` (branche `personal-scraper`),
pas sur personalscraper directement. Le checkout `.claude/` est un sous-repo séparé.

## Gate (prérequis avant cette phase)

- Branch `fix/tech-debt` checkout sur personalscraper (no changes)
- DESIGN.md + plan/INDEX.md + ACCEPTANCE.md committed (état post `cc0bb39` + `be8fc87`)
- `.claude/` branche `personal-scraper` checkout, repo clean
- 4 fix commits déjà shipped sur personalscraper (268cbee, 29c4953, fc39f77, 3993487)

## Sub-phases

### 0.1 Skill auto-detect missing matrix agents (DEV #1)

**Site** : `.claude/skills/pipeline-monitor/SKILL.md` PHASE 0

**Contexte** : la skill v2.0 a 4 agents matrix-aware (pipeline-bdd-validator,
pipeline-event-monitor, pipeline-invariant-checker, pipeline-matrix-stale-detector). Le run
2026-05-21 a montré qu'ils peuvent être "indécouvrables" si le harness Claude Code n'a pas
chargé la liste agents au boot. Conséquence : PHASE 0 stale-detector skip, PHASE 3 dégradée
en substituts `general-purpose`, host.py EventBus mode jamais réellement exercé.

**Implementation** : au start de la skill, après l'assertion `MATRIX_VERSION = "2.0"`, ajouter
une PHASE 0 step "Matrix agents discoverability check" qui vérifie que les 4 agents
matrix-aware figurent dans la liste available agents (visible dans le prompt system).

Pseudocode (à intégrer en prose dans SKILL.md) :

```
PHASE 0 — Matrix agents discoverability check (after MATRIX_VERSION assertion)

Required matrix-aware agents:
  - pipeline-bdd-validator
  - pipeline-event-monitor
  - pipeline-invariant-checker
  - pipeline-matrix-stale-detector

For each, verify it appears in the system's "available agents" list (as exposed
to the conversation). If ANY is missing:
  STOP. Report: "MATRIX_AGENTS_MISSING: <comma-separated list of missing agents>.
  Run `/plugins-reload` and re-invoke the skill, or proceed with --degraded-mode
  to fall back to `general-purpose` substitution (DEVIATION LIST will mark these
  as TOOLING_BUG)."

`--degraded-mode` opt-in : skill continues with `general-purpose` substitutes
for the missing agents, but every finding from a substitute agent gets a
trailing note "(substituted, matrix-aware agent unavailable)" so the operator
can spot reduced-confidence findings.
```

**Tests** : la skill n'a pas de tests Python directs, mais on peut tester :

1. Le SKILL.md mentionne la PHASE 0 discoverability check (`grep` assertion).
2. Si `--degraded-mode` est utilisé, le rapport final est tagué dans son frontmatter.

**Commit** (sur `.claude/` repo, branche `personal-scraper`) :
`feat(pipeline-monitor): auto-detect missing matrix agents at boot + --degraded-mode (DEV #1)`

## Phase 0 Gate

- [ ] 0.1 SKILL.md updated with PHASE 0 discoverability check + `--degraded-mode` opt-in
- [ ] `grep MATRIX_AGENTS_MISSING .claude/skills/pipeline-monitor/SKILL.md` returns ≥1 match
- [ ] CHANGELOG note added (will be folded into v2.1 entry at Phase 7.5)
- [ ] Pre-flight test : invoke skill in a session, expect either OK (agents present) or
      STOP MATRIX_AGENTS_MISSING (clean error)

**Phase gate commit** (sur `.claude/`) :
`chore(pipeline-monitor): phase 0 gate — skill safety net for DEV #1`

## Note sur Phase 7

Phase 7 garde `7.1` (matrix v2.1), `7.2` (skill bump v2.1), `7.3` (agents matrix-aware
defaults), `7.4` (CHANGELOG — promu depuis 7.5). L'ancien 7.4 est cette Phase 0.1.

L'entrée CHANGELOG v2.1 mentionnera DEV #1 + DEV #2 + DEV #3 (Phase 0.1 + Phase 7.3) côte à
côte, même si le fix DEV #1 est shipped plus tôt.
