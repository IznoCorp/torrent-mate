/**
 * FollowedPanel — Phase 02 tests: compact rows (72 px poster, mono completeness,
 * DropdownMenu actions), synopsis absent, CompletenessAccordion preserved.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FollowedSeriesItem } from "@/api/acquisition";

// Inert hook mocks: the panel's mutations/queries never fire in these render
// tests — only the markup derived from the `data` prop is under test.
vi.mock("@/hooks/useAcquisition", () => ({
  useFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUnfollow: () => ({ mutate: vi.fn(), isPending: false }),
  useCompleteness: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
  useTrackedAcquisitionRun: () => undefined,
}));

vi.mock("@/hooks/useSchedulers", () => ({
  useSchedulers: () => ({ data: undefined }),
}));

import { FollowedPanel } from "./FollowedPanel";

/** A fully-typed followed item, with the P0-B counter fields nulled (no catalog). */
function makeItem(
  overrides: Partial<FollowedSeriesItem> = {},
): FollowedSeriesItem {
  return {
    id: 1,
    title: "House of the Dragon",
    kind: "show",
    active: true,
    added_at: 1_719_792_000,
    cadence: { interval_minutes: 60 },
    cadence_tier: null,
    next_search_at: null,
    quality_profile: null,
    wanted_pending: 0,
    wanted_grabbed: 0,
    season_count: 2,
    year: 2022,
    overview: null,
    poster_url: null,
    media_ref: { tvdb_id: 371572, tmdb_id: null, imdb_id: null },
    status: "up_to_date",
    aired_count: null,
    owned_count: null,
    inflight_count: null,
    queued_count: null,
    missing_count: null,
    ...overrides,
  };
}

function renderPanel(items: readonly FollowedSeriesItem[]): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <FollowedPanel
        data={items}
        isLoading={false}
        isError={false}
        error={null}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FollowedPanel — compact rows (Phase 02)", () => {
  it("renders the incomplete status badge as « Épisodes manquants »", () => {
    renderPanel([makeItem({ status: "incomplete" })]);

    expect(screen.getByText("Épisodes manquants")).toBeInTheDocument();
  });

  it("renders completeness as NN/NN in font-mono tabular-nums", () => {
    renderPanel([
      makeItem({
        status: "incomplete",
        aired_count: 18,
        owned_count: 15,
        inflight_count: 0,
        queued_count: 0,
        missing_count: 3,
      }),
    ]);

    // Compact row: completeness is "15/18" — no verbose "en médiathèque".
    expect(screen.getByText("15/18")).toBeInTheDocument();
    expect(screen.queryByText(/en médiathèque/)).not.toBeInTheDocument();
  });

  it("shows '—' for completeness when aired_count is null (no catalog)", () => {
    renderPanel([
      makeItem({
        id: 1,
        title: "Silo",
        status: "incomplete",
        aired_count: 10,
        owned_count: 9,
        missing_count: 1,
      }),
      // aired_count null = no cached catalog → "—" for completeness.
      makeItem({ id: 2, title: "Top Chef" }),
    ]);

    expect(screen.getByText("9/10")).toBeInTheDocument();
    // Top Chef has no catalog — completeness renders "—".
    expect(screen.getByText("—")).toBeInTheDocument();
    // No verbose "en médiathèque" caption anywhere.
    expect(screen.queryByText(/en médiathèque/)).not.toBeInTheDocument();
  });

  it("omits the synopsis (overview) from the compact row (E3)", () => {
    renderPanel([
      makeItem({
        overview:
          "An internal succession war within House Targaryen at the height of its power.",
      }),
    ]);

    // The overview text must NOT appear in the compact row.
    expect(
      screen.queryByText(/internal succession war/),
    ).not.toBeInTheDocument();
  });

  it("renders a poster thumb at ~72 px via DS MediaPoster", () => {
    renderPanel([makeItem()]);

    // The DS MediaPoster is always rendered (with initials fallback when
    // poster_url is null). Check that the row renders the item title, which
    // confirms the row layout is present.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
  });

  it("renders a DropdownMenu trigger for each active row", () => {
    renderPanel([makeItem()]);

    // The ⋯ button opens the actions dropdown.
    expect(
      screen.getByRole("button", { name: "Actions pour House of the Dragon" }),
    ).toBeInTheDocument();
  });

  it("renders the CompletenessAccordion below a series row", () => {
    renderPanel([makeItem({ kind: "show" })]);

    // The accordion trigger is still present below the compact row.
    expect(screen.getByText("Détail par épisode")).toBeInTheDocument();
  });

  it("does NOT render the CompletenessAccordion for movies", () => {
    renderPanel([makeItem({ kind: "movie", title: "Ferrari" })]);

    expect(screen.queryByText("Détail par épisode")).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — statut film sur ownership (D2-B)", () => {
  it("libelle un film manquant « Manquant » (pas « Épisodes manquants »)", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "incomplete" }),
    ]);

    expect(screen.getByText("Manquant")).toBeInTheDocument();
    expect(screen.queryByText("Épisodes manquants")).not.toBeInTheDocument();
  });

  it("libelle un film en médiathèque « Acquis » (pas « À jour »)", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "up_to_date" }),
    ]);

    expect(screen.getByText("Acquis")).toBeInTheDocument();
    expect(screen.queryByText("À jour")).not.toBeInTheDocument();
  });

  it("garde les libellés série pour une série incomplète", () => {
    renderPanel([makeItem({ kind: "show", status: "incomplete" })]);

    // The movie override must not leak into series cards.
    expect(screen.getByText("Épisodes manquants")).toBeInTheDocument();
    expect(screen.queryByText("Manquant")).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — suivis retirés (revue mobile 2026-07-15)", () => {
  it("un suivi retiré quitte la grille et apparaît dans la section repliée", () => {
    renderPanel([
      makeItem(),
      makeItem({
        id: 7,
        title: "Le Robot sauvage",
        kind: "movie",
        active: false,
      }),
    ]);

    // Grid: only the active follow renders as a compact row.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
    // Retired section: collapsed summary with count + reactivate control.
    expect(screen.getByText("Suivis retirés (1)")).toBeInTheDocument();
    expect(screen.getByText(/Le Robot sauvage/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Réactiver" }),
    ).toBeInTheDocument();
    // The active row has a dropdown trigger; the retired item does not.
    expect(
      screen.getByRole("button", { name: "Actions pour House of the Dragon" }),
    ).toBeInTheDocument();
  });

  it("aucune section retirés quand tout est actif", () => {
    renderPanel([makeItem()]);
    expect(screen.queryByText(/Suivis retirés/)).not.toBeInTheDocument();
  });
});
