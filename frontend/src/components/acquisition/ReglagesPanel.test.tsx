/**
 * ReglagesPanel (#18) — the acquisition ranking editor.
 *
 * Proves the editor (a) renders the loaded criteria, (b) scores a live preview
 * against the current draft, and (c) saves through the S4 write-path carrying
 * the SHA-256 precondition. The config + preview APIs are mocked; the real
 * TanStack hooks and component logic run.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toastSuccess, toastError, toastWarning, getFileMock, putFileMock, previewMock } =
  vi.hoisted(() => ({
    toastSuccess: vi.fn(),
    toastError: vi.fn(),
    toastWarning: vi.fn(),
    getFileMock: vi.fn(),
    putFileMock: vi.fn(),
    previewMock: vi.fn(),
  }));

vi.mock("sonner", () => ({
  toast: { success: toastSuccess, error: toastError, warning: toastWarning },
}));

vi.mock("@/api/config", async () => {
  const actual = await vi.importActual<typeof import("@/api/config")>("@/api/config");
  return {
    ...actual,
    getConfigFile: getFileMock,
    putConfigFile: putFileMock,
  };
});

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>("@/api/acquisition");
  return { ...actual, previewRanking: previewMock };
});

import { ReglagesPanel } from "./ReglagesPanel";

const RANKING = {
  criteria: [
    { field: "language", weight: 2, values: { MULTI: 20, VOSTFR: 6 } },
    { field: "provider", weight: 1, values: { tr4ker: 15, c411: 5 } },
    {
      field: "seeders",
      weight: 2,
      prefer: "higher",
      thresholds: [
        { at: 0, score: 0 },
        { at: 5, score: 8 },
      ],
    },
  ],
  bonuses: { freeleech: 10, silverleech: 5 },
  min_seeders: 1,
};

function seedApis(): void {
  getFileMock.mockResolvedValue({
    name: "ranking.json5",
    values: { ranking: RANKING },
    sha256: "sha-abc",
    shadowed_keys: [],
  });
  previewMock.mockResolvedValue({
    ranked: [
      {
        title: "Sample tr4ker MULTI",
        provider: "tr4ker",
        resolution: "2160p",
        codec: "x265",
        language: "MULTI",
        source: "BluRay",
        seeders: 40,
        is_freeleech: true,
        score: 55,
        excluded: false,
      },
    ],
  });
  putFileMock.mockResolvedValue({ warnings: [], restart_required: false });
}

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <ReglagesPanel />
    </QueryClientProvider>,
  );
}

describe("ReglagesPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    seedApis();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the loaded criteria with French labels", async () => {
    renderPanel();
    expect(await screen.findByText("Langue / piste audio")).toBeInTheDocument();
    expect(screen.getByText("Tracker")).toBeInTheDocument();
    expect(screen.getByText("Sources (seeders)")).toBeInTheDocument();
    // Categorical value tokens are shown and editable.
    expect(screen.getByText("MULTI")).toBeInTheDocument();
  });

  it("scores a live preview against the loaded draft", async () => {
    renderPanel();
    await waitFor(() => {
      expect(previewMock).toHaveBeenCalled();
    });
    expect(await screen.findByText("Sample tr4ker MULTI")).toBeInTheDocument();
  });

  it("saves through the S4 write-path with the SHA precondition", async () => {
    renderPanel();
    // Wait for the editor to render, then grab the language-weight input by its
    // aria-label attribute (a wrapping <label> makes findByLabelText ambiguous).
    await screen.findByText("Langue / piste audio");
    const weightInput = screen
      .getAllByRole("spinbutton")
      .find((el) => el.getAttribute("aria-label") === "Poids Langue / piste audio");
    if (weightInput == null) throw new Error("weight input not found");
    // Initially not dirty → Save disabled.
    const saveButton = screen.getByRole("button", { name: "Enregistrer" });
    expect(saveButton).toBeDisabled();

    fireEvent.change(weightInput, { target: { value: "5" } });
    await waitFor(() => {
      expect(saveButton).toBeEnabled();
    });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(putFileMock).toHaveBeenCalled();
    });
    const [, body] = putFileMock.mock.calls[0] as [string, { values: { ranking: typeof RANKING }; base_sha256: string }];
    expect(body.base_sha256).toBe("sha-abc");
    expect(body.values.ranking.criteria[0]?.weight).toBe(5);
    expect(toastSuccess).toHaveBeenCalled();
  });
});
