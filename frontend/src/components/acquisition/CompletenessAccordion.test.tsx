/**
 * CompletenessAccordion — P0-B.1 tests: the aired-catalog provenance caption
 * renders honestly at the bottom of the open accordion — dated
 * « Catalogue du JJ/MM/AAAA » on the cache path, « Catalogue interrogé en
 * direct » on the live fallback path.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompletenessResponse } from "@/api/acquisition";

import { CompletenessAccordion } from "./CompletenessAccordion";
import * as hooks from "@/hooks/useAcquisition";

/** Epoch seconds of the detect pass in the cache fixture. */
const REFRESHED_AT = 1_751_000_000;

/** A one-season completeness payload (source/refreshed_at set per test). */
function makeCompleteness(
  overrides: Partial<CompletenessResponse> = {},
): CompletenessResponse {
  return {
    followed_id: 7,
    title: "House of the Dragon",
    kind: "show",
    provider_catalog_empty: false,
    seasons: [
      {
        season: 1,
        owned: 1,
        queued: 0,
        total: 2,
        episodes: [
          {
            episode: 1,
            state: "en_mediatheque",
            title: "The Heirs of the Dragon",
            air_date: "2022-08-21",
          },
          { episode: 2, state: "manquant", title: null, air_date: null },
        ],
      },
    ],
    source: "live",
    catalog_refreshed_at: null,
    ...overrides,
  };
}

function mockCompleteness(data: CompletenessResponse): void {
  vi.spyOn(hooks, "useCompleteness").mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof hooks.useCompleteness>);
}

/** Render the accordion and open it (the query is mocked, so no fetch fires). */
function renderOpen(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <CompletenessAccordion followedId={7} title="House of the Dragon" />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Détail par épisode/ }));
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("CompletenessAccordion catalog caption (P0-B.1)", () => {
  it("captions the dated cached catalog when source is cache", () => {
    mockCompleteness(
      makeCompleteness({
        source: "cache",
        catalog_refreshed_at: REFRESHED_AT,
      }),
    );
    renderOpen();

    // Same formatting path as the component — locale-stable expectation.
    const expected = new Date(REFRESHED_AT * 1000).toLocaleDateString("fr-FR");
    expect(screen.getByText(`Catalogue du ${expected}`)).toBeInTheDocument();
    // The matrix itself still renders above the caption.
    expect(screen.getByText("Saison 1")).toBeInTheDocument();
  });

  it("captions the live provider poll when source is live", () => {
    mockCompleteness(makeCompleteness({ source: "live" }));
    renderOpen();

    expect(
      screen.getByText("Catalogue interrogé en direct"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Catalogue du /)).not.toBeInTheDocument();
  });
});
