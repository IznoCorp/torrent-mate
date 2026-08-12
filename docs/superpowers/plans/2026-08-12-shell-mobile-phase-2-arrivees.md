# Shell Mobile — Phase 2: Arrivées Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn three surfaces that each answer half a question — `/medias`, `/pipeline`, `/controle` — into one that answers it whole: _what arrived, did it get through, and what is stuck._

**Architecture:** A new `/arrivees` route reads the staging contents and the pipeline's run state, and presents them as one narrative in five urgency sections. The pipeline's runs, health and controls move into `/systeme` in **reception only** — the same PR, or removing `/pipeline` from the bar orphans its runs. The three old routes become redirects; none is deleted, because a bookmark that 404s is a regression the operator would meet before anyone else.

**Tech Stack:** React 19, TypeScript, TanStack Query, vitest + Testing Library, FastAPI (existing endpoints, no new ones), the phase-0 parity guards.

## Global Constraints

- **The prototype is the source.** `frontend/maquette/refonte.html` is the design reference (§15 of `docs/reference/product-intent.md`). A design change starts there; the code follows.
- **CSS is extracted, never retyped.** Run `python scripts/extract-maquette-css.py`; never hand-edit `app-surface.css`.
- **No new backend endpoint in this phase.** `/api/staging/media`, `/api/pipeline/status`, `/api/pipeline/history` and `/api/maintenance/*` already serve everything Arrivées needs. If something genuinely cannot be built from them, that is a finding to report before inventing a route.
- **Every mutating endpoint stays staging-guarded** (`require_not_staging`) and typed (Pydantic `response_model` → OpenAPI → `schema.d.ts`). Any route change ⇒ `make openapi` and commit the regenerated files.
- **The auth perimeter is the single `guarded_api` dependency.** Never add a per-route `Depends(require_session)`.
- **No dead end (DOIT-7), no silent nothing (§8).** A surface that loads says so with skeletons of the right shape; a surface that is empty says why and offers a way out; a surface in error names the cause and offers a retry.
- **Probe emulation is fixed:** 390 × 844, DPR 2, `isMobile`, `hasTouch`. Never bind a local server to 8710 or 8711.
- **Search safety:** every `rg` carries `--type` or `-g`.
- **Frontend gates on every commit:** `npx tsc -b --noEmit`, `npx eslint src`, `npx vitest run`, `make check-frontend`.
- **Comments in English**, with no reference to a session, a phase number, or a dated decision. Interface copy stays French.
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

- **Resolving must FINISH the pipeline, not label a folder.** Choosing a candidate relaunches
  the scrape and the medium completes its whole pipeline — metadata, posters, trailer,
  verification, dispatch — by reusing the **single trigger authority** (the pipeline lock and
  the existing runner), **never a second mechanism**. The interface must show that
  continuation: the card advances, its journey fills, and it ends dispatched. A medium still
  stuck in staging after « resolution » is a breach of the constitution, not a rough edge.
- **Work on `feat/shell-mobile`, never on `main`.** Every phase of this rebuild targets the
  same integration branch; `main` — and therefore production — is touched once, at the end,
  after everything has been validated together. This is the mission's one non-negotiable
  arbitration. Before the first commit of any task, run `git branch --show-current` and stop
  if it is not `feat/shell-mobile`: a phase committed to `main` cannot be un-shipped, and a
  local `main` that has drifted produces a pull request with no checks at all.
---

## File Structure

| File                                                    | Responsibility                                                                                                                                     |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/pages/ArriveesPage.tsx`                   | **Create.** The route component: fetches, composes the five sections, owns the loading/empty/error phases.                                         |
| `frontend/src/components/arrivees/useArrivees.ts`       | **Create.** The read model: turns the staging and pipeline payloads into the five urgency buckets. Pure, and therefore testable without a browser. |
| `frontend/src/components/arrivees/ArrivalCard.tsx`      | **Create.** One arrival: poster, title, reason, journey strip, footer action.                                                                      |
| `frontend/src/components/arrivees/ResolutionScreen.tsx` | **Create.** The full screen that identifies a stuck folder — a screen, not a sheet.                                                                |
| `frontend/src/components/arrivees/JourneyStrip.tsx`     | **Create.** The pipeline stages of one arrival, on its own full-width line.                                                                        |
| `frontend/src/pages/SystemePage.tsx`                    | **Modify.** Receives runs, health and pipeline controls.                                                                                           |
| `frontend/src/router.tsx`                               | **Modify.** Add `/arrivees`; demote `/medias`, `/pipeline`, `/controle` to redirects.                                                              |
| `frontend/src/components/layout/nav.ts`                 | **Modify.** Four bottom-bar entries: Acquisition, Médiathèque, Arrivées, Système.                                                                  |
| `frontend/maquette/regions.json`                        | **Modify.** Move the `arrivees/*` states out of `unmeasuredStates` into measured regions.                                                          |

**Read before starting:** §3 and §5 of the spec, `frontend/maquette/README.md`, and the prototype states `arr-repos`, `arr-charge`, `arr-chargement`, `arr-erreur`, `arr-resolution`.

---

### Task 1: The read model

Everything else in this phase renders what this task computes. It is pure, so it is tested without a browser and without a network.

**Files:**

- Create: `frontend/src/components/arrivees/useArrivees.ts`
- Create: `frontend/src/components/arrivees/useArrivees.test.ts`

**Interfaces:**

- Consumes: `components["schemas"]["StagingMedia"]` and the pipeline status payload, both from `frontend/src/api/schema.d.ts`.
- Produces:
  - `type Bucket = "a_traiter" | "en_vol" | "ca_avance" | "range" | "rien"`
  - `bucketOf(media: StagingMedia): Bucket`
  - `groupArrivals(medias: StagingMedia[]): Record<Bucket, StagingMedia[]>`

- [ ] **Step 1: Read the real payload shape**

Run:

```bash
rg -n "class StagingMedia" -A 40 -g '*.py' personalscraper/web/models/staging.py
rg -n "StagingMedia" -g '*.d.ts' frontend/src/api/schema.d.ts | head -3
```

Expected: you can name every field the read model will branch on. Guessing a field name here produces a bucket that is always empty and a page that looks calm while it is lying.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/components/arrivees/useArrivees.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import { bucketOf, groupArrivals } from "./useArrivees";
import type { StagingMedia } from "./useArrivees";

/** A staging media with everything nominal; each test overrides what it needs. */
function media(over: Partial<StagingMedia> = {}): StagingMedia {
  return {
    id: "m1",
    title: "Silo",
    scrape_state: "done",
    dispatch_state: "done",
    blocked_reason: null,
    ...over,
  } as StagingMedia;
}

describe("bucketOf", () => {
  test("an unidentified media needs the operator", () => {
    expect(bucketOf(media({ scrape_state: "unidentified" }))).toBe("a_traiter");
  });

  test("a media blocked by a stated reason needs the operator", () => {
    expect(bucketOf(media({ blocked_reason: "disque plein" }))).toBe(
      "a_traiter",
    );
  });

  test("a media still moving through the pipeline is in flight", () => {
    expect(bucketOf(media({ dispatch_state: "running" }))).toBe("en_vol");
  });

  test("a media that finished today is filed", () => {
    expect(bucketOf(media())).toBe("range");
  });
});

describe("groupArrivals", () => {
  test("every media lands in exactly one bucket", () => {
    const all = [
      media({ id: "a", scrape_state: "unidentified" }),
      media({ id: "b", dispatch_state: "running" }),
      media({ id: "c" }),
    ];
    const grouped = groupArrivals(all);
    const placed = Object.values(grouped)
      .flat()
      .map((m) => m.id);
    expect(placed.sort()).toEqual(["a", "b", "c"]);
  });

  test("an empty staging area yields empty buckets, not undefined ones", () => {
    // A bucket that is undefined rather than empty makes the view crash on
    // `.length` — and the empty state is precisely the state this surface must
    // render well, because it is the usual one.
    const grouped = groupArrivals([]);
    expect(grouped.a_traiter).toEqual([]);
    expect(grouped.en_vol).toEqual([]);
    expect(grouped.range).toEqual([]);
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/components/arrivees/useArrivees.test.ts`
Expected: FAIL — the module does not exist.

- [ ] **Step 4: Write the read model**

Create `frontend/src/components/arrivees/useArrivees.ts`. Use the real field names read in Step 1; the branch order below is what matters:

```ts
import type { components } from "@/api/schema";

export type StagingMedia = components["schemas"]["StagingMedia"];

export type Bucket = "a_traiter" | "en_vol" | "ca_avance" | "range" | "rien";

const EMPTY: Record<Bucket, StagingMedia[]> = {
  a_traiter: [],
  en_vol: [],
  ca_avance: [],
  range: [],
  rien: [],
};

/**
 * Which section an arrival belongs to.
 *
 * The order of the branches is the order of urgency: what needs the operator
 * comes first, and nothing that needs them can be shadowed by a later branch.
 * A media is in exactly one bucket — a media in two would be counted twice by
 * the badge, which is the fastest way to make a count stop being believed.
 */
export function bucketOf(media: StagingMedia): Bucket {
  if (media.scrape_state === "unidentified" || media.blocked_reason)
    return "a_traiter";
  if (media.dispatch_state === "running" || media.scrape_state === "running")
    return "en_vol";
  if (media.dispatch_state === "pending") return "ca_avance";
  return "range";
}

/** Groups arrivals by section, always returning every bucket. */
export function groupArrivals(
  medias: StagingMedia[],
): Record<Bucket, StagingMedia[]> {
  const out: Record<Bucket, StagingMedia[]> = {
    a_traiter: [],
    en_vol: [],
    ca_avance: [],
    range: [],
    rien: [],
  };
  for (const media of medias) out[bucketOf(media)].push(media);
  return out;
}

export { EMPTY as EMPTY_BUCKETS };
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd frontend && npx vitest run src/components/arrivees/useArrivees.test.ts`
Expected: PASS — 6 passed. If a test fails because a field name differs, fix the **code** to the real name; never loosen the test to match a guess.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/arrivees
git commit -m "feat(shell-mobile): the read model behind Arrivées

Turns the staging payload into the five urgency sections. Pure, so it is tested
without a browser and without a network.

A media lands in exactly one bucket: one in two would be counted twice by the
badge, which is the fastest way to make a count stop being believed. Every
bucket is always present — an undefined bucket crashes the view on .length, and
the empty state is precisely the one this surface must render well, because it
is the usual one."
```

---

### Task 2: The page, with its three phases

**Files:**

- Create: `frontend/src/pages/ArriveesPage.tsx` + `ArriveesPage.test.tsx`
- Create: `frontend/src/components/arrivees/ArrivalCard.tsx` + test
- Create: `frontend/src/components/arrivees/JourneyStrip.tsx` + test
- Modify: `frontend/src/router.tsx`, `frontend/src/components/layout/nav.ts`

**Interfaces:**

- Consumes: `groupArrivals` from Task 1; `Chip`, `SectionHeader`, `SwipeRow`, `BottomSheet` from phase 1.
- Produces: the route `/arrivees`; `<ArrivalCard media={…} />`; `<JourneyStrip stages={…} />`.

- [ ] **Step 1: Write the failing test for the three phases**

Create `frontend/src/pages/ArriveesPage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ArriveesPage } from "./ArriveesPage";

// The three phases every surface goes through. A page that only renders its
// ready state is a page whose loading and error paths ship untested — and those
// are the ones the operator meets on a bad day.

test("while loading, the page shows skeletons of the right shape", () => {
  render(<ArriveesPage state={{ status: "loading" }} />);
  expect(screen.getAllByTestId("skeleton-card").length).toBeGreaterThan(0);
  expect(screen.queryByText(/chargement/i)).toBeNull();
});

test("on error, the page names the cause and offers a retry", () => {
  const retry = vi.fn();
  render(
    <ArriveesPage
      state={{
        status: "error",
        message: "Le service de staging ne répond pas.",
      }}
      onRetry={retry}
    />,
  );
  expect(screen.getByText(/ne répond pas/)).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /réessayer/i }),
  ).toBeInTheDocument();
});

test("when nothing arrived, the page says so and does not look broken", () => {
  render(<ArriveesPage state={{ status: "ready", medias: [] }} />);
  expect(screen.getByText(/rien n'est arrivé/i)).toBeInTheDocument();
});

test("a stuck arrival is listed first and offers a way out", () => {
  render(
    <ArriveesPage
      state={{
        status: "ready",
        medias: [
          {
            id: "a",
            title: "Backrooms 2026",
            scrape_state: "unidentified",
          } as never,
          {
            id: "b",
            title: "Silo",
            scrape_state: "done",
            dispatch_state: "done",
          } as never,
        ],
      }}
    />,
  );
  const headings = screen.getAllByRole("heading").map((h) => h.textContent);
  expect(headings[0]).toMatch(/à traiter/i);
  expect(screen.getByRole("button", { name: /résoudre/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/pages/ArriveesPage.test.tsx`
Expected: FAIL — the page does not exist.

- [ ] **Step 3: Write `JourneyStrip`**

Create `frontend/src/components/arrivees/JourneyStrip.tsx`:

```tsx
/**
 * One arrival's pipeline stages, on its own full-width line.
 *
 * It never shares a line with the card's text: the strip is the only thing that
 * says how far a media got, and squeezed beside a title it becomes decoration.
 *
 * A stage that was not reached is stated « à venir », never « pas faite »: a
 * journey has no hole, and showing an unreached step as failed describes a path
 * that does not exist.
 */
export type Stage = {
  key: string;
  label: string;
  state: "done" | "running" | "upcoming" | "failed";
};

export function JourneyStrip({ stages }: { stages: Stage[] }) {
  return (
    <ol className="journey">
      {stages.map((stage) => (
        <li key={stage.key} data-state={stage.state}>
          <span className="journeydot" />
          <span className="journeylabel">{stage.label}</span>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 4: Write `ArrivalCard`**

Create `frontend/src/components/arrivees/ArrivalCard.tsx`:

```tsx
import { Chip } from "@/components/ds/Chip";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { JourneyStrip, type Stage } from "./JourneyStrip";
import type { StagingMedia } from "./useArrivees";

/**
 * One arrival.
 *
 * The poster is a button only when a media sheet genuinely exists behind it: an
 * unidentified media is a release name, and offering a dead link is as broken a
 * promise as offering a greyed-out button.
 */
export function ArrivalCard({
  media,
  stages,
  footer,
}: {
  media: StagingMedia;
  stages: Stage[];
  footer?: { label: string; onClick: () => void };
}) {
  const identified = Boolean(media.provider && media.provider_id);
  return (
    <article className="card">
      <div className="ctop">
        {identified ? (
          <button
            type="button"
            className="poster"
            aria-label={`Fiche de ${media.title}`}
          >
            <MediaPoster title={media.title} />
          </button>
        ) : (
          <span
            className="poster"
            title="Média non identifié — pas de fiche disponible"
          >
            <MediaPoster title={media.title} />
          </span>
        )}
        <div className="cbody">
          <span className="ctitle">{media.title}</span>
          {media.blocked_reason ? (
            <Chip tone="danger" label={media.blocked_reason} />
          ) : null}
        </div>
      </div>
      <JourneyStrip stages={stages} />
      {footer ? (
        <button type="button" className="cfoot" onClick={footer.onClick}>
          {footer.label}
        </button>
      ) : null}
    </article>
  );
}
```

- [ ] **Step 5: Write the page**

Create `frontend/src/pages/ArriveesPage.tsx`, rendering the five sections in urgency order, and the three phases. Sections with no items are not rendered; **the view as a whole**, when empty, states why:

```tsx
import { SectionHeader } from "@/components/ds/SectionHeader";
import { ArrivalCard } from "@/components/arrivees/ArrivalCard";
import {
  groupArrivals,
  type StagingMedia,
} from "@/components/arrivees/useArrivees";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; medias: StagingMedia[] };

const SECTIONS = [
  { bucket: "a_traiter", tone: "danger", title: "À traiter" },
  { bucket: "en_vol", tone: "info", title: "En vol" },
  { bucket: "ca_avance", tone: "info", title: "Ça avance" },
  { bucket: "range", tone: "success", title: "Rangé aujourd'hui" },
] as const;

export function ArriveesPage({
  state,
  onRetry,
}: {
  state: State;
  onRetry?: () => void;
}) {
  if (state.status === "loading") {
    // Skeletons of the right SHAPE, never a bare « Chargement… »: a skeleton
    // that looks like the card it replaces tells you what is coming.
    return (
      <div className="tm body">
        {[0, 1, 2].map((i) => (
          <div key={i} className="skelcard" data-testid="skeleton-card" />
        ))}
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="tm body">
        <div className="surferr">
          <p>{state.message}</p>
          <button type="button" onClick={onRetry}>
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  const grouped = groupArrivals(state.medias);
  const total = state.medias.length;

  if (total === 0) {
    return (
      <div className="tm body">
        <div className="empty">
          <b>Rien n'est arrivé.</b>
          <p>
            La zone de transit est vide. Les médias apparaîtront ici dès qu'un
            téléchargement sera terminé.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="tm body">
      {SECTIONS.map(({ bucket, tone, title }) => {
        const items = grouped[bucket];
        if (items.length === 0) return null;
        return (
          <section key={bucket}>
            <SectionHeader tone={tone} title={title} count={items.length} />
            {items.map((media) => (
              <ArrivalCard
                key={media.id}
                media={media}
                stages={[]}
                footer={
                  bucket === "a_traiter"
                    ? { label: "Résoudre →", onClick: () => {} }
                    : undefined
                }
              />
            ))}
          </section>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/ArriveesPage.test.tsx`
Expected: PASS — 4 passed.

- [ ] **Step 7: Wire the route and the bottom bar**

In `frontend/src/router.tsx`, add `{ path: "arrivees", element: <ArriveesPage … /> }` next to the existing entries. In `frontend/src/components/layout/nav.ts`, make the four bottom-bar entries Acquisition, Médiathèque, Arrivées, Système.

- [ ] **Step 8: Verify the router tests still pass**

Run: `cd frontend && npx vitest run src/router.test.tsx src/components/layout`
Expected: PASS. If a nav test asserts the old five entries, update the assertion — but read it first: it may be asserting an invariant the new bar must still honour.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(shell-mobile): Arrivées answers the whole question, not a third of it

What arrived, whether it got through, and what is stuck — one surface where
three each answered a fragment.

The three phases ship together: skeletons of the right shape while loading, a
named cause and a retry on error, and an empty state that says why rather than
looking broken. Those are the states the operator meets on a bad day, and they
are the ones that used to ship untested.

A poster is a button only when a media sheet genuinely exists behind it: an
unidentified media is a release name, and a dead link is as broken a promise as
a greyed-out button."
```

---

### Task 3: The resolution screen

Identifying a stuck folder is the reason `/arrivees` exists. It is a **screen**, not a bottom sheet: on `/medias` it appeared _under_ the list one was reading, and on a phone it was never seen.

**Files:**

- Create: `frontend/src/components/arrivees/ResolutionScreen.tsx` + test

**Interfaces:**

- Produces: `<ResolutionScreen folder="Backrooms 2026" candidates={…} onAssociate={fn} onManualSearch={fn} />`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/arrivees/ResolutionScreen.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ResolutionScreen } from "./ResolutionScreen";

const CANDIDATES = [
  {
    id: 1284120,
    label: "Backrooms",
    meta: "2026 · Film · TMDB 1284120",
    confidence: 92,
  },
  {
    id: 1109371,
    label: "The Backrooms",
    meta: "2024 · Film · TMDB 1109371",
    confidence: 61,
  },
];

test("each candidate states what makes it a candidate", () => {
  render(
    <ResolutionScreen
      folder="Backrooms 2026"
      candidates={CANDIDATES}
      onAssociate={() => {}}
      onManualSearch={() => {}}
    />,
  );
  expect(screen.getByText(/confiance 92/i)).toBeInTheDocument();
});

test("choosing a candidate associates it — it never creates a follow", () => {
  // Identify is not follow. Offering « add to follows » here answers a question
  // nobody asked and leaves the folder just as stuck.
  const onAssociate = vi.fn();
  render(
    <ResolutionScreen
      folder="Backrooms 2026"
      candidates={CANDIDATES}
      onAssociate={onAssociate}
      onManualSearch={() => {}}
    />,
  );
  fireEvent.click(
    screen.getAllByRole("button", { name: /c'est celui-ci/i })[0],
  );
  expect(onAssociate).toHaveBeenCalledWith(1284120);
  expect(screen.queryByRole("button", { name: /suivre|ajouter/i })).toBeNull();
});

test("associating relaunches the pipeline, it does not merely label the folder", () => {
  // Resolving is not « writing an NFO ». The medium must complete its pipeline —
  // metadata, posters, trailer, verification, dispatch — through the existing
  // runner and its lock, never through a second mechanism. A medium still stuck
  // in staging after « resolution » is a breach of the constitution.
  const onAssociate = vi.fn();
  render(
    <ResolutionScreen
      folder="Backrooms 2026"
      candidates={CANDIDATES}
      onAssociate={onAssociate}
      onManualSearch={() => {}}
    />,
  );
  fireEvent.click(screen.getAllByRole("button", { name: /c'est celui-ci/i })[0]);
  // The screen hands the choice over; the caller is what relaunches. What this
  // test pins is that the screen does NOT offer a « write metadata only » path,
  // which is the shape the breach takes.
  expect(onAssociate).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("button", { name: /écrire la nfo|métadonnées seules/i })).toBeNull();
});

test("none of the candidates is never a dead end", () => {
  // The way out is not a sentence, it is a pre-filled screen.
  const onManualSearch = vi.fn();
  render(
    <ResolutionScreen
      folder="Backrooms 2026"
      candidates={CANDIDATES}
      onAssociate={() => {}}
      onManualSearch={onManualSearch}
    />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: /chercher manuellement/i }),
  );
  expect(onManualSearch).toHaveBeenCalledWith("Backrooms 2026");
});

test("an empty candidate list still offers the way out", () => {
  const onManualSearch = vi.fn();
  render(
    <ResolutionScreen
      folder="Machin Truc 2026"
      candidates={[]}
      onAssociate={() => {}}
      onManualSearch={onManualSearch}
    />,
  );
  expect(screen.getByText(/aucun média identifié/i)).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /chercher manuellement/i }),
  ).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it to verify it fails, then write the screen**

Run: `cd frontend && npx vitest run src/components/arrivees/ResolutionScreen.test.tsx` → FAIL.

Create `frontend/src/components/arrivees/ResolutionScreen.tsx`:

```tsx
export type Candidate = {
  id: number;
  label: string;
  meta: string;
  confidence: number;
};

/**
 * Identifies a stuck folder.
 *
 * A SCREEN, not a bottom sheet: as a sheet it appeared under the list one was
 * reading, and on a phone it was never seen.
 *
 * The verb here is ASSOCIATE, never follow. Identifying tells the pipeline which
 * media a folder is so it resumes its scrape; a media one already owns is the
 * expected case, not a warning. Offering « add to follows » answers a question
 * nobody asked and leaves the folder just as stuck.
 */
export function ResolutionScreen({
  folder,
  candidates,
  onAssociate,
  onManualSearch,
}: {
  folder: string;
  candidates: Candidate[];
  onAssociate: (id: number) => void;
  onManualSearch: (query: string) => void;
}) {
  return (
    <div className="tm body">
      <h2 className="h2">{folder}</h2>
      <p className="sub">
        Aucun média identifié. Voici ce que les providers proposent pour ce nom.
      </p>

      {candidates.map((candidate) => (
        <article key={candidate.id} className="card">
          <div className="cbody">
            <span className="ctitle">{candidate.label}</span>
            <span className="csub">{candidate.meta}</span>
            <span className="chip" data-tone="info">
              confiance {candidate.confidence} %
            </span>
          </div>
          <button
            type="button"
            className="cfoot solid"
            onClick={() => onAssociate(candidate.id)}
          >
            C'est celui-ci
          </button>
        </article>
      ))}

      <div className="rulenote">
        <b>Aucun de ceux-là ?</b>
        <p>La recherche manuelle s'ouvre pré-remplie avec le nom du dossier.</p>
        <button type="button" onClick={() => onManualSearch(folder)}>
          Chercher manuellement →
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run it to verify it passes**

Run: `cd frontend && npx vitest run src/components/arrivees/ResolutionScreen.test.tsx`
Expected: PASS — 4 passed.

- [ ] **Step 4: Verify the continuation, on the real pipeline**

Resolve a genuinely stuck folder on staging and watch what follows. Expected: the scrape
relaunches through the existing runner, the card leaves « À traiter », its journey fills, and
the medium ends dispatched. Check the pipeline lock was taken by that runner and not by a
second mechanism.

A medium still sitting in staging after « resolution » means the screen labelled a folder
instead of restarting it — which is the failure this whole surface exists to prevent.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/arrivees
git commit -m "feat(shell-mobile): resolving a stuck folder is a screen, not a sheet

As a sheet it appeared under the list one was reading, and on a phone it was
never seen.

The verb is ASSOCIATE, never follow: identifying tells the pipeline which media a
folder is so it resumes its scrape, and a media one already owns is the expected
case rather than a warning. « None of these » is not a sentence but a pre-filled
screen — a way out that is only described is a dead end with better manners."
```

---

### Task 4: Système receives the pipeline, and the old routes become redirects

These two must land in the same commit: removing `/pipeline` from the bar before Système receives its runs orphans them.

**Files:**

- Modify: `frontend/src/pages/SystemePage.tsx`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/components/layout/nav.ts`

- [ ] **Step 1: Write the failing test for the redirects**

Add to `frontend/src/router.test.tsx`:

```tsx
test.each(["/medias", "/pipeline", "/controle"])(
  "%s still resolves, as a redirect",
  async (path) => {
    // A bookmark that 404s is a regression the operator meets before anyone
    // else. None of these routes is deleted; each points at what replaced it.
    const router = makeTestRouter([path]);
    render(<RouterProvider router={router} />);
    expect(await screen.findByTestId("app-shell")).toBeInTheDocument();
    expect(router.state.location.pathname).not.toBe(path);
  },
);
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/router.test.tsx`
Expected: FAIL — the three routes still render their old pages.

- [ ] **Step 3: Move the pipeline's reception into Système**

In `frontend/src/pages/SystemePage.tsx`, add the runs, health and controls sections, reading from `/api/pipeline/status`, `/api/pipeline/history` and `/api/maintenance/*`. Its own mobile redesign is deliberately deferred — this task moves the reception, not the drawing.

- [ ] **Step 4: Demote the three routes**

In `frontend/src/router.tsx`:

```tsx
{ path: "medias", element: <LegacyRedirect to="/arrivees" /> },
{ path: "pipeline", element: <LegacyRedirect to="/systeme" /> },
{ path: "controle", element: <LegacyRedirect to="/systeme" /> },
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/router.test.tsx src/pages/SystemePage.test.tsx`
Expected: PASS.

- [ ] **Step 6: Check no link still points at a demoted route as if it were a page**

Run: `rg "to=\"/medias\"|to=\"/pipeline\"|to=\"/controle\"|href=\"/medias\"" -g '*.tsx' frontend/src`
Expected: only the redirect declarations themselves. A link that lands on a redirect works, but it teaches the wrong destination.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(shell-mobile): Système receives the pipeline, the old routes redirect

These land together on purpose: removing /pipeline from the bar before Système
receives its runs orphans them, and a run nobody can reach is a run nobody
trusts.

None of the three routes is deleted — a bookmark that 404s is a regression the
operator meets before anyone else. Each points at what replaced it."
```

---

### Task 5: Phase gate

- [ ] **Step 1: Move the Arrivées states into the measured set**

In `frontend/maquette/regions.json`, move `arr-repos`, `arr-charge`, `arr-chargement`, `arr-erreur` and `arr-resolution` out of `unmeasuredStates`, and add the `arrivees/*` regions with their selectors and states.

- [ ] **Step 2: Run the probe over the new regions**

Run:

```bash
cd frontend && npm run build
cd .. && python scripts/parity-probe.py --app-dir frontend/dist
```

Expected: `OK`. A divergence here is a defect in the app: fix the code, or amend the prototype **first** and write down why.

- [ ] **Step 3: Run every gate**

Run: `make check-frontend && pytest tests/scripts -v`
Expected: all pass.

- [ ] **Step 4: Exercise the surface by hand at 390 px**

Open `/arrivees` at 390 px wide with a genuinely empty staging area, then with a stuck folder present. Check: the empty state says why; the stuck folder is listed first; « Résoudre » opens a screen and not a sheet; the last action of that screen is reachable at maximum scroll.
This is the step no measurement replaces — the probe measures the regions it was told about.

- [ ] **Step 5: Update the tracker and bump the version, then commit**

```bash
git add IMPLEMENTATION.md pyproject.toml frontend/maquette/regions.json
git commit -m "chore(shell-mobile): phase 2 gate — three surfaces become one

Arrivées and the Système reception ship together, the old routes redirect, and
the Arrivées states join the measured set: from here on, a divergence on this
surface fails the build rather than waiting to be noticed."
```

---

## Self-Review

**1. Spec coverage.** §3's target architecture (four bottom-bar entries) → Task 2 Step 7 and Task 4. §5's Arrivées narrative → Tasks 1 and 2. The resolution screen and its two verbs (§5.4) → Task 3, whose second test asserts that no follow verb appears. B5 (Système in reception only) → Task 4, which moves the reception and explicitly does not redraw. §8's three phases per surface → Task 2 Step 1, which tests all three before any of them is written.

**2. Placeholder scan.** No TBD. Task 4 Step 3 describes moving existing sections rather than showing their code — that is a move of code that already exists and whose shape the implementer reads in `Pipeline.tsx`; the step names the endpoints so nothing is guessed.

**3. Type consistency.** `StagingMedia`, `Bucket`, `bucketOf`, `groupArrivals` are defined in Task 1 and used under those names in Tasks 2. `Stage` is defined in `JourneyStrip.tsx` and imported by `ArrivalCard.tsx`. `Candidate` is defined in `ResolutionScreen.tsx` and used only there.

**One risk named:** Task 1 Step 1 may reveal that `StagingMedia` does not carry a field the five buckets need — for instance no distinction between « pending » and « running ». If so, the honest move is to report it before inventing a derived state in the frontend: a bucket computed from a field that does not mean what its name suggests is a surface that looks calm while it lies.
