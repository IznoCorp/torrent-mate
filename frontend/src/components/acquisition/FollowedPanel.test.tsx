/**
 * FollowedPanel — P0-B tests: the backend-derived ``incomplete`` status maps to
 * its French badge label, and the cached-catalog owned/aired caption renders
 * (with proper singular/plural on the missing count) only when a catalog
 * exists (``aired_count != null``).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FollowedSeriesItem } from "@/api/acquisition";

// Inert hook mocks: the panel's mutations/queries never fire in these render
// tests — only the card markup derived from the `data` prop is under test.
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

describe("FollowedPanel (P0-B)", () => {
  it("renders the incomplete status badge as « Épisodes manquants »", () => {
    renderPanel([makeItem({ status: "incomplete" })]);

    expect(screen.getByText("Épisodes manquants")).toBeInTheDocument();
  });

  it("renders the owned/aired caption with a plural missing count", () => {
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

    expect(
      screen.getByText(/15\/18 en médiathèque · 3 manquants/),
    ).toBeInTheDocument();
  });

  it("renders a singular missing count and omits the caption without a catalog", () => {
    renderPanel([
      makeItem({
        id: 1,
        title: "Silo",
        status: "incomplete",
        aired_count: 10,
        owned_count: 9,
        missing_count: 1,
      }),
      // aired_count null = no cached catalog → no invented caption.
      makeItem({ id: 2, title: "Top Chef" }),
    ]);

    expect(
      screen.getByText(/9\/10 en médiathèque · 1 manquant$/),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/en médiathèque/)).toHaveLength(1);
  });

  it("omits the owned/aired caption for a movie even with counters", () => {
    renderPanel([
      makeItem({
        kind: "movie",
        title: "Ferrari",
        aired_count: 1,
        owned_count: 0,
        missing_count: 1,
      }),
    ]);

    expect(screen.queryByText(/en médiathèque/)).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — suivis retirés (revue mobile 2026-07-15)", () => {
  it("un suivi retiré quitte la grille et apparaît dans la section repliée", () => {
    renderPanel([
      makeItem(),
      makeItem({ id: 7, title: "Le Robot sauvage", kind: "movie", active: false }),
    ]);

    // Grid: only the active follow renders as a card.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
    // Retired section: collapsed summary with count + reactivate control.
    expect(screen.getByText("Suivis retirés (1)")).toBeInTheDocument();
    expect(screen.getByText(/Le Robot sauvage/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Réactiver" }),
    ).toBeInTheDocument();
    // The retired item must NOT render its card controls (no Retirer button).
    expect(screen.getAllByRole("button", { name: "Retirer" })).toHaveLength(1);
  });

  it("aucune section retirés quand tout est actif", () => {
    renderPanel([makeItem()]);
    expect(screen.queryByText(/Suivis retirés/)).not.toBeInTheDocument();
  });
});
