# Shell Mobile — Phase 6: Découvrir Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Offer the operator something to watch — drawn from what they own and what they have rated, never from what they already have — in three formats that share one grammar.

**Architecture:** A background pass paginates TMDB at a civil rhythm, filters against the library, the ratings, the follows and the dismissals, and files the survivors in a local reserve. The view reads the reserve, so scrolling costs nothing and batches of thirty are possible without ever turning a distracted thumb into a burst against a dependency. Three display formats — list, posters, slide cards — change how much of the poster one sees, never what the gestures mean.

**Tech Stack:** FastAPI + Pydantic, SQLite (the reserve), the existing TMDB client, React 19 + TanStack Query, vitest, pytest, the phase-0 parity guards.

## Global Constraints

- **The prototype is the source.** `frontend/maquette/refonte.html` is the design reference (§15 of `docs/reference/product-intent.md`).
- **CSS is extracted, never retyped.** Run `python scripts/extract-maquette-css.py`.
- **TMDB proposes, TVDB identifies.** A series suggestion is resolved TMDB → TVDB **before** the follow is created. TVDB has no recommendation API; TMDB has no series identity in this system.
- **No burst against a dependency.** The view reads a local reserve; it never paginates a provider in response to a scroll. The background pass has a rhythm and states it.
- **Exclusions, in order:** owned, rated (= seen), already followed, manually dismissed.
- **Degraded mode is not an empty page.** With no TMDB account, the view serves similars of the library and **says what is missing and why**.
- **One gesture grammar across the three formats.** In list and posters, a swipe dismisses. In slide cards, left « Passer » decides nothing and the card comes round again; right « Pas intéressé » removes it, with an undo. No format invents an action of its own: the verbs live in the bottom sheet, reached the same way everywhere.
- **The pile is animated, never rebuilt.** Advancing moves the existing nodes. A replaced node cannot transition, and the pile then cuts instead of moving. Checked **mid-flight**, not at rest.
- **A gesture claim requires real `TouchEvent`s** dispatched on the real surface. `PointerEvent`s are never cancelled by the browser, so they prove nothing about a gesture that has to claim an axis.
- **The account token is stored with the other secrets** — never in a document, never in a log.
- **Typed API**, `require_not_staging` on every mutation, `make openapi` + commit the regenerated files.
- **Probe emulation:** 390 × 844, DPR 2, `isMobile`, `hasTouch`. Never bind a local server to 8710 or 8711.
- **Search safety:** every `rg` carries `--type` or `-g`. **Network safety:** every `curl` carries `--connect-timeout 10 --max-time 30`.
- **Comments in English**, no session/phase/date references. Interface copy stays French.
- **Commits:** Conventional Commits, scope `(shell-mobile)`. No AI attribution. **Version bump on every PR.**
- **One card, one behaviour, and one panel per medium (R31, R41–R45).** In every list:
  the **poster** opens the media sheet; the **card body** opens the bottom panel; a **gallery
  tile**, being all poster, answers a **long press** for the panel. The **panel carries every
  action** available for that medium, and an inline action on a card is a shortcut to
  something the panel also offers — never the only way in. The panel is **derived** from what
  is true about the medium (followed, incomplete, in the library, to grab, blocked, has a
  sheet), never passed in by the calling screen: that is what makes the panel reached from a
  gallery identical to the one reached from a card. An element states **which** panel it
  addresses (`data-panel="media:<title>"`) and never how to build it; addressing it by list
  index is forbidden. `frontend/maquette/harness/cartes.py` is the executable form of this
  contract — port it, do not re-derive it.
- **One builder per SHAPE, not per screen.** `cardHTML` serves every list, `tileHTML`
  every gallery; a release candidate has its own builder because it is not a medium
  (no sheet, no panel — marked `data-nonmedia`, R46), and the selection row is a mode
  of the list rather than a variant of the card. The card takes a **descriptor of
  facts** — title, kind, sub-line, reason, fraction, chip, caption, fresh, strip. A
  view wanting something outside that list is naming a fact the card does not know
  yet: add the fact, never pass ready-made markup. Props that name an appearance
  (`dense`, `compact`, `showChip`) are the failure mode this avoids.
- **Same metrics in every list (R47), and a reason that never truncates (R48).** Poster
  38 × 57, padding 9, radius 8, title 13.5, gap 10 — everywhere. Card heights differ only
  because their content does. A surface wanting a bigger picture uses the gallery or deck
  format, which exist for that. Rich text reaches a card as SEGMENTS (plain text plus what
  is emphasised, at its position), never as ready-made markup — see `richText`.


> **Test fixtures — read this before writing a backend test.** This repository has
> no `client` or `staging_client` fixture. Web tests build their own client from
> the `make_web_client` factory and `test_config` (see `tests/web/conftest.py` and
> the `auth_client` fixture at the top of `tests/web/test_auth.py`). The test code
> below names its client `client` for readability: **replace it with a fixture
> built the repository's way**, and set the staging role through the settings the
> factory takes rather than inventing a second fixture name.

- **Work on `feat/shell-mobile`, never on `main`.** Every phase of this rebuild targets the
  same integration branch; `main` — and therefore production — is touched once, at the end,
  after everything has been validated together. This is the mission's one non-negotiable
  arbitration. Before the first commit of any task, run `git branch --show-current` and stop
  if it is not `feat/shell-mobile`: a phase committed to `main` cannot be un-shipped, and a
  local `main` that has drifted produces a pull request with no checks at all.
---

## File Structure

| File                                                      | Responsibility                                                            |
| --------------------------------------------------------- | ------------------------------------------------------------------------- |
| `personalscraper/insights/suggestions.py`                 | **Create.** The engine: seeds, pagination, exclusions, the reserve.       |
| `personalscraper/web/models/suggestions.py`               | **Create.** `Suggestion`, `SuggestionBatch`, `SuggestionSource`.          |
| `personalscraper/web/routes/suggestions.py`               | **Create.** `GET /api/suggestions`, `POST /api/suggestions/{id}/dismiss`. |
| `tests/insights/test_suggestions_engine.py`               | **Create.** Exclusion tests — the engine's whole value.                   |
| `frontend/src/components/decouvrir/SuggestionList.tsx`    | **Create.** Format one.                                                   |
| `frontend/src/components/decouvrir/SuggestionPosters.tsx` | **Create.** Format two.                                                   |
| `frontend/src/components/decouvrir/SlideCards.tsx`        | **Create.** Format three, with the animated pile.                         |
| `frontend/src/components/decouvrir/useDeck.ts`            | **Create.** The deck order: skip sends to the back, dismiss removes.      |
| `frontend/src/pages/AcquisitionPage.tsx`                  | **Modify.** Add the third view.                                           |

**Read before starting:** §5.2 of the spec, `docs/reference/tmdb-api.md`, and the prototype states `acq-decouvrir`, `acq-decouvrir-affiches`, `acq-decouvrir-deck`, `acq-decouvrir-degrade`, `acq-decouvrir-epuise`, `acq-decouvrir-chargement`.

---

### Task 1: The engine and its exclusions

The exclusions are the engine's entire value. A suggestion for something already owned is worse than no suggestion: it teaches the operator that the feature does not know them.

**Files:**

- Create: `personalscraper/insights/suggestions.py`
- Create: `tests/insights/test_suggestions_engine.py`

**Interfaces:**

- Produces: `build_reserve(*, db, tmdb, account=None) -> int` (number filed); `excluded_ids(db) -> set[int]`; `seeds(db, limit=16) -> list[SeedMedia]`.

- [ ] **Step 1: Write the failing test**

Create `tests/insights/test_suggestions_engine.py`:

```python
"""The suggestion engine, judged on what it refuses.

A suggestion for something already owned is worse than no suggestion: it teaches
the operator that the feature does not know them.
"""

from __future__ import annotations


def test_owned_media_are_excluded(db_with_library, fake_tmdb) -> None:
    """The first exclusion, and the one that carries the feature."""
    fake_tmdb.will_return([{"id": 618354, "title": "Owned"}, {"id": 999, "title": "New"}])
    build_reserve(db=db_with_library, tmdb=fake_tmdb)
    assert [s.tmdb_id for s in reserve(db_with_library)] == [999]


def test_rated_media_are_excluded(db_with_ratings, fake_tmdb) -> None:
    """A rating means it was seen: proposing it again is proposing a re-watch."""
    fake_tmdb.will_return([{"id": 111, "title": "Rated"}, {"id": 222, "title": "New"}])
    build_reserve(db=db_with_ratings, tmdb=fake_tmdb, account="token")
    assert [s.tmdb_id for s in reserve(db_with_ratings)] == [222]


def test_followed_media_are_excluded(db_with_follows, fake_tmdb) -> None:
    fake_tmdb.will_return([{"id": 333, "title": "Followed"}, {"id": 444, "title": "New"}])
    build_reserve(db=db_with_follows, tmdb=fake_tmdb)
    assert [s.tmdb_id for s in reserve(db_with_follows)] == [444]


def test_dismissed_media_stay_dismissed(db_with_dismissals, fake_tmdb) -> None:
    """« Pas intéressé » is durable, or the gesture is theatre."""
    fake_tmdb.will_return([{"id": 555, "title": "Dismissed"}, {"id": 666, "title": "New"}])
    build_reserve(db=db_with_dismissals, tmdb=fake_tmdb)
    assert [s.tmdb_id for s in reserve(db_with_dismissals)] == [666]


def test_media_without_a_tmdb_id_fall_back_visibly(db_with_untagged, fake_tmdb) -> None:
    """A fallback on title+year must be visible, never silent.

    A library entry with no TMDB id cannot be excluded by id. Matching on title
    is a heuristic, and a heuristic that hides is a heuristic nobody can audit.
    """
    result = build_reserve(db=db_with_untagged, tmdb=fake_tmdb)
    assert result.title_fallbacks > 0


def test_the_engine_paginates_at_a_civil_rhythm(db_with_library, counting_tmdb) -> None:
    """The reserve is filled by a background pass, not by a thumb.

    TMDB returns 20 results per page, invariably. The engine must not turn one
    scroll into a burst of pages against a dependency.
    """
    build_reserve(db=db_with_library, tmdb=counting_tmdb)
    assert counting_tmdb.calls <= 40
    assert counting_tmdb.max_burst <= 4
```

- [ ] **Step 2: Run it to verify it fails, then write the engine**

Run: `pytest tests/insights/test_suggestions_engine.py -v` → FAIL.

Write `personalscraper/insights/suggestions.py`: pick seeds from the library, ask TMDB for recommendations and similars, exclude in the documented order, and file the survivors in the reserve.

Run again: PASS — 6 passed.

- [ ] **Step 3: Run the engine once against the real library, read-only**

Run:

```bash
python -c "
from personalscraper.insights.suggestions import build_reserve
print(build_reserve(dry_run=True))
"
```

Expected: it reports how many seeds, how many calls, how many raw results and how many survivors. If the survivor count is near zero, the exclusions are too aggressive; if it is near the raw count, they are not running. Both are findings, not details.

- [ ] **Step 4: Commit**

```bash
git add personalscraper/insights/suggestions.py tests/insights/test_suggestions_engine.py
git commit -m "feat(shell-mobile): the suggestion engine, judged on what it refuses

Owned, rated, followed, dismissed — in that order. A suggestion for something
already owned is worse than no suggestion: it teaches the operator that the
feature does not know them.

A library entry with no TMDB id falls back to title matching, and the fallback is
COUNTED and reported: a heuristic that hides is a heuristic nobody can audit.

The reserve is filled by a background pass at a civil rhythm. TMDB returns 20
results per page invariably, and turning one scroll into a burst of pages is how
a feature gets its account throttled."
```

---

### Task 2: The route and the degraded mode

**Files:**

- Create: `personalscraper/web/models/suggestions.py`, `personalscraper/web/routes/suggestions.py`
- Create: `tests/web/test_suggestions_route.py`

**Interfaces:**

- Produces: `GET /api/suggestions?limit=30` → `SuggestionBatch` with `items`, `remaining`, `source: "account" | "library"`, `degraded_reason: str | None`; `POST /api/suggestions/{tmdb_id}/dismiss`.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_suggestions_route.py`:

```python
"""Suggestions are served from the reserve, and the degraded mode says why."""

from __future__ import annotations


def test_a_batch_states_what_remains(client, filled_reserve) -> None:
    """« 30 of how many » is what makes a batch a batch rather than a mystery."""
    body = client.get("/api/suggestions", params={"limit": 30}).json()
    assert len(body["items"]) <= 30
    assert isinstance(body["remaining"], int)


def test_without_an_account_the_view_is_degraded_but_not_empty(client, no_account_reserve) -> None:
    """It serves similars of the library and names what is missing."""
    body = client.get("/api/suggestions").json()
    assert body["source"] == "library"
    assert body["degraded_reason"]
    assert body["items"]


def test_dismissing_is_durable(client, filled_reserve) -> None:
    first = client.get("/api/suggestions").json()["items"][0]
    assert client.post(f"/api/suggestions/{first['tmdb_id']}/dismiss").status_code == 200
    after = client.get("/api/suggestions").json()["items"]
    assert all(item["tmdb_id"] != first["tmdb_id"] for item in after)


def test_dismissing_is_staging_guarded(staging_client, filled_reserve) -> None:
    assert staging_client.post("/api/suggestions/618354/dismiss").status_code == 403


def test_the_reserve_is_never_refilled_by_a_read(client, filled_reserve, counting_tmdb) -> None:
    """Reading the view must not call the provider. That is the whole point."""
    before = counting_tmdb.calls
    client.get("/api/suggestions")
    assert counting_tmdb.calls == before
```

- [ ] **Step 2: Run it to verify it fails, then write the route**

Run: `pytest tests/web/test_suggestions_route.py -v` → FAIL, then write the models and route and re-run → PASS — 5 passed.

- [ ] **Step 3: Regenerate the contract, run the backend gates, commit**

Run: `make openapi && make lint && make test`

```bash
git add personalscraper/web tests/web/test_suggestions_route.py frontend/openapi.json frontend/src/api/schema.d.ts
git commit -m "feat(shell-mobile): suggestions are served from the reserve, and say when degraded

Reading the view never calls the provider — a test asserts the call count does
not move. That is the whole point of a reserve.

Without a TMDB account the view does not blank: it serves similars of the library
and names what is missing and why. A page that empties itself teaches nothing."
```

---

### Task 3: Three formats, one grammar

**Files:**

- Create: `frontend/src/components/decouvrir/useDeck.ts` + test
- Create: `frontend/src/components/decouvrir/SlideCards.tsx` + test
- Create: `frontend/src/components/decouvrir/SuggestionList.tsx`, `SuggestionPosters.tsx` + tests
- Modify: `frontend/src/pages/AcquisitionPage.tsx`

**Interfaces:**

- Produces: `useDeck(items)` → `{visible, skip(id), dismiss(id), order}`; `<SlideCards items={…} onOpenSheet={fn} onDismiss={fn} />`.

- [ ] **Step 1: Write the failing test for the deck order**

Create `frontend/src/components/decouvrir/useDeck.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import { nextOrder, visibleCards } from "./useDeck";

describe("nextOrder", () => {
  test("skipping sends a card to the back, so it comes round again", () => {
    // « Passer » decides nothing. A card that never returns was dismissed, and
    // the operator was not asked.
    expect(nextOrder([1, 2, 3], 1, "skip")).toEqual([2, 3, 1]);
  });

  test("dismissing removes the card", () => {
    expect(nextOrder([1, 2, 3], 1, "dismiss")).toEqual([2, 3]);
  });

  test("skipping the last card leaves it as the only one", () => {
    expect(nextOrder([1], 1, "skip")).toEqual([1]);
  });
});

describe("visibleCards", () => {
  test("three cards are visible at most: the pile suggests depth, it does not render it", () => {
    expect(visibleCards([1, 2, 3, 4, 5])).toEqual([1, 2, 3]);
  });

  test("an exhausted deck is empty, not undefined", () => {
    expect(visibleCards([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run it to verify it fails, then write `useDeck`**

Run: `cd frontend && npx vitest run src/components/decouvrir/useDeck.test.ts` → FAIL, then write it and re-run → PASS — 5 passed.

- [ ] **Step 3: Write the failing test for the animated pile**

Create `frontend/src/components/decouvrir/SlideCards.test.tsx`:

```tsx
import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { SlideCards } from "./SlideCards";

const ITEMS = [
  { tmdb_id: 1, title: "A" },
  { tmdb_id: 2, title: "B" },
  { tmdb_id: 3, title: "C" },
] as never[];

test("the card claims the horizontal axis", () => {
  // Without the claim the browser owns the gesture and cancels it: the swipe
  // then works under synthetic events, which are never cancelled, and fails
  // under a thumb.
  const { container } = render(
    <SlideCards items={ITEMS} onOpenSheet={() => {}} onDismiss={() => {}} />,
  );
  const deck = container.querySelector(".deck") as HTMLElement;
  expect(getComputedStyle(deck).touchAction).toBe("pan-y");
});

test("advancing moves the existing nodes rather than replacing them", () => {
  // A replaced node cannot transition, and the pile then cuts instead of
  // moving. This is checked by identity, not by appearance.
  const { container, rerender } = render(
    <SlideCards items={ITEMS} onOpenSheet={() => {}} onDismiss={() => {}} />,
  );
  const before = container.querySelector('[data-deck="2"]');
  rerender(
    <SlideCards
      items={ITEMS.slice(1)}
      onOpenSheet={() => {}}
      onDismiss={() => {}}
    />,
  );
  const after = container.querySelector('[data-deck="2"]');
  expect(after).toBe(before);
});

test("the whole card opens the media sheet", () => {
  const { container } = render(
    <SlideCards items={ITEMS} onOpenSheet={() => {}} onDismiss={() => {}} />,
  );
  const top = container.querySelector('.dcard[data-depth="0"] button');
  expect(top).not.toBeNull();
});

test("the card carries no action of its own", () => {
  // The verbs live in the bottom sheet, reached the same way in every format.
  const { container } = render(
    <SlideCards items={ITEMS} onOpenSheet={() => {}} onDismiss={() => {}} />,
  );
  expect(container.textContent).not.toMatch(/pas intéressé|ajouter|suivre/i);
});
```

- [ ] **Step 4: Run it to verify it fails, then write `SlideCards`**

Run: `cd frontend && npx vitest run src/components/decouvrir/SlideCards.test.tsx` → FAIL.

Write it so that advancing changes each card's `data-depth` and inserts a new card at the back, **keying the cards by their id** so React reuses the nodes. Rebuilding the list would replace every node, and a replaced node cannot transition.

Run again: PASS — 4 passed.

- [ ] **Step 5: Prove the gesture under real touch**

Write a Playwright check — not a vitest one — that dispatches real `TouchEvent`s on the deck at 390 × 844 and asserts: a left swipe advances without dismissing and the card returns later; a right swipe dismisses and offers an undo. `PointerEvent`s are never cancelled by the browser and would prove nothing.

Run it and expect both to pass. Then break the axis claim on purpose (`touch-action: auto`), re-run, and confirm the check fails — a gesture test that cannot fail is a gesture test that is not testing.

- [ ] **Step 6: Write the two other formats and the switcher**

`SuggestionList` (full-width rows) and `SuggestionPosters` (two-column grid). In both, the poster opens the sheet and the body opens the bottom sheet; a swipe dismisses. Add the format switcher to the Découvrir view, using the same control Suivis already uses.

- [ ] **Step 7: Run the frontend gates**

Run: `cd frontend && npx tsc -b --noEmit && npx eslint src && npx vitest run`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/decouvrir frontend/src/pages/AcquisitionPage.tsx
git commit -m "feat(shell-mobile): Découvrir in three formats, with one grammar

The formats change how much of the poster one sees, never what the gestures mean
and never which actions exist. No format carries an action of its own: the verbs
live in the bottom sheet, reached the same way everywhere.

In the slide cards, left « Passer » decides nothing and the card comes round
again; right « Pas intéressé » removes it, with an undo. The pile is animated by
keeping its nodes: a replaced node cannot transition, so a rebuilt pile cuts
instead of moving — checked by node identity rather than by appearance.

The gesture is proven under real TouchEvents. PointerEvents are never cancelled
by the browser, so they prove nothing about a gesture that has to claim an axis."
```

---

### Task 4: Phase gate — and the mission gate

- [ ] **Step 1: Move the Découvrir states into the measured set**

In `frontend/maquette/regions.json`, move `acq-decouvrir*` out of `unmeasuredStates` and declare their regions. At this point `unmeasuredStates` should hold only surfaces deliberately out of scope; if it still holds a rebuilt one, that is a gap, not a detail.

- [ ] **Step 2: Run every gate, on everything**

Run:

```bash
make lint && make test && make check-frontend
cd frontend && npm run build
cd .. && python scripts/parity-probe.py --app-dir frontend/dist
```

Expected: all pass, the probe measures **every** rebuilt region and reports `OK`.

- [ ] **Step 3: Validate the whole thing together, on staging**

This is the mission's non-negotiable gate: nothing reaches production until everything has been validated together. Deploy the integration branch to staging and walk the six jobs the rebuild started from — something awaits me, did what I added by hand get through, unblock what is stuck, browse my library, check everything is healthy, offer me something to watch.

- [ ] **Step 4: Update the tracker, bump the version, commit**

```bash
git add IMPLEMENTATION.md pyproject.toml frontend/maquette/regions.json
git commit -m "chore(shell-mobile): phase 6 gate — the six jobs all have a surface

Two of them had none when this started. The probe now measures every rebuilt
region, and the integration branch is validated as a whole on staging before
anything reaches production."
```

---

## Self-Review

**1. Spec coverage.** B6 (TMDB only, TVDB still identifies) → Task 1, and the TMDB → TVDB resolution belongs to the follow-creation path already covered by phase 1's primitives. B7 (library + account, four exclusions in order) → Task 1's first four tests. §5.2's degraded mode → Task 2's second test. §5.2's three formats, R32, R33 and R34 → Task 3. Open item 5 (media with no TMDB id fall back visibly) → Task 1's fifth test.

**2. Placeholder scan.** No TBD. Task 3 Step 6 describes two formats without their full code — their structure is the list card already shipped in Acquisition and the grid already shipped in the library, and the step names the two tap targets and the swipe, which is what makes them conform.

**3. Type consistency.** `nextOrder(order, id, action)` and `visibleCards(order)` are defined in Task 3 and used under those names. `SuggestionBatch` (`items`, `remaining`, `source`, `degraded_reason`) is defined in Task 2 and consumed by the three formats through `schema.d.ts`.

**One risk named:** Task 1's rhythm test asserts a call budget the real TMDB account may not tolerate under a cold reserve — filling from nothing costs more than refilling. If the first real run exceeds the budget, the honest fix is to lower the seed count and state the reserve's fill time in the interface, not to raise the budget until the test passes: a test relaxed to match the code stops being a test.
