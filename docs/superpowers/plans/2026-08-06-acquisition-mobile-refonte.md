# Acquisition mobile-first rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 7-tab Acquisition page with two question-shaped views (« Maintenant », « Suivis »), a media sheet, a full-screen add flow and three touch gestures — mobile-first, per `docs/superpowers/specs/2026-08-06-acquisition-mobile-refonte-design.md`.

**Architecture:** One new backend read model (« À traiter » = pending scrape decisions correlated to the acquisition provenance spine) plus a frontend rebuild of `frontend/src/components/acquisition/*`. The page shell owns tab state and the live-event invalidation; each view is a panel; one shared `AcquisitionCard` is the single card grammar across every list. No DB migration — `ProvenanceRow` already carries `decision_id` / `resolution_state`.

**Tech Stack:** FastAPI + Pydantic + SQLite (backend), React 19 + TypeScript + TanStack Query + shadcn/ui + Tailwind + Vitest + Testing Library (frontend). Worktree `.claude/worktrees/acq-mobile`, branch `feat/acq-mobile`.

## Execution order

Task **numbers below never change** — tasks cite each other by number. What changed after the
pre-flight scan is the **order they are dispatched in**:

```
1 → 2 → 3 → 17 → 4 → 5 → 6 → 10 → 8 → 9 → 12 → 7 → 11 → 13 → 14 → 15 → 16
```

**Task 17 was added during execution** (operator decision A18) and is placed right after the backend work: it opens
staging's write path for acquisition and decisions, and staging must already accept those writes by the time the
mutating UI journeys exist to be validated.

**Why:** the original order had Task 7 (the shell) render placeholder components until Tasks 8 and 9
existed. A stub is dead code — exactly what a reviewer is right to flag — so the panels are built
first and the shell wires real components on its first day. The dependency chain that makes this
stub-free: `AcquisitionCard` (5) and `JourneyStrip` (6) before any panel; `FollowDetailSheet` (10)
before the panels, because a card's tap target opens it; the panels (8, 9) and the add screen (12)
before the shell (7) that hosts them; gestures (13, 14) after the surfaces they act on.

## Global Constraints

- **Spec is binding:** `docs/superpowers/specs/2026-08-06-acquisition-mobile-refonte-design.md`. Its §2 arbitrations A1–A17 are inputs, not proposals. Its §11 rules R1–R8 apply to every component written here.
- **Constitution:** `docs/reference/product-intent.md` — every PR body cites the § it serves. In any conflict between this plan and the constitution, the constitution wins.
- **Version:** already bumped to `0.87.0` in `personalscraper/__init__.py` on this branch. Do **not** bump again per task.
- **Staging before merge (A16):** every task's deliverable is validated on `tm-staging.iznogoudatall.xyz` at 390 px before the PR merges. Task 16 is the gate.
- **Frontend gates, all three, before every commit:** `npm run lint` **and** `npx tsc -b --noEmit` (NOT `tsc --noEmit` — the root tsconfig is a solution file and checks nothing) **and** `npm run test`.
- **Backend gate:** `make test` (0 failures is the bar) and `make check`.
- **OpenAPI:** any FastAPI route/signature/docstring change requires `make openapi` and committing **both** generated files — CI fails on drift.
- **Logging:** new backend modules use `from personalscraper.logger import get_logger`, never `structlog.get_logger` (enforced by `scripts/check_logging.py`).
- **French UI copy, English code/comments/docstrings.** Never print a machine token to the operator (NE-DOIT-PAS-4).
- **`rg` always with a type filter** (`-t py` / `-g '*.tsx'`) — an unfiltered `rg` scans 14 GB of fixtures.
- **Never** run `git stash` bare — the stash stack is shared with other sessions.

---

## File Structure

**Backend (new):**
- `personalscraper/web/acquisition/to_handle.py` — the « À traiter » read model. Pure: takes paths + a store, returns a rollup. One responsibility: correlate pending `scrape_decision` rows with `ProvenanceRow`.
- `tests/web/acquisition/test_to_handle.py` — its tests.

**Backend (modified):**
- `personalscraper/web/models/acquisition.py` — `ToHandleItem`, `ToHandleResponse`.
- `personalscraper/web/routes/acquisition_overview.py` — `GET /api/acquisition/to-handle`.

**Frontend (new), all under `frontend/src/components/acquisition/`:**
- `AcquisitionCard.tsx` — the single card grammar (poster target + main target + meta line + optional strip + optional footer). Every list uses it.
- `JourneyStrip.tsx` — the §14.3 stage strip, own line, `done` / `now` / `blocked` / pending.
- `MaintenantPanel.tsx` — the five sections of « Maintenant ».
- `SuivisPanel.tsx` — filters, view-mode switcher, three modes.
- `FollowDetailSheet.tsx` — per-follow sheet: primary action, legend, season matrix, secondary actions.
- `AddMediaScreen.tsx` — the full-screen add flow.
- `PlusSheet.tsx` — Veille + Obligations, second rank.
- `useViewMode.ts` — localStorage-backed display mode (A7/A8).
- `gestures.ts` — pure gesture helpers (axis lock, edge dead zone, snap thresholds), testable without a DOM gesture harness.

**Frontend (modified):**
- `pages/AcquisitionPage.tsx` — shell: two views, « Plus », legacy `?tab=` redirects.
- `components/acquisition/meta.ts` — vocabulary home; gains the film/série action maps.
- `components/layout/AppShell.tsx` — badge source change.
- `api/acquisition.ts`, `hooks/useAcquisition.ts` — the `to-handle` query.

**Frontend (deleted):** `StagingBanner.tsx` (+test), `OverviewPanel.tsx` (+test), `FileDAcquisitionPanel.tsx` (+test), `WantedPanel.tsx`, `ParcoursPanel.tsx` (+test) — each in the task that replaces it, never before.

---

### Task 1: Delete the staging banner (A17)

Independent of everything else — do it first so the 3 px frame stops distorting every 390 px measurement taken in later tasks.

**Files:**
- Delete: `frontend/src/components/StagingBanner.tsx`, `frontend/src/components/StagingBanner.test.tsx`
- Modify: `frontend/src/App.tsx` (import + line 62), `frontend/src/pages/Config.tsx` (import + line 83), `frontend/src/lib/env.ts` (docstring only)
- Test: `frontend/src/lib/env.test.ts` (create if absent)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. `isStaging()` and `BRAND_ICON` keep their exact current signatures — `isStaging(): boolean`, `BRAND_ICON: string`.

- [ ] **Step 1: Write the failing guard test**

The banner is being deleted *because* another signal survives. The test must prove the survivor is alive, not merely that the corpse is gone.

Create/extend `frontend/src/lib/env.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

describe("env — l'identité staging après le retrait de la bannière (A17)", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  async function loadEnvOn(hostname: string, port = "") {
    vi.stubGlobal("window", { location: { hostname, port } } as unknown as Window);
    vi.resetModules();
    return import("@/lib/env");
  }

  it("garde le logo staging comme signal survivant", async () => {
    const env = await loadEnvOn("tm-staging.iznogoudatall.xyz");
    expect(env.isStaging()).toBe(true);
    expect(env.BRAND_ICON).toBe("/icon-staging.svg");
  });

  it("garde le logo de prod ailleurs", async () => {
    const env = await loadEnvOn("tm.iznogoudatall.xyz");
    expect(env.isStaging()).toBe(false);
    expect(env.BRAND_ICON).toBe("/icon.svg");
  });

  it("plus aucun module n'importe StagingBanner", async () => {
    const modules = import.meta.glob("/src/**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true });
    const offenders = Object.entries(modules)
      .filter(([, source]) => /StagingBanner/.test(source as string))
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});
```

- [ ] **Step 2: Run it and watch the third case fail**

Run: `cd frontend && npx vitest run src/lib/env.test.ts`
Expected: the first two PASS, « plus aucun module n'importe StagingBanner » FAILS listing `App.tsx`, `Config.tsx`, `StagingBanner.tsx`, `StagingBanner.test.tsx`.

- [ ] **Step 3: Delete the component and its two render sites**

```bash
cd frontend
rm src/components/StagingBanner.tsx src/components/StagingBanner.test.tsx
```

In `src/App.tsx`: remove the `import { StagingBanner } …` line and the `<StagingBanner />` element.
In `src/pages/Config.tsx`: remove the `import { StagingBanner } …` line and the whole `{editor.isStaging && <StagingBanner />}` line — **keep** the `{editor.readOnly && …}` alert immediately below it, which carries the operative message on that page.
In `src/lib/env.ts`: the module docstring says *"so the {@link StagingBanner}, the in-app logo, and the PWA identity all agree"*. Rewrite it to:

```ts
/**
 * Environment detection shared across the UI.
 *
 * Staging is identified by host: the prod and staging origins differ
 * (`tm-staging.iznogoudatall.xyz` / the loopback staging port `8711`). Kept in
 * one place so the in-app logo and the PWA identity agree on what "staging"
 * means. The former full-viewport staging banner was removed (A17): the
 * installed PWA already carries a distinct icon (`index.html` swaps the
 * manifest and the apple-touch-icon on a staging host) and `BRAND_ICON` below
 * swaps the in-app mark, so a third signal only cost width at 390px.
 */
```

- [ ] **Step 4: Run the test again, then the full gates**

Run: `cd frontend && npx vitest run src/lib/env.test.ts`
Expected: 3 PASS.
Then: `npm run lint && npx tsc -b --noEmit && npm run test`
Expected: all green. If `Config.test.tsx` asserted the banner, delete that assertion — the read-only alert assertion stays.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src
git commit -m "$(cat <<'EOF'
refactor(acq-mobile): retirer la bannière de staging (A17)

Le cadre cyan de 3 px et son bandeau étaient un TROISIÈME signal : l'icône PWA
installée diffère déjà (index.html bascule le manifeste et l'apple-touch-icon
sur un hôte staging) et BRAND_ICON bascule le logo dans l'app. Le cadre coûtait
de la largeur sur les quatre bords à 390 px.

Le rendu de /config n'est pas basé sur l'hôte mais sur role === "staging" servi
par l'API ; l'alerte « Mode lecture seule » juste en dessous porte l'information
opérante et reste en place.

Un test prouve que le signal survivant est vivant, pas seulement que l'ancien
est parti.
EOF
)"
```

---

### Task 2: Backend read model — « À traiter »

**Files:**
- Create: `personalscraper/web/acquisition/to_handle.py`
- Test: `tests/web/acquisition/test_to_handle.py`

**Interfaces:**
- Consumes: `AcquireStore.provenance` (`ProvenanceRow` with `decision_id`, `resolution_state`, `current_path`, `ingest_path`, `followed_id`, `media_ref`, `status`, `grabbed_at`, `ingested_at`, `scraped_at`, `dispatched_at`), and the indexer DB's `scrape_decision` table (columns `id, staging_path, media_kind, extracted_title, extracted_year, trigger, candidates_count, status, created_at` — see `personalscraper/web/models/decisions.py:42-50`).
- Produces:
  ```python
  @dataclass(frozen=True)
  class ToHandleItem:
      decision_id: int
      title: str
      year: int | None
      kind: str                    # "movie" | "tvshow"
      reason: str                  # FRENCH, already mapped — never a raw trigger token
      candidates_count: int
      created_at: int
      followed_id: int | None      # None ⇒ no acquisition provenance
      info_hash: str | None
      stage: str                   # "pris"|"telech"|"ingere"|"scrape"|"range" — where it stopped

  @dataclass(frozen=True)
  class ToHandleRollup:
      items: tuple[ToHandleItem, ...]   # ONLY those with an acquisition provenance
      orphan_count: int                 # pending decisions with NO provenance row
  def build_to_handle(*, indexer_db: Path | None, store: AcquireStore | None) -> ToHandleRollup
  ```

- [ ] **Step 1: Write the failing tests**

The three behaviours that matter: correlation, the orphan split, and the honest stage.

```python
"""Tests for the « À traiter » read model (spec §3.1)."""

import sqlite3
from pathlib import Path

import pytest

from personalscraper.web.acquisition.to_handle import build_to_handle


def _make_indexer(tmp_path: Path, rows: list[tuple]) -> Path:
    db = tmp_path / "library.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE scrape_decision (id INTEGER PRIMARY KEY, staging_path TEXT, "
        "media_kind TEXT, extracted_title TEXT, extracted_year INTEGER, trigger TEXT, "
        "candidates_json TEXT, status TEXT, created_at REAL)"
    )
    conn.executemany(
        "INSERT INTO scrape_decision (id, staging_path, media_kind, extracted_title, "
        "extracted_year, trigger, candidates_json, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def test_a_decision_backed_by_an_acquisition_is_an_item(tmp_path, acquire_store):
    """Une décision dont le chemin est porté par la spine EST une acquisition."""
    db = _make_indexer(tmp_path, [
        (1, "/staging/Top Chef S16E12", "tvshow", "Top Chef", 2010, "ambiguous", "[{},{},{}]", "pending", 1000.0),
    ])
    acquire_store.provenance.upsert_grab(info_hash="abc", followed_id=42, kind="episode")
    acquire_store.provenance.set_ingest(info_hash="abc", ingest_path="/staging/Top Chef S16E12", ingested_at=900)

    roll = build_to_handle(indexer_db=db, store=acquire_store)

    assert roll.orphan_count == 0
    assert len(roll.items) == 1
    item = roll.items[0]
    assert item.decision_id == 1
    assert item.followed_id == 42
    assert item.info_hash == "abc"
    assert item.title == "Top Chef"
    assert item.candidates_count == 3
    # §14.3 — l'étape est celle réellement atteinte, jamais une valeur par défaut.
    assert item.stage == "ingere"


def test_a_manual_drop_is_counted_but_never_listed(tmp_path, acquire_store):
    """Un dépôt manuel n'est pas une acquisition : compté, jamais affiché ici."""
    db = _make_indexer(tmp_path, [
        (7, "/staging/Un Film Posé À La Main", "movie", "Un Film", None, "unmatched", "[]", "pending", 1000.0),
    ])

    roll = build_to_handle(indexer_db=db, store=acquire_store)

    assert roll.items == ()
    assert roll.orphan_count == 1


def test_a_resolved_decision_is_neither(tmp_path, acquire_store):
    db = _make_indexer(tmp_path, [
        (9, "/staging/Déjà Résolu", "movie", "Déjà", None, "ambiguous", "[]", "resolved", 1000.0),
    ])
    roll = build_to_handle(indexer_db=db, store=acquire_store)
    assert roll.items == ()
    assert roll.orphan_count == 0


def test_the_reason_is_french_never_a_raw_trigger(tmp_path, acquire_store):
    """NE-DOIT-PAS-4 : le verdict machine est mappé, jamais imprimé brut."""
    db = _make_indexer(tmp_path, [
        (1, "/s/a", "movie", "A", None, "ambiguous", "[{},{},{}]", "pending", 1.0),
        (2, "/s/b", "movie", "B", None, "unmatched", "[]", "pending", 2.0),
    ])
    acquire_store.provenance.upsert_grab(info_hash="h1", followed_id=1, kind="movie")
    acquire_store.provenance.set_ingest(info_hash="h1", ingest_path="/s/a", ingested_at=1)
    acquire_store.provenance.upsert_grab(info_hash="h2", followed_id=2, kind="movie")
    acquire_store.provenance.set_ingest(info_hash="h2", ingest_path="/s/b", ingested_at=1)

    roll = build_to_handle(indexer_db=db, store=acquire_store)
    reasons = {i.decision_id: i.reason for i in roll.items}

    assert reasons[1] == "titre ambigu — 3 candidats proposés"
    assert reasons[2] == "aucun candidat — recherche manuelle prête"
    for reason in reasons.values():
        assert "ambiguous" not in reason and "unmatched" not in reason


def test_no_indexer_db_is_an_empty_rollup_not_a_crash(acquire_store):
    """Fail-soft : une base absente ne fait pas tomber la vue (§méthode)."""
    roll = build_to_handle(indexer_db=None, store=acquire_store)
    assert roll.items == ()
    assert roll.orphan_count == 0
```

`acquire_store` — check `tests/conftest.py` for an existing fixture producing an `AcquireStore` on a temp DB (grep: `rg -t py "def acquire_store" tests/`). If none exists, add one to `tests/web/acquisition/conftest.py` that builds a store on `tmp_path / "acquire.db"` using the same constructor the app uses (`rg -t py "AcquireStore(" personalscraper/ | head`).

- [ ] **Step 2: Run to verify they fail**

Run: `cd /Users/izno/dev/PersonalScraper/.claude/worktrees/acq-mobile && command python -m pytest tests/web/acquisition/test_to_handle.py -v`
Expected: FAIL — `ModuleNotFoundError: personalscraper.web.acquisition.to_handle`.

- [ ] **Step 3: Implement the read model**

```python
"""« À traiter » — les médias bloqués QUI VIENNENT D'UNE ACQUISITION.

§14.3 : un parcours n'a pas de trou. Un item pris puis ingéré qui cale à
l'identification est au milieu de SON parcours ; il doit rester visible depuis
l'acquisition. Un dépôt manuel, lui, n'est pas une acquisition : il est compté
(§méthode — ne jamais sous-compter ce qui demande attention) mais jamais listé
ici, il appartient au panneau « À traiter » de Contrôle.

La corrélation n'exige AUCUNE migration : ``ProvenanceRow`` porte déjà
``decision_id``, et ``by_path()`` retrouve la ligne par son chemin de staging.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import AcquireStore

logger = get_logger(__name__)

# Verdict machine → raison française. NE-DOIT-PAS-4 : jamais le token brut.
_REASON: dict[str, str] = {
    "ambiguous": "titre ambigu",
    "unmatched": "aucun candidat — recherche manuelle prête",
    "verify_failed": "vérification refusée — reprise nécessaire",
}
_UNKNOWN_REASON = "identification impossible au dernier passage"


@dataclass(frozen=True)
class ToHandleItem:
    """Une décision bloquée portée par une acquisition."""

    decision_id: int
    title: str
    year: int | None
    kind: str
    reason: str
    candidates_count: int
    created_at: int
    followed_id: int | None
    info_hash: str | None
    stage: str


@dataclass(frozen=True)
class ToHandleRollup:
    """Le partage entre ce qui s'affiche ici et ce qui se compte ailleurs."""

    items: tuple[ToHandleItem, ...]
    orphan_count: int


def _stage_of(row: object) -> str:
    """L'étape réellement atteinte — jamais une valeur par défaut (§14.3)."""
    if getattr(row, "dispatched_at", None):
        return "range"
    if getattr(row, "scraped_at", None):
        return "scrape"
    if getattr(row, "ingested_at", None):
        return "ingere"
    if getattr(row, "grabbed_at", None):
        return "telech"
    return "pris"


def _reason_of(trigger: str, candidates: int) -> str:
    base = _REASON.get(trigger, _UNKNOWN_REASON)
    if trigger == "ambiguous":
        return f"{base} — {candidates} candidat{'s' if candidates > 1 else ''} proposé{'s' if candidates > 1 else ''}"
    return base


def build_to_handle(*, indexer_db: Path | None, store: AcquireStore | None) -> ToHandleRollup:
    """Build the « À traiter » rollup.

    Args:
        indexer_db: Path to ``library.db``, or ``None`` when unconfigured.
        store: The acquisition store whose provenance spine carries the journeys,
            or ``None``.

    Returns:
        The rollup. Fail-soft: an unreadable database yields an empty rollup and a
        warning, never an exception — a broken read model must not take the page
        down with it.
    """
    if indexer_db is None or not Path(indexer_db).exists():
        return ToHandleRollup(items=(), orphan_count=0)

    try:
        conn = sqlite3.connect(f"file:{indexer_db}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT id, staging_path, media_kind, extracted_title, extracted_year, "
                "trigger, candidates_json, created_at FROM scrape_decision "
                "WHERE status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.warning("to_handle_read_failed", db=str(indexer_db))
        return ToHandleRollup(items=(), orphan_count=0)

    items: list[ToHandleItem] = []
    orphans = 0
    for decision_id, staging_path, kind, title, year, trigger, candidates_json, created_at in rows:
        try:
            candidates = len(json.loads(candidates_json or "[]"))
        except (TypeError, ValueError):
            candidates = 0

        prov = store.provenance.by_path(staging_path) if store is not None else None
        if prov is None:
            orphans += 1
            continue

        items.append(
            ToHandleItem(
                decision_id=int(decision_id),
                title=str(title or ""),
                year=int(year) if year is not None else None,
                kind=str(kind or ""),
                reason=_reason_of(str(trigger or ""), candidates),
                candidates_count=candidates,
                created_at=int(created_at or 0),
                followed_id=getattr(prov, "followed_id", None),
                info_hash=getattr(prov, "info_hash", None),
                stage=_stage_of(prov),
            )
        )

    return ToHandleRollup(items=tuple(items), orphan_count=orphans)
```

- [ ] **Step 4: Run the tests**

Run: `command python -m pytest tests/web/acquisition/test_to_handle.py -v`
Expected: 5 PASS. If `by_path` normalisation bites (NFC/NFD — staging paths on macFUSE arrive NFD while the DB stores NFC), normalise both sides with `unicodedata.normalize("NFC", path)` **inside** `build_to_handle` and add a test case with an NFD path.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/web/acquisition/to_handle.py tests/web/acquisition/
git commit -m "feat(acq-mobile): read model « À traiter » — décisions bloquées portées par une acquisition"
```

---

### Task 3: Backend endpoint + typed client

**Files:**
- Modify: `personalscraper/web/models/acquisition.py` (append), `personalscraper/web/routes/acquisition_overview.py` (append a route)
- Modify: `frontend/src/api/acquisition.ts`, `frontend/src/hooks/useAcquisition.ts`
- Test: `tests/web/routes/test_acquisition_to_handle_route.py`

**Interfaces:**
- Consumes: `build_to_handle` / `ToHandleRollup` from Task 2.
- Produces:
  - HTTP: `GET /api/acquisition/to-handle` → `{ items: ToHandleItemModel[], orphan_count: int }`
  - TS: `getToHandle(): Promise<ToHandleResponse>` in `api/acquisition.ts`; `useToHandle()` in `hooks/useAcquisition.ts`; query key `acqKeys.toHandle()`.

- [ ] **Step 1: Write the failing route test**

```python
def test_to_handle_route_serves_items_and_orphan_count(client, seeded_to_handle):
    resp = client.get("/api/acquisition/to-handle")
    assert resp.status_code == 200
    body = resp.json()
    assert body["orphan_count"] == 1
    assert [i["decision_id"] for i in body["items"]] == [1]
    assert body["items"][0]["reason"] == "titre ambigu — 3 candidats proposés"
    assert body["items"][0]["stage"] == "ingere"


def test_to_handle_route_is_fail_soft_without_a_database(client_without_indexer):
    resp = client_without_indexer.get("/api/acquisition/to-handle")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "orphan_count": 0}
```

Mirror the fixture style of the existing overview route tests — find them with
`command rg -t py -l "acquisition/overview" tests/` and copy that file's `client` construction verbatim (it already wires config + auth bypass).

- [ ] **Step 2: Run to verify they fail**

Run: `command python -m pytest tests/web/routes/test_acquisition_to_handle_route.py -v`
Expected: FAIL with 404.

- [ ] **Step 3: Add the models**

Append to `personalscraper/web/models/acquisition.py`:

```python
class ToHandleItemModel(BaseModel):
    """Un média bloqué dont l'acquisition est la nôtre (§14.3).

    Attributes:
        decision_id: ``scrape_decision.id`` — la cible de « Résoudre → ».
        title / year / kind: Ce que l'opérateur lit sur la carte.
        reason: La raison EN FRANÇAIS, déjà mappée (NE-DOIT-PAS-4).
        candidates_count: Nombre de candidats proposés (§3 : le sélecteur s'ouvre AVEC des propositions).
        created_at: Epoch seconds de la mise en attente.
        followed_id: Le suivi porteur, ou ``None``.
        info_hash: La release concernée, ou ``None``.
        stage: L'étape RÉELLEMENT atteinte du parcours — jamais une valeur par défaut.
    """

    decision_id: int
    title: str
    year: int | None = None
    kind: str
    reason: str
    candidates_count: int = 0
    created_at: int = 0
    followed_id: int | None = None
    info_hash: str | None = None
    stage: str


class ToHandleResponse(BaseModel):
    """Réponse de ``GET /api/acquisition/to-handle``.

    Attributes:
        items: Les bloqués PORTÉS PAR UNE ACQUISITION, le plus ancien d'abord.
        orphan_count: Les bloqués SANS provenance d'acquisition (dépôts manuels).
            Ils n'ont pas de carte ici — mais on ne les tait pas : l'UI en fait un
            renvoi vers Contrôle (§méthode : ne jamais sous-compter ce qui demande
            attention).
    """

    items: list[ToHandleItemModel] = []
    orphan_count: int = 0
```

- [ ] **Step 4: Add the route**

Append to `personalscraper/web/routes/acquisition_overview.py`, following the exact `request.app.state` access pattern the `/overview` handler above it uses:

```python
@router.get("/to-handle", response_model=ToHandleResponse)
def get_to_handle(request: Request) -> ToHandleResponse:
    """Serve the « À traiter » rollup.

    Args:
        request: The FastAPI request (carries the app context).

    Returns:
        Blocked media carried by one of our acquisitions, plus the count of blocked
        media that are NOT ours (manual staging drops), which the UI turns into a
        cross-reference to Contrôle rather than hiding.
    """
    config = request.app.state.config
    with open_acquire_store(config) as store:
        rollup = build_to_handle(indexer_db=config.indexer.db_path, store=store)
    return ToHandleResponse(
        items=[ToHandleItemModel(**vars(item)) for item in rollup.items],
        orphan_count=rollup.orphan_count,
    )
```

Use whatever store-opening helper `/overview` uses in this same file (read lines 93–155 first and copy it — do not invent `open_acquire_store` if the file names it differently).

- [ ] **Step 5: Run the tests, then regenerate OpenAPI**

Run: `command python -m pytest tests/web/routes/test_acquisition_to_handle_route.py -v` → 2 PASS.
Then: `make openapi`
Then: `git status --short` — expect exactly two generated files changed. Commit both or CI fails on drift.

- [ ] **Step 6: Add the typed client and the hook**

In `frontend/src/api/acquisition.ts`, next to the existing `getOverview`:

```ts
/** One blocked media whose acquisition is ours (spec §3.1). */
export type ToHandleItem =
  paths["/api/acquisition/to-handle"]["get"]["responses"]["200"]["content"]["application/json"]["items"][number];

export type ToHandleResponse =
  paths["/api/acquisition/to-handle"]["get"]["responses"]["200"]["content"]["application/json"];

/** Fetch the « À traiter » rollup. */
export async function getToHandle(): Promise<ToHandleResponse> {
  return apiGet<ToHandleResponse>("/api/acquisition/to-handle");
}
```

Match the file's existing idiom exactly — read how `getOverview` is declared and mirror it (it may use a generated `paths` type or a hand-written interface; do not introduce a second style).

Add `toHandle: () => [...acqKeys.all, "to-handle"] as const` to `acqKeys`, and in `hooks/useAcquisition.ts`:

```ts
/** « À traiter » — blocked media carried by one of our acquisitions. */
export function useToHandle() {
  return useQuery({
    queryKey: acqKeys.toHandle(),
    queryFn: getToHandle,
    refetchInterval: 60_000,
  });
}
```

- [ ] **Step 7: Gates and commit**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run test`

```bash
git add -A
git commit -m "feat(acq-mobile): GET /api/acquisition/to-handle + client typé"
```

---

### Task 4: Vocabulary — film vs série (A14, spec §9)

**Files:**
- Modify: `frontend/src/components/acquisition/meta.ts`
- Test: `frontend/src/components/acquisition/meta.test.ts`

**Interfaces:**
- Consumes: `FollowStatus` (already exported from `meta.ts`).
- Produces:
  ```ts
  export type MediaKind = "movie" | "show" | "season";
  export interface ActionWords {
    readonly add: string; readonly added: string; readonly addAsk: string;
    readonly pause: string; readonly pauseShort: string;
    readonly resume: string; readonly resumeShort: string;
    readonly remove: string; readonly removeConfirmTitle: string; readonly removeConfirmBody: string;
  }
  export function actionWords(kind: string): ActionWords;
  ```

- [ ] **Step 1: Write the failing tests**

```ts
import { describe, expect, it } from "vitest";
import { actionWords, FOLLOW_STATUS_LABEL, followStatusLabel } from "./meta";

describe("vocabulaire film vs série (§9)", () => {
  it("un film s'ajoute, une série se suit", () => {
    expect(actionWords("movie").add).toBe("Ajouter");
    expect(actionWords("movie").added).toBe("✓ Ajouté");
    expect(actionWords("show").add).toBe("Suivre");
    expect(actionWords("show").added).toBe("✓ Suivi");
  });

  it("on n'met pas un film en pause, on arrête de le chercher", () => {
    expect(actionWords("movie").pause).toBe("Ne plus chercher");
    expect(actionWords("movie").resume).toBe("Chercher à nouveau");
    expect(actionWords("show").pause).toBe("Mettre en pause");
  });

  it("un film quitte la liste, une série est désactivée", () => {
    expect(actionWords("movie").remove).toBe("Retirer de la liste");
    expect(actionWords("show").remove).toBe("Retirer le suivi");
    expect(actionWords("movie").removeConfirmBody).toContain("quittera votre liste");
    expect(actionWords("show").removeConfirmBody).toContain("réactiver");
  });

  it("un film suspendu n'est pas « en pause » mais « recherche arrêtée »", () => {
    expect(followStatusLabel("disabled", "movie")).toBe("Recherche arrêtée");
    expect(followStatusLabel("disabled", "show")).toBe("En pause");
  });

  it("les libellés courts du balayage tiennent en deux mots", () => {
    for (const kind of ["movie", "show"]) {
      expect(actionWords(kind).pauseShort.split(" ").length).toBeLessThanOrEqual(3);
      expect(actionWords(kind).resumeShort.split(" ").length).toBeLessThanOrEqual(3);
    }
  });

  it("un kind inconnu retombe sur le vocabulaire série, jamais sur un slug", () => {
    const w = actionWords("what-is-this");
    expect(w.add).toBe("Suivre");
    expect(Object.values(w).every((v) => !/[a-z]+_[a-z]+/.test(v))).toBe(true);
  });

  it("chaque état a un libellé — un nouvel état casse tsc, il n'imprime pas un slug", () => {
    for (const status of Object.keys(FOLLOW_STATUS_LABEL)) {
      expect(FOLLOW_STATUS_LABEL[status as keyof typeof FOLLOW_STATUS_LABEL]).toBeTruthy();
    }
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/acquisition/meta.test.ts`
Expected: FAIL — `actionWords is not a function`.

- [ ] **Step 3: Implement in `meta.ts`, next to the existing `FOLLOW_STATUS_LABEL_MOVIE`**

```ts
/** Action wording for one media nature. */
export interface ActionWords {
  readonly add: string;
  readonly added: string;
  readonly addAsk: string;
  readonly pause: string;
  readonly pauseShort: string;
  readonly resume: string;
  readonly resumeShort: string;
  readonly remove: string;
  readonly removeConfirmTitle: string;
  readonly removeConfirmBody: string;
}

/**
 * Action verbs, by media nature (§9).
 *
 * One does not *follow* a film: nothing accrues, and §5 removes it from the list
 * once acquired — so « Suivre » is true of a série (a surveillance that lasts)
 * and false of a film, which one adds once. The `…Short` forms are the swipe
 * labels, where the button is 84px wide.
 */
const ACTION_WORDS: Record<"movie" | "show", ActionWords> = {
  movie: {
    add: "Ajouter",
    added: "✓ Ajouté",
    addAsk: "Ajouter…",
    pause: "Ne plus chercher",
    pauseShort: "Ne plus chercher",
    resume: "Chercher à nouveau",
    resumeShort: "Chercher",
    remove: "Retirer de la liste",
    removeConfirmTitle: "Retirer ce film de la liste ?",
    removeConfirmBody:
      "Ce film ne sera plus cherché et quittera votre liste. Vous pourrez le rajouter par une recherche.",
  },
  show: {
    add: "Suivre",
    added: "✓ Suivi",
    addAsk: "Suivre…",
    pause: "Mettre en pause",
    pauseShort: "Pause",
    resume: "Réactiver",
    resumeShort: "Activer",
    remove: "Retirer le suivi",
    removeConfirmTitle: "Retirer ce suivi ?",
    removeConfirmBody:
      "Cette série ne sera plus surveillée. Le suivi est désactivé, pas supprimé : vous pourrez le réactiver depuis le filtre « En pause ».",
  },
};

/**
 * Return the action vocabulary for a media kind.
 *
 * Args:
 *   kind: ``"movie"`` or anything else (a série, including ``"season"``).
 *
 * Returns:
 *   The wording set — never a raw token, whatever the input.
 */
export function actionWords(kind: string): ActionWords {
  return kind === "movie" ? ACTION_WORDS.movie : ACTION_WORDS.show;
}
```

Then extend the existing film override map — one added entry:

```ts
export const FOLLOW_STATUS_LABEL_MOVIE: Partial<Record<FollowStatus, string>> = {
  a_jour: "Acquis",
  // Un film n'est pas « en pause » : on a simplement arrêté de le chercher.
  disabled: "Recherche arrêtée",
};
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/components/acquisition/meta.test.ts`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/acquisition/meta.ts frontend/src/components/acquisition/meta.test.ts
git commit -m "feat(acq-mobile): vocabulaire d'action film vs série (§9)"
```

---

### Task 5: `AcquisitionCard` — the single card grammar

This is the heart. Every list in the rebuild renders through it, so R1/R2/R3 are enforced once.

**Files:**
- Create: `frontend/src/components/acquisition/AcquisitionCard.tsx`
- Test: `frontend/src/components/acquisition/AcquisitionCard.test.tsx`

**Interfaces:**
- Consumes: `MediaPoster` (`@/components/ds/MediaPoster`), `Badge` (`@/components/ui/badge`), `actionWords` (Task 4).
- Produces:
  ```ts
  export interface AcquisitionCardProps {
    readonly title: string;
    readonly posterUrl: string | null;
    readonly subtitle?: string;          // one line, truncates
    readonly reason?: string;            // wraps to 2 lines, NEVER truncates (§12)
    readonly meta?: ReactNode;           // the meta line: fraction, chips, tags
    readonly onOpen: () => void;         // tap the body → detail sheet
    readonly onPoster?: () => void;      // tap the poster → media sheet; omit ⇒ NOT a button (§11)
    readonly menu?: ReactNode;           // desktop-only « ··· », rendered INSIDE the card (R1)
    readonly strip?: ReactNode;          // full-width own line (R2)
    readonly footer?: ReactNode;         // full-width action row under the strip
  }
  export function AcquisitionCard(props: AcquisitionCardProps): ReactElement;
  ```

- [ ] **Step 1: Write the failing tests**

These encode R1, R2, R3 and the §11 exception as assertions, not as comments.

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AcquisitionCard } from "./AcquisitionCard";

const base = { title: "Silo", posterUrl: null, onOpen: () => {} };

describe("AcquisitionCard", () => {
  it("expose DEUX cibles distinctes : l'affiche et le corps (A13)", async () => {
    const onOpen = vi.fn();
    const onPoster = vi.fn();
    render(<AcquisitionCard {...base} onOpen={onOpen} onPoster={onPoster} />);

    await userEvent.click(screen.getByRole("button", { name: /Fiche de Silo/i }));
    expect(onPoster).toHaveBeenCalledOnce();
    expect(onOpen).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /Silo/ , exact: false }).closest("button")!);
    expect(onOpen).toHaveBeenCalled();
  });

  it("§11 exception — sans onPoster, l'affiche n'est PAS un bouton", () => {
    render(<AcquisitionCard {...base} />);
    expect(screen.queryByRole("button", { name: /Fiche de/i })).toBeNull();
  });

  it("R3 — la ligne du titre ne contient QUE le titre", () => {
    render(
      <AcquisitionCard {...base} meta={<span data-testid="chip">Nouveau</span>} />,
    );
    const titleLine = screen.getByTestId("acq-card-title");
    expect(titleLine).toHaveTextContent("Silo");
    expect(within(titleLine).queryByTestId("chip")).toBeNull();
  });

  it("R2 — la frise est sur sa propre ligne, hors de la rangée du haut", () => {
    render(<AcquisitionCard {...base} strip={<div data-testid="strip" />} />);
    const top = screen.getByTestId("acq-card-top");
    expect(within(top).queryByTestId("strip")).toBeNull();
    expect(screen.getByTestId("strip")).toBeInTheDocument();
  });

  it("R1 — le « ··· » est rendu DANS la carte (il voyage avec elle au balayage)", () => {
    render(<AcquisitionCard {...base} menu={<button data-testid="kebab">···</button>} />);
    const card = screen.getByTestId("acq-card");
    expect(within(card).getByTestId("kebab")).toBeInTheDocument();
  });

  it("§12 — la raison enroule et n'est jamais tronquée par nowrap", () => {
    render(<AcquisitionCard {...base} reason="titre ambigu — 3 candidats proposés" />);
    const reason = screen.getByText(/titre ambigu/);
    expect(reason.className).not.toMatch(/whitespace-nowrap/);
    expect(reason.className).toMatch(/line-clamp-2/);
  });

  it("le sous-titre, lui, tronque sur une ligne", () => {
    render(<AcquisitionCard {...base} subtitle="S02E05 · 1080p WEB-DL · 42 sources" />);
    const sub = screen.getByText(/S02E05/);
    expect(sub.className).toMatch(/truncate/);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/acquisition/AcquisitionCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```tsx
/**
 * AcquisitionCard — the single card grammar of the Acquisition page.
 *
 * Every list (Maintenant's five sections, Suivis' liste and groupé modes) renders
 * through this component, so the spec's transverse rules are enforced once rather
 * than re-derived per surface:
 *
 * - **R1** — the « ··· » lives INSIDE the card, in flow. It used to be
 *   `position: absolute` on the swipe wrapper while the *card* is what translates,
 *   so it stayed put and landed on top of « Retirer ».
 * - **R2** — `strip` and `footer` are full-width own lines, never siblings of the
 *   title row in a `row` flex, which squeezed the journey strip into a narrow
 *   column and overlapped its labels.
 * - **R3** — the title line accepts nothing but the title (§12). Everything that
 *   qualifies the media goes on the meta line, the only one that wraps.
 * - **§11** — the poster is a button only when `onPoster` is given. For an
 *   unidentified media it is not a disabled button, it is not a button at all:
 *   §11 forbids a dead link, and a greyed control is the same broken promise.
 */

import { type ReactElement, type ReactNode } from "react";

import { MediaPoster } from "@/components/ds/MediaPoster";

/** Props for {@link AcquisitionCard}. */
export interface AcquisitionCardProps {
  /** The media title — alone on its line (R3). */
  readonly title: string;
  /** Poster URL, or `null` for the initial-letter placeholder. */
  readonly posterUrl: string | null;
  /** One-line qualifier; truncates. */
  readonly subtitle?: string;
  /** Why this item needs a decision; wraps to two lines and never truncates (§12). */
  readonly reason?: string;
  /** The meta line — fraction, status chip, tags. */
  readonly meta?: ReactNode;
  /** Tap on the body → the detail sheet. */
  readonly onOpen: () => void;
  /** Tap on the poster → the media sheet. Omit when the media has no sheet (§11). */
  readonly onPoster?: () => void;
  /** Desktop-only actions menu, rendered inside the card (R1). */
  readonly menu?: ReactNode;
  /** Full-width own line under the top row (R2) — the journey strip. */
  readonly strip?: ReactNode;
  /** Full-width action row under the strip. */
  readonly footer?: ReactNode;
}

/**
 * Render one acquisition card.
 *
 * Args:
 *   props: See {@link AcquisitionCardProps}.
 *
 * Returns:
 *   The card element.
 */
export function AcquisitionCard({
  title,
  posterUrl,
  subtitle,
  reason,
  meta,
  onOpen,
  onPoster,
  menu,
  strip,
  footer,
}: AcquisitionCardProps): ReactElement {
  const poster = <MediaPoster title={title} src={posterUrl} className="w-[38px]" />;

  return (
    <div
      data-testid="acq-card"
      className="flex w-full flex-col rounded-lg border border-border bg-card p-[9px]"
    >
      <div data-testid="acq-card-top" className="flex min-w-0 items-center gap-[10px]">
        {onPoster ? (
          <button
            type="button"
            className="shrink-0 leading-none"
            aria-label={`Fiche de ${title}`}
            onClick={onPoster}
          >
            {poster}
          </button>
        ) : (
          <span
            className="shrink-0 leading-none"
            title="Média non identifié — pas de fiche disponible."
          >
            {poster}
          </span>
        )}

        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-[10px] text-left"
          onClick={onOpen}
        >
          <span className="block min-w-0 flex-1">
            <span data-testid="acq-card-title" className="block truncate text-sm font-medium">
              {title}
            </span>
            {subtitle != null && (
              <span className="mt-0.5 block truncate text-xs text-muted-foreground">{subtitle}</span>
            )}
            {reason != null && (
              <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
                {reason}
              </span>
            )}
            {meta != null && (
              <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">{meta}</span>
            )}
          </span>
        </button>

        {menu}
      </div>

      {strip}
      {footer}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/components/acquisition/AcquisitionCard.test.tsx`
Expected: all PASS. If the two-target click test is brittle on the body button's accessible name, give the body button an explicit `aria-label={title}` and query by that.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/acquisition/AcquisitionCard.tsx frontend/src/components/acquisition/AcquisitionCard.test.tsx
git commit -m "feat(acq-mobile): AcquisitionCard — grammaire unique des cartes (R1/R2/R3, §11)"
```

---

### Task 6: `JourneyStrip` — the §14.3 stage strip

**Files:**
- Create: `frontend/src/components/acquisition/JourneyStrip.tsx`
- Test: `frontend/src/components/acquisition/JourneyStrip.test.tsx`

**Interfaces:**
- Consumes: nothing.
- Produces:
  ```ts
  export type Stage = "pris" | "telech" | "ingere" | "scrape" | "range";
  export const STAGES: readonly { readonly key: Stage; readonly label: string }[];
  export function JourneyStrip(props: { readonly stage: Stage; readonly blocked?: boolean }): ReactElement;
  ```

- [ ] **Step 1: Write the failing tests**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JourneyStrip, STAGES } from "./JourneyStrip";

describe("JourneyStrip (§14.3)", () => {
  it("les étapes franchies, l'étape courante et celles à venir sont distinctes", () => {
    render(<JourneyStrip stage="ingere" />);
    expect(screen.getByText(/pris — franchie/)).toBeInTheDocument();
    expect(screen.getByText(/ingéré — en cours/)).toBeInTheDocument();
    expect(screen.getByText(/rangé — à venir/)).toBeInTheDocument();
  });

  it("une étape BLOQUÉE est un état à elle, ni « en cours » ni « à venir »", () => {
    render(<JourneyStrip stage="scrape" blocked />);
    expect(screen.getByText(/scrapé — bloquée/)).toBeInTheDocument();
    expect(screen.queryByText(/scrapé — en cours/)).toBeNull();
  });

  it("chaque étape est une piste de largeur égale qui tronque — anti-chevauchement par construction", () => {
    const { container } = render(<JourneyStrip stage="pris" />);
    const stations = container.querySelectorAll("[data-station]");
    expect(stations).toHaveLength(STAGES.length);
    stations.forEach((st) => {
      expect(st.className).toMatch(/min-w-0/);
      expect(st.className).toMatch(/flex-1/);
      const label = st.querySelector("[data-station-label]");
      expect(label?.className).toMatch(/truncate/);
    });
  });

  it("aucun libellé n'est un token machine", () => {
    render(<JourneyStrip stage="telech" />);
    for (const { key } of STAGES) {
      expect(screen.queryByText(key, { exact: true })).toBeNull();
    }
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/acquisition/JourneyStrip.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```tsx
/**
 * JourneyStrip — the §14.3 journey, on its own full-width line.
 *
 * Anti-overlap is GEOMETRIC, not typographic: each station is a `flex-1 min-w-0`
 * track whose label is a full-width truncating block. A label therefore cannot
 * spill onto its neighbour at any width — tuning a font-size would have broken
 * again at the next longer label.
 *
 * `blocked` is a state of its own: neither "now" (it is not moving) nor pending
 * (it was reached and stayed). §14.3 forbids painting an unreached step as if
 * nothing had happened.
 */

import { type ReactElement } from "react";

/** One stage of the acquisition journey. */
export type Stage = "pris" | "telech" | "ingere" | "scrape" | "range";

/** The stages in walking order, with their French labels. */
export const STAGES: readonly { readonly key: Stage; readonly label: string }[] = [
  { key: "pris", label: "pris" },
  { key: "telech", label: "téléch." },
  { key: "ingere", label: "ingéré" },
  { key: "scrape", label: "scrapé" },
  { key: "range", label: "rangé" },
];

/**
 * Render the journey strip.
 *
 * Args:
 *   stage: The stage actually reached.
 *   blocked: Whether the journey is stopped at that stage.
 *
 * Returns:
 *   The strip element.
 */
export function JourneyStrip({
  stage,
  blocked = false,
}: {
  readonly stage: Stage;
  readonly blocked?: boolean;
}): ReactElement {
  const current = STAGES.findIndex((s) => s.key === stage);

  return (
    <div className="mt-[10px] flex w-full border-t border-border pt-[10px]">
      {STAGES.map((s, i) => {
        const done = i < current;
        const here = i === current;
        const said = done ? "franchie" : here ? (blocked ? "bloquée" : "en cours") : "à venir";
        const dot = done
          ? "bg-success border-success"
          : here
            ? blocked
              ? "bg-danger border-danger ring-[3px] ring-danger/25"
              : "bg-info border-info ring-[3px] ring-info/25"
            : "bg-muted border-border";
        const text = here ? (blocked ? "text-danger font-semibold" : "text-info font-semibold") : "text-muted-foreground";

        return (
          <div
            key={s.key}
            data-station={s.key}
            className="relative flex min-w-0 flex-1 flex-col items-center gap-[5px]"
          >
            <span
              aria-hidden="true"
              className={`z-[1] size-[9px] shrink-0 rounded-full border-[1.5px] ${dot}`}
            />
            <span
              data-station-label
              className={`block w-full truncate px-0.5 text-center text-[9.5px] leading-tight ${text}`}
            >
              {s.label}
            </span>
            <span className="sr-only">{`${s.label} — ${said}`}</span>
            {i < STAGES.length - 1 && (
              <span
                aria-hidden="true"
                className={`absolute left-1/2 top-[5px] h-[1.5px] w-full ${done ? "bg-success" : "bg-border"}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/components/acquisition/JourneyStrip.test.tsx`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/acquisition/JourneyStrip.tsx frontend/src/components/acquisition/JourneyStrip.test.tsx
git commit -m "feat(acq-mobile): JourneyStrip — frise de parcours, anti-chevauchement par construction"
```

---

### Task 7: Page shell — two views, « Plus », legacy redirects, badge

> **SPLIT AND CORRECTED 2026-08-06 after validating this task against the code.**
> It is the largest task in the plan and it carried four drifts, one of which was a
> silent regression. It is now **two dispatches**:
>
> - **Task 7a — the page**: `meta.ts` (TABS + redirects), `AcquisitionPage.tsx`
>   rewrite, `PlusSheet.tsx`, **and the `+` control that opens `AddMediaScreen`**
>   (Steps 1-4 below, plus correction 1).
> - **Task 7b — the shell chrome**: the honest badge in `AppShell.tsx` and the
>   §10 notification docking (Steps 5-7 below, as rewritten by corrections 2-3).
>
> **Correction 1 — there is NO FAB, and nothing opens the add screen.** Step 7
> says "position the FAB and the toast container inside it" as if one existed;
> `rg 'FloatingAction|\bFAB\b' frontend/src` returns nothing. Task 12 shipped
> `AddMediaScreen({open, onOpenChange})` and **no surface opens it** — the add
> flow is currently unreachable. Task 7a must create the `+` control and wire it.
> This is the task that makes §7 reachable at all; without it the add flow is
> dead code.
>
> **Correction 2 — do NOT move the `Toaster` into `AppShell`.** Step 6 asserts
> "the dock belongs to whoever owns the bottom bar, which is this shell". It is
> architecturally tempting and factually breaking: the `Toaster` lives in
> `PwaLayer` (`App.tsx:27-38`), a **deliberate router sibling**, and that file's
> own docstring states why — "so the PWA update/install UI is visible on every
> route, **login page included**". `AppShell` renders inside `ProtectedRoute`
> (`router.tsx:47`). Moving the host would silently kill every toast on the login
> page, the PWA update toast among them. **The Toaster stays in `PwaLayer`**; only
> its position changes.
>
> **Correction 3 — a fixed `offset` reproduces the very defect §10 exists to fix.**
> The brief's own comment says a `bottom: 84px` calibrated on desktop pushed the
> notification UNDER the bar. A static sonner `offset` is that same bug with a
> different number. The offset must be **construction-correct**: express it as
> `calc()` over a CSS custom property that the bottom bar itself owns, so it
> tracks the real bar height including `env(safe-area-inset-bottom)`, and
> collapses to zero where there is no bar — `BottomTabBar` is `md:hidden`
> (`BottomTabBar.tsx:34`), and the login page has no bar at all. An unset
> variable must therefore fall back to `0px`, not to a phone-sized guess.
>
> **Correction 4 — the redirect test cannot read `window.location`.** The `it.each`
> case asserts `new URLSearchParams(window.location.search)`, but the suite renders
> through `MemoryRouter` (`AcquisitionPage.test.tsx:172`), which never touches the
> jsdom URL — the assertion would read the ambient location and pass or fail for
> reasons unrelated to the redirect. Assert through a `useLocation` probe instead;
> that test file already imports `useLocation` (`:20`) for exactly this purpose.

**Files:**
- Modify: `frontend/src/pages/AcquisitionPage.tsx`, `frontend/src/components/acquisition/meta.ts` (TABS), `frontend/src/components/layout/AppShell.tsx`, `frontend/src/App.tsx` (Toaster position only — 7b)
- Create: `frontend/src/components/acquisition/PlusSheet.tsx`
- Test: `frontend/src/pages/AcquisitionPage.test.tsx` (rewrite), `frontend/src/components/layout/AppShell.test.tsx` (amend)

**Interfaces:**
- Consumes: `useToHandle` (Task 3), `useWanted`, `useFollowed`, `AddMediaScreen` (Task 12).
- Produces: `TabId = "maintenant" | "suivis"`; `TABS` reduced to those two.

- [ ] **Step 1: Write the failing tests**

```tsx
it("n'expose que deux vues", () => {
  renderPage();
  expect(screen.getAllByRole("tab")).toHaveLength(2);
  expect(screen.getByRole("tab", { name: /Maintenant/ })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /Suivis/ })).toBeInTheDocument();
});

it("n'affiche plus de titre « Acquisition » — la barre du bas le dit déjà (§12/D3)", () => {
  renderPage();
  expect(screen.queryByRole("heading", { name: "Acquisition" })).toBeNull();
});

it.each([
  ["followed", "suivis"],
  ["file", "maintenant"],
  ["apercu", "maintenant"],
  ["obligations", "maintenant"],
  ["watcher", "maintenant"],
  ["parcours", "maintenant"],
  ["reglages", "maintenant"],
  ["wanted", "maintenant"],
  ["downloads", "maintenant"],
])("redirige l'ancien ?tab=%s vers %s sans empiler d'historique", async (legacy, target) => {
  renderPage(`/acquisition?tab=${legacy}`);
  await waitFor(() => {
    expect(new URLSearchParams(window.location.search).get("tab")).toBe(
      target === "maintenant" ? null : target,
    );
  });
});

it("« Plus » ouvre Veille et Obligations", async () => {
  renderPage();
  await userEvent.click(screen.getByRole("button", { name: /Veille et obligations/i }));
  expect(await screen.findByText(/Obligations de partage/i)).toBeInTheDocument();
});
```

And in `AppShell.test.tsx`:

```tsx
it("le badge compte ce qui M'ATTEND : à récupérer + à traiter (D6)", async () => {
  renderShell({ takeable: 2, toHandle: 2, inFlight: 7 });
  expect(await screen.findByLabelText(/4 éléments? à traiter/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/AcquisitionPage.test.tsx src/components/layout/AppShell.test.tsx`
Expected: FAIL — 7 tabs found, title present, badge count wrong.

- [ ] **Step 3: Reduce `TABS` in `meta.ts`**

```ts
/** View ids for the two panels (spec §3). */
export type TabId = "maintenant" | "suivis";

/**
 * The two views.
 *
 * Named after the operator's QUESTIONS, not after data tables. The former seven
 * tabs (apercu / followed / file / obligations / watcher / parcours / reglages)
 * were named after the tables behind them, which is why each of the operator's
 * three real questions cut across several of them.
 */
export const TABS: readonly { id: TabId; label: string }[] = [
  { id: "maintenant", label: "Maintenant" },
  { id: "suivis", label: "Suivis" },
];

/** Old ``?tab=`` values → the view that now answers them (DOIT-10: no dead deep link). */
export const LEGACY_TAB_REDIRECTS: Readonly<Record<string, TabId>> = {
  apercu: "maintenant",
  file: "maintenant",
  wanted: "maintenant",
  downloads: "maintenant",
  obligations: "maintenant",
  watcher: "maintenant",
  parcours: "maintenant",
  reglages: "maintenant",
  followed: "suivis",
};
```

- [ ] **Step 4: Rewrite the shell**

Keep the existing `useSearchParams` + live-event invalidation machinery from the current `AcquisitionPage.tsx` verbatim (the R13 `lastProcessedRef` pattern and the `ACQ_EVENT_TYPES` sets are correct and must survive). Change only:
- the tab list → `TABS` (now two), default `maintenant` carrying no `?tab=` param;
- the redirect effect → drive it from `LEGACY_TAB_REDIRECTS` with `{ replace: true }`;
- delete the `PageHeader` line entirely;
- add the « Plus » trigger button (`aria-label="Veille et obligations"`) opening `<PlusSheet />` in a `Sheet`;
- render `<MaintenantPanel />` / `<SuivisPanel />` — both already exist when this task runs (see **Execution order**: Tasks 8 and 9 ship before this one, precisely so no placeholder is ever written).

`PlusSheet.tsx` moves the existing `WatcherPanel` and `ObligationsPanel` **unchanged** into a `Sheet` body, plus a line stating that the ranking profiles moved to Config. Do not redesign those two panels — out of scope (spec §14).

- [ ] **Step 5: Change the badge source in `AppShell.tsx`**

Replace the `pendingWanted` computation feeding `map["/acquisition"]` with `takeableCount + toHandleCount`, read from `useFollowed` (`status === "a_recuperer"`) and `useToHandle` (`items.length`). Add a comment recording why:

```ts
// Le badge compte CE QUI ATTEND L'OPÉRATEUR, pas ce qui se passe : à récupérer +
// à traiter. Un item en vol n'attend rien de lui. L'ancien `pendingWanted`
// annonçait 3 et faisait atterrir sur une vue affichant 0/0/0/59 (D6).
```

- [ ] **Step 6: Write the failing notification test (spec §10)**

The dock belongs to whoever owns the bottom bar, which is this shell. In
`frontend/src/components/layout/AppShell.test.tsx`:

```tsx
it("§10 — la notification ne passe jamais sous la barre du bas, zone sûre comprise", async () => {
  renderShell();
  // Simule le home indicator d'un iPhone : la barre grandit de 34px.
  const bar = screen.getByRole("navigation");
  bar.style.paddingBottom = "34px";

  toast("Un message de deux lignes assez long pour occuper toute la largeur disponible.");
  const el = await screen.findByRole("status");

  expect(el.getBoundingClientRect().bottom).toBeLessThanOrEqual(bar.getBoundingClientRect().top);
});

it("§10 — la notification porte une croix qui la ferme", async () => {
  renderShell();
  toast("Coucou");
  await userEvent.click(await screen.findByRole("button", { name: /Fermer la notification/i }));
  await waitFor(() => { expect(screen.queryByRole("status")).toBeNull(); });
});
```

Run: `cd frontend && npx vitest run src/components/layout/AppShell.test.tsx`
Expected: FAIL — the toast is positioned by a fixed offset and has no close control.

- [ ] **Step 7: Implement the dock**

Render a **zero-height dock** as a flow sibling immediately above `<BottomTabBar>`:
`<div className="relative h-0" />`. Position the FAB and the toast container inside it
(`absolute bottom-4` and `absolute bottom-[82px]` respectively — 16 + 54 + 12, so the toast
sits above the FAB rather than on it).

Give the dock `position: relative` **without** a `z-index`: it must not create a stacking
context, or the toast could no longer rise above the full-screen add / media surfaces while the
FAB stays under them.

Configure `sonner` with `duration: 5000` and a close button. Record the reason in a comment:

```tsx
// Ancré au quai plutôt qu'à une distance du bas de l'écran : la barre grandit de
// env(safe-area-inset-bottom) (~34px sur iPhone), et un `bottom: 84px` calibré sur
// desktop faisait passer la notification SOUS la barre. Le quai rend la position
// correcte par construction, à n'importe quelle hauteur de barre (R4).
```

- [ ] **Step 8: Run the tests and the gates**

Run: `cd frontend && npx vitest run src/pages/AcquisitionPage.test.tsx src/components/layout/AppShell.test.tsx`
Then: `npm run lint && npx tsc -b --noEmit && npm run test`

- [ ] **Step 9: Commit**

```bash
git add -A frontend/src
git commit -m "feat(acq-mobile): coquille à deux vues, « Plus » au second rang, badge honnête, quai de notifications (D3/D4/D6, §10)"
```

---

### Task 8: `MaintenantPanel` — five sections including « À traiter »

**Files:**
- Create: `frontend/src/components/acquisition/MaintenantPanel.tsx`
- Test: `frontend/src/components/acquisition/MaintenantPanel.test.tsx`
- Delete: `frontend/src/components/acquisition/OverviewPanel.tsx` + its test

**Interfaces:**
- Consumes: `AcquisitionCard` (T5), `JourneyStrip` (T6), `useToHandle` (T3), `useFollowed`, `useWanted`, `useDownloads`.
- Produces: `MaintenantPanel(): ReactElement`.

- [ ] **Step 1: Write the failing tests**

```tsx
it("ordonne les sections par ce qui attend l'opérateur d'abord", async () => {
  renderPanel(fixtures.full);
  const heads = await screen.findAllByTestId("section-head");
  expect(heads.map((h) => h.textContent)).toEqual([
    expect.stringContaining("À récupérer"),
    expect.stringContaining("À traiter"),
    expect.stringContaining("En vol"),
    expect.stringContaining("Cherché, rien trouvé"),
    expect.stringContaining("Rangé aujourd'hui"),
  ]);
});

it("la frise n'apparaît QUE sur « en vol » et « à traiter » (A5)", async () => {
  renderPanel(fixtures.full);
  const takeable = await screen.findByTestId("section-a-recuperer");
  expect(within(takeable).queryByTestId("acq-card")?.querySelector("[data-station]")).toBeNull();
  const inflight = screen.getByTestId("section-en-vol");
  expect(within(inflight).getAllByTestId("acq-card")[0].querySelector("[data-station]")).toBeTruthy();
});

it("un bloqué affiche sa raison ENTIÈRE et l'action sous la frise (§12)", async () => {
  renderPanel(fixtures.full);
  expect(await screen.findByText("titre ambigu — 3 candidats proposés")).toBeInTheDocument();
  const card = screen.getByTestId("section-a-traiter").querySelector("[data-testid=acq-card]")!;
  const resolve = within(card as HTMLElement).getByRole("button", { name: /Résoudre/ });
  const strip = (card as HTMLElement).querySelector("[data-station]")!;
  expect(strip.compareDocumentPosition(resolve) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("les bloqués sans provenance ne sont pas listés mais ne sont pas tus non plus", async () => {
  renderPanel({ ...fixtures.full, toHandle: { items: [], orphan_count: 2 } });
  expect(screen.queryByTestId("section-a-traiter")).toBeInTheDocument();
  expect(
    await screen.findByRole("link", { name: /2 autres médias à traiter.*Contrôle/i }),
  ).toHaveAttribute("href", "/controle");
});

it("« À traiter » disparaît quand il n'y a ni item ni orphelin", () => {
  renderPanel({ ...fixtures.full, toHandle: { items: [], orphan_count: 0 } });
  expect(screen.queryByTestId("section-a-traiter")).toBeNull();
});

it("l'état vide ne prétend jamais que tout va bien alors qu'une pile est non nulle", () => {
  renderPanel({ ...fixtures.empty, toHandle: { items: [], orphan_count: 3 } });
  expect(screen.queryByText(/Rien en vol/)).toBeNull();
});
```

- [ ] **Step 2: Run to verify failure** — `npx vitest run src/components/acquisition/MaintenantPanel.test.tsx`, module not found.

- [ ] **Step 3: Implement the panel**

Section headers are `<button data-testid="section-head">` carrying pip + label + count, each section wrapped in `<section data-testid="section-<slug>">`. Section order is the constant

```ts
const SECTIONS = ["a-recuperer", "a-traiter", "en-vol", "cherche-rien-trouve", "range-aujourdhui"] as const;
```

so the order is data, not a rendering accident. Cards come from `AcquisitionCard`; `en-vol` and `a-traiter` pass `strip={<JourneyStrip stage={…} blocked={…} />}`; `a-traiter` also passes `footer={<Button className="w-full" …>Résoudre →</Button>}` linking to the resolution deck for that `decision_id` (reuse the href builder `ATraiterList.tsx` already uses — grep it, do not invent a second one).

The crossref is a `<Link to="/controle">` with the orphan sentence.

- [ ] **Step 4: Run the tests** — all PASS.

- [ ] **Step 5: Delete `OverviewPanel`**

```bash
git rm frontend/src/components/acquisition/OverviewPanel.tsx frontend/src/components/acquisition/OverviewPanel.test.tsx
```

Its four tiles are now the section headers of this panel — a number that opens nothing was a dead end (NE-DOIT-PAS-9); a section header *is* its own drill-down.

- [ ] **Step 6: Gates and commit**

```bash
cd frontend && npm run lint && npx tsc -b --noEmit && npm run test
git add -A && git commit -m "feat(acq-mobile): MaintenantPanel — cinq sections dont « À traiter » (§14.3)"
```

---

### Task 9: `SuivisPanel` — filters, switcher, three modes

**Files:**
- Create: `frontend/src/components/acquisition/SuivisPanel.tsx`, `frontend/src/components/acquisition/useViewMode.ts`
- Test: `frontend/src/components/acquisition/SuivisPanel.test.tsx`, `frontend/src/components/acquisition/useViewMode.test.ts`

**Interfaces:**
- Produces:
  ```ts
  export type ViewMode = "list" | "group" | "grid";
  export function useViewMode(): readonly [ViewMode, (m: ViewMode) => void];
  export function SuivisPanel(): ReactElement;
  ```

- [ ] **Step 1: Write the failing tests**

```ts
// useViewMode.test.ts
it("démarre en liste (A8)", () => {
  expect(renderHook(() => useViewMode()).result.current[0]).toBe("list");
});

it("mémorise le mode localement et le relit au montage (A7)", () => {
  const { result, unmount } = renderHook(() => useViewMode());
  act(() => { result.current[1]("grid"); });
  unmount();
  expect(renderHook(() => useViewMode()).result.current[0]).toBe("grid");
});

it("le mode n'entre JAMAIS dans l'URL — ?tab= reste la seule chose partageable (DOIT-10)", () => {
  const { result } = renderHook(() => useViewMode());
  act(() => { result.current[1]("group"); });
  expect(window.location.search).not.toMatch(/mode|vue|view/);
});

it("survit à un localStorage indisponible (navigation privée)", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("QuotaExceeded"); });
  const { result } = renderHook(() => useViewMode());
  expect(() => act(() => { result.current[1]("grid"); })).not.toThrow();
  expect(result.current[0]).toBe("grid");
});
```

```tsx
// SuivisPanel.test.tsx
it("les sous-onglets Séries/Films sont devenus des puces de filtre", async () => {
  renderPanel();
  expect(screen.queryByRole("tab", { name: "Séries" })).toBeNull();
  expect(await screen.findByRole("button", { name: /Séries\s*13/ })).toBeInTheDocument();
});

it("n'a plus qu'UN champ, celui qui filtre (D2)", () => {
  renderPanel();
  expect(screen.getAllByRole("searchbox")).toHaveLength(1);
  expect(screen.getByPlaceholderText(/Filtrer par nom/)).toBeInTheDocument();
});

it("mode groupé : l'état monte dans l'en-tête et quitte les lignes (§12)", async () => {
  renderPanel();
  await userEvent.click(screen.getByRole("button", { name: "Groupé par état" }));
  const section = screen.getByTestId("group-a-jour");
  expect(within(section).getByTestId("section-head")).toHaveTextContent("À jour");
  expect(within(section).queryByText("À jour", { selector: "[data-slot=badge]" })).toBeNull();
});

it("mode grille : la pastille porte un NOMBRE, et rien à faire ⇒ pas de pastille", async () => {
  renderPanel();
  await userEvent.click(screen.getByRole("button", { name: "Grille d'affiches" }));
  expect(screen.getByTestId("tile-silo").querySelector("[data-badge]")).toHaveTextContent("1");
  expect(screen.getByTestId("tile-rick-and-morty").querySelector("[data-badge]")).toBeNull();
});

it("le commutateur est séparé des puces par un séparateur, pas par un dégradé (A9)", () => {
  renderPanel();
  const group = screen.getByRole("group", { name: "Mode d'affichage" });
  expect(group.parentElement?.className).toMatch(/border-l/);
  expect(group.parentElement?.className).not.toMatch(/gradient/);
});
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement `useViewMode`**

```ts
/**
 * The « Suivis » display mode, persisted per browser / PWA install.
 *
 * Deliberately NOT in the URL (A7): the mode is a preference, not a location.
 * `?tab=` stays the only shareable state (DOIT-10) — a mode in the URL would make
 * every shared link impose the sender's habit on the receiver.
 */
import { useCallback, useState } from "react";

/** The three display modes of the Suivis view. */
export type ViewMode = "list" | "group" | "grid";

const KEY = "tm.follows.viewmode";
const MODES: readonly ViewMode[] = ["list", "group", "grid"];

/**
 * Read and write the persisted display mode.
 *
 * Returns:
 *   The current mode and a setter. Storage failures (private browsing, quota)
 *   are swallowed: the mode still applies for the session — a preference must
 *   never be able to break the page.
 */
export function useViewMode(): readonly [ViewMode, (m: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>(() => {
    try {
      const stored = localStorage.getItem(KEY);
      return MODES.includes(stored as ViewMode) ? (stored as ViewMode) : "list";
    } catch {
      return "list";
    }
  });

  const set = useCallback((next: ViewMode) => {
    setMode(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* private mode — the session keeps the choice, it just will not survive. */
    }
  }, []);

  return [mode, set] as const;
}
```

- [ ] **Step 4: Implement `SuivisPanel`**

Sticky filter zone: one `<input type="search" placeholder="Filtrer par nom">`, then a row whose left part is the horizontally-scrolling pill train (`Tout` / `Séries` / `Films` / `En pause`, each with its count) and whose right part is the switcher wrapper — `flex-none pl-2 border-l border-border bg-background` (A9's mitigation: hard divider, solid ground, **never** a gradient fade).

Sorting: `URGENCY = { a_recuperer: 0, en_acquisition: 1, en_attente: 2, non_verifie: 3, a_jour: 4, disabled: 5 }`, then title with `localeCompare(…, "fr")`.

Grid badge count: `Math.max(1, (aired ?? 0) - (owned ?? 0))` for actionable states, `?` for `non_verifie`, **no badge** for `a_jour`.

- [ ] **Step 5: Run the tests, then the gates.**

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src && git commit -m "feat(acq-mobile): SuivisPanel — filtres, commutateur trois modes, mode mémorisé localement"
```

---

### Task 10: `FollowDetailSheet` — matrix, collapse rules, one derivation

**Files:**
- Create: `frontend/src/components/acquisition/FollowDetailSheet.tsx`
- Test: `frontend/src/components/acquisition/FollowDetailSheet.test.tsx`
- Delete: `frontend/src/components/acquisition/CompletenessAccordion.tsx` + test — **only after** the matrix here passes, and reuse its episode-state → tone/label mapping from `meta.ts` rather than re-deriving it.

**Interfaces:**
- Consumes: `useCompleteness(id, enabled)`, `EPISODE_STATE_TONE`, `EPISODE_STATE_LABEL`, `EPISODE_LEGEND_ORDER`, `actionWords`.
- Produces: `FollowDetailSheet(props: { readonly followedId: number; readonly open: boolean; readonly onOpenChange: (o: boolean) => void }): ReactElement`.

- [ ] **Step 1: Write the failing tests**

```tsx
it("§13 — la fraction de la carte, l'en-tête et la somme des saisons disent le même nombre", async () => {
  renderSheet(silo);            // S01 10/10 ; S02 15 épisodes dont 1 à récupérer et 1 annoncé
  expect(await screen.findByTestId("sheet-meta")).toHaveTextContent("23/24 en médiathèque");
  const perSeason = screen.getAllByTestId("season-fraction").map((n) => n.textContent!);
  const owned = perSeason.reduce((a, t) => a + Number(t.split("/")[0]), 0);
  const aired = perSeason.reduce((a, t) => a + Number(t.split("/")[1]), 0);
  expect(`${owned}/${aired}`).toBe("23/24");
});

it("un épisode annoncé n'est pas diffusé : il ne peut pas manquer au dénominateur", async () => {
  renderSheet(silo);
  expect(await screen.findByTestId("season-2-fraction")).toHaveTextContent("13/14");
});

it("gros catalogue : la saison la plus récente est en tête", async () => {
  renderSheet(americanDad);     // 21 saisons
  const names = (await screen.findAllByTestId("season-name")).map((n) => n.textContent);
  expect(names[0]).toBe("Saison 21");
});

it("une saison complète est repliée, une incomplète est ouverte et signalée", async () => {
  renderSheet(americanDad);
  expect(await screen.findByTestId("season-21")).toHaveAttribute("open");
  expect(within(screen.getByTestId("season-21")).getByText(/1 manquant/)).toBeInTheDocument();
  expect(screen.getByTestId("season-19")).not.toHaveAttribute("open");
});

it("la légende est AU-DESSUS de la matrice", async () => {
  renderSheet(americanDad);
  const legend = await screen.findByTestId("episode-legend");
  const first = screen.getByTestId("season-21");
  expect(legend.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("l'écran s'ouvre sur l'état, pas sur sept boutons", async () => {
  renderSheet(silo);
  const legend = await screen.findByTestId("episode-legend");
  const secondary = screen.getByTestId("secondary-actions");
  expect(legend.compareDocumentPosition(secondary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("§5 — la fiche d'un film non acquis annonce le retrait automatique", async () => {
  renderSheet(movieNotOwned);
  expect(await screen.findByText(/quittera automatiquement votre liste/)).toBeInTheDocument();
});

it("§11 — sans identifiant résolu, « Voir la fiche » est absent et une phrase l'explique", async () => {
  renderSheet(unresolved);
  expect(screen.queryByRole("button", { name: "Voir la fiche" })).toBeNull();
  expect(await screen.findByText(/n'a pas pu être résolu/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

Derivation helper — the single computation the three surfaces read (§13):

```ts
/**
 * Owned / aired counts for a season.
 *
 * The card fraction, the sheet header and every season header answer the SAME
 * question, so they must read the SAME computation. An announced episode is not
 * aired and therefore can never be missing from the denominator.
 *
 * Args:
 *   episodes: The season's episodes as served.
 *
 * Returns:
 *   `{ owned, aired }`.
 */
export function seasonCounts(
  episodes: readonly { readonly state: string }[],
): { readonly owned: number; readonly aired: number } {
  return {
    owned: episodes.filter((e) => e.state === "en_mediatheque").length,
    aired: episodes.filter((e) => e.state !== "annonce").length,
  };
}
```

Seasons render reversed, each as `<details data-testid={`season-${n}`} open={owned !== aired}>`; the summary carries name, a « N manquant(s) » chip when incomplete, and the fraction. Episodes are 31×27 pills with `sr-only` state text. Legend before the seasons. Secondary actions last.

- [ ] **Step 4: Run the tests.**

- [ ] **Step 5: Retire `CompletenessAccordion` and commit**

```bash
git rm frontend/src/components/acquisition/CompletenessAccordion.tsx frontend/src/components/acquisition/CompletenessAccordion.test.tsx
git add -A frontend/src
git commit -m "feat(acq-mobile): feuille de détail — matrice en pastilles, une seule dérivation (§13)"
```

---

### Task 11: Media sheet wiring (§11)

**Files:**
- Modify: `frontend/src/components/acquisition/MaintenantPanel.tsx`, `SuivisPanel.tsx`, `FollowDetailSheet.tsx`
- Modify: `frontend/src/components/media/__tests__/constitution.test.tsx` (extend `WIRED_SURFACES`)

**Interfaces:**
- Consumes: `mediaSheetHref` from `@/lib/media-href` (already used by `MediaSearchAdd.tsx:27`).
- Produces: nothing new — it wires `onPoster` and the « Voir la fiche » action to `mediaSheetHref`.

- [ ] **Step 1: Extend the constitution test**

Add the new surfaces to the existing `WIRED_SURFACES` array (`constitution.test.tsx:129`) — the file's own comment says that array is the single source of truth and that adding a surface means adding it there. Add `AcquisitionCard` (poster), `MaintenantPanel`, `SuivisPanel` (liste, groupé, grille), `FollowDetailSheet`.

**Also migrate the add surface (added 2026-08-06).** That test currently registers `MediaSearchAdd` as a covered
surface and renders it (`:117`, `:130`, `:315-363`). Task 12 built its replacement, `AddMediaScreen`, and Task 15
deletes the old component — so this task must repoint the surface to `AddMediaScreen`, keeping the same §11
assertion (opening a result leads to the media sheet). Leave `MediaSearchAdd` itself on disk; Task 15 owns the
deletion and re-checks that nothing imports it.

- [ ] **Step 2: Run to verify failure** — the new entries have no wiring yet.

- [ ] **Step 3: Wire**

`onPoster` is passed **only** when `mediaSheetHref(item)` returns non-null; when it returns null the prop is omitted, so `AcquisitionCard` renders a non-button poster (T5 already enforces this). « Voir la fiche » in the sheet is rendered under the same condition, with the explanatory line in the `else`.

- [ ] **Step 4: Run the constitution test + the panel tests.**

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src && git commit -m "feat(acq-mobile): l'affiche mène à la fiche, et l'exception §11 est tenue"
```

---

### Task 12: `AddMediaScreen` — the add flow

**Files:**
- Create: `frontend/src/components/acquisition/AddMediaScreen.tsx`
- Test: `frontend/src/components/acquisition/AddMediaScreen.test.tsx`
- **Do NOT delete `MediaSearchAdd.tsx`** — corrected 2026-08-06 against the code. It is still rendered by
  `AcquisitionPage.tsx:217` (rewritten in Task 7) and still imported by
  `components/media/__tests__/constitution.test.tsx:117` (migrated in Task 11). Deleting it here breaks
  the build. Its removal belongs to Task 15, behind that task's "prove nothing still imports them" gate.

**Interfaces:**
- Consumes: `useMediaSearch(q, kind)`, `useFollow()`, `buildIdFollowBody` (`@/hooks/useFollowedPanel`).
- Produces: `AddMediaScreen(props: { readonly open: boolean; readonly onOpenChange: (o: boolean) => void }): ReactElement`.

- [ ] **Step 1: Write the failing tests**

```tsx
it("n'interroge le fournisseur qu'à la validation, jamais à la frappe", async () => {
  const spy = vi.fn();
  renderAdd({ onSearch: spy });
  await userEvent.type(screen.getByRole("searchbox"), "Dune");
  expect(spy).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Chercher" }));
  expect(spy).toHaveBeenCalledWith("Dune", undefined);
});

it("§8 — affiche le total du fournisseur, pas le nombre de lignes", async () => {
  renderAdd({ results: 5, total: 81 });
  expect(await screen.findByText(/5 résultats affichés sur 81 trouvés/)).toBeInTheDocument();
});

it("chaque résultat porte année, type et fournisseur — ce qui départage deux homonymes", async () => {
  renderAdd({ results: [{ title: "Dune", year: 2019, kind: "tv", provider: "tvdb" },
                        { title: "Dune", year: 2013, kind: "movie", provider: "tmdb" }] });
  expect(await screen.findByText("2019 · Série · TVDB")).toBeInTheDocument();
  expect(screen.getByText("2013 · Film · TMDB")).toBeInTheDocument();
});

it("A14 — un film s'ajoute, une série se suit", async () => {
  renderAdd({ results: [{ title: "Dune", kind: "movie" }, { title: "Silo", kind: "tv" }] });
  expect(await screen.findByRole("button", { name: "Ajouter" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Suivre" })).toBeInTheDocument();
});

it("§5 — un film déjà en médiathèque demande AVANT de suivre", async () => {
  const follow = vi.fn();
  renderAdd({ results: [{ title: "Blade Runner 2049", kind: "movie", already_owned: true }], onFollow: follow });
  await userEvent.click(await screen.findByRole("button", { name: "Ajouter…" }));
  expect(follow).not.toHaveBeenCalled();
  expect(screen.getByText(/REMPLACERA la version en place/i)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remplacer" }));
  expect(follow).toHaveBeenCalledOnce();
});

it("l'état déjà-suivi est SUR le bouton, sans étiquette redondante (§12)", async () => {
  renderAdd({ results: [{ title: "Silo", kind: "tv", followed: true }] });
  const btn = await screen.findByRole("button", { name: "✓ Suivi" });
  expect(btn).toBeDisabled();
  expect(screen.queryByText(/déjà dans vos suivis/)).toBeNull();
});

it("zéro résultat n'est jamais un écran blanc (§3)", async () => {
  renderAdd({ results: [] , query: "zzzz" });
  expect(await screen.findByText(/Aucun résultat pour « zzzz »/)).toBeInTheDocument();
  expect(screen.getByRole("group", { name: /identifiant/i })).toBeInTheDocument();
});

it("ajout par ID : la notation scientifique est refusée et le bouton dit pourquoi", async () => {
  renderAdd({});
  await userEvent.type(screen.getByLabelText(/Identifiant/), "12e34");
  expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
  expect(screen.getByText(/entrez un nombre entier positif/)).toBeInTheDocument();
});

it("un ID TVDB non résolu est AVOUÉ, pas tu", async () => {
  renderAdd({ followResult: { tvdb_unresolved: true } });
  await addById("tt0903747", "imdb");
  expect(await screen.findByText(/détection d'épisodes.*indisponible/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

A full-screen overlay. **Corrected 2026-08-06 against the code:** the original instruction said to follow whatever
full-screen pattern the codebase already uses — there is none. `rg 'h-dvh|h-screen' frontend/src` returns nothing, and
the only bottom-sheet convention is `Sheet side="bottom"` capped at `max-h-[85vh]` (`FollowDetailSheet.tsx:220-221`,
Task 10), over a primitive that hardcodes `max-h-[80vh]` (`ui/sheet.tsx:27`). **You are establishing the first
full-screen surface**, so you must override that cap rather than inherit it, and the spec says why: §7 — « A full
screen, not a low sheet: **the keyboard eats half the phone** ». A results list under an open keyboard inside 80vh is
exactly the failure the spec names. Use `h-dvh` (not `h-screen`: on iOS Safari `100vh` excludes the retracting URL bar
and overflows), keep `pb-[env(safe-area-inset-bottom)]`, and make the results list the only scrolling region so the
search field stays reachable.

Search form submits on `onSubmit` only. Results as a **vertical list**, each row: poster 54×81, title, `{year} · {Film|Série} · {PROVIDER}`, two-line clamped overview, and the action button whose label comes from `actionWords(kind)`.

The by-ID block is a `<details>` with provider segmented control, validated input (`/^[0-9]+$/` for tvdb/tmdb, `/^tt[0-9]{7,}$/` for imdb) and an error line — reuse `buildIdFollowBody`, do not re-implement it.

After a successful follow: mark the row done, show the footer bar with the count and a « Voir mes suivis → » action.

- [ ] **Step 4: Run the tests.** `MediaSearchAdd` stays on disk and stays wired — see the Files note above.
      Both components coexist until Task 15. Do not "clean up" the old one.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src && git commit -m "feat(acq-mobile): écran d'ajout — liste verticale, total fournisseur, confirmation §5"
```

---

### Task 13: Gestures — view swipe and pull-to-refresh

**Files:**
- Create: `frontend/src/components/acquisition/gestures.ts`
- Test: `frontend/src/components/acquisition/gestures.test.ts`
- Modify: `frontend/src/pages/AcquisitionPage.tsx`

**Interfaces:**
- Produces:
  ```ts
  export const EDGE_DEAD_ZONE_PX = 30;
  export const VIEW_SWIPE_RATIO = 0.28;
  export const PULL_THRESHOLD_PX = 64;
  export function lockAxis(dx: number, dy: number, slop?: number): "x" | "y" | null;
  export function shouldStartViewSwipe(startX: number, containerLeft: number): boolean;
  export function viewSwipeResult(dx: number, width: number, current: "maintenant" | "suivis"): "maintenant" | "suivis";
  ```

- [ ] **Step 1: Write the failing tests**

Pure functions, so the arbitration is testable without a DOM gesture harness.

```ts
it("ignore un geste parti du bord gauche — iOS y réserve le retour", () => {
  expect(shouldStartViewSwipe(12, 0)).toBe(false);
  expect(shouldStartViewSwipe(31, 0)).toBe(true);
});

it("ne verrouille aucun axe sous le seuil de bruit", () => {
  expect(lockAxis(3, 4)).toBeNull();
  expect(lockAxis(12, 3)).toBe("x");
  expect(lockAxis(3, 12)).toBe("y");
});

it("un glissement trop court revient à la vue de départ", () => {
  expect(viewSwipeResult(-40, 390, "maintenant")).toBe("maintenant");
  expect(viewSwipeResult(-140, 390, "maintenant")).toBe("suivis");
  expect(viewSwipeResult(140, 390, "suivis")).toBe("maintenant");
});

it("un glissement au-delà de la dernière vue ne dépasse pas", () => {
  expect(viewSwipeResult(-300, 390, "suivis")).toBe("suivis");
  expect(viewSwipeResult(300, 390, "maintenant")).toBe("maintenant");
});
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement the helpers, then wire them**

In `AcquisitionPage.tsx`: pointer handlers on the pager that (a) bail out when the event target is inside `[data-swipe]` — **the card owns a gesture that starts on it** — and (b) bail out inside the edge dead zone. The scroller gets `overscroll-behavior-y: contain` (Tailwind `overscroll-y-contain`) so the browser's own pull-to-refresh cannot reload the page, and a pull indicator driven by `PULL_THRESHOLD_PX`.

Add a comment at the arbitration site:

```ts
// Deux gestes horizontaux se disputent la même surface. Arbitrage : un geste qui
// PART d'une carte appartient à la carte ; partout ailleurs il change de vue.
// Conséquence assumée : dans les zones denses en cartes, le changement de vue
// passe surtout par les onglets. À éprouver au doigt sur staging (A16).
```

- [ ] **Step 4: Run the tests and gates.**

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src && git commit -m "feat(acq-mobile): swipe entre les vues + tirer pour rafraîchir, avec leurs conflits arbitrés"
```

---

### Task 14: Gestures — card swipe actions and the desktop « ··· »

**Files:**
- Create: `frontend/src/components/acquisition/SwipeActions.tsx`
- Test: `frontend/src/components/acquisition/SwipeActions.test.tsx`
- Modify: `AcquisitionCard` call sites to wrap in `SwipeActions`

**Interfaces:**
- Produces:
  ```ts
  export interface SwipeAction { readonly key: string; readonly label: string; readonly icon: ReactNode; readonly tone: "primary" | "neutral" | "danger"; readonly onRun: () => void }
  export function SwipeActions(props: { readonly left?: SwipeAction; readonly right?: readonly SwipeAction[]; readonly children: ReactNode }): ReactElement;
  ```

- [ ] **Step 1: Write the failing tests**

```tsx
it("R1 — le « ··· » n'existe qu'au pointeur fin", () => {
  matchMediaMock("(hover: hover) and (pointer: fine)", false);
  renderCard();
  expect(screen.queryByRole("button", { name: /Actions pour/ })).toBeNull();
  matchMediaMock("(hover: hover) and (pointer: fine)", true);
  renderCard();
  expect(screen.getByRole("button", { name: /Actions pour/ })).toBeInTheDocument();
});

it("le « ··· » ouvre EXACTEMENT le même bloc d'actions que la feuille", async () => {
  renderCardDesktop();
  await userEvent.click(screen.getByRole("button", { name: /Actions pour/ }));
  const fromMenu = screen.getAllByTestId("action-item").map((b) => b.textContent);
  await userEvent.click(screen.getByTestId("acq-card-body"));
  const fromSheet = screen.getAllByTestId("action-item").map((b) => b.textContent);
  expect(fromMenu).toEqual(fromSheet);
});

it("une action destructrice reste atteignable sans balayage (A11)", async () => {
  renderCardTouch();
  await userEvent.click(screen.getByTestId("acq-card-body"));
  expect(await screen.findByRole("button", { name: /Retirer/ })).toBeInTheDocument();
});

it("R6 — retirer un suivi ne laisse aucune ligne qui le référence", async () => {
  const { store } = renderPageWithMovieInFlight();
  await removeFollow("Le Robot sauvage");
  expect(store.takeable.some((r) => r.fid === 14)).toBe(false);
  expect(store.blocked.some((r) => r.fid === 14)).toBe(false);
  expect(store.inflight.some((r) => r.fid === 14)).toBe(false);
  expect(screen.queryByText("Le Robot sauvage")).toBeNull();
});
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

`SwipeActions` renders an absolutely-positioned action layer behind `children`, and translates **the card** (not the wrapper) on pointer drag. Action buttons are `flex-none basis-[84px]` with `text-center` and wrapping labels, so « Ne plus chercher » fits.

**Do not name any class `grab`** — R5: the sheet handle already owns that name, and at equal specificity the later declaration wins, which once painted the « Récupérer » action as a 36×4 px grey pill.

The « ··· » is rendered by the card's `menu` prop (T5), gated on `useMediaQuery("(hover: hover) and (pointer: fine)")`, and opens the shared action list — the same array the detail sheet renders, exported once from `FollowDetailSheet.tsx` as `useFollowActions(followedId)`.

- [ ] **Step 4: Run the tests and gates.**

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src && git commit -m "feat(acq-mobile): actions par balayage + « ··· » desktop, une seule liste d'actions"
```

---

### Task 15: Retire the old panels and move the ranking editor

**Files:**
- Delete: `FileDAcquisitionPanel.tsx` (+test), `WantedPanel.tsx`, `ParcoursPanel.tsx` (+test), `FollowedPanel.tsx` (+test), `MediaSearchAdd.tsx` (+test — moved here from Task 12 on 2026-08-06; it stayed wired until Task 7 swapped the page and Task 11 repointed the constitution surface), `EpisodeStateLegende.tsx` (if now unused), `EpisodeDatePopover.tsx` (if now unused)
- Move: `ReglagesPanel.tsx` → `frontend/src/components/config/RankingPanel.tsx`, rendered from `pages/Config.tsx`
- Modify: `frontend/src/components/acquisition/meta.ts` — drop now-dead exports

**Interfaces:** none new.

- [ ] **Step 1: Prove nothing still imports them**

Run: `cd frontend && command rg -g '*.tsx' -g '*.ts' -n "FileDAcquisitionPanel|WantedPanel|ParcoursPanel|FollowedPanel|ReglagesPanel|MediaSearchAdd" src`
Expected: only the files themselves and their tests. Any other hit is a task that is not finished — go fix it before deleting.

- [ ] **Step 2: Move the ranking editor**

`git mv frontend/src/components/acquisition/ReglagesPanel.tsx frontend/src/components/config/RankingPanel.tsx` (same for its test), update its imports, and render it from `Config.tsx` under its own heading. Its internals do not change — it is a move, not a redesign.

- [ ] **Step 3: Delete the dead panels**

```bash
git rm frontend/src/components/acquisition/FileDAcquisitionPanel.tsx frontend/src/components/acquisition/FileDAcquisitionPanel.test.tsx \
       frontend/src/components/acquisition/WantedPanel.tsx \
       frontend/src/components/acquisition/ParcoursPanel.tsx frontend/src/components/acquisition/ParcoursPanel.test.tsx \
       frontend/src/components/acquisition/FollowedPanel.tsx frontend/src/components/acquisition/FollowedPanel.test.tsx
```

- [ ] **Step 4: Prune dead exports from `meta.ts`**

Remove `WANTED_STATUS_OPTIONS`, `OBLIGATION_STATUS_OPTIONS` **only if** nothing imports them (`rg` first — `ObligationsPanel` still lives in the Plus sheet and may still use them). Leave anything still referenced. Deleting a live export to tidy up is how a green typecheck turns into a red CI.

- [ ] **Step 5: Full gates**

Run: `cd frontend && npm run lint && npx tsc -b --noEmit && npm run test`
Run: `cd .. && make test`
Expected: 0 failures.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor(acq-mobile): retirer les panneaux remplacés, déplacer l'éditeur de classement dans Config"
```

---

### Task 17: Open staging's write path — acquisition and decisions only (A18)

Added during execution. Dispatched right after Task 3 (see **Execution order**), because staging must accept these
writes before any mutating UI journey exists to validate.

**Files:**
- Modify: `personalscraper/web/deps.py` (docstring of `require_not_staging` — it currently claims to guard every
  mutating POST, which stops being true)
- Modify: `personalscraper/web/routes/acquisition.py` (3 sites), `acquisition_triggers.py` (5 sites),
  `acquisition_seasons.py` (1 site), `decisions.py` (2 sites)
- Test: `tests/unit/web/routes/test_staging_write_policy.py` (create)

**Interfaces:**
- Consumes: `is_staging_role()` / `require_not_staging` from `personalscraper/web/deps.py`.
- Produces: no new symbol. The policy is expressed by *which routes carry the dependency*, and asserted by one test.

- [ ] **Step 1: Write the failing policy test**

The policy must be asserted as data, not left to eleven scattered edits nobody re-reads. Enumerate the app's routes
and check the guard's presence against an explicit table — so that a future route added to a guarded family without
the dependency fails this test.

```python
"""The staging write policy (A18) — asserted as a table, not as eleven edits."""

import inspect

from fastapi.routing import APIRoute

# Families whose writes are OPEN on staging: their worst case is a repairable row.
_OPEN_PREFIXES = ("/api/acquisition", "/api/decisions")
# Families whose writes stay GUARDED: they move real files, or hold shared state.
_GUARDED_PREFIXES = ("/api/pipeline", "/api/maintenance", "/api/config", "/api/staging")

_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}

# Routes that LOOK mutating (they are POSTs, because they take a body) but write
# nothing at all. Each entry carries the sentence from its own docstring that
# says so — an exemption without a reason is how a real hole hides in a list.
_PURE_DESPITE_POST = {
    "/api/config/validate": "« Validate a candidate config file without writing to disk »",
    "/api/acquisition/ranking/preview": "« Read-only + pure: no DB, no filesystem, no torrent client »",
}


def _is_staging_guarded(route: APIRoute) -> bool:
    """Whether a route refuses writes on staging — by EITHER of the two mechanisms.

    This codebase expresses ONE policy in TWO shapes, and a test that knows only
    one of them reports a false hole (it did, on first run — see the ledger):

    - as a FastAPI dependency — ``Depends(require_not_staging)``: pipeline,
      maintenance, staging-media, and (until A18) acquisition / decisions;
    - inside the handler body — ``if _is_staging(): raise HTTPException(403)``:
      every ``/api/config`` write.

    The divergence itself is a standing finding (see the ledger): one policy
    should have one implementation. Until it is unified, this predicate must
    recognise both, or it lies in one direction or the other.

    Args:
        route: The route to inspect.

    Returns:
        ``True`` when the route is guarded by either mechanism.
    """
    for dep in route.dependant.dependencies:
        if "require_not_staging" in repr(dep.call):
            return True
    try:
        source = inspect.getsource(route.endpoint)
    except (OSError, TypeError):
        return False
    return "_is_staging()" in source or "is_staging_role()" in source


def _mutating_routes(app):
    """Yield ``(path, method, route)`` for every route that can change state."""
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in _PURE_DESPITE_POST:
            continue
        for method in route.methods & _MUTATING:
            yield route.path, method, route


def test_acquisition_and_decision_writes_are_open_on_staging(app):
    """A18 : ces écritures doivent PASSER sur staging (pire cas réparable à la main)."""
    still_guarded = [
        f"{method} {path}"
        for path, method, route in _mutating_routes(app)
        if path.startswith(_OPEN_PREFIXES) and _is_staging_guarded(route)
    ]
    assert still_guarded == [], f"encore gardées alors qu'A18 les ouvre : {still_guarded}"


def test_dangerous_writes_stay_guarded_on_staging(app):
    """A18 : celles-ci DOIVENT rester gardées — elles déplacent des fichiers ou tiennent l'état partagé."""
    unguarded = [
        f"{method} {path}"
        for path, method, route in _mutating_routes(app)
        if path.startswith(_GUARDED_PREFIXES) and not _is_staging_guarded(route)
    ]
    assert unguarded == [], f"écriture non gardée hors du périmètre A18 : {unguarded}"
```

Build the `app` fixture the way the existing route tests do (`tests/unit/web/routes/` — copy their client wiring).

**This predicate was wrong on its first version** and reported four `/api/config` routes as unguarded holes. They
were not: three carry the in-handler `_is_staging()` check and the fourth writes nothing. Before trusting a red
result from this test, verify the named route by reading it — a policy test that only knows one guard shape produces
exactly this kind of confident false alarm.

- [ ] **Step 2: Run it — the first test must FAIL, the second must PASS**

Run: `command python -m pytest tests/unit/web/routes/test_staging_write_policy.py -v`
Expected: `test_acquisition_and_decision_writes_are_open_on_staging` FAILS listing the 11 currently-guarded routes;
`test_pipeline_and_config_writes_stay_guarded_on_staging` PASSES already. If the second one fails, STOP and report —
that would mean a write route outside A18's scope is already unguarded, which is a separate finding.

- [ ] **Step 3: Remove the dependency from the eleven sites**

Delete `Depends(require_not_staging)` — and only that — from the `dependencies=[…]` lists at:
`acquisition.py:877, 995, 1042` · `acquisition_triggers.py:298, 460, 497, 622, 637` ·
`acquisition_seasons.py:94` · `decisions.py:533, 665`.

**Keep `Depends(require_x_requested_with)` everywhere it appears** — it is a CSRF guard, unrelated to A18.
Remove the now-unused `require_not_staging` import only where nothing else in the file uses it.

- [ ] **Step 4: Correct the policy docstring — it is about to become false**

`personalscraper/web/deps.py`, `require_not_staging`, currently says: *"every mutating POST under /api/* must be
blocked on the staging instance … applied to all write routes in pipeline (S2), maintenance (S3), and config (S4)"*.
Replace with:

```python
def require_not_staging() -> None:
    """FastAPI dependency: 403 read-only on the staging clone — for the DANGEROUS writes.

    Prod and staging share the same ``config/`` directory, and therefore the same
    ``data_dir``, ``library.db``, ``acquire.db`` and storage disks. This dependency
    used to guard EVERY mutating route. Since A18 it guards the two families whose
    damage cannot be undone by hand:

    - the **pipeline runner** — it MOVES REAL FILES on the storage disks, and no
      database backup rolls that back;
    - the **config editor** and the staging-media writes — the config is the one
      piece of state both instances share, so corrupting it breaks prod and
      staging in the same stroke.

    Acquisition and decision writes are deliberately NOT guarded (A18): their
    worst case is a wrong follow row or an extra torrent in the client, both
    repairable, and blocking them made the mobile rebuild's mutating journeys
    impossible to validate on staging before merge.

    The policy is asserted as a table in
    ``tests/unit/web/routes/test_staging_write_policy.py`` — change it there, not
    by editing routes one at a time.

    Raises:
        HTTPException: 403 with detail ``"read-only"`` when
            ``PERSONALSCRAPER_WEB_ROLE`` is ``"staging"``.
    """
```

- [ ] **Step 5: Run the policy test, then the full backend suite**

Run: `command python -m pytest tests/unit/web/routes/test_staging_write_policy.py -v` → both PASS.
Then: `command python -m pytest tests/ -q` → 0 failures. Existing tests may assert a 403 on a now-open route; if one
does, that test encoded the OLD policy — update it and say so in the commit message.

- [ ] **Step 6: Commit**

```bash
git add -A personalscraper tests
git commit -m "$(cat <<'EOF'
feat(acq-mobile): staging peut écrire sur acquisition et décisions (A18)

Prod et staging partagent config/, donc data_dir et les bases. Toutes les
écritures d'acquisition rendaient 403 sur staging, ce qui rendait les parcours
mutants de la refonte — confirmation §5, récupérer, retirer, balayage —
impossibles à valider avant merge.

Ouvertes : follows (create/update/delete), triggers, grab de saison, résolution
et rejet de décision. Pire cas : une ligne de suivi fausse ou un torrent en trop,
réparables à la main.

Restent gardés : le runner de pipeline, qui DÉPLACE de vrais fichiers sur les
disques et qu'aucune sauvegarde de base ne rattrape, et l'éditeur de config, seul
état partagé par les deux instances.

La politique est désormais asservie à une table de test plutôt qu'à onze
décorations éparses : une future route d'écriture ajoutée à une famille gardée
sans la dépendance fait échouer le test.
EOF
)"
```

---

### Task 16: Staging validation gate (A16) and PR

**Files:** none — this task produces evidence.

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin feat/acq-mobile
gh pr create --title "feat(acq-mobile): refonte mobile-first de la page Acquisition" --body-file docs/superpowers/specs/2026-08-06-acquisition-mobile-refonte-design.md
```

Add to the PR body the § list this serves (spec header) and the sentence: *« Validée sur staging avant merge — preuves ci-dessous. »*

- [ ] **Step 2: Wait for CI green**

Run: `gh pr checks --watch`
A job failing in 3–4 s with no log is a GitHub spending limit, not the code — re-check billing before debugging.

- [ ] **Step 3: Deploy to staging and validate at 390 px**

Deploy the branch to `tm-staging.iznogoudatall.xyz`. Then walk this list **on a real phone**, and record a screenshot for each:

0. **A blocked station vs an in-progress one — without relying on colour.** The
   differentiator shipped is a dashed border on a 9 px dot with a 1.5 px stroke.
   That satisfies the letter of the accessibility finding, but whether it is
   actually *perceptible* at that size cannot be settled by reading code. Look at
   an « À traiter » card next to an « En vol » one and answer plainly: can you tell
   them apart with the colour ignored? If not, the differentiator must change
   (shape, size, or a glyph) before merge — a marker only some users can see is
   not a marker.
1. « Maintenant » — the five sections, in order, with real counts.
2. The **gesture arbitration** — swipe from a card (expect: card actions) vs from a section header (expect: view change). This is the decision that cannot be judged from a mockup.
3. Pull-to-refresh in the PWA **and** in a browser tab — the page must not reload.
4. « Suivis » — the three modes; reload and confirm the mode survived; confirm the URL carries no mode.
5. A 20+-season follow — most recent first, complete seasons collapsed, legend above.
6. A film — the vocabulary of §9 everywhere, and the §5 auto-removal sentence.
7. An unidentified media — no poster button, no « Voir la fiche ».
8. The add flow — a real search, the provider total, and an already-owned film's confirmation.
9. A notification — above the bottom bar, with its cross, on a device with a home indicator.
10. **`/config` on staging** — confirm the « Mode lecture seule » alert renders there (the open question left by Task 1). If it does not, the read-only state must be surfaced before merge.

- [ ] **Step 4: Report honestly**

Post the screenshots to the PR. For anything that failed, say so and fix it — a partial pass is not a pass.

- [ ] **Step 5: Merge**

Squash-merge once staging is validated and CI is green. Note: `gh pr merge --delete-branch` switches the local checkout and can break git-over-HTTPS — delete the branch from the web UI, or re-point the remote to SSH afterwards.

---

## Self-Review

**Spec coverage.** §3 IA → T7, T8, T15. §3.1 « À traiter » → T2, T3, T8. §3.2 badge → T7. §4 Maintenant → T5, T6, T8. §5 Suivis → T9, T10. §5.4 one derivation → T10. §6 media sheet + §11 exception → T11 (and T5 for the poster rule). §7 add flow → T12. §8 gestures → T13, T14. §9 vocabulary → T4 (consumed by T10, T12, T14). §10 notifications → **gap found and closed below**. §11 rules R1–R3 → T5; R2 → T6; R5 → T14 (naming); R6 → T14 (test); R7/R8 → applied where grids and `[hidden]` appear, asserted in T9. §12 delivery → T1 (A17), T16 (A16). §13 test plan → its 9 assertions map to T5/T7/T10/T11/T12/T14/T9/T4/T1.

**Gap found and closed:** §10 (notification dock, close cross, 5 s) had no task. It belongs with the shell that owns the bottom bar, so it became **Task 7 steps 6–7** — with its own failing test first (safe-area simulated by setting `padding-bottom: 34px` on the tab bar, then asserting `toast.bottom <= tabbar.top`).

**Placeholders:** none — every code step carries real code; every test step carries real assertions.

**Type consistency:** `ToHandleItem` (py dataclass, T2) ↔ `ToHandleItemModel` (pydantic, T3) ↔ `ToHandleItem` (TS, T3) share field names and order. `Stage` (T6) uses the same five keys as `_stage_of` (T2). `ViewMode` (T9) is `"list" | "group" | "grid"` in the hook, the switcher and the tests. `actionWords` (T4) is the only source of action labels in T10, T12 and T14.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-06-acquisition-mobile-refonte.md`.
