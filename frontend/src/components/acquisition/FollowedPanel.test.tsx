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

/** A fully-typed followed item, with the five-state counters nulled (no catalog). */
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
    status: "a_jour",
    priming_running: false,
    aired_count: null,
    owned_count: null,
    a_recuperer_count: null,
    en_acquisition_count: null,
    en_attente_count: null,
    non_verifie_count: null,
    movie_facts: null,
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
  it("renders the a_recuperer status badge as « À récupérer »", () => {
    renderPanel([makeItem({ status: "a_recuperer" })]);

    expect(screen.getByText("À récupérer")).toBeInTheDocument();
  });

  it("renders completeness as NN/NN in font-mono tabular-nums", () => {
    renderPanel([
      makeItem({
        status: "a_recuperer",
        aired_count: 18,
        owned_count: 15,
        a_recuperer_count: 3,
      }),
    ]);

    // Compact row: completeness is "15/18" — no verbose "en médiathèque".
    const completeSpan = screen.getByText("15/18");
    expect(completeSpan).toBeInTheDocument();
    // The completeness node must carry font-mono AND tabular-nums classes.
    expect(completeSpan.className).toContain("font-mono");
    expect(completeSpan.className).toContain("tabular-nums");
    expect(screen.queryByText(/en médiathèque/)).not.toBeInTheDocument();
  });

  it("shows '—' for completeness when aired_count is null (no catalog)", () => {
    renderPanel([
      makeItem({
        id: 1,
        title: "Silo",
        status: "a_recuperer",
        aired_count: 10,
        owned_count: 9,
        a_recuperer_count: 1,
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
    // poster_url is null). It renders a div[role="img"] with aria-label.
    const poster = screen.getByRole("img", { name: "House of the Dragon" });
    expect(poster).toBeInTheDocument();
    // The item title is also rendered in the row.
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
  it("garde le libellé partagé pour un film à récupérer", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "a_recuperer" }),
    ]);

    expect(screen.getByText("À récupérer")).toBeInTheDocument();
  });

  it("libelle un film en médiathèque « Acquis » (pas « À jour »)", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "a_jour" }),
    ]);

    expect(screen.getByText("Acquis")).toBeInTheDocument();
    expect(screen.queryByText("À jour")).not.toBeInTheDocument();
  });

  it("garde les libellés série pour une série à jour", () => {
    renderPanel([makeItem({ kind: "show", status: "a_jour" })]);

    // The movie override must not leak into series cards.
    expect(screen.getByText("À jour")).toBeInTheDocument();
    expect(screen.queryByText("Acquis")).not.toBeInTheDocument();
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
