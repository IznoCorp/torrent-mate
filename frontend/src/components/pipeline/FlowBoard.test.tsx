/**
 * Unit tests for FlowBoard (webui-overhaul OBJ1 living pipeline).
 *
 * Mocks usePipelineStages + react-router so the board rendering, station
 * counts/states, loading/error branches, and the Matching drawer action are
 * tested in isolation.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const stagesMock = vi.fn();
const navigateMock = vi.fn();

vi.mock("@/hooks/usePipelineStages", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  usePipelineStages: () => stagesMock(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
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

const NINE = [
  stage("arrival", "Arrivée", 10, "ok"),
  stage("staging", "Staging", 8, "ok"),
  stage("cleaning", "Nettoyage", 0, "idle"),
  stage("sorting", "Tri", 0, "idle"),
  stage("matching", "Matching", 4, "attention", {
    attention: 4,
    split: [
      { label: "ambigu", count: 2, tone: "warning" },
      { label: "sans correspondance", count: 1, tone: "danger" },
      { label: "incertain", count: 1, tone: "info" },
    ],
  }),
  stage("scraping", "Scraping", 5, "ok"),
  stage("trailers", "Trailers", 0, "idle"),
  stage("verify", "Vérification", 0, "idle"),
  stage("dispatch", "Dispatch", 5, "ok"),
];

beforeEach(() => {
  stagesMock.mockReturnValue({
    data: {
      stages: NINE,
      run_uid: "run-1",
      run_state: "idle",
      updated_at: 1750000000,
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
  it("renders all nine stage stations with their counts", () => {
    render(<FlowBoard />);
    for (const label of [
      "Arrivée",
      "Staging",
      "Nettoyage",
      "Tri",
      "Matching",
      "Scraping",
      "Trailers",
      "Vérification",
      "Dispatch",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // Matching headline count is shown.
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("shows a loading skeleton row while fetching", () => {
    stagesMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    const { container } = render(<FlowBoard />);
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
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
    render(<FlowBoard />);
    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("opens the Matching drawer and navigates to the resolution queue", () => {
    render(<FlowBoard />);
    fireEvent.click(screen.getByRole("button", { name: /Matching/ }));
    // Drawer action for a non-empty matching stage.
    const action = screen.getByRole("button", {
      name: /Ouvrir la file de résolution/,
    });
    fireEvent.click(action);
    expect(navigateMock).toHaveBeenCalledWith("/scraping");
  });
});
