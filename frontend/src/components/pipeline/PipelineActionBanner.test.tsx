/**
 * Tests for PipelineActionBanner (C5): renders nothing at zero pending, shows a
 * count + deck CTA when decisions await, sourced from usePipelineStages.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const stagesMock = vi.fn();
const navigateMock = vi.fn();

vi.mock("@/hooks/usePipelineStages", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  usePipelineStages: () => stagesMock(),
}));
vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

import { PipelineActionBanner } from "@/components/pipeline/PipelineActionBanner";

function stagesData(matchingCount: number) {
  return {
    data: {
      stages: [
        {
          key: "matching",
          label: "Matching",
          count: matchingCount,
          state: "attention",
        },
      ],
      run_uid: null,
      run_state: "idle",
      updated_at: null,
    },
  };
}

describe("PipelineActionBanner", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders nothing when no decision is pending", () => {
    stagesMock.mockReturnValue(stagesData(0));
    const { container } = render(<PipelineActionBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the count + deck CTA when decisions are pending", () => {
    stagesMock.mockReturnValue(stagesData(3));
    render(<PipelineActionBanner />);
    expect(screen.getByText(/3 décisions à résoudre/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Ouvrir la file/ }));
    expect(navigateMock).toHaveBeenCalledWith("/scraping");
  });
});
