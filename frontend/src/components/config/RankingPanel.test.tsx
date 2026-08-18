/**
 * RankingPanel (#18) — the acquisition ranking editor.
 *
 * Proves the editor (a) renders the loaded criteria, (b) scores a live preview
 * against the current draft, and (c) saves through the S4 write-path carrying
 * the SHA-256 precondition.  The config + preview APIs are mocked; the real
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

import { RankingPanel } from "./RankingPanel";

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

function seedApis(
  overrides?: Partial<{
    knownTrackers: string[];
    ranked: typeof MOCK_RANKED;
  }>,
): void {
  getFileMock.mockResolvedValue({
    name: "ranking.json5",
    values: { ranking: RANKING },
    sha256: "sha-abc",
    shadowed_keys: [],
  });
  const ranked = overrides?.ranked ?? MOCK_RANKED;
  previewMock.mockResolvedValue({
    ranked,
    known_trackers: overrides?.knownTrackers ?? ["c411", "tr4ker"],
  });
  putFileMock.mockResolvedValue({ warnings: [], restart_required: false });
}

const MOCK_RANKED = [
  {
    title: "Sample tr4ker MULTI",
    provider: "tr4ker",
    resolution: "2160p",
    codec: "x265",
    language: "MULTI",
    source: "BluRay",
    seeders: 40,
    leechers: 2,
    is_freeleech: true,
    score: 55,
    excluded: false,
  },
];

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <RankingPanel />
    </QueryClientProvider>,
  );
}

describe("RankingPanel", () => {
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

  it("preview rows show seeders/leechers values from the mocked response", async () => {
    renderPanel();
    await screen.findByText("Sample tr4ker MULTI");
    // Seeders/leechers displayed compactly: S:XX L:YY.
    expect(screen.getByText("S:40")).toBeInTheDocument();
    expect(screen.getByText("L:2")).toBeInTheDocument();
  });

  it("tracker criterion renders a select with known trackers minus already-used", async () => {
    renderPanel();
    await screen.findByText("Tracker");

    // Wait for the preview to load (debounced, 300ms) — the tracker criterion
    // only gets the select treatment once known_trackers arrives via the preview.
    await screen.findByText("S:40");

    // The tracker criterion (provider) gets a select instead of free-text input.
    const select = screen.getByRole("combobox", {
      name: "Ajouter un tracker",
    });
    expect(select).toBeInTheDocument();

    // "c411" and "tr4ker" are already in values → disabled.
    const c411Opt = screen.getByText("c411 (déjà présent)");
    const tr4kerOpt = screen.getByText("tr4ker (déjà présent)");
    expect(c411Opt).toBeInTheDocument();
    expect(tr4kerOpt).toBeInTheDocument();

    // With only 2 known trackers and both used, no available options remain other
    // than the placeholder — the select shows the disabled placeholder + used entries.
    const options = Array.from(select.querySelectorAll("option"));
    expect(options.length).toBe(3); // placeholder + 2 disabled
  });

  it("tracker select has available options when a known tracker is unused", async () => {
    // Use a RANKING with only tr4ker in provider values — c411 becomes available.
    const rankingWithoutC411 = {
      ...RANKING,
      criteria: [
        { field: "language", weight: 2, values: { MULTI: 20, VOSTFR: 6 } },
        { field: "provider", weight: 1, values: { tr4ker: 15 } },
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
    };
    getFileMock.mockResolvedValue({
      name: "ranking.json5",
      values: { ranking: rankingWithoutC411 },
      sha256: "sha-abc",
      shadowed_keys: [],
    });

    renderPanel();
    await screen.findByText("Tracker");
    // Wait for the debounced preview to load — the select only appears after.
    await screen.findByText("S:40");

    // "c411" should be available (not disabled).
    const c411Opt = screen.getByText("c411");
    expect(c411Opt).toBeInTheDocument();
    // It must NOT have "(déjà présent)" suffix.
    expect(c411Opt.closest("option")?.disabled).toBe(false);

    // "tr4ker" is already present → disabled.
    expect(screen.getByText("tr4ker (déjà présent)")).toBeInTheDocument();
  });

  it("selecting a tracker adds it with the default score", async () => {
    // Only tr4ker in values, c411 is available.
    const rankingWithOneTracker = {
      ...RANKING,
      criteria: [
        { field: "provider", weight: 1, values: { tr4ker: 15 } },
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
    };
    getFileMock.mockResolvedValue({
      name: "ranking.json5",
      values: { ranking: rankingWithOneTracker },
      sha256: "sha-abc",
      shadowed_keys: [],
    });

    renderPanel();
    await screen.findByText("Tracker");
    // Wait for the debounced preview to load.
    await screen.findByText("S:40");

    const select = screen.getByRole("combobox", {
      name: "Ajouter un tracker",
    });
    fireEvent.change(select, { target: { value: "c411" } });

    // After selection, c411 appears in the list with the default score.
    // Default score for a single-value map (tr4ker=15) is the midpoint: 15.
    await waitFor(() => {
      expect(screen.getByText("c411")).toBeInTheDocument();
    });

    // The "Enregistrer" button should be enabled (dirty draft).
    const saveBtn = () => screen.getByRole("button", { name: "Enregistrer" });
    await waitFor(() => {
      expect(saveBtn()).toBeEnabled();
    });

    // Click save and check the PUT payload includes c411 with the default score.
    fireEvent.click(saveBtn());
    await waitFor(() => {
      expect(putFileMock).toHaveBeenCalled();
    });
    const [, body] = putFileMock.mock.calls[0] as [
      string,
      {
        values: { ranking: typeof rankingWithOneTracker };
        base_sha256: string;
      },
    ];
    const providerCriterion = body.values.ranking.criteria.find(
      (c) => c.field === "provider",
    );
    expect(providerCriterion?.values).toEqual({ tr4ker: 15, c411: 15 });
  });

  it("legacy unknown tracker key is still rendered in the editor", async () => {
    // A legacy key not in known_trackers must still be displayed.
    const rankingWithLegacy = {
      ...RANKING,
      criteria: [
        { field: "provider", weight: 1, values: { tr4ker: 15, oldtracker: 7 } },
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
    };
    getFileMock.mockResolvedValue({
      name: "ranking.json5",
      values: { ranking: rankingWithLegacy },
      sha256: "sha-abc",
      shadowed_keys: [],
    });

    renderPanel();
    await screen.findByText("Tracker");

    // The legacy key is rendered (never silently dropped).
    expect(screen.getByText("oldtracker")).toBeInTheDocument();
    // It has an editable score input.
    expect(
      screen.getByRole("spinbutton", { name: "Score oldtracker" }),
    ).toBeInTheDocument();
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

  // -----------------------------------------------------------------------
  // Size thresholds by type — per-media-type size tiers editor
  // -----------------------------------------------------------------------

  it("renders 3 type blocks with rows from a mocked config carrying by-type tiers", async () => {
    const RANKING_WITH_TIERS = {
      ...RANKING,
      size_thresholds_by_type: {
        movie: [
          { at: 1_000_000_000, score: 5 },
          { at: 5_000_000_000, score: 10 },
        ],
        episode: [{ at: 500_000_000, score: 3 }],
        // season: absent → inherit
      },
    };
    getFileMock.mockResolvedValue({
      name: "ranking.json5",
      values: { ranking: RANKING_WITH_TIERS },
      sha256: "sha-abc",
      shadowed_keys: [],
    });

    renderPanel();
    await screen.findByText("Langue / piste audio");

    // All three type blocks rendered.
    expect(screen.getByText("Films")).toBeInTheDocument();
    expect(screen.getByText("Saisons")).toBeInTheDocument();
    expect(screen.getByText("Épisodes")).toBeInTheDocument();

    // Films has 2 rows → GB values displayed.
    const filmGbInputs = screen.getAllByLabelText("Seuil Films GB");
    expect(filmGbInputs).toHaveLength(2);
    // First row: 1 GB → "1"
    expect(filmGbInputs[0]).toHaveValue(1);
    // Second row: 5 GB → "5"
    expect(filmGbInputs[1]).toHaveValue(5);

    // Episode has 1 row → 0.5 GB.
    const epGbInputs = screen.getAllByLabelText("Seuil Épisodes GB");
    expect(epGbInputs).toHaveLength(1);
    expect(epGbInputs[0]).toHaveValue(0.5);

    // Season inherits (absent key).
    expect(
      screen.getByText("Hérite des paliers génériques."),
    ).toBeInTheDocument();
  });

  it("adding a row to Films marks dirty and the save payload carries the new entry sorted", async () => {
    const RANKING_WITH_TIERS = {
      ...RANKING,
      size_thresholds_by_type: {
        movie: [{ at: 1_000_000_000, score: 5 }],
      },
    };
    getFileMock.mockResolvedValue({
      name: "ranking.json5",
      values: { ranking: RANKING_WITH_TIERS },
      sha256: "sha-abc",
      shadowed_keys: [],
    });

    renderPanel();
    await screen.findByText("Films");

    const saveBtn = () => screen.getByRole("button", { name: "Enregistrer" });
    // Not dirty initially.
    expect(saveBtn()).toBeDisabled();

    // Click "Ajouter un palier" for Films.
    const addBtns = screen.getAllByRole("button", {
      name: "Ajouter un palier",
    });
    expect(addBtns).toHaveLength(1); // Only Films is enabled.
    const addBtn = addBtns[0];
    if (!addBtn) throw new Error("add button not found");
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(saveBtn()).toBeEnabled();
    });

    // The new row defaults to 1 GB / 5 score.
    const filmGbInputs = screen.getAllByLabelText("Seuil Films GB");
    expect(filmGbInputs).toHaveLength(2);
    const secondGbInput = filmGbInputs[1];
    if (!secondGbInput) throw new Error("second GB input not found");
    expect(secondGbInput).toHaveValue(1);

    // Edit the new row's at to 8 GB (higher than the existing 1 GB).
    fireEvent.change(secondGbInput, { target: { value: "8" } });

    // Save.
    fireEvent.click(saveBtn());
    await waitFor(() => {
      expect(putFileMock).toHaveBeenCalled();
    });

    const [, body] = putFileMock.mock.calls[0] as [
      string,
      { values: { ranking: typeof RANKING_WITH_TIERS }; base_sha256: string },
    ];
    const tiers = body.values.ranking.size_thresholds_by_type;
    expect(tiers).toBeDefined();
    const movieTiers = tiers.movie;
    expect(movieTiers).toBeDefined();
    // Sorted by at ascending: 1 GB (1e9) first, 8 GB (8e9) second —
    // structural assertion (no indexing: satisfies noUncheckedIndexedAccess
    // without optional chains that no-unnecessary-condition rejects).
    expect(movieTiers).toEqual([
      expect.objectContaining({ at: 1_000_000_000 }),
      expect.objectContaining({ at: 8_000_000_000 }),
    ]);
  });

  it("a type without entry series the inherit state", async () => {
    const RANKING_WITH_PARTIAL = {
      ...RANKING,
      size_thresholds_by_type: {
        movie: [{ at: 2_000_000_000, score: 5 }],
        // episode: absent
        // season: absent
      },
    };
    getFileMock.mockResolvedValue({
      name: "ranking.json5",
      values: { ranking: RANKING_WITH_PARTIAL },
      sha256: "sha-abc",
      shadowed_keys: [],
    });

    renderPanel();
    await screen.findByText("Films");

    // Films is enabled (has entries).
    const filmCheckbox = screen.getByLabelText("Activer les paliers Films");
    expect(filmCheckbox).toBeChecked();

    // Season checkbox is unchecked → inherit state visible.
    const seasonCheckbox = screen.getByLabelText("Activer les paliers Saisons");
    expect(seasonCheckbox).not.toBeChecked();

    // Episode checkbox is unchecked → inherit state visible.
    const epCheckbox = screen.getByLabelText("Activer les paliers Épisodes");
    expect(epCheckbox).not.toBeChecked();

    // "Hérite des paliers génériques" appears twice (season + episode).
    const inheritTexts = screen.getAllByText("Hérite des paliers génériques.");
    expect(inheritTexts).toHaveLength(2);
  });

  it("removing the last row of a type removes the key rather than leaving an empty list", async () => {
    const RANKING_ONE_EP = {
      ...RANKING,
      size_thresholds_by_type: {
        episode: [{ at: 500_000_000, score: 3 }],
      },
    };
    getFileMock.mockResolvedValue({
      name: "ranking.json5",
      values: { ranking: RANKING_ONE_EP },
      sha256: "sha-abc",
      shadowed_keys: [],
    });

    renderPanel();
    await screen.findByText("Épisodes");

    const saveBtn = () => screen.getByRole("button", { name: "Enregistrer" });
    expect(saveBtn()).toBeDisabled();

    // Remove the single episode row.
    const removeBtn = screen.getByLabelText("Retirer le seuil Épisodes");
    fireEvent.click(removeBtn);

    // All three types now show inherit state (key removed, dict is empty).
    const inheritTexts = screen.getAllByText("Hérite des paliers génériques.");
    expect(inheritTexts).toHaveLength(3);

    // Draft is dirty (key was removed from the dict).
    await waitFor(() => {
      expect(saveBtn()).toBeEnabled();
    });

    // Save and verify the payload has NO "episode" key.
    fireEvent.click(saveBtn());
    await waitFor(() => {
      expect(putFileMock).toHaveBeenCalled();
    });

    const [, body] = putFileMock.mock.calls[0] as [
      string,
      { values: { ranking: typeof RANKING_ONE_EP }; base_sha256: string },
    ];
    const tiers = body.values.ranking.size_thresholds_by_type;
    // After removing the only key, the dict should be null (no entries left).
    expect(tiers).toBeNull();
  });
});
