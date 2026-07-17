# Phase 06 — Final gate

**Gate:** All tests green, mobile 390px proof, version bumped, ACC criteria executed.

## Sub-phases

### 6.1 — Full quality gate

**Commit:** `chore(control-medias): full quality gate — lint + typecheck + vitest + make check`

```bash
# Frontend
cd frontend && npm run lint && npm run typecheck && npx vitest run

# Backend
make lint && make test && make check
```

Fix any failures. If `vitest` or `make test` shows failures, iterate fixes within this commit (no separate fix commits — each gate in this phase is atomic).

**Gate:** Both frontend and backend gates pass (required before proceeding).

---

### 6.2 — Residual import grep + module size check

**Commit:** `chore(control-medias): residual import sweep + module-size audit`

```bash
# Verify no stale /scraping imports remain in non-test frontend code
rg "/scraping" -g '*.tsx' -g '*.ts' frontend/src/

# Verify no stale Decisions import in router
rg "Decisions" frontend/src/router.tsx

# Verify no stale "Tableau de bord" label
rg "Tableau de bord" -g '*.tsx' -g '*.ts' frontend/src/

# Module size check
python3 scripts/check-module-size.py
```

Expected: zero matches for `/scraping` in non-test files; zero matches for `"Tableau de bord"` in nav/shell; `Decisions` import removed from router; all modules under the 1000-line hard ceiling.

**Gate:** `make check` green.

---

### 6.3 — Version bump to 0.51.0

**Commit:** `chore(control-medias): bump version to 0.51.0`

```bash
# Update version in pyproject.toml
# Also verify GET /api/version returns the bumped commit SHA
```

**File:** `pyproject.toml` — `version = "0.51.0"`

**Gate:** `make lint && make test`

---

### 6.4 — Mobile 390px iframe proof

**No commit (verification only)**

Per `docs/reference/product-intent.md` §méthode, execute:

1. Open `tm-staging.iznogoudatall.xyz` via the Chrome 390px iframe harness.
2. Verify `/` (Contrôle): `scrollWidth - innerWidth === 0` — no horizontal overflow.
3. Verify `/medias`: `scrollWidth - innerWidth === 0`.
4. Verify `/medias?media=<id>`: sheet full-screen on mobile, egress actions visible.
5. Verify `/scraping?media=X` redirects → `/medias?media=X` and opens the sheet.
6. Verify BottomTabBar shows: Contrôle · Médias · Pipeline · Acquisition.

**Mobile overflow = 0 on both `/` and `/medias` is the §méthode proof gate.**

---

### 6.5 — ACC criteria verification

**No commit (verification only)**

Execute the DESIGN.md §3 acceptance criteria:

1. **Redirect:** `curl --connect-timeout 10 --max-time 30 "https://tm-staging.iznogoudatall.xyz/scraping?media=X"` → redirects to `/medias?media=X` with 301/302.
2. **DOIT-7:** Open each seeded media's sheet — verify action count ≥ 1 for: ambiguous, absent, other-unknown, matched+blocked, matched+clean.
3. **§4:** A matched+blocked media « Relancer et terminer » → 202 → verify run visible via `GET /api/pipeline/history`.
4. **§7:** « Ignorer / nettoyer » → verify journal row: `SELECT * FROM destructive_op WHERE actor='web'`.
5. **Contrôle:** À traiter lists seeded blocked media; « Ce qui n'avance pas » shows last run's skip reasons; single primary control drives run start/stop.

**Gate:** All 5 ACC criteria pass with executed evidence.
