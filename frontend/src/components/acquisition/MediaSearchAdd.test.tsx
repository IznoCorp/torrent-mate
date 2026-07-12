/**
 * Unit tests for MediaSearchAdd (webui-overhaul OBJ3 add-by-search).
 *
 * Mocks useMediaSearch + useFollow so the component logic (submit-gated search,
 * result cards, follow action, empty state) is tested in isolation.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mediaSearchMock = vi.fn();
const followMutate = vi.fn();

vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useMediaSearch: (...a: unknown[]) => mediaSearchMock(...a),
  useFollow: () => ({ mutate: followMutate, isPending: false }),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { MediaSearchAdd } from "@/components/acquisition/MediaSearchAdd";

beforeEach(() => {
  mediaSearchMock.mockReturnValue({
    data: {
      results: [
        {
          provider: "tvdb",
          provider_id: 1,
          title: "Dune",
          year: 2021,
          kind: "tv",
          poster_url: null,
          overview: "Sur Arrakis.",
          score: 0.9,
        },
      ],
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

describe("MediaSearchAdd", () => {
  it("shows the initial prompt before any search", () => {
    render(<MediaSearchAdd />);
    expect(screen.getByText("Recherchez un média")).toBeInTheDocument();
    // No result card yet (query is empty).
    expect(screen.queryByText("Dune")).not.toBeInTheDocument();
  });

  it("renders results after submitting and follows on click", () => {
    render(<MediaSearchAdd />);
    fireEvent.change(
      screen.getByLabelText("Rechercher un média à suivre"),
      { target: { value: "dune" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Chercher" }));

    expect(screen.getByText("Dune")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    // The candidate's card metadata (year/overview; poster_url is null → omitted)
    // is carried into the follow body so the watch-list card can show it (OBJ3).
    expect(followMutate).toHaveBeenCalledWith(
      { tvdb_id: 1, title: "Dune", overview: "Sur Arrakis.", year: 2021 },
      expect.anything(),
    );
  });
});
