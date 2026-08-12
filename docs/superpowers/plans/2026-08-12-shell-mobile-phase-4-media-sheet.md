# Shell Mobile — Phase 4: The Media Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every poster in the library lead somewhere worth arriving at: one media sheet, the same everywhere, that says what a medium is, where it stands, and — for an incomplete series — **which** episodes are missing.

**Architecture:** The sheet keeps its URL `/media/:provider/:id` and its status as a destination rather than a layer. Four rules make it single: a melting visual header, one back control in the flow, a trailer that always leaves for YouTube, and one season rendering. Two bounded backend openings: episode presence per season exposed to the web layer, and the quality-profile write path.

**Tech Stack:** FastAPI + Pydantic, SQLite (read), React 19 + TanStack Query, vitest, pytest, the phase-0 parity guards.

## Global Constraints

- **The prototype is the source.** `frontend/maquette/refonte.html` is the design reference (§15 of `docs/reference/product-intent.md`).
- **CSS is extracted, never retyped.** Run `python scripts/extract-maquette-css.py`.
- **Episode presence is read, never inferred.** A `number <= owned count` threshold assumes the hole sits at the end of the season and is **false for 35 series in this library**. Presence comes from the list of owned episode numbers.
- **One season rendering**, within a sheet and across sheets. The numbered matrix is the declared fallback when a provider gives no episode titles — never a second design chosen by accident.
- **A trailer always opens YouTube**, never in-app playback, wherever one arrives from — even when a local trailer file exists next to the media.
- **One back-control design**, in the flow so it pushes content instead of covering it. No text closer than 8px to it.
- **Missing data is written « inconnu »**, never a mute dash: an unknown step is stated as unknown, never as « not done ».
- **Typed API:** any new route carries a Pydantic `response_model`; run `make openapi` and **commit** the regenerated files.
- **Every mutating endpoint is staging-guarded** (`require_not_staging`). The quality-profile write path is a mutation: it carries the guard.
- **The auth perimeter is the single `guarded_api` dependency.**
- **Probe emulation:** 390 × 844, DPR 2, `isMobile`, `hasTouch`. Never bind a local server to 8710 or 8711.
- **Search safety:** every `rg` carries `--type` or `-g`.
- **Gates:** `make lint`, `make test`, `make check-frontend`, `npx tsc -b --noEmit`, `npx eslint src`, `npx vitest run`.
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

| File                                           | Responsibility                                                                           |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `personalscraper/web/models/media.py`          | **Modify.** Add `MediaSeason` (`number`, `aired`, `owned_numbers`) to the sheet payload. |
| `personalscraper/web/routes/media.py`          | **Modify.** Serve owned episode numbers per season.                                      |
| `personalscraper/web/models/acquisition.py`    | **Modify.** Add `quality_profile` to `UpdateFollowRequest`.                              |
| `personalscraper/web/routes/acquisition.py`    | **Modify.** Persist the profile's four fields.                                           |
| `tests/web/test_media_sheet_seasons.py`        | **Create.** Season payload tests, including a series with an internal hole.              |
| `tests/web/test_follow_quality_profile.py`     | **Create.** Write-path tests, including the staging guard.                               |
| `frontend/src/pages/MediaSheetPage.tsx`        | **Modify.** The four rules.                                                              |
| `frontend/src/components/media/MediaHero.tsx`  | **Create.** The melting visual header.                                                   |
| `frontend/src/components/media/SeasonList.tsx` | **Create.** Expandable seasons naming their missing episodes.                            |
| `frontend/src/components/media/TrailerRow.tsx` | **Create.** The outbound YouTube link.                                                   |
| `frontend/src/components/ds/BackBar.tsx`       | **Create.** The single back control.                                                     |

**Read before starting:** §5.6 and §5.7 of the spec, `frontend/maquette/regions.json` → rules R26 to R31, and the prototype states `fiche-serie`, `fiche-film`, `fiche-sans-trailer`, `fiche-suggestion-serie`, `fiche-suggestion-film`.

---

### Task 1: Owned episode numbers, server side

**Files:**

- Modify: `personalscraper/web/models/media.py`, `personalscraper/web/routes/media.py`
- Create: `tests/web/test_media_sheet_seasons.py`

**Interfaces:**

- Produces: `MediaSeason` with `number: int`, `aired: int | None`, `owned_numbers: list[int]`, added to the media-sheet payload as `seasons: list[MediaSeason]`.

- [ ] **Step 1: Confirm the join, on the real database**

Run:

```bash
python - <<'EOF'
import sqlite3
con = sqlite3.connect("file:.data/library.db?mode=ro", uri=True)
rows = con.execute("""
  select i.title, s.number, e.number
    from media_item i
    join season s on s.item_id = i.id
    join episode e on e.season_id = s.id
    join media_release r on r.episode_id = e.id
    join media_file f on f.release_id = r.id
   where i.kind != 'movie'
   group by i.id, s.number, e.number
   limit 5
""").fetchall()
print(rows)
EOF
```

Expected: rows of `(title, season, episode)`. This is the join the route uses; running it first means the endpoint is written against a query that is known to return something.

- [ ] **Step 2: Write the failing test**

Create `tests/web/test_media_sheet_seasons.py`:

```python
"""The media sheet must say WHICH episodes are missing, not how many.

A `number <= owned count` threshold assumes the hole sits at the end of the
season. It is false for 35 series in this library — one owns episodes 1, 3, 5, 7,
9, 11 and 13 and was displayed as owning 1 to 7.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_a_season_reports_the_numbers_it_owns(client: TestClient, seeded_show) -> None:
    """The payload carries a LIST of numbers, never a count alone."""
    response = client.get(f"/api/media/tvdb/{seeded_show.tvdb_id}")
    assert response.status_code == 200
    season = response.json()["seasons"][0]
    assert isinstance(season["owned_numbers"], list)
    assert all(isinstance(n, int) for n in season["owned_numbers"])


def test_an_internal_hole_survives_the_payload(client: TestClient, holed_show) -> None:
    """Owning 1, 3 and 5 must not be reported as owning 1, 2 and 3."""
    body = client.get(f"/api/media/tvdb/{holed_show.tvdb_id}").json()
    season = body["seasons"][0]
    assert season["owned_numbers"] == [1, 3, 5]


def test_an_unknown_aired_count_is_null_not_zero(client: TestClient, uncatalogued_show) -> None:
    """Zero would read as « nothing aired »; null reads as « nobody counted »."""
    body = client.get(f"/api/media/tvdb/{uncatalogued_show.tvdb_id}").json()
    assert body["seasons"][0]["aired"] is None


def test_a_film_carries_no_seasons(client: TestClient, seeded_movie) -> None:
    """A film has no catalogue: the field is an empty list, never a fabricated one."""
    body = client.get(f"/api/media/tmdb/{seeded_movie.tmdb_id}").json()
    assert body["seasons"] == []
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/web/test_media_sheet_seasons.py -v`
Expected: FAIL — `seasons` is absent from the payload.

- [ ] **Step 4: Add the model and serve it**

Add `MediaSeason` to `personalscraper/web/models/media.py`:

```python
class MediaSeason(BaseModel):
    """One season of a series, as the media sheet needs it.

    Attributes:
        number: Season number.
        aired: How many episodes the provider catalogue lists for this season,
            or ``None`` when no catalogue is known. ``None`` and ``0`` are
            different facts: ``0`` says nothing has aired, ``None`` says nobody
            counted, and reporting the second as the first is how a library
            starts lying about itself.
        owned_numbers: The episode numbers actually held, in order. A LIST and
            not a count: « 21 of 26 » does not say which are missing, and a hole
            is rarely at the end of a season.
    """

    number: int
    aired: int | None = None
    owned_numbers: list[int] = []
```

Then extend the media-sheet route to fill it with the join from Step 1.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/web/test_media_sheet_seasons.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 6: Regenerate the typed contract and run the backend gates**

Run: `make openapi && make lint && make test`
Expected: all pass. Commit `frontend/openapi.json` and `frontend/src/api/schema.d.ts`.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/web tests/web/test_media_sheet_seasons.py frontend/openapi.json frontend/src/api/schema.d.ts
git commit -m "feat(shell-mobile): the media sheet payload says WHICH episodes are held

A list of numbers, never a count. « 21 of 26 » does not say which are missing,
and a hole is rarely at the end of a season: 35 series in this library have an
internal one, and one of them owns episodes 1, 3, 5, 7, 9, 11 and 13 while being
displayed as owning 1 to 7.

An unknown aired count is null and never zero — zero says nothing has aired,
null says nobody counted, and reporting the second as the first is how a library
starts lying about itself."
```

---

### Task 2: The visual header and the single back control

**Files:**

- Create: `frontend/src/components/media/MediaHero.tsx` + test
- Create: `frontend/src/components/ds/BackBar.tsx` + test
- Modify: `frontend/src/pages/MediaSheetPage.tsx`

**Interfaces:**

- Produces: `<MediaHero visual={url|null} title meta rating />`; `<BackBar label="Retour" onBack={fn} trailing={…} />`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/media/MediaHero.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { MediaHero } from "./MediaHero";

test("the visual occupies the header and carries its legibility gradient", () => {
  // The gradient is what makes the rule true, not good intentions: text must
  // always be read on a solid colour and never on an image.
  const { container } = render(
    <MediaHero
      visual="data:image/webp;base64,AA"
      title="Silo"
      meta="2023 · Série"
      rating={8.2}
    />,
  );
  const header = container.querySelector("[data-media-hero]") as HTMLElement;
  expect(header).not.toBeNull();
  expect(header.dataset.hasVisual).toBe("true");
});

test("without a visual the header degrades to a short field, not a broken box", () => {
  const { container } = render(
    <MediaHero visual={null} title="Silo" meta="2023 · Série" rating={null} />,
  );
  const header = container.querySelector("[data-media-hero]") as HTMLElement;
  expect(header.dataset.hasVisual).toBe("false");
  expect(screen.getByText("Silo")).toBeInTheDocument();
});

test("a missing rating is stated, never dropped", () => {
  render(
    <MediaHero visual={null} title="Silo" meta="2023 · Série" rating={null} />,
  );
  expect(screen.getByText(/note inconnue/i)).toBeInTheDocument();
});
```

Create `frontend/src/components/ds/BackBar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { BackBar } from "./BackBar";

test("the back bar sits in the flow, so it pushes content instead of covering it", () => {
  // A floating variant created a second design which, on screens without an
  // image, overlapped the title instead of pushing it.
  const { container } = render(<BackBar label="Retour" onBack={() => {}} />);
  const bar = container.firstElementChild as HTMLElement;
  expect(["", "static", "relative"]).toContain(bar.style.position);
});

test("the back control is a button with an accessible name", () => {
  render(<BackBar label="Retour" onBack={() => {}} />);
  expect(screen.getByRole("button", { name: /retour/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run them to verify they fail, then write both components**

Run: `cd frontend && npx vitest run src/components/media/MediaHero.test.tsx src/components/ds/BackBar.test.tsx` → FAIL.

Write `MediaHero.tsx`, whose header is a block **in the flow** carrying the visual as a background, with a closing gradient over its lower half and the title overlapping that edge; and `BackBar.tsx`, a single design used by every screen that has one.

Run again: PASS — 5 passed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/media/MediaHero.tsx frontend/src/components/media/MediaHero.test.tsx \
        frontend/src/components/ds/BackBar.tsx frontend/src/components/ds/BackBar.test.tsx
git commit -m "feat(shell-mobile): the visual is the top of the sheet, and there is one back control

The visual occupies the header in the flow and melts into the body through a
closing gradient — the gradient is what makes « text is never read on an image »
true, rather than good intentions. A medium without a visual degrades to a short
muted field: a declared difference, and the only one.

One back design, in the flow. A floating variant created a second design which,
on screens without an image, covered the title instead of pushing it — a bar
outside the flow pushes nothing, so it ends up covering."
```

---

### Task 3: Seasons that name their missing episodes

**Files:**

- Create: `frontend/src/components/media/SeasonList.tsx` + test
- Create: `frontend/src/components/media/missing.ts` + test

**Interfaces:**

- Produces: `missingNumbers(aired: number | null, owned: number[]): number[]`; `formatRanges(nums: number[]): string`; `<SeasonList seasons={…} episodes={…} />`.

- [ ] **Step 1: Write the failing test for the pure part**

Create `frontend/src/components/media/missing.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import { formatRanges, missingNumbers } from "./missing";

describe("missingNumbers", () => {
  test("an internal hole is found, not assumed to be at the end", () => {
    expect(missingNumbers(13, [1, 3, 5, 7, 9, 11, 13])).toEqual([
      2, 4, 6, 8, 10, 12,
    ]);
  });

  test("with no known aired count, reasoning stops at the highest owned episode", () => {
    // Above that maximum nothing is known; claiming a gap there would be an
    // invention, and claiming completeness would be a lie.
    expect(missingNumbers(null, [1, 2, 4])).toEqual([3]);
  });

  test("an announced season with nothing aired has nothing missing", () => {
    expect(missingNumbers(0, [])).toEqual([]);
  });

  test("a complete season has nothing missing", () => {
    expect(missingNumbers(3, [1, 2, 3])).toEqual([]);
  });
});

describe("formatRanges", () => {
  test("consecutive numbers become a range", () => {
    expect(formatRanges([3, 7, 12, 13, 14])).toBe("3, 7, 12–14");
  });

  test("two consecutive numbers stay listed, because a range of two reads worse", () => {
    expect(formatRanges([3, 4])).toBe("3, 4");
  });

  test("an empty list is an empty string", () => {
    expect(formatRanges([])).toBe("");
  });
});
```

- [ ] **Step 2: Run it to verify it fails, then write the module**

Run: `cd frontend && npx vitest run src/components/media/missing.test.ts` → FAIL.

Create `frontend/src/components/media/missing.ts`:

```ts
/**
 * Which episodes a season is missing.
 *
 * Presence is read from the LIST of owned numbers, never from a
 * `number <= owned count` threshold: that threshold assumes the hole sits at the
 * end of the season, which is false for 35 series in this library.
 *
 * With no known aired count, reasoning stops at the highest owned episode: below
 * it a gap is a genuine gap, above it nothing is known. Claiming a gap there
 * would be an invention; claiming completeness would be a lie.
 */
export function missingNumbers(
  aired: number | null,
  owned: number[],
): number[] {
  if (aired === 0) return [];
  const held = new Set(owned);
  const bound = aired ?? (owned.length ? Math.max(...owned) : 0);
  const out: number[] = [];
  for (let n = 1; n <= bound; n += 1) if (!held.has(n)) out.push(n);
  return out;
}

/** « 3, 7, 12, 13, 14 » reads badly; « 3, 7, 12–14 » reads. */
export function formatRanges(nums: number[]): string {
  const sorted = [...nums].sort((a, b) => a - b);
  const parts: string[] = [];
  for (let i = 0; i < sorted.length;) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j += 1;
    parts.push(
      j > i + 1
        ? `${sorted[i]}–${sorted[j]}`
        : sorted.slice(i, j + 1).join(", "),
    );
    i = j + 1;
  }
  return parts.join(", ");
}
```

Run again: PASS — 7 passed.

- [ ] **Step 3: Write the failing test for `SeasonList`**

Create `frontend/src/components/media/SeasonList.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { SeasonList } from "./SeasonList";

const SEASONS = [
  { number: 1, aired: 13, owned_numbers: [1, 3, 5, 7, 9, 11, 13] },
  { number: 2, aired: 10, owned_numbers: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] },
] as never[];

test("an incomplete season is open and names its missing episodes", () => {
  render(<SeasonList seasons={SEASONS} episodes={{}} />);
  expect(
    screen.getByText(/manquants : 2, 4, 6, 8, 10, 12/i),
  ).toBeInTheDocument();
});

test("a complete season is collapsed, because its header says enough", () => {
  const { container } = render(<SeasonList seasons={SEASONS} episodes={{}} />);
  const details = container.querySelectorAll("details");
  expect(details[0].open).toBe(true);
  expect(details[1].open).toBe(false);
});

test("an announced season says « à venir » rather than 0 of nothing", () => {
  render(
    <SeasonList
      seasons={[{ number: 3, aired: 0, owned_numbers: [] }] as never[]}
      episodes={{}}
    />,
  );
  expect(screen.getByText(/à venir/i)).toBeInTheDocument();
});

test("an unknown aired count shows « ? », never a fabricated total", () => {
  render(
    <SeasonList
      seasons={[{ number: 1, aired: null, owned_numbers: [1, 2] }] as never[]}
      episodes={{}}
    />,
  );
  expect(screen.getByText("2/?")).toBeInTheDocument();
});
```

- [ ] **Step 4: Run it to verify it fails, then write `SeasonList`**

Write it so that **one rendering** serves every season: the titled list when episode titles are known, and the numbered matrix as the declared fallback when they are not. A sheet must never contain both.

Run: `cd frontend && npx vitest run src/components/media/SeasonList.test.tsx`
Expected: PASS — 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/media
git commit -m "feat(shell-mobile): a season names the episodes it is missing

The question an incomplete series raises is WHICH, not how many. Presence is read
from the list of owned numbers, never from a « number <= owned count » threshold:
that threshold assumes the hole is at the end of the season, and it is false for
35 series here.

Three cases stay honest rather than invented: an unknown aired total shows « ? »
and reasoning stops at the highest owned episode, an announced season says
« à venir », and nothing known says so."
```

---

### Task 4: The trailer always leaves for YouTube

**Files:**

- Create: `frontend/src/components/media/TrailerRow.tsx` + test

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/media/TrailerRow.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { TrailerRow } from "./TrailerRow";

test("the trailer is a real outbound link", () => {
  render(
    <TrailerRow
      url="https://www.youtube.com/watch?v=8QOFIMvl-PU"
      label="Bande-annonce officielle"
    />,
  );
  const link = screen.getByRole("link", { name: /bande-annonce/i });
  expect(link).toHaveAttribute(
    "href",
    "https://www.youtube.com/watch?v=8QOFIMvl-PU",
  );
  expect(link).toHaveAttribute("target", "_blank");
  expect(link.getAttribute("rel")).toContain("noopener");
});

test("the control never promises in-app playback", () => {
  // Playback never happens inside the app, even when a local trailer file
  // exists next to the media: file presence is a separate fact and must not
  // change this control.
  const { container } = render(
    <TrailerRow
      url="https://www.youtube.com/watch?v=abc123"
      label="Bande-annonce"
    />,
  );
  expect(container.textContent).not.toMatch(
    /lecture ici|plein écran|dans l'app/i,
  );
});

test("no trailer says so rather than hiding the section", () => {
  render(<TrailerRow url={null} label={null} />);
  expect(screen.getByText(/aucune bande-annonce/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it to verify it fails, then write `TrailerRow`**

Run: `cd frontend && npx vitest run src/components/media/TrailerRow.test.tsx` → FAIL, then write it and re-run → PASS — 3 passed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/media/TrailerRow.tsx frontend/src/components/media/TrailerRow.test.tsx
git commit -m "feat(shell-mobile): a trailer always opens YouTube, never the app

Wherever one arrives from — library, acquisitions or Découvrir — and even when a
local trailer file sits next to the media: file presence is a separate fact and
must not change this control.

A missing trailer is stated rather than hiding the section: a section that
vanishes leaves the reader wondering whether it failed to load."
```

---

### Task 5: The quality-profile write path

**Files:**

- Modify: `personalscraper/web/models/acquisition.py`, `personalscraper/web/routes/acquisition.py`
- Create: `tests/web/test_follow_quality_profile.py`

**Interfaces:**

- Produces: `PATCH /api/acquisition/follows/{id}` accepts `quality_profile` with exactly four keys — `min_resolution`, `required_audio`, `require_known_resolution`, `exclude_3d`.

- [ ] **Step 1: Confirm the four fields, in the engine**

Run: `rg -n "class QualityProfile" -A 20 --type py personalscraper/acquire/desired.py`
Expected: exactly four fields. Anything the editor offers beyond them is a setting the engine never reads — a promise the interface cannot keep.

- [ ] **Step 2: Write the failing test**

Create `tests/web/test_follow_quality_profile.py`:

```python
"""The quality profile becomes writable — and only in the four fields that exist.

The profile FILTERS (it eliminates); the ranking ORDERS (it separates what
remains, and lives in ranking.json5). Losing that distinction is how an editor
ends up promising settings the engine never reads.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_the_four_fields_round_trip(client: TestClient, seeded_follow) -> None:
    """What is written is what is read back."""
    payload = {
        "quality_profile": {
            "min_resolution": "1080p",
            "required_audio": ["VF", "VOSTFR"],
            "require_known_resolution": True,
            "exclude_3d": True,
        }
    }
    assert client.patch(f"/api/acquisition/follows/{seeded_follow.id}", json=payload).status_code == 200
    body = client.get(f"/api/acquisition/follows/{seeded_follow.id}").json()
    assert body["quality_profile"]["min_resolution"] == "1080p"
    assert body["quality_profile"]["required_audio"] == ["VF", "VOSTFR"]


def test_an_unknown_key_is_rejected(client: TestClient, seeded_follow) -> None:
    """A key the engine never reads must not be silently accepted."""
    response = client.patch(
        f"/api/acquisition/follows/{seeded_follow.id}",
        json={"quality_profile": {"exclude_cam": True}},
    )
    assert response.status_code == 422


def test_the_write_path_is_staging_guarded(staging_client: TestClient, seeded_follow) -> None:
    """Every mutating endpoint refuses to write from the staging role."""
    response = staging_client.patch(
        f"/api/acquisition/follows/{seeded_follow.id}",
        json={"quality_profile": {"exclude_3d": True}},
    )
    assert response.status_code == 403
```

- [ ] **Step 3: Run it to verify it fails, then open the write path**

Run: `pytest tests/web/test_follow_quality_profile.py -v` → FAIL.

Add `quality_profile` to `UpdateFollowRequest` with a model that admits exactly the four keys (`model_config = ConfigDict(extra="forbid")`), persist it to `quality_profile_json`, and keep the route behind `require_not_staging`.

Run again: PASS — 3 passed.

- [ ] **Step 4: Regenerate the contract and run the gates**

Run: `make openapi && make lint && make test`
Expected: all pass. Commit the regenerated files.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/web tests/web/test_follow_quality_profile.py frontend/openapi.json frontend/src/api/schema.d.ts
git commit -m "feat(shell-mobile): the quality profile becomes writable, in its four real fields

The read path, the overlay precedence and the hard filter already existed; only
the write path was closed, deliberately, until an editor consumed it.

Exactly four keys, and an unknown one is rejected rather than silently accepted:
the profile FILTERS while the ranking ORDERS, and an editor that offers settings
the engine never reads makes a promise the interface cannot keep."
```

---

### Task 6: Phase gate

- [ ] **Step 1: Assemble the sheet**

In `frontend/src/pages/MediaSheetPage.tsx`, compose `BackBar`, `MediaHero`, `TrailerRow`, the synopsis, the cast, the library block, `SeasonList` and the identifiers — **in that fixed order**, with only nature-imposed variations between a film and a series.

- [ ] **Step 2: Test the order across the real spectrum**

Write a test that renders the sheet for a complete series, an incomplete series, a film and a medium with no visual, and asserts the section order is identical. Draw the sample **from the data**, not from a fixed handful: sampling five frozen cases is exactly how a divergence stayed invisible before.

- [ ] **Step 3: Move the sheet states into the measured set**

In `frontend/maquette/regions.json`, move `fiche-*` out of `unmeasuredStates` and declare the `fiche/*` regions.

- [ ] **Step 4: Run every gate**

Run:

```bash
make lint && make test && make check-frontend
cd frontend && npm run build
cd .. && python scripts/parity-probe.py --app-dir frontend/dist
```

Expected: all pass, probe `OK`.

- [ ] **Step 5: Exercise it by hand at 390 px, in both themes**

Open a complete series, an incomplete one, a film and a medium with no visual — in dark **and** light. Check: the header is in the flow and the title overlaps its lower edge in both; the back control is identical everywhere; the trailer leaves for YouTube; an incomplete season names its missing episodes.
The light theme is not a formality: a header once rendered upside down there while the dark theme looked perfect.

- [ ] **Step 6: Update the tracker, bump the version, commit**

```bash
git add IMPLEMENTATION.md pyproject.toml frontend/maquette/regions.json frontend/src
git commit -m "chore(shell-mobile): phase 4 gate — every poster leads somewhere worth arriving at

One sheet, the same everywhere, that says what a medium is, where it stands, and
which episodes are missing. Checked in both themes, because a header once
rendered upside down in light while dark looked perfect."
```

---

## Self-Review

**1. Spec coverage.** §5.6's four rules → Task 2 (header, back control), Task 4 (trailer), Task 6 Step 2 (section order drawn from the data). §5.7's two rules → Task 1 (presence read, server side) and Task 3 (one rendering, missing episodes named). §5.5's bounded backend opening → Task 5. R26 to R31 are each exercised by a test in this plan.

**2. Placeholder scan.** No TBD. Task 2 Step 2 and Task 6 Steps 1–2 describe composition rather than showing every line — the components they compose are fully specified above them, and the assertions those steps must make are stated exactly.

**3. Type consistency.** `MediaSeason` (`number`, `aired`, `owned_numbers`) is defined in Task 1 and consumed by `SeasonList` in Task 3 through `schema.d.ts`. `missingNumbers(aired, owned)` and `formatRanges(nums)` are defined and used under those names. `BackBar({label, onBack, trailing})` and `MediaHero({visual, title, meta, rating})` match their tests.

**One risk named:** Task 1's join returns owned episodes only for series whose files are linked to an episode row. A series indexed as loose files, with no episode link, would report an empty `owned_numbers` and its sheet would claim everything is missing — the loudest possible lie about a library. Before shipping, count how many series that affects; if any, the honest move is to state the case in the sheet rather than render it as a total loss.
