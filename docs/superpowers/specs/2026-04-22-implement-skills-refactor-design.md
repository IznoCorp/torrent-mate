# Implement Skills Refactor — Design Spec

**Date**: 2026-04-22
**Status**: Draft (awaiting user review)
**Scope**: Refonte des skills `.claude/skills/implement-*` et `archive-version` / `model-version` vers un modèle orienté feature avec préfixe `implement:*`.

## 1. Contexte et motivation

Le workflow actuel de `personalscraper` est organisé autour de **versions** numérotées (v0 → v15). Chaque nouvelle version est un incrément majeur du logiciel, conçue puis implémentée par `model-version` → `implement-version` → `implement-phase` → `archive-version`.

Limites observées :

- Le numéro de version ne reflète pas la nature du changement (bugfix vs feature majeure vs breaking change).
- Le concept "version" force à bundler du travail hétérogène sous un même numéro (une "v14" peut mélanger library maintenance, encoding optimization, et cleanup).
- Pas de lien naturel avec SemVer : impossible d'évoluer `major.minor.bugfix` en fonction du contenu réel.
- Nom de branche / scope commit / PR title dérivent d'un numéro plutôt que d'un code signifiant.

**Objectif** : passer à un modèle **feature-oriented** où chaque unité de travail porte un codename lisible (`trailer`, `library-maint`, `tmdb-keywords`), et où la version logicielle évolue en SemVer selon le type réel de la feature.

## 2. Principes directeurs

1. **Codename > numéro de version** pour l'identification métier d'une feature.
2. **Version logicielle en SemVer** (`major.minor.bugfix`), bumpée à la création de la branche selon le type.
3. **Séquentiel strict** pour l'instant : une seule feature active à la fois (parallélisme futur hors scope).
4. **Main session (Opus) orchestre**, subagents exécutent. Allocation du modèle la moins chère capable sans risque.
5. **Granularité sous-phase** : 1 dispatch Sonnet = 1 sous-phase = 1 commit minimum. Résilience aux troncatures.
6. **Vérification continue** : `implement:check` entre chaque sous-phase, pas seulement en fin de phase.
7. **Flux continu** : aucune pause entre sous-phases/phases sauf erreur bloquante.
8. **Idempotence** : chaque skill relançable sans dégât.

## 3. Règles de bump de version

| Type     | Critère                                                                                                                                                       | Branche           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| `major`  | Breaking change (nouvelle fonctionnalité modifiant le comportement existant), refactor touchant > 50% de la codebase, breaking API/UX, demande explicite user | `feat/{codename}` |
| `minor`  | Ajout d'une nouvelle fonctionnalité sans casser l'existant                                                                                                    | `feat/{codename}` |
| `bugfix` | Correction d'un bug d'une feature existante                                                                                                                   | `fix/{codename}`  |

Le bump est appliqué à l'étape `implement:create-branch`, avant le premier commit applicatif, et inscrit dans `VERSION` + `pyproject.toml` (si Python) via un commit dédié : `chore({codename}): bump version to {X.Y.Z}`.

## 4. Architecture des skills

### 4.1 Liste finale (10 skills)

| Skill                     | Rôle                                                                                         | Modèle                          |
| ------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------- |
| `implement:feature`       | Orchestrateur entrée nouvelle feature (enchaîne archive → brainstorm → create-branch → plan) | Opus (main)                     |
| `implement:archive`       | Archivage de la feature précédente (pre-flight, git mv, commit)                              | Haiku subagent                  |
| `implement:create-branch` | Bump version, crée branche, initialise IMPLEMENTATION.md                                     | Inline Opus                     |
| `implement:brainstorm`    | Wrap `superpowers:brainstorming` ; produit DESIGN.md et dérive codename + type               | Opus (main)                     |
| `implement:plan`          | Wrap `superpowers:writing-plans` ; produit INDEX.md + phase-NN-\*.md                         | Sonnet subagent                 |
| `implement:phase`         | Orchestrateur phase : boucle sur sous-phases, garant de la cohérence                         | Opus (main)                     |
| `implement:sub-phase`     | Dispatch Sonnet pour UNE sous-phase, commit inclus                                           | Sonnet subagent                 |
| `implement:check`         | Vérification cohérence design/plan + quality gate après sous-phase                           | Opus (main)                     |
| `implement:feature-pr`    | Gate local, push, création PR, polling CI                                                    | Opus + Sonnet + Haiku (hybride) |
| `implement:pr-review`     | Orchestration `/pr-review-toolkit`, filtrage retours, boucle fix (max 3)                     | Opus (main)                     |

### 4.2 Arbre d'appel

```
implement:feature                            [entry point nouvelle feature]
├── implement:archive                        [si feature précédente non archivée]
├── implement:brainstorm                     [wrap superpowers:brainstorming]
│   └── dérive codename + type + bump
├── implement:create-branch                  [bump VERSION, crée feat/{codename}]
└── implement:plan                           [wrap superpowers:writing-plans]

implement:phase                              [entry point par phase, flux continu]
├── POUR chaque sous-phase:
│   ├── implement:sub-phase                  [1 Sonnet dispatch, 1 commit]
│   └── implement:check                      [vérif cohérence + quality gate]
├── milestone commit "chore({codename}): phase {N} gate"
└── SI dernière phase: implement:feature-pr
                       └── SI CI verte: implement:pr-review
                           ├── /pr-review-toolkit (Sonnet)
                           ├── filtrage Opus vs DESIGN/plan
                           ├── SI retours critiques + cycle < 3:
                           │   └── phase-XX-pr-fixes.md → loop implement:phase
                           └── SINON: merge squash (manual ou auto selon config)
```

## 5. Politique d'allocation des modèles

**Principe** : chaque action choisit le modèle le moins cher capable de la faire sans risque.

| Type de travail                         | Modèle | Lieu           |
| --------------------------------------- | ------ | -------------- |
| Orchestration globale                   | Opus   | Main session   |
| Brainstorming, conception, design       | Opus   | Main session   |
| Vérification cohérence design/plan/code | Opus   | Main session   |
| Filtrage pertinence retours PR          | Opus   | Main session   |
| Écriture de code applicatif             | Sonnet | Agent dispatch |
| Écriture de plans                       | Sonnet | Agent dispatch |
| Auto-fix après échec quality gate       | Sonnet | Agent dispatch |
| Code review (`/pr-review-toolkit`)      | Sonnet | Agent dispatch |
| Composition titre/description PR        | Sonnet | Agent dispatch |
| Migration de fichiers mécanique         | Haiku  | Agent dispatch |
| Parsing structuré (SHA, phase status)   | Haiku  | Agent dispatch |
| Polling CI                              | Haiku  | Agent dispatch |

**Règle de dispatch** : si le travail tient en ≤ 5 appels bash sans jugement, il reste **inline dans la main session** — le coût d'un dispatch Haiku dépasserait le bénéfice.

## 6. Conventions de nommage et arborescence

### 6.1 Codename

- Format : `kebab-case`, 2-15 caractères.
- Dérivé par `implement:brainstorm` depuis le titre de la feature.
- Confirmé par l'utilisateur avant `create-branch`.
- Exemples : `trailer`, `library-maint`, `tmdb-keywords`, `config-driven`.

### 6.2 Branche git

- Feature `major` ou `minor` → `feat/{codename}`
- Feature `bugfix` → `fix/{codename}`

### 6.3 Commits

- Format : **Conventional Commits** avec scope = codename.
- Commits applicatifs (par sous-phase, écrits par Sonnet) : `{type}({codename}): description`.
- Milestone commits (par phase, écrits par main session) : `chore({codename}): phase {N} gate — {phase_name}`.
- Commit de bump version : `chore({codename}): bump version to {X.Y.Z}`.
- Aucun préfixe `v{N}` dans les commits. Aucune attribution IA.

### 6.4 PR

- Titre : `{type}({codename}): {description}` (ex : `feat(trailer): Integrate YoutubeTrailerScraper to personalScraper`).
- Merge toujours en **squash** (message = titre de la PR).
- Stratégie `manual` ou `auto` choisie par l'utilisateur à l'étape `implement:feature`.

### 6.5 Arborescence des docs

```
<project_root>/
├── IMPLEMENTATION.md                        # Feature courante uniquement
├── VERSION                                  # SemVer, bumpé à create-branch
├── pyproject.toml                           # version synchro
└── docs/
    ├── features/
    │   └── {codename}/                      # Feature active
    │       ├── DESIGN.md
    │       └── plan/
    │           ├── INDEX.md
    │           ├── phase-01-{slug}.md
    │           └── ...
    └── archive/
        └── features/
            └── {codename_archived}/         # Features archivées
                ├── IMPLEMENTATION.md
                ├── DESIGN.md
                └── plan/...
```

**Note** : les archives historiques `docs/archive/v0/` à `docs/archive/v15/` restent telles quelles. Seules les nouvelles features adoptent `docs/archive/features/{codename}/`.

### 6.6 Format IMPLEMENTATION.md

```markdown
# Implementation Progress — {codename}

> For Claude: read this file at session start. Current feature tracker.

**Feature**: {Full title} ({type: major|minor|bugfix})
**Version bump**: {X.Y.Z} → {X'.Y'.Z'}
**Branch**: feat/{codename} | fix/{codename}
**PR merge**: manual | auto
**PR**: _(created after last phase)_
**Design**: docs/features/{codename}/DESIGN.md
**Master plan**: docs/features/{codename}/plan/INDEX.md

## Phases

| #   | Phase | File           | Status |
| --- | ----- | -------------- | ------ |
| 1   | ...   | phase-01-...md | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

...
```

## 7. Flux détaillé par skill

### 7.1 `implement:feature`

**Rôle** : orchestrateur d'entrée pour une nouvelle feature.

**Usage** : `/implement:feature` (auto-détecte contexte) ou `/implement:feature "titre de la feature"`.

**Étapes** :

1. Détecter l'état de la feature précédente :
   - **Pas de `IMPLEMENTATION.md` à la racine** → pas de feature précédente, sauter à l'étape 2.
   - **`IMPLEMENTATION.md` existe, toutes phases `[x]`, PR mergée** → lire le codename depuis le header, invoquer `implement:archive`, puis étape 2.
   - **`IMPLEMENTATION.md` existe, feature incomplète** → **STOP**, message utilisateur : "Feature précédente `{codename}` incomplète. Terminer via `/implement:phase` avant de démarrer une nouvelle feature."
2. Invoquer `implement:brainstorm` → retourne `{codename, title, type, bump}`.
3. Demander à l'utilisateur : stratégie de merge (`manual` ou `auto`).
4. Invoquer `implement:create-branch` avec les arguments.
5. Invoquer `implement:plan` pour générer les fichiers de plan.
6. Rapport final : prêt pour `/implement:phase`.

### 7.2 `implement:archive`

**Rôle** : archiver la feature précédente avec pre-flight strict.

**Pre-flight (tout doit passer, sinon stop)** :

- Repo propre (`git status --porcelain` vide).
- Tests verts.
- Toutes les phases de IMPLEMENTATION.md courant = `[x]` ou `✅`.
- PR **présente et mergée**. `implement:archive` ne merge jamais — le merge est la responsabilité exclusive de `implement:pr-review` (cf. §7.10). Si la PR n'est pas mergée, stop avec message explicite : "PR non mergée ; terminer le cycle pr-review ou merger manuellement avant d'archiver."

**Actions** :

- Dispatch Haiku subagent pour la partie mécanique :
  - `mkdir -p docs/archive/features/{codename}/`
  - `git mv IMPLEMENTATION.md docs/archive/features/{codename}/IMPLEMENTATION.md`
  - `git mv docs/features/{codename}/* docs/archive/features/{codename}/`
  - Créer nouveau IMPLEMENTATION.md vierge à la racine
  - Mettre à jour CLAUDE.md racine projet (section "Current Feature" — cf. §10.1)
  - Commit : `milestone: archive {codename}`
- Optionnel : supprimer la branche locale.

### 7.3 `implement:create-branch`

**Rôle** : bump version, créer branche, initialiser IMPLEMENTATION.md.

**Inline Opus** (pas de dispatch) :

1. Lire VERSION actuelle (ou créer `0.1.0` si absent).
2. Calculer nouveau numéro selon type (major/minor/bugfix).
3. `git checkout -b feat/{codename}` (ou `fix/{codename}`).
4. **Déplacer** le design doc depuis `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` vers `docs/features/{codename}/DESIGN.md` (création du dossier), via `mv` simple (le fichier n'est pas encore git-tracked à ce stade — cf. §7.4 étape 1).
5. Écrire VERSION + `pyproject.toml` (si présent).
6. Remplir header IMPLEMENTATION.md (codename, branch, merge strategy, version bump, chemin DESIGN).
7. Commit unique : `chore({codename}): bump version to {X.Y.Z}` — inclut VERSION, pyproject.toml, DESIGN.md, IMPLEMENTATION.md.

**Gestion conflit** : si branche existe déjà → demander reprendre ou renommer.

### 7.4 `implement:brainstorm`

**Rôle** : brainstorming conception via `superpowers:brainstorming`.

**Opus main session** :

1. Invoquer `superpowers:brainstorming` avec contexte projet (CLAUDE.md, archives DESIGN). Le design doc initial est écrit **non committé** à l'emplacement par défaut de superpowers (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) — superpowers commitera ; on intercepte avant le commit pour éviter de polluer main.
2. Une fois le brainstorm terminé, dériver `codename` depuis le titre (proposition auto-générée, kebab-case, ≤ 15 chars, **confirmée par user**).
3. Déduire `type` (major/minor/bugfix) depuis les décisions du brainstorm selon les critères de la section 3, **le présenter au user pour validation** (avec calcul du nouveau numéro de version). User peut override.
4. Retourner `{codename, title, type, bump, design_doc_path}` à `implement:feature` **sans déplacer ni committer** le design doc — le déplacement + commit sur la branche feature est délégué à `implement:create-branch` (cf. §7.3) une fois la branche créée.

### 7.5 `implement:plan`

**Rôle** : générer les fichiers de plan par phase.

**Sonnet subagent** :

1. Invoquer `superpowers:writing-plans` avec le DESIGN.md.
2. Output attendu : `docs/features/{codename}/plan/INDEX.md` + `phase-NN-{slug}.md` pour chaque phase.
3. Contraintes injectées :
   - Chaque phase indépendamment complétable
   - Gates de cohérence entre phases explicites
   - Chaque sous-phase = 1 commit, scope = codename
   - Chaque phase doit tenir dans une fenêtre de contexte d'un agent
4. Main session met à jour le tableau "Phases" dans IMPLEMENTATION.md.

### 7.6 `implement:phase`

**Rôle** : orchestrer l'exécution d'une phase, garant de la cohérence.

**Opus main session**, flux continu MANDATORY (jamais de pause).

**Étapes** :

1. Lire IMPLEMENTATION.md → identifier la prochaine phase `[ ]`.
2. Charger `docs/features/{codename}/plan/phase-NN-*.md`.
3. Parser la liste des sous-phases.
4. **Boucle** sur chaque sous-phase :
   a. Capturer baseline SHA.
   b. Invoquer `implement:sub-phase` avec (phase, sous-phase, contexte).
   c. Vérifier rapport Sonnet (schéma, truncation, commits faits).
   d. Invoquer `implement:check` pour vérifier cohérence design/plan.
   e. Si échec → **auto-fix** : main session dispatch un Agent Sonnet dédié (pas une skill nommée — dispatch direct via l'outil `Agent` avec prompt "fix-only mode" : scope = fichiers touchés par la sous-phase, erreurs verbatim de la quality gate). Max 2 tentatives. Sinon fail loud.
5. Milestone commit : `chore({codename}): phase {N} gate — {phase_name}`.
6. Marquer phase `[x]` dans IMPLEMENTATION.md, commit.
7. **Si dernière phase** → invoquer `implement:feature-pr`.
8. **Sinon** → boucle sur la phase suivante (pas de pause).

**Cas d'arrêt** : erreur bloquante nécessitant décision user, ou context ≥ 80%.

### 7.7 `implement:sub-phase`

**Rôle** : exécuter UNE sous-phase via dispatch Sonnet.

**Sonnet subagent** (dispatch par main session) :

- Prompt contient :
  - Répertoire + branche
  - Baseline SHA
  - CHEMIN UNIQUE vers le fichier de phase (pas d'autres)
  - Numéro de la sous-phase cible + scope explicite
  - Instructions : `STOP à la fin de la sous-phase. Ne pas lire phase-{N+1}. Ne pas exécuter d'autres sous-phases.`
  - Conventions projet (Conventional Commits avec scope codename, pas d'IA, docstrings Google, mypy strict)
  - Quality gates à exécuter AVANT chaque commit
  - Schéma de rapport à retourner

**Contraintes Sonnet** :

- DO NOT push
- DO NOT modifier IMPLEMENTATION.md
- DO NOT toucher fichiers hors scope (sauf import break fixable)
- Commit immédiatement après quality gate vert, ne pas batcher

**Rapport retourné** : schéma fixe `Status / Sub-phase attempted / Commits / Quality gates / Files changed / Deviations / Concerns`.

### 7.8 `implement:check`

**Rôle** : vérifier cohérence design/plan/code après une sous-phase.

**Opus main session** (non délégable).

**Vérifications** (6 checks, ordre impératif) :

1. **Truncation detection** : sections attendues présentes dans le rapport Sonnet.
2. **Git range audit** : `git log baseline..HEAD` correspond au rapport (SHA cohérents).
3. **Plan compliance** : chaque sous-phase du plan a un commit associé.
4. **Full quality gate independent re-run** : ruff check + ruff format + mypy + pytest sur le scope. Ne jamais faire confiance au rapport Sonnet.
5. **Scope drift detection** : `git log --name-only baseline..HEAD` ne contient pas de fichiers hors plan (tolérance : tests, docs, IMPLEMENTATION.md).
6. **Design coherence check** : lire DESIGN.md + code modifié → vérifier alignement (interfaces, modules, data flow). Si déviation → fail loud, user décide.

**Sortie** : `OK`, `AUTO_FIX_NEEDED {list d'erreurs}`, ou `FAIL_LOUD {diagnostic}`.

### 7.9 `implement:feature-pr`

**Rôle** : gate local, push, création PR, polling CI.

**Phase 1 — Gate local (inline Opus)** :

- `ruff check` + `ruff format --check` sur toute la codebase
- `mypy` sur les modules touchés par la feature
- Suite de tests complète (`pytest tests/`)
- Si échec → stop, rapport, pas de push.

**Phase 2 — Push + création PR** :

- `git push -u origin {branch}`
- Vérifier si PR existe déjà (idempotent via `**PR:**` dans IMPLEMENTATION.md).
- Dispatch **Sonnet subagent** pour composer titre + body :
  - Titre : `{type}({codename}): {description}` (description depuis DESIGN.md H1)
  - Body : résumé des phases complétées + liens DESIGN.md et plans + changelog bump version
- Créer PR via `/github-curl`.
- Mettre à jour IMPLEMENTATION.md avec URL PR, commit `docs({codename}): add PR link`.

**Phase 3 — Polling CI** :

- Dispatch **Haiku subagent** pour poller `/github-curl pr-checks` toutes les 30s jusqu'à résolution (succès ou échec).
- Timeout : 20 min → rapport user.
- Si CI verte → enchaîner `implement:pr-review`.
- Si CI rouge → stop, rapport détaillé.

### 7.10 `implement:pr-review`

**Rôle** : orchestrer review PR, filtrer retours pertinents, boucler correctifs.

**Opus main session** (filtrage et jugement).

**Étapes** :

1. Lire cycle actuel dans IMPLEMENTATION.md section "Review cycles". Si premier cycle, initialiser.
2. Lancer `/pr-review-toolkit:start-review` (ou équivalent) → subagents Sonnet produisent retours.
3. **Filtrage Opus** : pour chaque retour, évaluer pertinence contre DESIGN.md + plans :
   - Cohérent avec design → retenu
   - Hors scope design → ignoré (noter dans rapport cycle)
   - Contradiction design → signaler au user (peut nécessiter update DESIGN)
4. Classer retours retenus en `critique | majeur | moyen | mineur`.
5. **Décision** :
   - Aucun retour `critique/majeur/moyen` → fin de boucle, déclencher merge squash selon config.
   - Retours critiques/majeurs/moyens ET cycle < 3 :
     a. Générer `docs/features/{codename}/plan/phase-XX-pr-fixes-cycle-{N}.md` où `XX` = numéro suivant le plus élevé dans le tableau Phases.
     b. **Ajouter une ligne dans le tableau "Phases" de IMPLEMENTATION.md** : `| XX | PR fixes cycle N | phase-XX-pr-fixes-cycle-{N}.md | [ ] |`.
     c. Commit : `docs({codename}): add PR fixes phase cycle {N}`.
     d. **Invoquer automatiquement `implement:phase`** (flux continu, pas de pause user). Au retour : reprendre à l'étape 5 du présent skill pour évaluer à nouveau (nouveau push → nouvelle CI → nouveau cycle review).
   - Cycle = 3 et retours toujours critiques → stop, escalade user avec résumé.
6. Enregistrer cycle dans IMPLEMENTATION.md section "Review cycles".

**Merge final** :

- Mode `auto` → `/github-curl pr-merge {PR} squash` avec message = titre PR.
- Mode `manual` → stop, message user ("review clean, merge quand tu veux").

## 8. Gestion d'erreurs

### 8.1 Invariants critiques (jamais enfreints)

1. Main session ne commite JAMAIS du code applicatif (seulement milestones + IMPLEMENTATION.md).
2. Jamais de `git commit --amend` ni `git push --force` sauf instruction explicite user.
3. Jamais d'attribution IA dans les commits/code (hook `block_ai_attribution.py`).
4. Un dispatch Sonnet = une sous-phase (pas de batching).
5. Chaque sous-phase = au moins 1 commit.
6. Main session re-run la quality gate après chaque retour subagent (ne jamais faire confiance au rapport).
7. Cohérence vérifiée entre sous-phases, pas seulement en fin de phase.
8. Max 2 tentatives auto-fix par sous-phase, max 3 cycles review-fix.

### 8.2 Matrice d'échecs

| Skill                     | Situation                   | Comportement                                                                                                                                                                                 |
| ------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `implement:archive`       | Repo sale                   | Stop, user commit/stash                                                                                                                                                                      |
| `implement:archive`       | Tests rouges                | Stop, fix d'abord                                                                                                                                                                            |
| `implement:archive`       | Phase non-DONE              | Stop, lister incomplètes                                                                                                                                                                     |
| `implement:archive`       | PR non mergée (mode manual) | Stop, user merge d'abord                                                                                                                                                                     |
| `implement:archive`       | Archive dir existe déjà     | Stop, refuse écraser                                                                                                                                                                         |
| `implement:create-branch` | Branche existe              | Demander reprendre/renommer                                                                                                                                                                  |
| `implement:create-branch` | VERSION absent              | Créer `0.1.0`, continuer                                                                                                                                                                     |
| `implement:plan`          | Plan déjà présent           | Demander écraser/reprendre                                                                                                                                                                   |
| `implement:sub-phase`     | Sonnet BLOCKED              | Stop phase, rapport user                                                                                                                                                                     |
| `implement:sub-phase`     | Rapport tronqué             | Check git state : `≥ 1 commit + clean` → conserver, rapport user pour partie manquante ; `0 commit + dirty` → `git checkout --` puis retry (tentative 2) ; `0 commit + clean` → retry direct |
| `implement:sub-phase`     | Quality gate échoue         | Auto-fix (max 2) → sinon fail loud                                                                                                                                                           |
| `implement:check`         | Scope drift                 | Fail loud, user décide (pas d'auto-fix)                                                                                                                                                      |
| `implement:check`         | Déviation design            | Fail loud, user décide                                                                                                                                                                       |
| `implement:feature-pr`    | Gate local échoue           | Stop avant push                                                                                                                                                                              |
| `implement:feature-pr`    | Push rejeté                 | Stop, message (branch protection, etc.)                                                                                                                                                      |
| `implement:feature-pr`    | CI rouge                    | Rapport user, stop cycle pr-review                                                                                                                                                           |
| `implement:pr-review`     | Cycle 3 + retours critiques | Escalade user avec résumé                                                                                                                                                                    |
| `implement:pr-review`     | Merge API échoue            | Rapport, user merge manuel                                                                                                                                                                   |
| Toute skill               | Context ≥ 80%               | Compact ou split session                                                                                                                                                                     |

### 8.3 Idempotence

Chaque skill détecte l'état existant et ne ré-exécute pas silencieusement une action déjà faite :

- `implement:archive` : `docs/archive/features/{codename}/` existe → refuse.
- `implement:create-branch` : branche existe → demande confirmation.
- `implement:plan` : plan existe → demande confirmation.
- `implement:phase` : lit état depuis IMPLEMENTATION.md + git, reprend à la phase `[ ]` suivante.
- `implement:feature-pr` : PR existe (via `**PR:**`) → skip création, vérifie seulement CI.
- `implement:pr-review` : enregistre cycle courant, reprend au bon cycle.

### 8.4 Fail-loud protocol uniforme

À chaque échec non-récupérable :

1. Bloc diagnostic écrit : attendu, observé, commits faits, actions conseillées.
2. Aucune modification automatique de l'historique git.
3. Stop de la skill courante.
4. L'utilisateur reprend manuellement.

## 9. Validation du refactor

### 9.1 Inspection statique

- Lancer `config-health-checker` et `skill-dependency-checker` avant et après le refactor.
- Grep exhaustif des anciennes références (`implement-phase`, `implement-version`, `archive-version`, `model-version`, `plan:execute-next-phase`, `plan:end-phase`, `plan:check-execution`) dans `.claude/`, `CLAUDE.md`, `docs/`, hooks. Zéro orphelin.

### 9.2 Checklist frontmatter

Pour chaque nouvelle skill :

- `name` = nom dossier
- `description` ≤ 200 chars, verbe initial
- Clauses `WHEN` / `WHEN NOT`
- Cross-refs pointent vers skills existantes
- Section "Model allocation" mentionnant Opus/Sonnet/Haiku

### 9.3 Smoke test feature pilote

Exécuter le flux complet sur une feature triviale et jetable de `personalscraper` (ex : ajout flag `--dry-run` à une commande). Critères :

- Parcours bout-en-bout sans intervention hors points interactifs prévus (codename confirm, merge strategy).
- IMPLEMENTATION.md à jour après chaque sous-phase.
- Historique git Conventional Commits, scope = codename, pas de `v{N}`.
- Zéro référence AI dans les commits.
- Version bumpée correctement.

### 9.4 Rollback

- Refactor dans un commit unique → `git revert` restaure.
- Feature pilote sur branche isolée → supprimer branche + dossier `docs/features/{pilote}/`.

### 9.5 Documentation post-refactor

- Mettre à jour `CLAUDE.md` racine projet (section "Implementation Workflow").
- Mettre à jour `.claude/CLAUDE.md` (doc config).
- Archiver ancienne doc si trace souhaitée.

## 10. Scope final

### 10.1 Dans le scope

- Création des 10 skills `implement:*`
- Suppression des 4 anciennes (`implement-phase`, `implement-version`, `archive-version`, `model-version`)
- Évaluation des skills `plan:execute-next-phase`, `plan:end-phase`, `plan:check-execution` : **retrait** si aucune référence externe à `.claude/` et recouvrement fonctionnel confirmé avec le nouveau flux ; **migration** sinon (renommage en `implement:*` équivalent ou conservation avec note de déprécation).
- Mise à jour `CLAUDE.md` racine projet :
  - Renommer section `## Current Version` → `## Current Feature`
  - Remplacer contenu (archive v14/v15 historique → codename courant + chemins `docs/features/{codename}/`)
  - Section "Implementation Workflow" reflétant les 10 nouvelles skills
- Mise à jour `.claude/CLAUDE.md` (doc config) : liste des skills `implement:*`, politique modèles, règles SemVer
- Grep + correction de toutes références aux anciennes skills
- Smoke test pilote

### 10.2 Hors scope

- Re-migration des archives v0-v15 (restent en `docs/archive/v{N}/`)
- Système de workspaces parallèles (futur)
- Auto-suggestion LLM de codename
- Modification code `personalscraper` en dehors de la feature pilote
- Refactor des skills `pr-review-toolkit:*`

## 11. Plan d'écriture (ordre recommandé)

**Batch 1 — Fondations indépendantes** (parallélisables) :

1. `implement:archive`
2. `implement:create-branch`
3. `implement:brainstorm`
4. `implement:plan`

**Batch 2 — Orchestrateur feature** : 5. `implement:feature`

**Batch 3 — Exécution de phase** : 6. `implement:sub-phase` 7. `implement:check` 8. `implement:phase`

**Batch 4 — Finalisation PR** : 9. `implement:feature-pr` 10. `implement:pr-review`

**Batch 5 — Nettoyage** :

- Suppression anciennes skills
- Mise à jour CLAUDE.md × 2
- Run health-checkers
- Smoke test pilote

## 12. Livrables

- 10 fichiers `.claude/skills/implement:{skill}/SKILL.md`
- 4 fichiers supprimés (anciennes skills)
- 2 fichiers docs mis à jour (CLAUDE.md × 2)
- 1 spec (ce document)
- 1 plan d'implémentation (généré par `superpowers:writing-plans` après validation du spec)
