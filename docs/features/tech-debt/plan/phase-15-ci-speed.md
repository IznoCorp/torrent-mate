# Phase 15 — CI Speed Optimization (GitHub Actions credits)

**Status** : DESIGN APPROVED (2026-05-26)
**Effort** : 0.5-1 j
**Target** : Réduire le runner time cumulé de ~50% (objectif : 900-1000 → 450-500 min/mois)

## Problem Statement

Le workflow CI actuel (9 jobs, `ci.yml`) gaspille des minutes GitHub Actions sur
plusieurs axes :

1. **`pip install -e ".[dev]"` exécuté 5 fois par run** (typecheck, test, security,
   licenses, design-gaps) — chaque install coûte 20-30s
2. **`lint` installe `.[dev]` alors qu'il n'a besoin que de `ruff`**
3. **Pas de `concurrency`** : 3 pushes rapides = 3 runs complets gaspillés
4. **Pas de `paths-ignore`** : les PRs docs-only déclenchent la CI complète
5. **`gitleaks` téléchargé à chaque run** (appel API + curl + tar)
6. **`test` dépend de `secrets` et `licenses`** alors qu'il n'en a pas besoin
7. **`coverage-monotonic` a son propre runner** pour une vérif de 10 secondes

## Design Summary

### Architecture cible (11 jobs, 3 étages)

```
Stage 0 (immédiat, parallèle)
  ├─ lint          (~45s)  — ruff uniquement, pas de .[dev]
  └─ secrets       (~20s)  — gitleaks caché

Stage 1 (needs: lint, parallèle)
  ├─ typecheck     (~45s)  — mypy, cache .venv
  ├─ test-unit     (~90s)  — pytest unit, cache .venv + xdist
  ├─ test-integ    (~60s)  — pytest integration, cache .venv + xdist
  ├─ security      (~20s)  — pip-audit
  ├─ licenses      (~15s)  — pip-licenses
  └─ design-gaps   (~20s)  — feature map + design audit

Stage 2 (needs: [test-unit, test-integ])
  └─ coverage-merge (~15s) — coverage combine + upload codecov + fail_under monotonic check
```

### Changements détaillés

1. **`concurrency: cancel-in-progress`** — annule les runs obsolètes sur la même PR
2. **`paths-ignore: ['**.md', 'docs/**', '\*.md']`** — skip CI sur PRs docs-only
3. **Cache `.venv/`** remplace `~/.cache/pip` pour les jobs `.[dev]` — install passe
   de 20-30s à ~2s sur cache hit. Clé : `venv-${{ runner.os }}-3.12-${{ hashFiles('pyproject.toml') }}`
4. **`lint` n'installe que `ruff`** (pas `.[dev]`) — économie ~20s sur ce job
5. **Cache `gitleaks`** dans `~/.local/bin/` — clé liée à `hashFiles('.github/workflows/ci.yml')`
6. **`needs` affinés** : test-unit/test-integ dépendent seulement de `lint` + `typecheck`.
   design-gaps et security ne dépendent plus de `secrets` + `licenses`.
7. **Split `test` → `test-unit` + `test-integ`** parallèles, coverage combiné dans `coverage-merge`
8. **`coverage-monotonic` fondu dans `coverage-merge`** — économise un runner complet

### Impact estimé

| Métrique                   | Avant     | Après       | Delta |
| -------------------------- | --------- | ----------- | ----- |
| Runner time / run          | ~9-10 min | ~4-5 min    | -50%  |
| Wall time / run            | ~5-7 min  | ~3-4 min    | -40%  |
| Jobs / run                 | 9         | 11          | +2    |
| `pip install .[dev]` / run | 5         | 3 (+ cache) | -40%  |

Hypothèses : cache hit rate ~90% (seulement invalidé quand `pyproject.toml` change).

## Sub-phases

### 15.1 — Quick structural wins (concurrency + paths-ignore + needs affinés)

- Ajouter `concurrency` et `paths-ignore`
- Affiner les `needs` de tous les jobs
- Commit: `ci(tech-debt): concurrency + paths-ignore + refined needs`

### 15.2 — Cache .venv sur tous les jobs .[dev]

- Remplacer `~/.cache/pip` par `.venv/` dans typecheck, test-\*, security, licenses, design-gaps
- Supprimer l'install redondante dans lint (ruff uniquement)
- Commit: `ci(tech-debt): cache .venv + install minimal lint job`

### 15.3 — Cache gitleaks

- Ajouter cache gitleaks dans le job `secrets`
- Commit: `ci(tech-debt): cache gitleaks binary`

### 15.4 — Split test + coverage-merge + fusion coverage-monotonic

- Créer `test-unit` et `test-integ` parallèles
- Créer `coverage-merge` avec upload artifact, `coverage combine`, upload codecov
- Fusionner la vérif `coverage-monotonic` dans `coverage-merge`
- Commit: `ci(tech-debt): split test matrix + coverage merge job`

### 15.5 — ACCEPTANCE criteria + Phase 15 gate

- Ajouter ACC-55..ACC-60 dans `ACCEPTANCE.md`
- Mettre à jour `plan/INDEX.md`
- Commit: `docs(tech-debt): Phase 15 ACC criteria + plan INDEX update`

### 15.6 — Phase gate

- `make check` passe
- Vérification manuelle : premier run CI post-merge avec cache froid puis cache chaud
- Commit: `chore(tech-debt): phase 15 gate — CI speed optimization`

## Dependencies

Aucune dépendance sur les phases précédentes. Modifie uniquement `.github/workflows/ci.yml`
et `docs/features/tech-debt/`. Aucun changement dans `personalscraper/` ni `tests/`.

## ACCEPTANCE Criteria

### ACC-55 — concurrency cancel-in-progress

```bash
grep -c 'concurrency:' .github/workflows/ci.yml && grep -c 'cancel-in-progress' .github/workflows/ci.yml
# Expected: ≥1, ≥1
```

### ACC-56 — paths-ignore docs

```bash
grep -c 'paths-ignore' .github/workflows/ci.yml
# Expected: ≥1
```

### ACC-57 — Cache .venv present

```bash
grep -c '\.venv' .github/workflows/ci.yml
# Expected: ≥1
```

### ACC-58 — Lint job sans .[dev]

```bash
grep -A 20 'name: lint' .github/workflows/ci.yml | grep -c '\.\[dev\]'
# Expected: 0
```

### ACC-59 — Gitleaks cached

```bash
grep -B 2 -A 5 'cache-gitleaks' .github/workflows/ci.yml | grep -c 'cache-hit'
# Expected: ≥1
```

### ACC-60 — test split + coverage merge

```bash
grep -cE 'test-unit|test-integ|coverage-merge' .github/workflows/ci.yml
# Expected: 3
```
