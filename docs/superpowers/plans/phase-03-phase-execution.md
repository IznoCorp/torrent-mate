# Phase 3 — Exécution de phase

**Objectif** : Créer les 3 skills qui gèrent l'exécution d'une phase du plan d'implémentation : `implement:sub-phase` (1 dispatch Sonnet), `implement:check` (vérification cohérence Opus), `implement:phase` (orchestrateur qui boucle sur les sous-phases).

**Spec référence** : §7.6 (phase), §7.7 (sub-phase), §7.8 (check), §8.1 (invariants), §8.2 (matrice d'échecs).

**Skills créées** :

1. `implement:sub-phase`
2. `implement:check`
3. `implement:phase`

**Ordre recommandé** : sub-phase et check sont indépendants, phase dépend des deux. Écrire sub-phase + check avant phase.

---

## Task 3.1 — Créer `implement:sub-phase`

**Files:**

- Create: `.claude/skills/implement:sub-phase/SKILL.md`

**Spec section** : §7.7 du spec.

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:sub-phase"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:sub-phase
description: |
  Dispatch a Sonnet subagent to execute ONE sub-phase (scope-bounded) and commit. Returns structured report for main-session verification.
  WHEN: Invoked by /implement:phase per sub-phase. One dispatch = one sub-phase = one commit minimum.
  WHEN NOT: Executing multiple sub-phases in a row (that's the phase orchestrator's job).
---
```

Sections :

1. `# Implement Sub-Phase`
2. `## Usage` — invoqué par `implement:phase`, arguments : `{phase_file_path, sub_phase_number, baseline_sha, codename, branch}`.
3. `## Model Allocation` — **Sonnet subagent** via `Agent(subagent_type="general-purpose", model="sonnet")`.
4. `## Process` — 3 étapes :
   1. **Construire le prompt Sonnet** (template ci-dessous).
   2. **Dispatcher** via `Agent(...)`.
   3. **Retourner le rapport** brut à `implement:phase` (qui fera la vérification via `implement:check`).
5. `## Sonnet Prompt Template` — section dédiée montrant la structure exacte du prompt :

```
WORKING DIRECTORY: {repo_root}
BRANCH: {branch}
BASELINE SHA: {baseline_sha}
PHASE FILE: {phase_file_path}
TARGET SUB-PHASE: {N}.{M}

SCOPE BOUND: STOP at the end of sub-phase {N}.{M}. Do NOT read other phase files.
Do NOT execute sub-phases beyond {N}.{M}.

PROJECT CONVENTIONS:
- Commit format: Conventional Commits with scope = codename ({codename})
  Example: feat({codename}): add trailer URL parser
- Types allowed: feat | fix | chore | refactor | style | docs | test | perf | build | ci
- NEVER include AI attribution (Co-Authored-By, Claude, Anthropic, AI)
- Google-style docstrings, English, line length 120
- mypy strict mode

QUALITY GATES (run BEFORE each commit):
- ruff check {touched_files}
- ruff format --check {touched_files}
- python -m mypy {touched_modules}
- {test_command} {touched_tests}

CONSTRAINTS:
- DO NOT push
- DO NOT modify IMPLEMENTATION.md (main session owns it)
- DO NOT touch files outside sub-phase scope (unless fixing import break caused by your changes)
- Commit IMMEDIATELY after quality gate passes, do NOT batch multiple sub-phases
- If BLOCKED, STOP and report — do not guess

REPORT SCHEMA (return this exact structure):
## Sub-phase {N}.{M} Report

**Status**: DONE | DONE_WITH_CONCERNS | BLOCKED
**Sub-phase attempted**: {N}.{M}

**Commits**:
- <SHA> <conventional commit message>
- ...

**Quality gates** (your own run):
- mypy: <0 errors | N errors>
- ruff check: <clean | issues>
- ruff format --check: <clean | issues>
- tests: <X passed | X passed, Y failed>

**Files changed**: <count>
- <path/to/file1>
- ...

**Deviations from plan**: <list or "none">

**Concerns** (if DONE_WITH_CONCERNS): <list>
```

6. `## Error Handling` — matrice : dispatch retourne BLOCKED (bubble up), rapport tronqué (main session décide — voir `implement:check`), dispatch crash (rapport au parent).
7. `## Idempotence` — relançable ; si sub-phase déjà committée (SHA dans git range `baseline..HEAD`), le dispatch peut no-op et retourner un rapport "already done". En pratique, l'orchestrateur `implement:phase` ne relance pas une sous-phase déjà validée.
8. `## What this skill does NOT do` — ne vérifie pas le rapport (c'est `implement:check`), ne fait pas d'auto-fix (dispatch Sonnet ad-hoc par `implement:phase`), ne met pas à jour IMPLEMENTATION.md.

- [ ] **Step 3 : Vérifier frontmatter**

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:sub-phase/SKILL.md"
git commit -m "feat(.claude): add implement:sub-phase skill"
```

---

## Task 3.2 — Créer `implement:check`

**Files:**

- Create: `.claude/skills/implement:check/SKILL.md`

**Spec section** : §7.8 du spec.

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:check"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:check
description: |
  Verify a sub-phase or phase result vs DESIGN/plan. 6 independent checks (truncation, git range, plan compliance, quality gate re-run, scope drift, design coherence).
  WHEN: Invoked by /implement:phase after each sub-phase report, and at end of phase.
  WHEN NOT: PR-level review (use /implement:pr-review). Standalone design review (use the spec doc directly).
---
```

Sections :

1. `# Implement Check`
2. `## Usage` — invoqué par `implement:phase`, arguments : `{baseline_sha, phase_file_path, sub_phase_report, codename, scope="sub-phase"|"phase"}`.
3. `## Model Allocation` — **Opus main session** (non-délégable : jugement architectural + quality gate run + analyse diff).
4. `## Process` — 6 checks en ordre impératif (bail-out au premier échec) conformément au spec §7.8 :
   - **Check 0 — Truncation detection** : scanner le rapport Sonnet pour les sections requises. Si absent → treat as BLOCKED, ne pas parser plus loin.
   - **Check 1 — Git range audit** : `git log --oneline baseline..HEAD` + `git status --short`. Table de décision :
     | `git log` | `git status` | Interprétation | Action |
     |---|---|---|---|
     | ≥1 commits | clean | Subagent committed cleanly | Continuer checks |
     | 0 commits | clean | Subagent BLOCKED or no-op | Retry ou report |
     | 0 commits | dirty | Cut-off mid-edit | Rollback via `git checkout --`, retry |
     | ≥1 commits | dirty | Cut-off mid-cycle | Préserver commits, rapport delta user |
   - **Check 2 — Plan compliance** : chaque sous-phase `{N}.{M}` du plan a un commit dans le rapport. Cross-check : tout SHA du rapport existe dans `git log baseline..HEAD`.
   - **Check 3 — Full quality gate independent re-run** :
     ```bash
     ruff check {scope_dirs}
     ruff format --check {scope_dirs}
     python -m mypy {scope_modules}
     {test_command} tests/ -q      # full suite
     ```
     Ne jamais faire confiance au rapport Sonnet — ce check est non-négociable. Si le rapport dit "clean" et le re-run dit "22 errors" → `MISMATCH` → auto-fix (dispatch Sonnet par `implement:phase`).
   - **Check 4 — Scope drift** : `git log --name-only baseline..HEAD | grep -v <expected_files_pattern>`. Tolérance : `tests/`, `docs/IMPLEMENTATION.md`, `*.md` si phase mentionne doc updates. Tout autre fichier hors plan → `SCOPE_DRIFT` → fail loud (pas d'auto-fix, user décide).
   - **Check 5 — Design coherence** : lire `docs/features/{codename}/DESIGN.md` + diff des fichiers touchés. Vérifier alignement interfaces/modules/data flow. Si déviation → fail loud, user décide (peut nécessiter update DESIGN).
5. `## Output` — retour structuré à `implement:phase` :
   ```
   {
     "status": "OK" | "AUTO_FIX_NEEDED" | "FAIL_LOUD",
     "failed_check": 0..5 | null,
     "errors": [...],           # Verbatim output pour nourrir le prompt auto-fix
     "drift_files": [...],      # Si Check 4 échoue
     "design_deviations": [...] # Si Check 5 échoue
   }
   ```
6. `## Error Handling` — matrice : déviation design (fail loud, user), scope drift (fail loud, user), quality gate échoue (AUTO_FIX_NEEDED), truncation (re-dispatch sub-phase).
7. `## Idempotence` — pure function, pas de side effect git, relançable.
8. `## What this skill does NOT do` — ne corrige rien (pas d'auto-fix interne), ne commit rien, ne modifie pas IMPLEMENTATION.md.

- [ ] **Step 3 : Vérifier frontmatter**

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:check/SKILL.md"
git commit -m "feat(.claude): add implement:check skill"
```

---

## Task 3.3 — Créer `implement:phase`

**Files:**

- Create: `.claude/skills/implement:phase/SKILL.md`

**Spec section** : §7.6 du spec + §8.1 (invariants).

- [ ] **Step 1 : Créer le dossier**

```bash
mkdir -p ".claude/skills/implement:phase"
```

- [ ] **Step 2 : Écrire `SKILL.md`**

Frontmatter :

```yaml
---
name: implement:phase
description: |
  Execute ALL remaining phases of the implementation plan. Per sub-phase: dispatch via /implement:sub-phase, verify via /implement:check, auto-fix if needed. Continuous flow, never pauses between phases.
  WHEN: Continuing feature implementation after /implement:feature. Invoked repeatedly until all phases done.
  WHEN NOT: No IMPLEMENTATION.md or plan yet — use /implement:feature first.
---
```

Sections :

1. `# Implement Phase`
2. `## Usage` — `/implement:phase` (auto-détecte la prochaine phase `[ ]`).
3. `## Model Allocation` — **Opus main session** (orchestration + vérification via `implement:check`).
4. `## Continuous Execution (MANDATORY)` — section dédiée, wording EXACT :
   > **NEVER pause, ask for confirmation, or wait for user input between sub-phases, phases, or on phase completion.** After a gate passes, immediately proceed. Stop only for: blocking error requiring user decision, or context ≥ 80% full.
   >
   > **Anti-patterns** (NEVER do these) :
   >
   > - Asking "Shall I proceed to sub-phase X ?"
   > - Asking "Shall I proceed to phase N+1 ?"
   > - Stopping after a phase gate to "report phase complete"
   > - Running code yourself instead of dispatching via /implement:sub-phase
5. `## Process` — étapes conformément au spec §7.6 révisé :
   1. **Lire IMPLEMENTATION.md** → identifier la prochaine phase `[ ]`.
   2. **Charger** `docs/features/{codename}/plan/phase-NN-*.md`. Parser la liste des sous-phases (`### N.M` headings).
   3. **Boucle sur chaque sous-phase** :
      a. Capturer baseline SHA : `git rev-parse HEAD`.
      b. Invoquer `/implement:sub-phase` avec `{phase_file_path, sub_phase_number, baseline_sha, codename, branch}`. Attendre rapport.
      c. Invoquer `/implement:check` avec `{baseline_sha, phase_file_path, sub_phase_report, codename, scope="sub-phase"}`.
      d. Analyser le résultat de check :
      - `OK` → continuer à la sous-phase suivante.
      - `AUTO_FIX_NEEDED` → **dispatch Agent Sonnet inline** (pas une skill nommée) avec prompt fix-only, scope = fichiers touchés, erreurs verbatim. Max 2 tentatives. Relancer `/implement:check` après chaque. Si toujours échec après 2 → fail loud.
      - `FAIL_LOUD` → stop, diagnostic au user.
   4. **Après dernière sous-phase de la phase** : milestone commit sur la phase :
      ```bash
      git commit --allow-empty -m "chore({codename}): phase {N} gate — {phase_name}"
      ```
      Marquer phase `[x]` dans IMPLEMENTATION.md, commit `docs({codename}): mark phase {N} done`.
   5. **Si dernière phase** (toutes `[x]` dans IMPLEMENTATION.md) → invoquer `/implement:feature-pr` (flux continu, pas de pause).
   6. **Sinon** → boucle sur la phase suivante (pas de pause, pas de confirmation).
6. `## Auto-fix Pattern` — section dédiée avec le prompt template pour le dispatch Sonnet fix-only :

```
FIX-ONLY MODE
SCOPE: {files_touched_in_current_sub_phase}
BASELINE: {baseline_sha} (do not modify commits before this)

Errors to fix:
<verbatim output of failing quality gate>

CONSTRAINTS:
- No new features, only fix the listed errors
- Commit: fix({codename}): {description}
- No AI attribution
- Same quality gates as sub-phase (ruff + mypy + tests)
- Return the same report schema as sub-phase
```

7. `## Error Handling` — matrice §8.2 subset : sub-phase BLOCKED (stop phase), rapport tronqué (voir check décision), quality gate échoue (auto-fix max 2), scope drift (fail loud), context ≥ 80% (compact ou split session).
8. `## Idempotence` — lit l'état depuis IMPLEMENTATION.md + git range, reprend à la phase `[ ]` suivante. Si crash au milieu d'une phase, les commits sous-phase sont préservés, relance reprend à la sous-phase non committée.
9. `## What this skill does NOT do` — ne crée pas la PR (c'est `implement:feature-pr`), ne lance pas la review (`implement:pr-review`), ne push pas, ne modifie pas DESIGN.md.

- [ ] **Step 3 : Vérifier frontmatter**

- [ ] **Step 4 : Commit**

```bash
git add ".claude/skills/implement:phase/SKILL.md"
git commit -m "feat(.claude): add implement:phase skill"
```

---

## Gate cohérence Phase 3 → Phase 4

- [ ] **Step 1 : Vérifier présence des 3 skills**

```bash
ls ".claude/skills/implement:sub-phase/SKILL.md" \
   ".claude/skills/implement:check/SKILL.md" \
   ".claude/skills/implement:phase/SKILL.md"
```

- [ ] **Step 2 : Vérifier cross-refs internes**

`implement:phase` doit référencer :

- `/implement:sub-phase`
- `/implement:check`

```bash
grep -E '/implement:(sub-phase|check)' ".claude/skills/implement:phase/SKILL.md"
```

Expected : au moins 2 matches.

- [ ] **Step 3 : Vérifier absence de référence circulaire**

`implement:sub-phase` et `implement:check` ne doivent PAS référencer `implement:phase` hors clauses descriptives.

```bash
grep 'implement:phase' ".claude/skills/implement:sub-phase/SKILL.md" \
                      ".claude/skills/implement:check/SKILL.md"
```

Matches acceptés uniquement dans `WHEN NOT:` ou en texte descriptif. Pas d'appel type `/implement:phase`.

- [ ] **Step 4 : Vérifier mention du dispatch Sonnet**

```bash
grep -i 'sonnet' ".claude/skills/implement:sub-phase/SKILL.md"
grep -i 'model="sonnet"' ".claude/skills/implement:sub-phase/SKILL.md" || echo "Vérifier manuellement la mention du dispatch Sonnet"
```

- [ ] **Step 5 : Lancer skill-dependency-checker**

- [ ] **Step 6 : Milestone commit Phase 3**

```bash
git commit --allow-empty -m "chore(.claude): phase 3 gate — phase execution (3 skills)"
```

- [ ] **Step 7 : Mettre à jour INDEX du master plan**

```bash
git add docs/superpowers/plans/2026-04-22-implement-skills-refactor.md
git commit -m "docs(plan): mark phase 3 done"
```
