# Phase 5 — Nettoyage + migration docs + smoke test

**Objectif** : Supprimer les anciennes skills, migrer la documentation, vérifier zéro référence orpheline, et valider le nouveau flux via un smoke test sur une feature pilote jetable.

**Spec référence** : §9 (validation), §10 (scope).

**Résultat attendu** : état final de la config `.claude/` propre, documenté, et validé par un parcours end-to-end réel.

---

## Task 5.1 — Grep exhaustif des références à corriger

**Objectif** : cartographier toutes les occurrences des anciennes skills avant suppression.

- [ ] **Step 1 : Grep global**

```bash
grep -rnE '(implement-phase|implement-version|archive-version|model-version|plan:execute-next-phase|plan:end-phase|plan:check-execution)' \
     .claude/ CLAUDE.md docs/ 2>/dev/null | \
  grep -v "^docs/archive/" | \
  grep -v "^docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md" | \
  grep -v "^docs/superpowers/plans/" \
  > /tmp/old_skill_refs.txt
wc -l /tmp/old_skill_refs.txt
cat /tmp/old_skill_refs.txt
```

Expected : liste de fichiers à corriger. Typiquement : `CLAUDE.md` racine projet, `.claude/CLAUDE.md`, éventuellement hooks, éventuellement autres docs.

- [ ] **Step 2 : Classer les hits**

Pour chaque fichier listé, catégoriser :

- **À remplacer** : référence active à corriger (ex : `/implement-phase` → `/implement:phase`)
- **À conserver** : mention descriptive dans une archive ou un commentaire historique
- **À évaluer** : incertain (ex : hook qui appelle l'ancienne skill)

Créer une note `/tmp/refs_to_fix.md` avec le plan de substitution.

- [ ] **Step 3 : Commit de la checklist (optionnel, pour tracer l'analyse)**

```bash
# Pas de commit ici, la liste est temporaire dans /tmp
```

---

## Task 5.2 — Évaluer retrait de `plan:*`

**Spec section** : §10.1 (critère retrait/migration).

- [ ] **Step 1 : Identifier usages**

```bash
grep -rnE '/(plan:execute-next-phase|plan:end-phase|plan:check-execution)' .claude/ CLAUDE.md docs/ 2>/dev/null
```

- [ ] **Step 2 : Appliquer le critère §10.1 par skill**

Pour chaque skill, appliquer la matrice déterministe suivante — **pas de décision ouverte** :

| Skill                     | Recouverte par                                                        | Références externes actives (depuis Step 1) | Décision                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `plan:execute-next-phase` | `implement:phase` (flux continu + dispatch sub-phase)                 | À vérifier avec grep Step 1                 | Retrait ssi aucune ref externe                                                                                                                 |
| `plan:end-phase`          | `implement:phase` milestone + auto-invoke `implement:feature-pr`      | À vérifier avec grep Step 1                 | Retrait ssi aucune ref externe                                                                                                                 |
| `plan:check-execution`    | **Non recouverte** (audit post-merge ≠ `implement:check` inter-phase) | À vérifier avec grep Step 1                 | **Conservation** (ajouter note dans SKILL.md : "superseded for new features by the implement:\* flow, kept for auditing legacy v0-v15 phases") |

Procédure explicite :

1. Pour `plan:execute-next-phase` et `plan:end-phase` : si `grep -rn '/plan:execute-next-phase\|/plan:end-phase' .claude/ CLAUDE.md docs/ | grep -v "^docs/archive"` renvoie du contenu, **ne PAS supprimer**, migrer les appelants d'abord. Sinon : supprimer.
2. Pour `plan:check-execution` : **conserver systématiquement**, ajouter une note de déprécation dans son `SKILL.md` (header).

- [ ] **Step 3 : Supprimer (après vérif Step 2)**

```bash
# Uniquement si grep Step 2 a confirmé 0 référence externe :
git rm -r ".claude/skills/plan:execute-next-phase"
git rm -r ".claude/skills/plan:end-phase"
# plan:check-execution : NE PAS supprimer (conservation décidée en Step 2)
```

- [ ] **Step 4 : Ajouter note de déprécation sur plan:check-execution**

Éditer `.claude/skills/plan:check-execution/SKILL.md` pour ajouter en haut du corps :

```markdown
> **Note** : Cette skill est un vestige du flux version-based. Pour les nouvelles features (post-refactor 2026-04-22), l'audit inter-phase est pris en charge par `/implement:check`. `plan:check-execution` reste utilisable pour auditer les archives v0-v15 historiques.
```

- [ ] **Step 5 : Commit**

```bash
git add -A
git commit -m "chore(.claude): retire plan:execute-next-phase and plan:end-phase, deprecate plan:check-execution

- plan:execute-next-phase → superseded by implement:phase
- plan:end-phase → superseded by implement:phase milestone + feature-pr auto-invoke
- plan:check-execution → kept with deprecation note (audits legacy v0-v15)
"
```

---

## Task 5.3 — Supprimer les 4 anciennes skills implement-\*

- [ ] **Step 1 : Vérification préalable — aucune référence active**

```bash
grep -rn --include='*.md' '/implement-version\|/implement-phase\|/archive-version\|/model-version' \
     .claude/ CLAUDE.md docs/ 2>/dev/null | \
  grep -v "^docs/archive/" | \
  grep -v "^docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md" | \
  grep -v "^docs/superpowers/plans/"
```

Expected : vide OU uniquement mentions descriptives à corriger en Task 5.4. Si un hook ou une skill active référence encore ces noms → **corriger d'abord** avant de supprimer.

- [ ] **Step 2 : Supprimer**

```bash
git rm -r ".claude/skills/implement-phase"
git rm -r ".claude/skills/implement-version"
git rm -r ".claude/skills/archive-version"
git rm -r ".claude/skills/model-version"
```

- [ ] **Step 3 : Commit**

```bash
git commit -m "chore(.claude): remove legacy version-based implement skills

Replaced by feature-oriented implement:* skills:
- implement-phase → implement:phase (+ implement:sub-phase + implement:check)
- implement-version → implement:feature (+ implement:archive + implement:create-branch + implement:brainstorm + implement:plan)
- archive-version → implement:archive
- model-version → implement:brainstorm + implement:plan

See docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md
"
```

---

## Task 5.4 — Mettre à jour `CLAUDE.md` racine projet

**Fichier** : `/Volumes/IznoServer SSD/A TRIER/CLAUDE.md`

**Spec section** : §10.1 du spec.

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat CLAUDE.md | head -100
```

Repérer :

- Section `## Current Version` — à renommer
- Section `## Implementation Workflow` (ou équivalent) — à réécrire
- Mentions de `/implement-phase`, `/model-version`, `v15`, etc. — à remplacer

- [ ] **Step 2 : Renommer section `## Current Version` → `## Current Feature`**

Utiliser Edit. Nouvelle structure proposée :

```markdown
## Current Feature

**Codename**: _(no feature in progress)_
**Version**: {current SemVer from VERSION file}
**Archive**: `docs/archive/features/` — previous features by codename
**Historical archive**: `docs/archive/v0/` to `docs/archive/v15/` — legacy version-based work (preserved as-is)

When a feature is in progress, this section is updated by `/implement:feature` with :

- Codename (kebab-case, derived from feature title)
- Type (major / minor / bugfix)
- Version bump (X.Y.Z → X'.Y'.Z')
- Branch name, PR URL, design/plan paths
```

- [ ] **Step 3 : Remplacer la section Implementation Workflow**

Nouvelle version intégrant les 10 skills et le flux feature-oriented. Inclure :

- Description des 10 skills et leur rôle
- Ordre d'invocation (feature → phase → feature-pr → pr-review → archive au prochain feature)
- Règles SemVer (§3 du spec)
- Convention branches (`feat/{codename}`, `fix/{codename}`)
- Convention commits (`{type}({codename}): desc`)
- Pointer vers `docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md` pour détails complets

- [ ] **Step 4 : Grep post-édition**

```bash
grep -nE '(implement-phase|implement-version|archive-version|model-version|v\d+-[a-z-]+)' CLAUDE.md
```

Expected : aucun hit, sauf mentions explicites des archives historiques (`v0/` à `v15/`).

- [ ] **Step 5 : Commit**

```bash
git add CLAUDE.md
git commit -m "docs: migrate CLAUDE.md from version-based to feature-oriented workflow"
```

---

## Task 5.5 — Mettre à jour `.claude/CLAUDE.md`

**Fichier** : `/Volumes/IznoServer SSD/A TRIER/.claude/CLAUDE.md`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat .claude/CLAUDE.md
```

- [ ] **Step 2 : Mettre à jour la section "Implementation Lifecycle"**

Remplacer la liste des skills `/model-version`, `/implement-version`, `/implement-phase`, `/archive-version`, ainsi que les mentions de `/plan:execute-next-phase`, `/plan:end-phase` (supprimés en Task 5.2) et `/plan:check-execution` (conservé avec note de déprécation) par la nouvelle liste `/implement:*` avec 1 ligne descriptive chacune.

Structure suggérée :

```markdown
### Implementation Lifecycle (feature-oriented)

10 skills orchestrating the full feature lifecycle with Opus/Sonnet/Haiku model allocation:

**Entry orchestrator:**

- `/implement:feature` — Start a new feature: archive prev, brainstorm, create branch, plan

**Feature definition (invoked by /implement:feature):**

- `/implement:archive` — Archive previous feature (Haiku mechanical)
- `/implement:brainstorm` — Brainstorm via superpowers + derive codename + type (Opus)
- `/implement:create-branch` — Bump SemVer, create branch, init IMPLEMENTATION.md (Opus inline)
- `/implement:plan` — Generate phase files via superpowers:writing-plans (Sonnet)

**Phase execution:**

- `/implement:phase` — Orchestrate phase with continuous flow (Opus)
- `/implement:sub-phase` — Execute ONE sub-phase (Sonnet dispatch)
- `/implement:check` — Verify coherence design/plan/code (Opus, 6 checks)

**PR finalization (auto-invoked after last phase):**

- `/implement:feature-pr` — Local gate + push + create PR + poll CI (hybrid)
- `/implement:pr-review` — pr-review-toolkit + filter + fix loop (max 3) + merge squash (Opus)

**Rules:**

- Branches: `feat/{codename}` or `fix/{codename}`
- Commits: Conventional Commits with `{codename}` as scope
- SemVer bump at create-branch: bugfix → Z+1, minor → Y+1, major → X+1
- Merge strategy: squash, chosen at feature start (manual or auto)

Design details: see per-feature `docs/features/{codename}/DESIGN.md` once a feature is active,
or the refactor spec at `docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md`.
```

- [ ] **Step 3 : Grep post-édition**

```bash
grep -nE '(implement-phase|implement-version|archive-version|model-version)' .claude/CLAUDE.md
```

Expected : aucun hit.

- [ ] **Step 4 : Commit**

```bash
git add .claude/CLAUDE.md
git commit -m "docs(.claude): update config documentation for implement:* skills"
```

---

## Task 5.6 — Corriger autres fichiers référençant les anciennes skills

Pour chaque fichier identifié en Task 5.1 non encore traité (hors archives + ce plan + le spec) :

- [ ] **Step 1 : Lister**

```bash
grep -rnE '(implement-phase|implement-version|archive-version|model-version)' \
     .claude/ CLAUDE.md docs/ 2>/dev/null | \
  grep -v "^docs/archive/" | \
  grep -v "^docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md" | \
  grep -v "^docs/superpowers/plans/2026-04-22-implement-skills-refactor.md" | \
  grep -v "^docs/superpowers/plans/phase-0"
```

Expected : peu ou pas de hits à ce stade (la plupart corrigés en 5.4/5.5).

- [ ] **Step 2 : Pour chaque hit**

Utiliser Edit pour remplacer par l'équivalent `implement:*`. Substitutions standard :

- `/implement-phase` → `/implement:phase`
- `/implement-version` → `/implement:feature`
- `/archive-version` → `/implement:archive` (attention : l'invocation est différente maintenant — c'est une sous-skill de feature, plus directement appelable, mais la réf peut rester en mention)
- `/model-version` → `/implement:feature` (fusion)

- [ ] **Step 3 : Vérifier les hooks**

```bash
ls .claude/hooks/ 2>/dev/null
grep -rn 'implement-\|archive-version\|model-version' .claude/hooks/ 2>/dev/null
```

Si un hook invoque une ancienne skill, migrer vers l'équivalent ou supprimer le hook si obsolète.

- [ ] **Step 4 : Commit des corrections**

```bash
git add -A
git commit -m "refactor(.claude): update remaining references to implement:* skills"
```

---

## Task 5.7 — Vérification statique finale

- [ ] **Step 1 : Grep zéro-orphan**

```bash
grep -rnE '(/implement-phase|/implement-version|/archive-version|/model-version|/plan:execute-next-phase|/plan:end-phase)' \
     .claude/ CLAUDE.md docs/ 2>/dev/null | \
  grep -v "^docs/archive/" | \
  grep -v "^docs/superpowers/specs/" | \
  grep -v "^docs/superpowers/plans/"
```

Expected : **aucun hit**. Si hit → revenir à 5.6, corriger.

- [ ] **Step 2 : Lancer config-health-checker**

Dispatch l'agent `config-health-checker` sur `.claude/`. Expected : clean ou uniquement warnings déjà connus (pas de nouvelle erreur).

- [ ] **Step 3 : Lancer skill-dependency-checker**

Dispatch l'agent `skill-dependency-checker`. Expected : toutes cross-refs résolues. Pas d'orphelin.

- [ ] **Step 4 : Milestone commit (static OK)**

```bash
git commit --allow-empty -m "chore(.claude): phase 5 static validation pass"
```

---

## Task 5.8 — Smoke test feature pilote

**Spec section** : §9.3 du spec.

- [ ] **Step 1 : Choisir une feature pilote**

Critères :

- Petite (1 phase, 2-3 sous-phases)
- Jetable (pas critique si la branche est supprimée)
- Réaliste (exerce tout le flux)

Proposition : **ajouter un flag `--dry-run` à une commande de `personalscraper`**. Scope attendu : 1 phase, 2 sous-phases (impl + test).

Confirmer avec l'utilisateur avant de démarrer le smoke test.

- [ ] **Step 2 : Lancer `/implement:feature` sur la pilote**

```
/implement:feature "Add --dry-run flag to personalscraper sort command"
```

Observer :

- Pas de feature précédente à archiver (ou archive de la feature de refactor si déjà mergée — voir note plus bas)
- Brainstorm : codename proposé, confirmer (`dry-run-flag` par ex)
- Type dérivé : `minor` (nouvelle fonctionnalité)
- Bump calculé : si `VERSION` absent, `implement:create-branch` le crée à `0.1.0` puis bump selon type. Pour un `minor` sur VERSION initial absent : `0.1.0` → `0.2.0`. (Le projet est historiquement "v15" mais cette numérotation n'est PAS reprise dans VERSION SemVer — point de départ frais.)
- Branche créée : `feat/dry-run-flag`
- Plan généré : 1 phase, 2-3 sous-phases

- [ ] **Step 3 : Lancer `/implement:phase`**

Observer :

- Dispatch Sonnet par sous-phase
- `implement:check` entre chaque
- Commits avec scope `(dry-run-flag)`
- Milestone commit en fin de phase
- Auto-invoke `/implement:feature-pr` car dernière phase

- [ ] **Step 4 : Observer `/implement:feature-pr`**

- Gate local passe
- Push effectué
- PR créée (Sonnet compose titre/body)
- CI pollée par Haiku

- [ ] **Step 5 : Observer `/implement:pr-review`**

- pr-review-toolkit lancé
- Filtrage Opus
- Cycle 1 : ou bien rien de critique (sortie propre + merge), ou bien fix cycle et re-run

- [ ] **Step 6 : Critères d'acceptation smoke test**

Vérifier :

- [ ] Parcours complet sans intervention hors points interactifs prévus (codename confirm, merge strategy)
- [ ] IMPLEMENTATION.md mis à jour après chaque sous-phase (checkbox cochée)
- [ ] Commits : Conventional Commits, scope = `dry-run-flag`, aucun `v{N}`
- [ ] Aucune référence AI dans les messages de commit
- [ ] Version bumpée correctement dans VERSION + pyproject.toml
- [ ] PR squash-mergée (si mode auto) ou ready-to-merge (si manuel)
- [ ] Tests ajoutés pour la feature, verts en CI

- [ ] **Step 7 : Rollback si échec**

Si n'importe quel critère échoue :

```bash
# Supprimer la branche feature pilote
git checkout main
git branch -D feat/dry-run-flag
rm -rf docs/features/dry-run-flag

# Si la PR a été créée : fermer via gh-api
# gh pr close {PR_NUM}
```

**Si c'est le refactor qui échoue** (pas la feature pilote elle-même) :

```bash
# Rollback du refactor (approche 2, commit unique visible)
git log --oneline | grep "phase 5 gate"
git revert {SHA_du_refactor_range}
```

- [ ] **Step 8 : Si smoke test OK**

```bash
git commit --allow-empty -m "chore(.claude): smoke test passed on pilot feature"
```

---

## Gate finale Phase 5

- [ ] **Step 1 : Vérifier état final**

```bash
# Skills présentes
ls .claude/skills/ | grep -E '^implement:' | wc -l
# Expected: 10

# Anciennes absentes
ls .claude/skills/ | grep -E '^(implement-phase|implement-version|archive-version|model-version)$'
# Expected: vide
```

- [ ] **Step 2 : Milestone commit final**

```bash
git commit --allow-empty -m "chore(.claude): phase 5 gate — refactor complete and smoke tested"
```

- [ ] **Step 3 : Mettre à jour INDEX du master plan**

Marquer Phase 5 `[x]`.

```bash
git add docs/superpowers/plans/2026-04-22-implement-skills-refactor.md
git commit -m "docs(plan): mark phase 5 done — refactor complete"
```

- [ ] **Step 4 : Rapport final au user**

Afficher :

- 10 skills créées, 4 supprimées, CLAUDE.md × 2 migrés
- Smoke test : [result + branche pilote + URL PR si créée]
- Prochain pas : l'utilisateur peut maintenant lancer `/implement:feature` sur une vraie feature
- Mention que ce refactor lui-même n'a pas utilisé le nouveau flux (bootstrap). La prochaine feature utilisera.

---

## Note sur le bootstrap

Ce refactor CRÉE le système qu'il voudrait utiliser. Par définition, il ne peut pas utiliser `/implement:feature` pour se créer lui-même. C'est un pattern classique de bootstrap.

Conséquences pratiques :

- Les commits de ce refactor n'utilisent pas la convention `{type}({codename}): desc` — ils utilisent `{type}(.claude): desc`
- Il n'y a pas de codename pour ce refactor
- Il n'y a pas de version bump (le refactor touche uniquement `.claude/`, pas le code applicatif)
- Le refactor n'est pas tracké dans un `IMPLEMENTATION.md` à la racine — il est tracké dans ce master plan `docs/superpowers/plans/`

Une fois ce refactor mergé, la PROCHAINE feature utilisera le nouveau système (elle aura un codename, une version bumpée, un IMPLEMENTATION.md, etc.).
