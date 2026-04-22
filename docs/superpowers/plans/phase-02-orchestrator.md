# Phase 2 — Orchestrateur feature

**Objectif** : Créer `implement:feature`, la skill entry-point qui enchaîne archive → brainstorm → create-branch → plan pour démarrer une nouvelle feature.

**Spec référence** : §7.1 du spec.

**Skills créées** :

1. `implement:feature`

**Prérequis** : Phase 1 complète — les 4 skills invoquées existent déjà.

---

## Task 2.1 — Créer `implement:feature`

**Files:**

- Create: `.claude/skills/implement:feature/SKILL.md`

**Spec section** : §7.1 du spec.

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:feature"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:feature
description: |
  Start a new feature: archive previous (if complete+merged), brainstorm, derive codename and SemVer bump, create feature branch, generate phased plan.
  WHEN: Starting any new feature (major, minor, or bugfix). Entry point for the feature lifecycle.
  WHEN NOT: Continuing an in-progress feature. Use /implement:phase instead.
---
```

Sections :

1. `# Implement Feature`
2. `## Usage`
   - `/implement:feature` — auto-détecte contexte
   - `/implement:feature "Feature title hint"` — optionnel, sert le brainstorm
3. `## Model Allocation` — **Opus main session** (orchestration pure, enchaîne des sous-skills).
4. `## Process` — 6 étapes conformément au spec §7.1 révisé :
   1. **Détecter l'état de la feature précédente** :
      - Pas de `IMPLEMENTATION.md` à la racine → skip archive, aller à étape 2.
      - `IMPLEMENTATION.md` existant, toutes phases `[x]`, PR mergée → lire le codename depuis le header, invoquer `/implement:archive`, puis étape 2.
      - `IMPLEMENTATION.md` existant, feature incomplète → **STOP** avec message : "Feature précédente `{codename}` incomplète. Terminer via `/implement:phase` avant de démarrer une nouvelle feature."
   2. **Invoquer `/implement:brainstorm`** → attend retour `{codename, title, type, bump_from, bump_to, design_doc_path}`. Si user abandonne → stop propre.
   3. **Demander stratégie de merge** à l'utilisateur :
      > Stratégie de merge pour la PR ? (manual / auto)
      >
      > - `manual` — tu merges manuellement la PR quand la review est clean
      > - `auto` — merge squash automatique via API quand la review est clean
   4. **Invoquer `/implement:create-branch`** avec `{codename, title, type, bump_from, bump_to, merge_mode, design_doc_path}`.
   5. **Invoquer `/implement:plan`** avec `{codename, design_doc_path}`.
   6. **Rapport final** : afficher récapitulatif (codename, version bump, branche créée, nombre de phases générées) et indiquer : "Prêt. Lance `/implement:phase` pour commencer l'implémentation."
5. `## Error Handling` — matrice :
   - Feature précédente incomplète → stop, message utilisateur (voir étape 1)
   - Brainstorm abandonné → rien n'a été créé (idempotent), pas de commit parasite
   - Archive échoue (voir §7.2) → stop, bubble up le message d'erreur
   - Create-branch échoue (branche existe, etc.) → stop, message
   - Plan échoue → la branche existe mais pas de plan → message à user pour relancer `/implement:plan` manuellement ou cleanup
6. `## Idempotence` — la skill détecte l'état courant à chaque étape et ne re-fait pas ce qui existe déjà :
   - Si branche déjà créée mais pas de plan → skip archive + brainstorm + create-branch, invoque uniquement plan
   - Si design doc + codename déjà calculés mais pas de branche → reprendre à create-branch
   - En pratique : l'état est déduit de (présence IMPLEMENTATION.md, branche courante, fichiers `docs/features/{codename}/`)
7. `## What this skill does NOT do` — ne lance pas `/implement:phase` (l'utilisateur décide), ne push pas, ne touche pas à la feature courante si elle est incomplète.

**Diagramme de flux** à inclure :

```
/implement:feature [title?]
    │
    ▼
Previous IMPLEMENTATION.md ?
    ├── absent → skip archive
    ├── present + all phases [x] + PR merged → /implement:archive
    └── present + incomplete → STOP
    │
    ▼
/implement:brainstorm
    └── returns {codename, title, type, bump, design_path}
    │
    ▼
Ask user: merge strategy (manual | auto)
    │
    ▼
/implement:create-branch
    └── creates feat/{codename} or fix/{codename}, bumps version, commits
    │
    ▼
/implement:plan
    └── generates docs/features/{codename}/plan/
    │
    ▼
Report ready → user runs /implement:phase
```

- [ ] **Step 3 : Vérifier frontmatter**

```bash
head -10 ".claude/skills/implement:feature/SKILL.md"
```

Check : `name: implement:feature`, description multi-ligne avec WHEN/WHEN NOT.

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:feature/SKILL.md"
git commit -m "feat(.claude): add implement:feature orchestrator skill"
```

---

## Gate cohérence Phase 2 → Phase 3

- [ ] **Step 1 : Vérifier présence**

```bash
ls ".claude/skills/implement:feature/SKILL.md"
```

- [ ] **Step 2 : Cross-refs P1 → P2**

Vérifier que `implement:feature/SKILL.md` référence bien par slash les 4 skills de P1 :

- `/implement:archive`
- `/implement:brainstorm`
- `/implement:create-branch`
- `/implement:plan`

```bash
grep -E '/implement:(archive|brainstorm|create-branch|plan)' ".claude/skills/implement:feature/SKILL.md"
```

Expected : au moins 4 matches (un par skill).

- [ ] **Step 3 : Vérifier absence de boucle**

Aucune skill de P1 ne doit référencer `implement:feature`.

```bash
grep -l 'implement:feature' ".claude/skills/implement:archive/SKILL.md" \
                             ".claude/skills/implement:create-branch/SKILL.md" \
                             ".claude/skills/implement:brainstorm/SKILL.md" \
                             ".claude/skills/implement:plan/SKILL.md" || echo "No loop detected (expected)"
```

Expected : aucune sortie de `grep -l`, ou seulement mentions descriptives dans `WHEN NOT` (OK).

- [ ] **Step 4 : Lancer skill-dependency-checker**

```
Invoquer l'agent skill-dependency-checker via Agent tool.
```

Expected : toutes cross-refs de `implement:feature` résolues vers skills existantes. Le warning P1 sur `implement:feature` (depuis P1) disparaît maintenant.

- [ ] **Step 5 : Milestone commit Phase 2**

```bash
git commit --allow-empty -m "chore(.claude): phase 2 gate — orchestrator (implement:feature)"
```

- [ ] **Step 6 : Mettre à jour INDEX du master plan**

Éditer `docs/superpowers/plans/2026-04-22-implement-skills-refactor.md`, marquer Phase 2 `[x]`.

```bash
git add docs/superpowers/plans/2026-04-22-implement-skills-refactor.md
git commit -m "docs(plan): mark phase 2 done"
```
