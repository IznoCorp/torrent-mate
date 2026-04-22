# Phase 1 — Fondations indépendantes

**Objectif** : Créer les 4 skills de base qui n'ont aucune dépendance sur les autres skills `implement:*` (elles ne s'appellent pas entre elles). Ce sont les briques réutilisables par les orchestrateurs (phases suivantes).

**Spec référence** : §7.2 (archive), §7.3 (create-branch), §7.4 (brainstorm), §7.5 (plan).

**Skills créées** :

1. `implement:archive`
2. `implement:create-branch`
3. `implement:brainstorm`
4. `implement:plan`

**Ordre** : les 4 tâches sont indépendantes — peuvent être exécutées en parallèle par des subagents distincts, ou séquentiellement. Pas de dépendance d'ordre à l'intérieur de P1.

---

## Task 1.1 — Créer `implement:archive`

**Files:**

- Create: `.claude/skills/implement:archive/SKILL.md`

**Spec section** : §7.2 du spec (lire intégralement avant de commencer).

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:archive"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Le fichier doit commencer par ce frontmatter exact :

```yaml
---
name: implement:archive
description: |
  Archive the current feature (move IMPLEMENTATION.md + docs/features/{codename}/ to docs/archive/features/). Pre-flight strict: repo clean, tests green, all phases DONE, PR merged.
  WHEN: Previous feature complete and PR merged; about to start a new feature via /implement:feature.
  WHEN NOT: Feature still in progress. Use /implement:phase to finish it first. Never merge a PR from here — that is pr-review's job.
---
```

Puis structurer le corps selon les sections :

1. `# Implement Archive`
2. `## Usage` — `/implement:archive` (invoqué par `implement:feature`, rarement direct)
3. `## Model Allocation` — Haiku subagent pour les opérations mécaniques (git mv + template + commit). Main session Opus uniquement pour lancer le dispatch et vérifier le résultat.
4. `## Process` — 4 étapes conformément au spec §7.2 :
   - **Pre-flight** (Opus inline) : repo clean, tests verts, toutes phases `[x]`, PR mergée. En cas d'échec : message d'erreur explicite (voir spec §7.2 pour wording exact).
   - **Lire le codename courant** depuis le header IMPLEMENTATION.md.
   - **Dispatch Haiku subagent** avec prompt listant les opérations : `mkdir docs/archive/features/{codename}/`, `git mv IMPLEMENTATION.md ...`, `git mv docs/features/{codename}/* ...`, créer nouveau IMPLEMENTATION.md vierge à la racine (template ci-dessous), mettre à jour CLAUDE.md section "Current Feature", commit `milestone: archive {codename}`.
   - **Post-archive** (Opus inline) : optionnellement `git branch -d feat/{codename}` (warning-only si échec, pas bloquant).
5. `## Error Handling` — matrice pour : repo sale, tests rouges, phase non-DONE, PR non mergée, dossier d'archive existant.
6. `## Idempotence` — refuse d'écraser `docs/archive/features/{codename}/` existant.
7. `## What this skill does NOT do` — **ne merge JAMAIS une PR** (délégué à `implement:pr-review` §7.10), ne crée pas la feature suivante (c'est `implement:feature`).

**Template IMPLEMENTATION.md vierge** à inclure dans la skill (le Haiku subagent l'écrit) :

```markdown
# Implementation Progress — (awaiting feature)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: _(to be defined by /implement:feature)_
**Version bump**: _(to be defined)_
**Branch**: _(to be defined)_
**PR merge**: _(to be defined: manual or auto)_
**PR**: _(created after last phase)_
**Design**: _(to be defined after brainstorm)_
**Master plan**: _(to be defined after plan generation)_

## Phases

_(filled by /implement:plan)_

## Review cycles

_(filled by /implement:pr-review)_

## Next action

**Awaiting new feature definition** — run /implement:feature
```

- [ ] **Step 3 : Vérifier le frontmatter**

Lire le fichier et confirmer :

- `name` == `implement:archive`
- `description` multi-ligne avec WHEN et WHEN NOT
- Description totale ≤ 200 chars pour la première ligne (pour affichage dans slash menu)

Commande de vérification rapide :

```bash
head -10 ".claude/skills/implement:archive/SKILL.md"
```

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:archive/SKILL.md"
git commit -m "feat(.claude): add implement:archive skill"
```

---

## Task 1.2 — Créer `implement:create-branch`

**Files:**

- Create: `.claude/skills/implement:create-branch/SKILL.md`

**Spec section** : §7.3 du spec + §3 (règles de bump).

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:create-branch"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:create-branch
description: |
  Bump SemVer version, create the feature branch (feat/{codename} or fix/{codename}), move DESIGN.md onto branch, initialize IMPLEMENTATION.md header, single commit.
  WHEN: Invoked by /implement:feature after /implement:brainstorm returned {codename, title, type, bump}.
  WHEN NOT: Feature not yet brainstormed; standalone use discouraged.
---
```

Sections :

1. `# Implement Create Branch`
2. `## Usage` — invoqué par `implement:feature` avec arguments `{codename, title, type, bump, merge_mode, design_doc_path}`.
3. `## Model Allocation` — **inline Opus** (pas de dispatch — ≤ 10 commandes bash, pas de jugement).
4. `## Process` — 7 étapes conformément au spec §7.3 révisé :
   1. Lire VERSION actuelle (ou créer `0.1.0` si fichier absent).
   2. Calculer nouveau numéro selon `type` : `bugfix` → Z+1, `minor` → Y+1 Z=0, `major` → X+1 Y=0 Z=0.
   3. `git checkout -b feat/{codename}` (ou `fix/{codename}` si `type==bugfix`). Si existe → demander user : reprendre ou renommer.
   4. `mv {design_doc_path} docs/features/{codename}/DESIGN.md` (fichier non git-tracked à ce stade).
   5. Écrire/mettre à jour VERSION + `pyproject.toml` (si présent) avec le nouveau numéro.
   6. Remplir header IMPLEMENTATION.md (feature title, type, version bump X.Y.Z → X'.Y'.Z', branch, merge mode, chemin DESIGN, chemin master plan placeholder).
   7. Commit unique : `chore({codename}): bump version to {X.Y.Z}` — inclut VERSION, pyproject.toml, DESIGN.md, IMPLEMENTATION.md.
5. `## Error Handling` — matrice : branche existe (ask reprendre/renommer), VERSION absent (créer 0.1.0), pyproject.toml mal formé (stop).
6. `## Idempotence` — détecte branche existante → demande confirmation.
7. `## What this skill does NOT do` — ne lance pas le plan, ne push pas, ne crée pas la PR.

**Bump rules reference** (à inclure en sous-section pour l'implémenteur) :

| Type     | Critère                                                                | Bump          | Branche           |
| -------- | ---------------------------------------------------------------------- | ------------- | ----------------- |
| `bugfix` | Fix d'une feature existante                                            | Z+1           | `fix/{codename}`  |
| `minor`  | Nouvelle fonctionnalité                                                | Y+1, Z=0      | `feat/{codename}` |
| `major`  | Breaking change / refactor > 50% / breaking UX/API / demande explicite | X+1, Y=0, Z=0 | `feat/{codename}` |

- [ ] **Step 3 : Vérifier frontmatter**

Même check qu'en Task 1.1 Step 3.

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:create-branch/SKILL.md"
git commit -m "feat(.claude): add implement:create-branch skill"
```

---

## Task 1.3 — Créer `implement:brainstorm`

**Files:**

- Create: `.claude/skills/implement:brainstorm/SKILL.md`

**Spec section** : §7.4 du spec.

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:brainstorm"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:brainstorm
description: |
  Run feature brainstorming via superpowers:brainstorming, derive codename (user-confirmed), deduce SemVer bump type (user-validated), return {codename, title, type, bump, design_doc_path}.
  WHEN: Invoked by /implement:feature at feature start, after optional archive of previous feature.
  WHEN NOT: Already brainstormed; standalone use when not starting a new feature.
---
```

Sections :

1. `# Implement Brainstorm`
2. `## Usage` — invoqué par `implement:feature`, optionnellement avec argument titre feature.
3. `## Model Allocation` — **Opus main session** (c'est du brainstorming, cœur métier d'Opus).
4. `## Process` — 4 étapes conformément au spec §7.4 révisé :
   1. Invoquer `superpowers:brainstorming` avec contexte (CLAUDE.md + archives `docs/archive/features/*/DESIGN.md` si existent). **Intercepter le commit automatique** du design doc — le fichier doit rester non-committé à l'issue (car le déplacement + commit seront faits par `implement:create-branch` après création de la branche).
   2. Dériver codename auto depuis le titre (algorithme : kebab-case, ≤ 15 chars, enlever stopwords communs). Exemple : "Integrate YoutubeTrailerScraper" → `trailer` ou `yts-integrate`. Présenter 2-3 propositions au user et demander confirmation.
   3. Déduire type (bugfix/minor/major) selon critères §3. Présenter au user avec justification et calcul du nouveau numéro de version. User peut override.
   4. Retourner à `implement:feature` : `{codename, title, type, bump_from, bump_to, design_doc_path}`.
5. `## Error Handling` — matrice : user abandonne le brainstorm (skill retourne ABORTED, feature non créée), superpowers:brainstorming crash (rapport erreur, pas de codename généré).
6. `## Idempotence` — pas de side effect git (le design doc reste non-committé), relançable.
7. `## What this skill does NOT do` — ne crée pas de branche, ne déplace pas DESIGN.md (délégué à create-branch), ne génère pas de plan.

**Interception du commit superpowers** — note technique à inclure :

Le skill `superpowers:brainstorming` commit automatiquement le design doc à la fin. Options pour intercepter :

- Option A : laisser commit se faire sur main, puis reset soft le commit et reporter le fichier à `create-branch` pour re-commit sur la branche feature.
- Option B : hook git pre-commit temporaire qui laisse passer mais marque le commit comme "relocatable".
- **Option C (retenue)** : après retour de superpowers, vérifier si un commit a été fait sur main avec le design doc. Si oui → `git reset --soft HEAD~1` pour ré-émerger le fichier non committé, puis passer le chemin à `create-branch` qui se chargera du move + commit sur la branche.

Inclure le détail pratique (commandes git exactes) dans la section Process.

- [ ] **Step 3 : Vérifier frontmatter**

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:brainstorm/SKILL.md"
git commit -m "feat(.claude): add implement:brainstorm skill"
```

---

## Task 1.4 — Créer `implement:plan`

**Files:**

- Create: `.claude/skills/implement:plan/SKILL.md`

**Spec section** : §7.5 du spec.

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:plan"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:plan
description: |
  Generate per-phase implementation plan via superpowers:writing-plans. Output: docs/features/{codename}/plan/INDEX.md + phase-NN-*.md. Updates IMPLEMENTATION.md phases table.
  WHEN: Invoked by /implement:feature after create-branch, with DESIGN.md on the feature branch.
  WHEN NOT: DESIGN.md absent; reuse existing plan (request plan-regen instead).
---
```

Sections :

1. `# Implement Plan`
2. `## Usage` — invoqué par `implement:feature`, arguments : `{codename, design_doc_path}`.
3. `## Model Allocation` — **Sonnet subagent** (écriture de plans = ~1000-3000 tokens, Sonnet suffisant et moins cher qu'Opus).
4. `## Process` — 4 étapes conformément au spec §7.5 :
   1. Dispatch Sonnet subagent via `Agent(subagent_type="general-purpose", model="sonnet")` avec prompt : invoquer `superpowers:writing-plans` sur `docs/features/{codename}/DESIGN.md`, output dans `docs/features/{codename}/plan/`.
   2. Contraintes injectées dans le prompt Sonnet :
      - Chaque phase indépendamment complétable
      - Gates de cohérence explicites entre phases
      - Chaque sous-phase = 1 commit, scope = codename (`{type}({codename}): description`)
      - Chaque phase doit tenir dans une fenêtre de contexte d'un agent (indicatif : ≤ 150 lignes de plan par fichier phase)
      - Output files : `plan/INDEX.md` + `plan/phase-NN-{slug}.md` pour chaque phase
   3. Au retour du subagent : main session (Opus) vérifie que les fichiers existent et que INDEX.md contient bien un tableau des phases.
   4. Main session met à jour le tableau "Phases" dans IMPLEMENTATION.md (racine), commit `docs({codename}): add implementation plan`.
5. `## Error Handling` — matrice : plan existe déjà (demander écraser/reprendre), Sonnet ne produit pas de INDEX.md (fail loud, rapport), DESIGN.md absent (stop, erreur).
6. `## Idempotence` — détecte plan existant → demande confirmation.
7. `## What this skill does NOT do` — n'implémente aucune phase (c'est `implement:phase`), ne crée pas la branche.

- [ ] **Step 3 : Vérifier frontmatter**

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:plan/SKILL.md"
git commit -m "feat(.claude): add implement:plan skill"
```

---

## Gate cohérence Phase 1 → Phase 2

- [ ] **Step 1 : Vérifier présence des 4 skills**

```bash
ls ".claude/skills/implement:archive/SKILL.md" \
   ".claude/skills/implement:create-branch/SKILL.md" \
   ".claude/skills/implement:brainstorm/SKILL.md" \
   ".claude/skills/implement:plan/SKILL.md"
```

Expected : 4 fichiers présents.

- [ ] **Step 2 : Vérifier frontmatters**

Pour chaque skill, confirmer :

- `name` valide (slug `implement:X`)
- `description` multi-ligne avec WHEN / WHEN NOT
- Pas de tag YAML cassé

- [ ] **Step 3 : Lancer config-health-checker**

```
Invoquer l'agent config-health-checker via Agent tool.
```

Expected : aucune erreur sur les 4 nouvelles skills (warnings acceptables sur cross-refs vers `implement:feature`/`phase` pas encore créées).

- [ ] **Step 4 : Lancer skill-dependency-checker**

```
Invoquer l'agent skill-dependency-checker via Agent tool.
```

Expected : cross-refs vers `superpowers:brainstorming`, `superpowers:writing-plans` valides. Cross-refs vers `implement:feature` / `implement:phase` peuvent être flaggées → noter mais pas bloquant (seront résolues en P2/P3).

- [ ] **Step 5 : Milestone commit Phase 1**

```bash
git commit --allow-empty -m "chore(.claude): phase 1 gate — fondations (4 skills)"
```

- [ ] **Step 6 : Mettre à jour INDEX du master plan**

Éditer `docs/superpowers/plans/2026-04-22-implement-skills-refactor.md`, marquer Phase 1 `[x]`.

```bash
git add docs/superpowers/plans/2026-04-22-implement-skills-refactor.md
git commit -m "docs(plan): mark phase 1 done"
```
