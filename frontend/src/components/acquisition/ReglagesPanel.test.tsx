/**
 * ReglagesPanel (#18) — the acquisition ranking editor.
 *
 * Proves the editor (a) renders the loaded criteria, (b) scores a live preview
 * against the current draft, and (c) saves through the S4 write-path carrying
 * the SHA-256 precondition. The config + preview APIs are mocked; the real
 * TanStack hooks and component logic run.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  toastSuccess,
  toastError,
  toastWarning,
  getFileMock,
  putFileMock,
  previewMock,
} = vi.hoisted(() => ({
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
  const actual =
    await vi.importActual<typeof import("@/api/config")>("@/api/config");
  return {
    ...actual,
    getConfigFile: getFileMock,
    putConfigFile: putFileMock,
  };
});

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
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

  it("save does not snap back to stale values (issue 372)", async () => {
    // The bug: handleSave calls setDraft(null) after a successful PUT.
    // The re-seed effect immediately re-seeds the draft from fileQ.data — still
    // the STALE pre-save snapshot — so the form snaps back to the OLD values.
    // The fix: await fileQ.refetch() then seed from the FRESH result.
    //
    // We use a deferred to control the refetch timing: the refetch does NOT
    // resolve until we say so.  That guarantees the re-seed effect fires while
    // fileQ.data is still the stale pre-save snapshot — exactly the scenario
    // the bug lives in.
    let resolveRefetch!: (value: unknown) => void;
    const refetchDeferred = new Promise<unknown>((resolve) => {
      resolveRefetch = resolve;
    });

    const v0 = structuredClone(RANKING);
    const v1 = structuredClone(RANKING);
    const c0 = v1.criteria[0];
    if (c0 != null) c0.weight = 5;

    let call = 0;
    getFileMock.mockImplementation(() => {
      call++;
      if (call === 1) {
        // Initial load: v0.
        return Promise.resolve({
          name: "ranking.json5",
          values: { ranking: v0 },
          sha256: "sha-abc",
          shadowed_keys: [],
        });
      }
      // Refetch: held by the deferred so we control when it lands.
      return refetchDeferred;
    });

    renderPanel();
    await screen.findByText("Langue / piste audio");

    const getWeightInput = () =>
      screen
        .getAllByRole("spinbutton")
        .find(
          (el) =>
            el.getAttribute("aria-label") === "Poids Langue / piste audio",
        );

    const weightInput = getWeightInput();
    if (weightInput == null) throw new Error("weight input not found");
    expect(weightInput).toHaveValue(2);

    // Edit weight: 2 → 5.
    fireEvent.change(weightInput, { target: { value: "5" } });

    const saveBtn = () => screen.getByRole("button", { name: "Enregistrer" });
    await waitFor(() => {
      expect(saveBtn()).toBeEnabled();
    });
    fireEvent.click(saveBtn());

    await waitFor(() => {
      expect(putFileMock).toHaveBeenCalled();
    });

    // Core assertion: after save settles, the edited field MUST still show
    // the saved value (5), NOT snap back to the stale pre-save snapshot (2).
    //
    // Pre-fix: setDraft(null) → the effect re-seeds from stale fileQ.data
    // (v0, weight=2) → the input shows 2 → this assertion FAILS.
    // Post-fix: await refetch + setDraft(fresh) → the input shows 5 → PASSES.
    await waitFor(() => {
      const current = getWeightInput();
      expect(current).toHaveValue(5);
    });

    // The PUT payload correctly carried the user's edit (weight=5).
    const [, body] = putFileMock.mock.calls[0] as [
      string,
      { values: { ranking: typeof RANKING }; base_sha256: string },
    ];
    expect(body.values.ranking.criteria[0]?.weight).toBe(5);

    // Now resolve the refetch so handleSave can finish (post-fix) or
    // so the invalidateQueries refetch completes (pre-fix).
    resolveRefetch({
      name: "ranking.json5",
      values: { ranking: v1 },
      sha256: "sha-xyz",
      shadowed_keys: [],
    });

    // After the refetch settles the input must STILL show 5.
    // Pre-fix: loaded=v1 but draft=v0 (not null) → the effect does NOT
    // re-seed → input stays at 2 → this assertion FAILS.
    // Post-fix: setDraft(v1) already ran → input is 5 → PASSES.
    await waitFor(() => {
      const current = getWeightInput();
      expect(current).toHaveValue(5);
    });
  });

  it("saves through the S4 write-path with the SHA precondition", async () => {
    renderPanel();
    // Wait for the editor to render, then grab the language-weight input by its
    // aria-label attribute (a wrapping <label> makes findByLabelText ambiguous).
    await screen.findByText("Langue / piste audio");
    const weightInput = screen
      .getAllByRole("spinbutton")
      .find(
        (el) => el.getAttribute("aria-label") === "Poids Langue / piste audio",
      );
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
    const [, body] = putFileMock.mock.calls[0] as [
      string,
      { values: { ranking: typeof RANKING }; base_sha256: string },
    ];
    expect(body.base_sha256).toBe("sha-abc");
    expect(body.values.ranking.criteria[0]?.weight).toBe(5);
    expect(toastSuccess).toHaveBeenCalled();
  });
});
