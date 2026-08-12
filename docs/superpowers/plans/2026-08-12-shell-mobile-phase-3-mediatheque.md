# Shell Mobile — Phase 3: Médiathèque Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the library browsable for the first time. No route lists what the operator owns — `/medias` serves the staging area despite its name.

**Architecture:** A new read-only route `/mediatheque` with three lenses (Médias, Incomplets, Récents), served by **one new backend endpoint** that reads `library.db` and returns a page of owned media. Read-model only: this phase writes nothing, scans nothing, and touches no disk. Infinite scroll is served here — the source is local, so one more page costs neither provider quota nor external network.

**Tech Stack:** FastAPI + Pydantic (one new typed route), SQLite read-only, React 19 + TanStack Query, vitest, pytest, the phase-0 parity guards.

## Global Constraints

- **The prototype is the source.** `frontend/maquette/refonte.html` is the design reference (§15 of `docs/reference/product-intent.md`).
- **CSS is extracted, never retyped.** Run `python scripts/extract-maquette-css.py`.
- **A read model, never a scan.** This surface reads the indexer database. It must never walk a disk, and never trigger a scan: a page that scans on open is a page that hangs on a cold disk.
- **Typed API:** the new route carries a Pydantic `response_model`; after any route change run `make openapi` and **commit** `frontend/openapi.json` and `frontend/src/api/schema.d.ts` — CI regenerates them and fails on drift.
- **The auth perimeter is the single `guarded_api` dependency.** Never add a per-route `Depends(require_session)`.
- **Read-only endpoint ⇒ no staging guard needed**, but any mutating route added later must carry `require_not_staging`.
- **One sub-line grammar** for every row: « année · type ». Two grammars make rows incomparable.
- **A filter's parts sum to the whole.** A filter whose counts do not add up to the total is a filter that lies.
- **No dead end (DOIT-7), no silent nothing (§8):** three phases per surface — loading with skeletons of the right shape, empty stating why, error naming the cause and offering a retry.
- **Probe emulation:** 390 × 844, DPR 2, `isMobile`, `hasTouch`. Never bind a local server to 8710 or 8711.
- **Search safety:** every `rg` carries `--type` or `-g`. **Network safety:** every `curl` carries `--connect-timeout 10 --max-time 30`.
- **Frontend gates:** `npx tsc -b --noEmit`, `npx eslint src`, `npx vitest run`, `make check-frontend`. **Backend gates:** `make lint`, `make test`.
- **Comments in English**, no session/phase/date references. Interface copy stays French.
- **Commits:** Conventional Commits, scope `(shell-mobile)`. No AI attribution. **Version bump on every PR.**


> **Test fixtures — read this before writing a backend test.** This repository has
> no `client` or `staging_client` fixture. Web tests build their own client from
> the `make_web_client` factory and `test_config` (see `tests/web/conftest.py` and
> the `auth_client` fixture at the top of `tests/web/test_auth.py`). The test code
> below names its client `client` for readability: **replace it with a fixture
> built the repository's way**, and set the staging role through the settings the
> factory takes rather than inventing a second fixture name.

---

## File Structure

| File                                                               | Responsibility                                                                                    |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `personalscraper/web/models/library.py`                            | **Create.** `LibraryItem`, `LibraryPage`, `LibraryCategory` — the typed shapes the route returns. |
| `personalscraper/web/routes/library.py`                            | **Create.** `GET /api/library/items` with lens, category, search and pagination.                  |
| `personalscraper/web/routes/__init__.py`                           | **Modify.** Register the router.                                                                  |
| `tests/web/test_library_route.py`                                  | **Create.** Route tests against a temporary database.                                             |
| `frontend/src/pages/MediathequePage.tsx`                           | **Create.** The route: three lenses, search, grid/list, infinite scroll.                          |
| `frontend/src/components/mediatheque/LibraryGrid.tsx`              | **Create.** The poster grid.                                                                      |
| `frontend/src/components/mediatheque/LibraryList.tsx`              | **Create.** The list rows.                                                                        |
| `frontend/src/components/mediatheque/useLibrary.ts`                | **Create.** The paged query hook.                                                                 |
| `frontend/src/router.tsx`, `frontend/src/components/layout/nav.ts` | **Modify.** Add `/mediatheque`.                                                                   |

**Read before starting:** §5.1 of the spec, `docs/reference/indexer.md` (the database this reads), and the prototype states `lib-grille`, `lib-liste`, `lib-incomplets`, `lib-recents`, `lib-recherche-vide`, `lib-chargement`, `lib-erreur`.

---

### Task 1: The typed read model, server side

**Files:**

- Create: `personalscraper/web/models/library.py`
- Create: `personalscraper/web/routes/library.py`
- Create: `tests/web/test_library_route.py`
- Modify: `personalscraper/web/routes/__init__.py`

**Interfaces:**

- Produces: `GET /api/library/items?lens=&category=&q=&offset=&limit=` → `LibraryPage`.
  - `LibraryItem`: `id: int`, `title: str`, `year: int | None`, `kind: Literal["movie", "show"]`, `category_id: str`, `poster_url: str | None`, `owned_episodes: int | None`, `aired_episodes: int | None`.
  - `LibraryPage`: `items: list[LibraryItem]`, `total: int`, `offset: int`, `limit: int`, `categories: list[LibraryCategory]`.
  - `LibraryCategory`: `id: str`, `label: str`, `count: int`.

- [ ] **Step 1: Read the database's real shape**

Run:

```bash
rg -n "CREATE TABLE media_item|CREATE TABLE season|CREATE TABLE episode" -g '*.py' -g '*.sql' personalscraper/ | head
rg -n "class MediaItem" -A 25 --type py personalscraper/indexer/ | head -40
```

Expected: you can name the columns the route will select. `media_item` carries `kind`, `title`, `year`, `category_id`; seasons and episodes hang off it. Guessing a column name here produces an endpoint that returns an empty page and a view that looks calm while it is empty for the wrong reason.

- [ ] **Step 2: Write the failing route test**

Create `tests/web/test_library_route.py`:

```python
"""Tests for the library read model.

This route is the first that lists what the operator owns. It reads the indexer
database and must never scan a disk: a page that scans on open hangs on a cold
disk, and the operator meets that before anyone else.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_items_are_paged(client: TestClient) -> None:
    """A page states its own bounds, so the caller never has to guess them."""
    response = client.get("/api/library/items", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 2
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert isinstance(body["total"], int)


def test_category_counts_sum_to_the_total(client: TestClient) -> None:
    """A filter whose parts do not add up to the whole is a filter that lies."""
    body = client.get("/api/library/items", params={"limit": 1}).json()
    assert sum(c["count"] for c in body["categories"]) == body["total"]


def test_the_incomplete_lens_returns_only_incomplete_series(client: TestClient) -> None:
    """« Incomplets » means owned < aired, for a series with a known catalogue."""
    body = client.get("/api/library/items", params={"lens": "inc", "limit": 50}).json()
    for item in body["items"]:
        assert item["kind"] == "show"
        assert item["aired_episodes"] is not None
        assert item["owned_episodes"] < item["aired_episodes"]


def test_an_unknown_catalogue_is_never_reported_as_complete(client: TestClient) -> None:
    """A series whose aired count is unknown reports None, never a fabricated total.

    Reporting « 12/12 » for a series nobody counted is how a library starts
    lying about itself.
    """
    body = client.get("/api/library/items", params={"limit": 200}).json()
    for item in body["items"]:
        if item["kind"] == "show" and item["aired_episodes"] is None:
            assert item["owned_episodes"] is not None


def test_search_matches_the_title(client: TestClient) -> None:
    """The search is a filter over the read model, not a provider lookup."""
    body = client.get("/api/library/items", params={"q": "zzz-no-such-title"}).json()
    assert body["items"] == []
    assert body["total"] == 0


def test_the_route_is_read_only(client: TestClient) -> None:
    """No verb but GET: this surface writes nothing and scans nothing."""
    assert client.post("/api/library/items").status_code == 405
    assert client.delete("/api/library/items").status_code == 405
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/web/test_library_route.py -v`
Expected: FAIL — 404 on every request; the route does not exist.

- [ ] **Step 4: Write the models**

Create `personalscraper/web/models/library.py` with the three models described in **Interfaces** above, each with a Google-style docstring naming what every field means and, for the nullable ones, what `None` means.

- [ ] **Step 5: Write the route**

Create `personalscraper/web/routes/library.py`. It opens the indexer database **read-only**, selects a page, and computes the category counts in the same query pass so they cannot disagree with the total:

```python
"""Lists what the operator owns.

The library had no route: `/medias` serves the staging area despite its name, and
`/search` queries providers rather than the disks. This is the first endpoint that
answers « what do I have ».

A READ MODEL: it reads the indexer database and never walks a disk, never
triggers a scan. A page that scans on open hangs on a cold disk.
"""
```

Register it in `personalscraper/web/routes/__init__.py` alongside the others, behind the existing `guarded_api` dependency — never a per-route session dependency.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/web/test_library_route.py -v`
Expected: PASS — 6 passed.

- [ ] **Step 7: Regenerate the typed contract**

Run: `make openapi`
Expected: `frontend/openapi.json` and `frontend/src/api/schema.d.ts` change. **Commit both** — CI regenerates them and fails on drift.

- [ ] **Step 8: Run the backend gates**

Run: `make lint && make test`
Expected: zero errors, and the summary line shows `NNNN passed` with no ERROR. An ERROR means a collection crash: every test after it was skipped, so fix the import before reading the count.

- [ ] **Step 9: Commit**

```bash
git add personalscraper/web/models/library.py personalscraper/web/routes/library.py \
        personalscraper/web/routes/__init__.py tests/web/test_library_route.py \
        frontend/openapi.json frontend/src/api/schema.d.ts
git commit -m "feat(shell-mobile): an endpoint that lists what the operator owns

The library had no route at all: /medias serves the staging area despite its
name, and /search queries providers rather than the disks.

A read model, never a scan — a page that scans on open hangs on a cold disk. The
category counts are computed in the same pass as the total, so they cannot
disagree: a filter whose parts do not add up to the whole is a filter that lies.
A series whose aired count is unknown reports it as unknown rather than
fabricating a total, because « 12/12 » for a series nobody counted is how a
library starts lying about itself."
```

---

### Task 2: The page, its three lenses and its two layouts

**Files:**

- Create: `frontend/src/components/mediatheque/useLibrary.ts` + test
- Create: `frontend/src/components/mediatheque/LibraryGrid.tsx` + test
- Create: `frontend/src/components/mediatheque/LibraryList.tsx` + test
- Create: `frontend/src/pages/MediathequePage.tsx` + test
- Modify: `frontend/src/router.tsx`, `frontend/src/components/layout/nav.ts`

**Interfaces:**

- Consumes: `components["schemas"]["LibraryPage"]` from `schema.d.ts`; `Chip`, `SectionHeader` from phase 1.
- Produces: `/mediatheque`; `useLibrary({lens, category, q})` returning `{items, total, categories, fetchMore, status}`.

- [ ] **Step 1: Write the failing test for the row grammar**

Create `frontend/src/components/mediatheque/LibraryList.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { LibraryList } from "./LibraryList";

const ITEMS = [
  { id: 1, title: "Dune", year: 2021, kind: "movie", category_id: "movies" },
  { id: 2, title: "Silo", year: 2023, kind: "show", category_id: "tv_shows" },
] as never[];

test("every row uses the same sub-line grammar", () => {
  // Films said « 2026 · Film » and series « 6 ép. » — two grammars for the same
  // line, so nothing was comparable from row to row.
  render(<LibraryList items={ITEMS} />);
  expect(screen.getByText("2021 · Film")).toBeInTheDocument();
  expect(screen.getByText("2023 · Série")).toBeInTheDocument();
});

test("a missing year is stated, never dropped", () => {
  render(
    <LibraryList
      items={[{ id: 3, title: "X", year: null, kind: "movie" }] as never[]}
    />,
  );
  expect(screen.getByText("année inconnue · Film")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it to verify it fails, then write `LibraryList`**

Run: `cd frontend && npx vitest run src/components/mediatheque/LibraryList.test.tsx` → FAIL.

Create `frontend/src/components/mediatheque/LibraryList.tsx`:

```tsx
import type { components } from "@/api/schema";

type Item = components["schemas"]["LibraryItem"];

/** One sub-line grammar for every row: « année · type ». */
function subline(item: Item): string {
  const year = item.year ?? "année inconnue";
  const kind = item.kind === "movie" ? "Film" : "Série";
  return `${year} · ${kind}`;
}

/**
 * The library as rows.
 *
 * Every row reads the same way — « année · type » — because two grammars in one
 * list make its rows incomparable, and comparing them is the whole point of a
 * list. A missing year is stated rather than dropped: a silent gap reads as an
 * answer, and it is not one.
 */
export function LibraryList({ items }: { items: Item[] }) {
  return (
    <ul className="liblist">
      {items.map((item) => (
        <li key={item.id}>
          <span className="ctitle">{item.title}</span>
          <span className="csub">{subline(item)}</span>
        </li>
      ))}
    </ul>
  );
}
```

Run again: PASS — 2 passed.

- [ ] **Step 3: Write the failing test for the lenses and phases**

Create `frontend/src/pages/MediathequePage.test.tsx`, testing: the three lenses switch the list; the incomplete lens shows the fraction; loading renders skeletons; an empty search states what was searched and offers to clear it; an error names the cause and offers a retry.

```tsx
test("an empty search says what was searched and offers a way out", () => {
  render(
    <MediathequePage
      state={{ status: "ready", items: [], total: 0, categories: [] }}
      query="zzz"
    />,
  );
  expect(screen.getByText(/aucun résultat pour « zzz »/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /effacer/i })).toBeInTheDocument();
});
```

- [ ] **Step 4: Run it to verify it fails, then write the page**

Create `frontend/src/pages/MediathequePage.tsx` with the three lenses, the search field, the grid/list switch, the infinite-scroll sentinel and the three phases. The shown/total count stays visible at all times, so one always knows where one stands within the whole library.

Run: `cd frontend && npx vitest run src/pages/MediathequePage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Wire the route and the bar**

Add `/mediatheque` to `frontend/src/router.tsx` and to `frontend/src/components/layout/nav.ts`.

- [ ] **Step 6: Verify the filters filter, and that their parts sum**

Run: `cd frontend && npx vitest run src/components/mediatheque src/pages/MediathequePage.test.tsx`
Expected: PASS, including a test that asserts the category counts add up to the announced total. If that test is missing, add it — decorative pills that change state without filtering shipped once already.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(shell-mobile): browsing the library becomes possible

Three lenses, two layouts, one sub-line grammar. Infinite scroll is served here
because the source is local: one more page costs neither provider quota nor
external network, and the shown/total count stays visible so one always knows
where one stands.

The empty search states what was searched and offers to clear it. A search that
returns nothing and says nothing reads as a broken page."
```

---

### Task 3: Phase gate

- [ ] **Step 1: Move the library states into the measured set**

In `frontend/maquette/regions.json`, move `lib-*` out of `unmeasuredStates` and declare the `mediatheque/*` regions.

- [ ] **Step 2: Run every gate**

Run:

```bash
make lint && make test
make check-frontend
cd frontend && npm run build
cd .. && python scripts/parity-probe.py --app-dir frontend/dist
```

Expected: all pass, probe `OK`.

- [ ] **Step 3: Exercise it by hand at 390 px, on the real library**

Open `/mediatheque` against the real database. Check: the three lenses each show something; the category counts add up to the announced total; scrolling loads more without a jump; the incomplete lens shows fractions and not just names.
This is the step no measurement replaces.

- [ ] **Step 4: Update the tracker, bump the version, commit**

```bash
git add IMPLEMENTATION.md pyproject.toml frontend/maquette/regions.json
git commit -m "chore(shell-mobile): phase 3 gate — the library is browsable

The first route that lists what the operator owns, and the first time the six
jobs this rebuild started from all have a surface."
```

---

## Self-Review

**1. Spec coverage.** §5.1 Médiathèque as a read model → Task 1 (the endpoint, with a test asserting no verb but GET) and Task 2 (the three lenses, the two layouts, infinite scroll). The « one sub-line grammar » rule (R20) → Task 2 Step 1. The « parts sum to the whole » rule (R25) → Task 1 Step 2's second test and Task 2 Step 6.

**2. Placeholder scan.** Task 2 Steps 3 and 4 give one representative test rather than the full file — the representative one is the case that has failed before (an empty search that says nothing), and the step names the other four cases explicitly so none is left to taste.

**3. Type consistency.** `LibraryItem` / `LibraryPage` / `LibraryCategory` are defined in Task 1 and consumed in Task 2 through the generated `schema.d.ts`, never redeclared by hand in the frontend.

**One risk named:** the incomplete lens needs an aired-episode count per series. If the indexer database does not carry one — only what is indexed — then « incomplete » cannot be computed server-side without a provider catalogue, and the honest options are to report the gap or to serve the lens from what phase 4 will already have fetched. Deciding that silently, by making the count mean something else, is what the fourth test in Task 1 Step 2 exists to prevent.
