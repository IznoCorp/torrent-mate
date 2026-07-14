/**
 * Unit tests for FlowBoard (P0-A living pipeline).
 *
 * Mocks usePipelineStages and renders inside a real MemoryRouter so the
 * board rendering, station stocks/states, the URL-addressable ?stage= drawer
 * (open pushes, close cleans the param) and the header run caption are
 * tested against genuine router behaviour.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const stagesMock = vi.fn();

vi.mock("@/hooks/usePipelineStages", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  usePipelineStages: () => stagesMock(),
}));

// The stage drawer mounts StageMediaList → stub its data hook so no real query
// (and no QueryClient/event context) is needed in this isolated board test.
vi.mock("@/hooks/useStagingMedia", () => ({
  useStagingMedia: () => ({
    data: { items: [], counts: {}, total: 0, page: 1, page_size: 50 },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

import { FlowBoard } from "@/components/pipeline/FlowBoard";

/** Renders the live location so tests can assert path + ?stage param. */
function LocationProbe(): React.ReactElement {
  const location = useLocation();
  return (
    <span data-testid="location-search">
      {location.pathname + location.search}
    </span>
  );
}

function renderBoard(initialEntries: string[] = ["/pipeline"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <FlowBoard />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function stage(
  key: string,
  label: string,
  count: number,
  state: string,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    key,
    label,
    count,
    state,
    attention: 0,
    blocked: 0,
    split: null,
    ...extra,
  };
}

/** The eight P0-A stations — stocks, not last-run throughput. */
const EIGHT = [
  stage("arrival", "Arrivée", 1, "ok"),
  stage("sorting", "Tri", 0, "idle"),
  stage("cleaning", "Nettoyage", 0, "idle"),
  stage("matching", "Identification", 4, "blocked", {
    blocked: 4,
    split: [
      { label: "à résoudre", count: 3, tone: "warning" },
      { label: "à qualifier", count: 1, tone: "info" },
    ],
  }),
  stage("scraping", "Scraping", 0, "idle"),
  stage("trailers", "Trailers", 0, "idle"),
  stage("verify", "Vérification", 1, "blocked", { blocked: 1 }),
  stage("dispatch", "Dispatch", 2, "ok"),
];

beforeEach(() => {
  stagesMock.mockReturnValue({
    data: {
      stages: EIGHT,
      run_uid: "run-1",
      run_state: "idle",
      updated_at: 1750000000,
      run_trigger: "watch",
      run_processed: 3,
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FlowBoard", () => {
  it("renders the eight stations with their stock counts — no Staging step", () => {
    renderBoard();
    for (const label of [
      "Arrivée",
      "Tri",
      "Nettoyage",
      "Identification",
      "Scraping",
      "Trailers",
      "Vérification",
      "Dispatch",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByText("Staging")).not.toBeInTheDocument();
    // Identification stock is shown.
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("carries the last run's throughput in the header, not on stations", () => {
    renderBoard();
    expect(screen.getByText(/Dernier run · .* · 3 médias traités/)).toBeInTheDocument();
  });

  it("shows a loading skeleton row while fetching", () => {
    stagesMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = renderBoard();
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
  });

  it("falls back to the skeleton when a settled query yields no stages", () => {
    // Regression: a settled query with empty stages must not paint a blank
    // board (the mobile 'FLUX DU PIPELINE with an empty void' report).
    stagesMock.mockReturnValue({
      data: { stages: [], run_uid: null, run_state: "idle", updated_at: null },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = renderBoard();
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(screen.queryByText("Arrivée")).not.toBeInTheDocument();
  });

  it("shows an error state with a retry action on failure", () => {
    const refetch = vi.fn();
    stagesMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
      refetch,
    });
    renderBoard();
    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("opening a station sets ?stage= (URL-addressable) and closing removes it", () => {
    renderBoard();
    fireEvent.click(screen.getByRole("button", { name: /Vérification/ }));
    expect(screen.getByTestId("location-search").textContent).toContain(
      "stage=verify",
    );
    // Close via the sheet's close affordance → the param is cleaned up.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByTestId("location-search").textContent).not.toContain(
      "stage=verify",
    );
  });

  it("restores the open drawer from a ?stage= deep link", () => {
    renderBoard(["/pipeline?stage=matching"]);
    // The drawer is open on the Identification stage without any click.
    expect(
      screen.getByRole("button", { name: /Ouvrir la file de résolution/ }),
    ).toBeInTheDocument();
  });

  it("opens the Identification drawer and navigates to the resolution queue", () => {
    renderBoard();
    fireEvent.click(screen.getByRole("button", { name: /Identification/ }));
    const action = screen.getByRole("button", {
      name: /Ouvrir la file de résolution/,
    });
    fireEvent.click(action);
    // Real router: the action leaves /pipeline for the resolution deck.
    expect(screen.getByTestId("location-search").textContent).toBe("/scraping");
  });
});
