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
  it("rappelle ce qui a été réglé, par DOSSIER (R57)", () => {
    // The journal and the queue are two views of one thing, so they draw the
    // same card — and its subject is the folder, not the title the scrape
    // guessed.
    decisionsMock.mockReturnValue({
      data: {
        items: [
          {
            id: 2,
            staging_path: "/staging/001-MOVIES/Obsession (2026)",
            media_kind: "movie",
            trigger: "ambiguous",
            status: "resolved",
            resolved_at: 1_752_591_300,
            resolution_json: {
              provider: "tmdb",
              provider_id: 1339713,
              via: "pick",
              title: "Obsession",
            },
          },
          {
            id: 3,
            staging_path: "/staging/001-MOVIES/Ferrari (2025)",
            media_kind: "movie",
            trigger: "manual",
            status: "resolved",
            resolved_at: 1_752_591_300,
            resolution_json: null,
          },
        ],
      },
      isLoading: false,
    });
    render(<RecentResolutions />);
    expect(screen.getByText("Réglées récemment")).toBeInTheDocument();
    expect(screen.getByText("Obsession (2026)")).toBeInTheDocument();
    expect(screen.getByText("Ferrari (2025)")).toBeInTheDocument();
    // What was chosen is the line one comes back to read.
    expect(screen.getByText(/TMDB 1339713 · choisi dans la liste/)).toBeInTheDocument();
    // And both say what became of them.
    expect(screen.getAllByText("Réglée")).toHaveLength(2);
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
