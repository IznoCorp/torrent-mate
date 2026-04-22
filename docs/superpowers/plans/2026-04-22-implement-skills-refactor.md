# Implement Skills Refactor — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refonte des skills `.claude/skills/implement-*` et `archive-version` / `model-version` vers 10 skills `implement:*` orientées feature (codename + SemVer), avec allocation modèles Opus/Sonnet/Haiku et flux continu.

**Architecture:** 10 skills Markdown (fichiers `SKILL.md` avec frontmatter YAML) dans `.claude/skills/implement:<name>/`. Main session Opus orchestre, dispatch Sonnet pour l'écriture de code et Haiku pour les tâches mécaniques. Rename + split en place (approche "big-bang ciblé" discutée en brainstorming, transposée dans le plan d'écriture §11 du spec en 5 batches) : un commit par skill, un commit final pour suppressions et mise à jour docs, puis smoke test sur une feature pilote.

**Tech Stack:** Markdown, YAML frontmatter, Bash, Git, Claude Code skills system.

**Spec de référence:** `docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md` (SHA `b4deae6`).

---

## Phases

| #   | Phase                                                               | File                                                             | Status |
| --- | ------------------------------------------------------------------- | ---------------------------------------------------------------- | ------ |
| 1   | Fondations indépendantes (archive, create-branch, brainstorm, plan) | [phase-01-fondations.md](phase-01-fondations.md)                 | [x]    |
| ·   | _Cohérence P1 → P2_                                                 |                                                                  | [ ]    |
| 2   | Orchestrateur feature                                               | [phase-02-orchestrator.md](phase-02-orchestrator.md)             | [ ]    |
| ·   | _Cohérence P2 → P3_                                                 |                                                                  | [ ]    |
| 3   | Exécution de phase (sub-phase, check, phase)                        | [phase-03-phase-execution.md](phase-03-phase-execution.md)       | [ ]    |
| ·   | _Cohérence P3 → P4_                                                 |                                                                  | [ ]    |
| 4   | Finalisation PR (feature-pr, pr-review)                             | [phase-04-pr-finalization.md](phase-04-pr-finalization.md)       | [ ]    |
| ·   | _Cohérence P4 → P5_                                                 |                                                                  | [ ]    |
| 5   | Nettoyage + migration docs + smoke test                             | [phase-05-cleanup-smoke-test.md](phase-05-cleanup-smoke-test.md) | [ ]    |

## Dépendances entre phases

```
P1 (4 skills de base)
  └── P2 (implement:feature orchestre les 4 de P1)
        └── P3 (implement:phase orchestre sub-phase + check, indépendant de P1/P2)
              └── P4 (feature-pr + pr-review branchent au bout de phase)
                    └── P5 (supprime l'ancien, migre docs, smoke test de bout en bout)
```

Les phases sont strictement séquentielles — pas de parallélisation entre phases (même si P3 est logiquement indépendant de P1/P2, on garde l'ordre pour cohérence de validation).

## Contrôles de cohérence

### Après Phase 1 (P1 → P2)

- [ ] 4 fichiers `SKILL.md` créés dans `.claude/skills/implement:{archive,create-branch,brainstorm,plan}/`
- [ ] Chaque frontmatter `name` correspond au dossier (slug `implement:X`)
- [ ] Chaque `description` ≤ 200 chars, commence par un verbe
- [ ] Chaque fichier contient les clauses `WHEN` et `WHEN NOT`
- [ ] Aucun cross-ref vers skills non encore existantes (sauf skills externes : `superpowers:*`, `github-curl`)
- [ ] `config-health-checker` pass
- [ ] `skill-dependency-checker` pass (en attendant P2/P3, cross-refs vers `implement:feature`/`implement:phase` peuvent être flaggées — OK)

### Après Phase 2 (P2 → P3)

- [ ] `implement:feature` créé, référence correctement `implement:archive`, `implement:brainstorm`, `implement:create-branch`, `implement:plan`
- [ ] Pas de boucle de référence (P1 ne référence pas feature)
- [ ] `skill-dependency-checker` : toutes les cross-refs de feature pointent vers skills existantes

### Après Phase 3 (P3 → P4)

- [ ] 3 skills créées : `implement:sub-phase`, `implement:check`, `implement:phase`
- [ ] `implement:phase` référence `sub-phase` + `check`
- [ ] Aucune référence circulaire
- [ ] Dispatch Sonnet explicite dans `sub-phase` (paramètre `model="sonnet"` documenté)

### Après Phase 4 (P4 → P5)

- [ ] 2 skills créées : `implement:feature-pr`, `implement:pr-review`
- [ ] `implement:pr-review` peut invoquer `implement:phase` (auto-continuation cycle fix)
- [ ] Dispatch Haiku pour polling CI documenté dans `feature-pr`
- [ ] `pr-review-toolkit` référencé correctement dans `pr-review`

### Après Phase 5 (clôture)

- [ ] 4 anciennes skills supprimées
- [ ] `CLAUDE.md` racine projet mis à jour (section "Current Feature")
- [ ] `.claude/CLAUDE.md` mis à jour
- [ ] Zéro grep hit sur anciennes références dans `.claude/`, `CLAUDE.md`, `docs/` (hors archives)
- [ ] Smoke test pilote 100% vert
- [ ] `config-health-checker` + `skill-dependency-checker` tous deux clean

## Conventions globales (tous les SKILL.md)

**Frontmatter standard** :

```yaml
---
name: implement:{short-name}
description: |
  {Verb-initial one-line description, ≤ 200 chars}
  WHEN: {Condition d'usage}
  WHEN NOT: {Condition d'exclusion, mention de la skill alternative}
---
```

**Structure de corps standard** (adaptée par skill) :

1. `# {Skill Title}` — titre
2. `## Usage` — syntaxe d'invocation (`/implement:X`) + arguments
3. `## Model Allocation` — Opus / Sonnet / Haiku selon §5 du spec
4. `## Process` — étapes numérotées, référence section §7.X du spec pour détails
5. `## Error Handling` — matrice des cas d'échec (sous-ensemble pertinent du §8.2 du spec)
6. `## Idempotence` — comment la skill gère les reprises
7. `## What this skill does NOT do` — garde-fous

**Commit convention** :

- Un commit par skill : `feat(.claude): add implement:{skill-name} skill`
- Commit de clôture phase : `chore(.claude): phase {N} gate — {phase name}`
- Pas de scope codename pour ce refactor (le refactor ciblé `.claude/` n'utilise pas le workflow feature lui-même pendant sa création — pattern classique de bootstrap).

**Quality gate** (par skill créée) :

- [ ] Frontmatter parseable YAML
- [ ] `name` == slug du dossier
- [ ] `description` ≤ 200 chars
- [ ] Clauses `WHEN` et `WHEN NOT` présentes
- [ ] Cross-refs pointent vers skills existantes (ou marquées "créée en phase N")
- [ ] Section Model Allocation présente

## Next action

**Start Phase 1** : créer les 4 skills fondations en parallèle ou séquentiellement (peu importe, indépendantes). Voir `phase-01-fondations.md`.
