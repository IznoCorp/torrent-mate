/**
 * Unit tests for RecentResolutions (webui-overhaul #4 — resolved decisions in
 * the pipeline summary).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const decisionsMock = vi.fn();

vi.mock("@/hooks/useDecisions", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDecisions: () => decisionsMock(),
}));

import { RecentResolutions } from "@/components/pipeline/RecentResolutions";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("RecentResolutions", () => {
  it("lists recently resolved decisions", () => {
    decisionsMock.mockReturnValue({
      data: {
        items: [
          { id: 2, extracted_title: "Obsession", extracted_year: 2026, trigger: "ambiguous" },
          { id: 3, extracted_title: "Ferrari", extracted_year: 2025, trigger: "ambiguous" },
        ],
      },
      isLoading: false,
    });
    render(<RecentResolutions />);
    expect(
      screen.getByText("Décisions de scraping résolues récemment"),
    ).toBeInTheDocument();
    expect(screen.getByText("Obsession")).toBeInTheDocument();
    expect(screen.getByText("Ferrari")).toBeInTheDocument();
  });

  it("renders nothing when there is no resolved decision", () => {
    decisionsMock.mockReturnValue({ data: { items: [] }, isLoading: false });
    const { container } = render(<RecentResolutions />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while loading", () => {
    decisionsMock.mockReturnValue({ data: undefined, isLoading: true });
    const { container } = render(<RecentResolutions />);
    expect(container).toBeEmptyDOMElement();
  });
});
