/**
 * AddMediaScreen — full-screen add-by-search + add-by-ID surface.
 *
 * Tests the search-gating, vertical-result rows, provider-total display,
 * §5 replacement confirmation, session-local follow state, empty/error
 * states, and the by-ID validation rules.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MediaSearchResult } from "@/api/acquisition";

// ── Mocks ──────────────────────────────────────────────────────────────────

const mediaSearchMock = vi.fn();
const followMutate = vi.fn();
/** Follow rows as the screen reads them: a title AND the provider identity
 *  (the add screen keys « déjà suivi » on the ids, never on the title). */
interface FollowedMockItem {
  readonly title: string;
  /** REQUIRED, like the API's own shape: a mock that omits it lets a test
   *  pass against a payload production never sends. */
  readonly media_ref: {
    readonly tmdb_id: number | null;
    readonly tvdb_id: number | null;
  };
}
const followedListMock = vi.fn(
  (): { data: { items: FollowedMockItem[] } | undefined } => ({
    data: { items: [] },
  }),
);

vi.mock("@/hooks/useAcquisition", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useMediaSearch: (...a: unknown[]) => mediaSearchMock(...a),
  useFollow: () => ({ mutate: followMutate, isPending: false }),
  useFollowed: () => followedListMock(),
}));

/** The by-ID lookup: resolves an id to a card. Default = a known media. */
const lookupMediaMock = vi.fn(() =>
  Promise.resolve({
    provider: "tvdb",
    provider_id: 255968,
    title: "Kaamelott",
    year: 2005,
    kind: "tv",
    poster_url: null,
    overview: null,
    score: 1,
    already_owned: false,
  }),
);
vi.mock("@/api/acquisition", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/acquisition")>();
  return {
    ...actual,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    lookupMedia: (...a: unknown[]) => lookupMediaMock(...(a as [])),
  };
});

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));

const navigateMock = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

import { AddMediaScreen } from "@/components/acquisition/AddMediaScreen";

// ── Helpers ────────────────────────────────────────────────────────────────

/** Default media-search infinite-query shape with no data (idle). */
function emptySearchResult() {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
  };
}

/** Build a single MediaSearchResult with defaults for every optional field. */
function makeResult(
  overrides: Partial<MediaSearchResult> & { followed?: boolean } = {},
): MediaSearchResult {
  return {
    provider: "tmdb",
    provider_id: 1,
    title: "Dune",
    year: 2021,
    kind: "movie",
    poster_url: null,
    overview: "Sur Arrakis.",
    score: 0.95,
    ...overrides,
    // `followed` is stripped — it is a harness-only field, not part of
    // MediaSearchResult.
  } as MediaSearchResult;
}

/**
 * Render the AddMediaScreen wrapped in a QueryClientProvider and
 * pre-configure the mocks from the brief's test-harness vocabulary.
 */
function renderAdd(opts?: {
  /** Number of results to generate, or an explicit row array. */
  results?: number | readonly (Partial<MediaSearchResult> & { followed?: boolean })[];
  /** Provider total (≠ row count, §8). */
  total?: number;
  /** The query that was submitted (for the empty-state message). */
  query?: string;
  /** Spy called each time a provider search is triggered. */
  onSearch?: (...args: unknown[]) => void;
  /** Spy called each time a follow body is submitted. */
  onFollow?: (...args: unknown[]) => void;
  /** What the follow mutation's onSuccess receives. */
  followResult?: { tvdb_unresolved?: boolean };
  isError?: boolean;
}) {
  // --- Build the search result ---
  const resultsArg = opts?.results;
  let results: MediaSearchResult[];
  if (resultsArg === undefined) {
    results = [];
  } else if (typeof resultsArg === "number") {
    results = Array.from({ length: resultsArg }, (_, i) =>
      makeResult({ title: `Résultat ${String(i + 1)}`, provider_id: i + 1 }),
    );
  } else {
    results = resultsArg.map((r) => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { followed: _f, ...rest } = r as MediaSearchResult & { followed?: boolean };
      return makeResult(rest);
    });
  }
  const total = opts?.total ?? results.length;

  const searchData =
    results.length > 0 || total > 0
      ? { pages: [{ total, offset: 0, limit: 30, results }] }
      : undefined;

  const onSearch = opts?.onSearch;
  mediaSearchMock.mockImplementation((q: string, kind?: string) => {
    // Fire the onSearch spy only when a real query was passed — the empty
    // initial call on mount (q === "") must not count as a search.
    if (q && onSearch) onSearch(q, kind);
    return {
      ...emptySearchResult(),
      data: opts?.isError ? undefined : searchData,
      isLoading: false,
      isError: opts?.isError ?? false,
      error: opts?.isError ? new Error("500: upstream provider unavailable") : null,
      hasNextPage: false,
    };
  });

  // --- Build the follow mutation ---
  const onFollow = opts?.onFollow;
  followMutate.mockImplementation(
    (body: unknown, mutationOpts?: { onSuccess?: (created: unknown) => void }) => {
      if (onFollow) onFollow(body);
      mutationOpts?.onSuccess?.(opts?.followResult ?? {});
    },
  );

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const view = render(
    <QueryClientProvider client={qc}>
      <AddMediaScreen open={true} onOpenChange={vi.fn()} />
    </QueryClientProvider>,
  );

  /** Re-render the SAME mounted screen with a new `open` — the Sheet stays
   *  mounted in production, so closing must be exercised that way. */
  const setOpen = (open: boolean): void => {
    view.rerender(
      <QueryClientProvider client={qc}>
        <AddMediaScreen open={open} onOpenChange={vi.fn()} />
      </QueryClientProvider>,
    );
  };

  return { ...view, setOpen };
}

/**
 * Click the single ENABLED "Suivre" button among potentially multiple.
 *
 * When results are visible, two « Suivre » buttons coexist: the always-visible
 * by-ID entry (disabled while its id field is empty) and the result card action.
 * Asserts exactly one is enabled, then clicks it.
 */
function clickResultSuivre(): void {
  const enabled = screen
    .getAllByRole("button", { name: "Suivre" })
    .filter((b) => !(b as HTMLButtonElement).disabled);
  expect(enabled).toHaveLength(1);
  const btn = enabled[0];
  if (btn === undefined) throw new Error("no enabled « Suivre » button");
  fireEvent.click(btn);
}


/** Submit a search for the given title. */
function search(title: string): void {
  const searchbox = screen.getByRole("searchbox");
  fireEvent.change(searchbox, { target: { value: title } });
  fireEvent.click(screen.getByRole("button", { name: "Chercher" }));
}

// ── Tests ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  mediaSearchMock.mockReturnValue(emptySearchResult());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
  followedListMock.mockReturnValue({ data: { items: [] } });
});

describe("AddMediaScreen", () => {
  it("n'interroge le fournisseur qu'à la validation, jamais à la frappe", () => {
    const spy = vi.fn();
    renderAdd({ onSearch: spy });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Dune" } });
    expect(spy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Chercher" }));
    expect(spy).toHaveBeenCalledWith("Dune", undefined);
  });

  it("§8 — affiche le total du fournisseur, pas le nombre de lignes", () => {
    renderAdd({ results: 5, total: 81 });
    // Submit a search so results render.
    search("dune");
    expect(
      screen.getByText(/5 résultats affichés sur 81 trouvés/),
    ).toBeInTheDocument();
  });

  it("chaque résultat porte année, type et fournisseur — ce qui départage deux homonymes", () => {
    renderAdd({
      results: [
        { title: "Dune", year: 2019, kind: "tv", provider: "tvdb", provider_id: 1 },
        { title: "Dune", year: 2013, kind: "movie", provider: "tmdb", provider_id: 2 },
      ],
    });
    search("dune");
    // First verify the count text renders (proves results section is visible).
    expect(screen.getByText(/2 résultats affichés sur 2 trouvés/)).toBeInTheDocument();
    // Then verify specific row content.
    expect(screen.getByText("2019 · Série · TVDB")).toBeInTheDocument();
    expect(screen.getByText("2013 · Film · TMDB")).toBeInTheDocument();
  });

  it("A14 — un film s'ajoute, une série se suit", () => {
    renderAdd({
      results: [
        { title: "Dune", kind: "movie", provider_id: 1 },
        { title: "Silo", kind: "tv", provider_id: 2 },
      ],
    });
    search("test");
    expect(
      screen.getByRole("button", { name: "Ajouter" }),
    ).toBeInTheDocument();
    // Multiple « Suivre » buttons coexist (by-ID + result row) — at least one
    // must be present.
    const suivreBtns = screen.getAllByRole("button", { name: "Suivre" });
    expect(suivreBtns.length).toBeGreaterThanOrEqual(1);
  });

  it("§5 — un film déjà en médiathèque demande AVANT de suivre", () => {
    const follow = vi.fn();
    renderAdd({
      results: [
        { title: "Blade Runner 2049", kind: "movie", provider_id: 1, already_owned: true },
      ],
      onFollow: follow,
    });
    search("blade runner");
    // Operator directive: an owned-but-not-followed media wears the NORMAL
    // primary button — the confirmation lives in the dialog, not the label.
    fireEvent.click(screen.getByRole("button", { name: "Ajouter" }));
    expect(follow).not.toHaveBeenCalled();
    expect(
      screen.getByText(/REMPLACERA la version en place/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remplacer" }));
    expect(follow).toHaveBeenCalledOnce();
  });

  it("fermer l'écran REMET la recherche à zéro (opérateur)", () => {
    // The screen stays mounted (a Sheet), so its state outlived the closing:
    // « Voir mes suivis » left the last query in place and it reappeared on
    // the next opening. Every exit must behave like the Back one.
    const { setOpen } = renderAdd({
      results: [{ title: "Silo", kind: "tv", provider_id: 1 }],
    });
    search("silo");
    expect(screen.getByRole("searchbox")).toHaveValue("silo");

    setOpen(false);
    setOpen(true);

    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("une SÉRIE déjà en médiathèque ne déclenche PAS le dialogue de remplacement", () => {
    // Owning episodes of a series is not owning « the » copy: following it
    // tracks the MISSING episodes and replaces nothing. Showing the film
    // replacement dialog there states something false (§14).
    const follow = vi.fn();
    renderAdd({
      results: [
        { title: "Kaamelott", kind: "tv", provider_id: 2, already_owned: true },
      ],
      onFollow: follow,
    });
    search("kaamelott");

    // The badge stays — that part is true for both natures.
    expect(screen.getByText("Déjà en médiathèque")).toBeInTheDocument();
    // The by-ID form carries a « Suivre » button too — take the RESULT's.
    const resultBtn = screen
      .getAllByRole("button", { name: "Suivre" })
      .find((b) => b.className.includes("resbtn"));
    expect(resultBtn).toBeDefined();
    if (resultBtn === undefined) throw new Error("no result button");
    fireEvent.click(resultBtn);

    // MqDialog stays mounted and inert when closed — assert the OPEN state,
    // not mere presence of its copy in the DOM.
    const dlg = screen.getByRole("alertdialog", { hidden: true });
    expect(dlg.className).not.toMatch(/\bopen\b/);
    expect(follow).toHaveBeenCalledOnce();
  });

  it("l'état déjà-suivi est SUR le bouton, sans étiquette redondante (§12)", () => {
    // Simulate a session-local follow: the row's button flips to « ✓ Suivi ».
    renderAdd({
      results: [{ title: "Silo", kind: "tv", provider_id: 1 }],
    });
    search("silo");
    // Follow it once — the onSuccess handler marks it done.
    clickResultSuivre();
    const btn = screen.getByRole("button", { name: "✓ Suivi" });
    expect(btn).toBeDisabled();
    // No redundant tag.
    expect(screen.queryByText(/déjà dans vos suivis/)).toBeNull();
  });

  it("zéro résultat n'est jamais un écran blanc (§3)", () => {
    renderAdd({ results: [], query: "zzzz" });
    search("zzzz");
    expect(
      screen.getByText(/Aucun résultat pour « zzzz »/),
    ).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /identifiant/i })).toBeInTheDocument();
  });

  it("ajout par ID : la notation scientifique est refusée et le bouton dit pourquoi", () => {
    renderAdd({});
    // Expand the by-ID section by clicking the summary text.
    fireEvent.click(screen.getByText(/Ajouter directement par identifiant/i));
    const idInput = screen.getByLabelText(/Identifiant/);
    fireEvent.change(idInput, { target: { value: "12e34" } });
    expect(screen.getByRole("button", { name: /Chercher cet ID/ })).toBeDisabled();
    expect(
      screen.getByText(/entrez un nombre entier positif/),
    ).toBeInTheDocument();
  });

  it("un ID valide RÉSOUT et montre le média — il ne suit pas tout seul", async () => {
    // Operator, 2026-08-08: submitting an id followed the media sight unseen,
    // with whatever title had been typed (usually none) — which is how a
    // nameless follow was created. The id must resolve to a card first.
    const follow = vi.fn();
    renderAdd({ onFollow: follow });
    fireEvent.click(screen.getByText(/Ajouter directement par identifiant/i));
    fireEvent.change(screen.getByLabelText(/Identifiant/), {
      target: { value: "255968" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Chercher cet ID/ }));

    // The resolved media appears as an ordinary result card…
    expect(await screen.findByText("Kaamelott")).toBeInTheDocument();
    // …and NOTHING was followed by the lookup itself.
    expect(follow).not.toHaveBeenCalled();

    // The add stays one deliberate tap.
    const suivre = screen
      .getAllByRole("button", { name: "Suivre" })
      .find((b) => b.className.includes("resbtn"));
    expect(suivre).toBeDefined();
    if (suivre === undefined) throw new Error("no result button");
    fireEvent.click(suivre);
    expect(follow).toHaveBeenCalledOnce();
  });

  it("un identifiant inconnu le DIT au lieu de créer une ligne sans nom", async () => {
    lookupMediaMock.mockRejectedValueOnce(new Error("404"));
    const follow = vi.fn();
    renderAdd({ onFollow: follow });
    fireEvent.click(screen.getByText(/Ajouter directement par identifiant/i));
    fireEvent.change(screen.getByLabelText(/Identifiant/), {
      target: { value: "999999999" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Chercher cet ID/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Aucun média avec cet identifiant/,
    );
    expect(follow).not.toHaveBeenCalled();
  });

  // ── Pagination (infinite scroll) ─────────────────────────────────────

  it("le défilement près de la fin du conteneur appelle fetchNextPage", () => {
    const fetchNextPageSpy = vi.fn();
    // Override beforeEach default with a paginated search result.
    mediaSearchMock.mockReturnValue({
      ...emptySearchResult(),
      data: {
        pages: [
          {
            total: 81,
            offset: 0,
            limit: 30,
            results: [makeResult({ title: "Dune", provider_id: 1 })],
          },
        ],
      },
      isLoading: false,
      hasNextPage: true,
      isFetchingNextPage: false,
      fetchNextPage: fetchNextPageSpy,
    });

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <AddMediaScreen open={true} onOpenChange={vi.fn()} />
      </QueryClientProvider>,
    );

    // Submit a search so results are visible.
    search("dune");

    const container = screen.getByTestId("search-results");

    // jsdom reports 0 for every layout metric — set them explicitly so the
    // branch is genuinely exercised.
    Object.defineProperty(container, "scrollHeight", {
      value: 1000,
      configurable: true,
    });
    Object.defineProperty(container, "clientHeight", {
      value: 200,
      configurable: true,
    });
    Object.defineProperty(container, "scrollTop", {
      value: 850,
      configurable: true,
      writable: true,
    });

    // remaining = 1000 - 850 - 200 = -50 < 200 → triggers fetch
    fireEvent.scroll(container);

    expect(fetchNextPageSpy).toHaveBeenCalledOnce();
  });

  it("n'appelle PAS fetchNextPage quand hasNextPage est false", () => {
    const fetchNextPageSpy = vi.fn();
    mediaSearchMock.mockReturnValue({
      ...emptySearchResult(),
      data: {
        pages: [
          {
            total: 30,
            offset: 0,
            limit: 30,
            results: [makeResult({ title: "Dune", provider_id: 1 })],
          },
        ],
      },
      isLoading: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: fetchNextPageSpy,
    });

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <AddMediaScreen open={true} onOpenChange={vi.fn()} />
      </QueryClientProvider>,
    );

    search("dune");

    const container = screen.getByTestId("search-results");
    Object.defineProperty(container, "scrollHeight", {
      value: 1000,
      configurable: true,
    });
    Object.defineProperty(container, "clientHeight", {
      value: 200,
      configurable: true,
    });
    Object.defineProperty(container, "scrollTop", {
      value: 850,
      configurable: true,
      writable: true,
    });

    fireEvent.scroll(container);

    expect(fetchNextPageSpy).not.toHaveBeenCalled();
  });

  it("n'appelle PAS fetchNextPage pendant un isFetchingNextPage déjà actif", () => {
    const fetchNextPageSpy = vi.fn();
    mediaSearchMock.mockReturnValue({
      ...emptySearchResult(),
      data: {
        pages: [
          {
            total: 81,
            offset: 0,
            limit: 30,
            results: [makeResult({ title: "Dune", provider_id: 1 })],
          },
        ],
      },
      isLoading: false,
      hasNextPage: true,
      isFetchingNextPage: true,
      fetchNextPage: fetchNextPageSpy,
    });

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <AddMediaScreen open={true} onOpenChange={vi.fn()} />
      </QueryClientProvider>,
    );

    search("dune");

    const container = screen.getByTestId("search-results");
    Object.defineProperty(container, "scrollHeight", {
      value: 1000,
      configurable: true,
    });
    Object.defineProperty(container, "clientHeight", {
      value: 200,
      configurable: true,
    });
    Object.defineProperty(container, "scrollTop", {
      value: 850,
      configurable: true,
      writable: true,
    });

    fireEvent.scroll(container);

    expect(fetchNextPageSpy).not.toHaveBeenCalled();
  });
  it("§8 — un échec du fournisseur est NOMMÉ en français, avec la voie de secours", async () => {
    renderAdd({ isError: true });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Dune" } });
    fireEvent.click(screen.getByRole("button", { name: "Chercher" }));

    const mentions = await screen.findAllByText(/La recherche a échoué/);
    expect(mentions.length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/ajoutez par identifiant/).length,
    ).toBeGreaterThan(0);
    // The by-ID fallback stays reachable under the error.
    expect(screen.getByRole("group", { name: /identifiant/i })).toBeInTheDocument();
  });

  // ── `.sugg` chips — honest shortcuts (arbitration §3.5c) ─────────────────

  describe("chips .sugg (recherches récentes)", () => {
    it("l'idle sans historique ne montre aucune chip", () => {
      renderAdd();
      expect(document.querySelector(".sugg")).toBeNull();
    });

    it("une recherche soumise ressort en chip à l'idle suivant", () => {
      renderAdd();
      fireEvent.change(screen.getByRole("searchbox"), { target: { value: "silo" } });
      fireEvent.click(screen.getByRole("button", { name: "Chercher" }));
      cleanup();

      renderAdd();
      const sugg = document.querySelector(".sugg");
      expect(sugg).not.toBeNull();
      expect(sugg?.textContent).toContain("silo");
    });

    it("taper une chip RELANCE la recherche — pas un simple préremplissage", () => {
      localStorage.setItem("tm.add.recentSearches", JSON.stringify(["severance"]));
      renderAdd();

      fireEvent.click(screen.getByRole("button", { name: "severance" }));

      // The idle prompt is gone: the query ran (maquette: a shortcut that
      // leaves a gesture to make is not a shortcut).
      expect(screen.queryByText("Cherchez un titre")).toBeNull();
      expect(screen.getByRole("searchbox")).toHaveValue("severance");
    });

    it("un résultat DÉJÀ SUIVI (même id) répond « ✓ Suivi », désactivé", () => {
      followedListMock.mockReturnValue({
        data: {
          items: [
            { title: "Silo", media_ref: { tvdb_id: 1, tmdb_id: null } },
          ],
        },
      });
      renderAdd({
        results: [{ title: "Silo", kind: "tv", provider: "tvdb", provider_id: 1 }],
      });
      fireEvent.change(screen.getByRole("searchbox"), { target: { value: "silo" } });
      fireEvent.click(screen.getByRole("button", { name: "Chercher" }));

      const doneBtn = screen.getByRole("button", { name: /✓ Suivi/ });
      expect(doneBtn).toBeDisabled();
      expect(doneBtn).toHaveClass("resbtn", "done");
    });

    it("un HOMONYME reste ajoutable — le titre n'est pas une identité", () => {
      // « Dune » (1984) must stay followable while « Dune » (2021) is
      // followed: a title match hard-disabled the button and locked the
      // operator out of the other film entirely.
      followedListMock.mockReturnValue({
        data: {
          items: [
            { title: "Dune", media_ref: { tmdb_id: 438631, tvdb_id: null } },
          ],
        },
      });
      renderAdd({
        results: [
          { title: "Dune", kind: "movie", provider: "tmdb", provider_id: 841 },
        ],
      });
      fireEvent.change(screen.getByRole("searchbox"), { target: { value: "dune" } });
      fireEvent.click(screen.getByRole("button", { name: "Chercher" }));

      const btn = screen
        .getAllByRole("button", { name: "Ajouter" })
        .find((b) => b.className.includes("resbtn"));
      expect(btn).toBeDefined();
      expect(btn).not.toBeDisabled();
    });

    it("une requête déjà suivie n'est pas proposée", () => {
      localStorage.setItem(
        "tm.add.recentSearches",
        JSON.stringify(["Dune", "silo"]),
      );
      followedListMock.mockReturnValue({
        data: {
          items: [
            { title: "dune", media_ref: { tmdb_id: 438631, tvdb_id: null } },
          ],
        },
      });
      renderAdd();

      const sugg = document.querySelector(".sugg");
      expect(sugg?.textContent).toContain("silo");
      expect(sugg?.textContent).not.toContain("Dune");
    });
  });
});
