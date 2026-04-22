# Phase 4 — Finalisation PR

**Objectif** : Créer les 2 skills qui ferment le cycle feature : `implement:feature-pr` (gate local + push + création PR + polling CI) et `implement:pr-review` (orchestration pr-review-toolkit + boucle fix + merge).

**Spec référence** : §7.9 (feature-pr), §7.10 (pr-review), §8.1 (invariant max 3 cycles).

**Skills créées** :

1. `implement:feature-pr`
2. `implement:pr-review`

**Prérequis** : Phase 3 complète — `implement:phase` existe et sera ré-invoquée par `implement:pr-review` en cas de phase de fix.

---

## Task 4.1 — Créer `implement:feature-pr`

**Files:**

- Create: `.claude/skills/implement:feature-pr/SKILL.md`

**Spec section** : §7.9 du spec.

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:feature-pr"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:feature-pr
description: |
  After last phase: run full local quality gate, push branch, create PR with generated title/body, poll CI to green. Hybrid: Opus gate, Sonnet PR composition, Haiku CI poll.
  WHEN: Invoked automatically by /implement:phase when all phases are [x].
  WHEN NOT: Phase still in progress or local gate not ready — finish phases first.
---
```

Sections :

1. `# Implement Feature PR`
2. `## Usage` — invoqué par `implement:phase`, arguments : `{codename, branch, merge_mode}`. Lit IMPLEMENTATION.md pour la description/phases.
3. `## Model Allocation` — **hybride** :
   - Gate local + push : inline Opus
   - Composition titre/body PR : Sonnet subagent
   - Polling CI : Haiku subagent
4. `## Process` — 3 phases conformément au spec §7.9 :

   ### Phase 1 — Gate local (inline Opus)

   ```bash
   ruff check .
   ruff format --check .
   python -m mypy {feature_modules}           # modules touchés sur la branche
   {test_command} tests/                      # suite complète
   ```

   Si ANY échoue → stop, rapport user, pas de push. Exit skill.

   ### Phase 2 — Push + création PR

   a. `git push -u origin {branch}`. Si rejet → stop (branch protection, concurrent push).

   b. Vérifier idempotence : lire IMPLEMENTATION.md. Si `**PR:**` contient une URL (pas placeholder `_(created after last phase)_`) → skip création, passer directement à Phase 3 polling CI.

   c. **Dispatch Sonnet subagent** pour composer titre + body :

   ```
   Prompt Sonnet:
   Compose a PR title and body for the completed feature.

   Inputs:
   - codename: {codename}
   - feature type: {type: major|minor|bugfix}
   - IMPLEMENTATION.md phases (completed): {list from IMPLEMENTATION.md}
   - DESIGN.md path: docs/features/{codename}/DESIGN.md
   - Version bump: {X.Y.Z} → {X'.Y'.Z'}

   Required output:
   1. Title (strict format): {type}({codename}): {description}
      where {description} = H1 title from DESIGN.md, max 70 chars total

   2. Body (markdown):
      ## Summary
      <1-3 bullet points from DESIGN.md introduction>

      ## Phases completed
      <bullet list of phases with their descriptions>

      ## Design
      See: docs/features/{codename}/DESIGN.md

      ## Version
      {X.Y.Z} → {X'.Y'.Z'}

      ## Test plan
      - [ ] CI passes
      - [ ] Manual verification: <to be filled by user if needed>

   Return TITLE and BODY as separate blocks, plain text.
   ```

   d. **Créer la PR via `/github-curl`** :

   ```bash
   SKILL_DIR=".claude/skills/github-curl"
   PR_JSON=$(bash "$SKILL_DIR/gh-api.sh" pr-create "$TITLE" "$BODY" "main")
   PR_URL=$(echo "$PR_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-url)
   PR_NUM=$(echo "$PR_JSON" | python3 "$SKILL_DIR/gh-parse.py" pr-number)
   ```

   e. **Mettre à jour IMPLEMENTATION.md** : remplacer placeholder `**PR:**` par `**PR:** {PR_URL}`. Commit : `docs({codename}): add PR link`.

   ### Phase 3 — Polling CI (Haiku subagent)

   Dispatch Haiku subagent :

   ```
   Prompt Haiku:
   Poll GitHub CI status for PR #{PR_NUM} every 30 seconds until all checks complete or timeout (20 min).

   Commands:
   - Check status: bash .claude/skills/github-curl/gh-api.sh pr-checks {PR_NUM}
   - Parse: python3 .claude/skills/github-curl/gh-parse.py checks-status

   Exit conditions:
   - All checks SUCCESS → return "CI_GREEN"
   - Any check FAILURE → return "CI_RED" + list of failed checks
   - Timeout 20 min → return "CI_TIMEOUT"

   Output schema:
   {"result": "CI_GREEN"|"CI_RED"|"CI_TIMEOUT", "failed_checks": [...]}
   ```

5. `## Output` — retour à `implement:phase` :
   - `CI_GREEN` → automatiquement invoquer `/implement:pr-review` (flux continu).
   - `CI_RED` → stop, rapport détaillé des checks échoués. User décide.
   - `CI_TIMEOUT` → stop, message user (reprendre manuellement une fois CI résolue).
   - Gate local échoue → stop, rapport des fichiers et erreurs.
6. `## Error Handling` — matrice : gate local échoue (stop avant push), push rejeté (stop, branch protection probable), PR existe déjà (idempotent, skip à CI poll), CI rouge (rapport), CI timeout (rapport).
7. `## Idempotence` — détecte PR existante via `**PR:**` dans IMPLEMENTATION.md, ne recrée pas. Re-run = re-poll CI uniquement.
8. `## What this skill does NOT do` — ne fait pas la review (c'est `implement:pr-review`), ne merge pas, ne modifie pas le code (auto-fix c'est la phase fix dans pr-review).

- [ ] **Step 3 : Vérifier frontmatter**

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:feature-pr/SKILL.md"
git commit -m "feat(.claude): add implement:feature-pr skill"
```

---

## Task 4.2 — Créer `implement:pr-review`

**Files:**

- Create: `.claude/skills/implement:pr-review/SKILL.md`

**Spec section** : §7.10 du spec.

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:pr-review"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:pr-review
description: |
  Run /pr-review-toolkit on the PR, filter reviews against DESIGN/plan, loop max 3 cycles, generate fix-phase and auto-invoke /implement:phase if needed. Final merge squash.
  WHEN: Invoked automatically by /implement:feature-pr once CI is green.
  WHEN NOT: PR not yet created, CI still running or red.
---
```

Sections :

1. `# Implement PR Review`
2. `## Usage` — invoqué par `implement:feature-pr`, arguments : `{codename, branch, pr_number, pr_url, merge_mode}`.
3. `## Model Allocation` — **Opus main session** (filtrage des retours vs design = jugement). Dispatch `/pr-review-toolkit:review-pr` (Sonnet interne au toolkit).
4. `## Process` — étapes conformément au spec §7.10 révisé :
   1. **Lire cycle courant** dans IMPLEMENTATION.md section "Review cycles". Premier cycle → initialiser à 1. Sinon incrémenter.
   2. **Lancer `/pr-review-toolkit:review-pr`** (ou `/pr-review-toolkit:start-review` selon préférence — à décider à la création). Les subagents Sonnet produisent des retours structurés.
   3. **Filtrage Opus** : pour chaque retour, évaluer pertinence contre `docs/features/{codename}/DESIGN.md` + plans :
      - Cohérent avec design → **retenu**
      - Hors scope design → **ignoré** (noter dans rapport cycle)
      - Contradiction design → **signaler au user** (peut nécessiter update DESIGN avant de continuer)
   4. **Classer retours retenus** en `critique | majeur | moyen | mineur`.
   5. **Décision** :
      - **Aucun retour critique/majeur/moyen** → fin de boucle, aller à étape 6 (merge).
      - **Retours critiques/majeurs/moyens ET cycle < 3** :
        a. Générer `docs/features/{codename}/plan/phase-XX-pr-fixes-cycle-{N}.md` (XX = numéro suivant le plus élevé dans le tableau Phases).
        b. **Ajouter une ligne** dans le tableau "Phases" de IMPLEMENTATION.md : `| XX | PR fixes cycle N | phase-XX-pr-fixes-cycle-{N}.md | [ ] |`.
        c. Commit : `docs({codename}): add PR fixes phase cycle {N}`.
        d. **Invoquer automatiquement `/implement:phase`** (flux continu). Au retour (la phase fix est committée + pushée + CI re-run par `implement:phase` → `implement:feature-pr` → CI green → re-invoke de `implement:pr-review`) → revenir à l'étape 1 (cycle +1).
      - **Cycle = 3 et retours toujours critiques** → **stop**, escalade user avec résumé structuré :

        ```
        3 review cycles completed. Remaining critical/major/medium findings:

        [list filtered findings]

        Options:
        1. Manual fix and push → then re-run /implement:pr-review
        2. Update DESIGN.md if findings indicate design revision needed
        3. Close PR if the approach is flawed
        ```

   6. **Enregistrer cycle** dans IMPLEMENTATION.md section "Review cycles" (résumé : retours reçus, retenus, ignorés, fix phase créée ou non).

   ### Merge final (étape 6, après exit boucle)
   - Mode `auto` → `/github-curl pr-merge {PR_NUM} squash` avec message = titre de la PR (lu depuis GitHub).
   - Mode `manual` → stop, message user : "Review clean. Merge quand tu veux (squash)."

5. `## Error Handling` — matrice : cycle 3 + retours critiques (escalade user), merge API échoue (rapport, user merge manuel), aucun retour de pr-review-toolkit (succès trivial, passer au merge).
6. `## Idempotence` — cycle courant enregistré dans IMPLEMENTATION.md. Si relancé après crash, reprend au cycle courant (ne re-run pas les checks déjà passés).
7. `## What this skill does NOT do` — ne pousse pas le code des fixes (c'est `implement:phase` qui commit, `implement:feature-pr` qui push), ne remplace pas l'humain pour les décisions design (escalade si contradiction design détectée).

**Note importante sur la boucle fix-push-review** — à inclure en sous-section :

La boucle entière se déroule ainsi :

```
implement:pr-review (cycle N)
  ├── pr-review-toolkit → retours
  ├── filtrage Opus
  └── si fix requis :
       ├── créer phase-XX-pr-fixes-cycle-N.md
       ├── ajouter à IMPLEMENTATION.md
       └── invoquer /implement:phase
            ├── exécute les fixes (sub-phases)
            ├── milestone commit phase fix
            └── invoque /implement:feature-pr (car dernière phase restée [x])
                 ├── gate local
                 ├── push (nouveaux commits sur la branche)
                 └── poll CI
                      └── si green → invoque /implement:pr-review (cycle N+1)
```

La récursion termine via :

- sortie normale (cycle < 3 et aucun retour critique)
- plafond atteint (cycle = 3 et retours persistants → escalade)

- [ ] **Step 3 : Vérifier frontmatter**

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:pr-review/SKILL.md"
git commit -m "feat(.claude): add implement:pr-review skill"
```

---

## Gate cohérence Phase 4 → Phase 5

- [ ] **Step 1 : Vérifier présence**

```bash
ls ".claude/skills/implement:feature-pr/SKILL.md" \
   ".claude/skills/implement:pr-review/SKILL.md"
```

- [ ] **Step 2 : Cross-refs**

`implement:feature-pr` doit référencer :

- `github-curl` (via `gh-api.sh`, `gh-parse.py`)
- `/implement:pr-review` (appel final si CI green)

`implement:pr-review` doit référencer :

- `/pr-review-toolkit:*` (review-pr ou start-review)
- `/implement:phase` (auto-invoke cycle fix)
- `github-curl` (merge final)

```bash
grep -E '/(implement:(phase|pr-review)|pr-review-toolkit|github-curl)' \
     ".claude/skills/implement:feature-pr/SKILL.md" \
     ".claude/skills/implement:pr-review/SKILL.md"
```

- [ ] **Step 3 : Vérifier mention dispatch Haiku**

`implement:feature-pr` doit mentionner le dispatch Haiku pour le polling CI.

```bash
grep -i 'haiku' ".claude/skills/implement:feature-pr/SKILL.md"
```

Expected : au moins 2 mentions (Model Allocation + Process Phase 3).

- [ ] **Step 4 : Vérifier plafond 3 cycles**

```bash
grep -E 'cycle.*3|3.*cycle|max.*3' ".claude/skills/implement:pr-review/SKILL.md"
```

Expected : mention explicite du plafond.

- [ ] **Step 5 : Lancer skill-dependency-checker**

Expected : toutes cross-refs résolues (feature-pr → pr-review, pr-review → phase + pr-review-toolkit + github-curl).

- [ ] **Step 6 : Milestone commit Phase 4**

```bash
git commit --allow-empty -m "chore(.claude): phase 4 gate — PR finalization (2 skills)"
```

- [ ] **Step 7 : Mettre à jour INDEX du master plan**

```bash
git add docs/superpowers/plans/2026-04-22-implement-skills-refactor.md
git commit -m "docs(plan): mark phase 4 done"
```
