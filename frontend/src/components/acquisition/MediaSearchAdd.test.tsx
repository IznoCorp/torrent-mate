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

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const navigateMock = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

import { MediaSearchAdd } from "@/components/acquisition/MediaSearchAdd";
import { toast } from "sonner";

beforeEach(() => {
  mediaSearchMock.mockReturnValue({
    // useInfiniteQuery shape: pages, not a flat results array.
    data: {
      pages: [
        {
          total: 1,
          offset: 0,
          limit: 20,
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
      ],
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

/**
 * Click the single ENABLED « Suivre » button. After a search, two « Suivre »
 * buttons coexist (the always-visible by-ID entry + the result card); the by-ID
 * one is disabled while its id field is empty, so exactly one is enabled — the
 * result-card action. Asserts that invariant, then clicks it (lint-clean: no
 * non-null assertion, narrowed via a runtime guard).
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

/** Expand the collapsed « ou ajouter directement par ID » section. */
function expandById(): void {
  fireEvent.click(
    screen.getByRole("button", { name: /ou ajouter directement par ID/i }),
  );
}

describe("MediaSearchAdd", () => {
  it("shows no encumbering empty-state before a search, but keeps the by-ID entry (#21)", () => {
    render(<MediaSearchAdd />);
    // #21: the « Recherchez un média / Tapez un titre… » empty-state is gone —
    // an idle query renders nothing where the results grid would be.
    expect(screen.queryByText("Recherchez un média")).not.toBeInTheDocument();
    // The by-ID entry is merged into this surface and always visible.
    expect(
      screen.getByText("ou ajouter directement par ID"),
    ).toBeInTheDocument();
    // No result card yet (query is empty).
    expect(screen.queryByText("Dune")).not.toBeInTheDocument();
  });

  it("keeps the search row inside a narrow viewport (mobile-shell: input min-w-0, row flex-wrap)", () => {
    // Class-contract guard (jsdom does not lay out, so a real 390 px overflow
    // measurement is vacuous here — that is ACC-05 in Chrome). This pins the two
    // structural fixes that stop « Chercher » overflowing past 390 px: the input
    // column may shrink, and the kind-filter/Chercher row wraps the button below
    // instead of pushing it off-screen.
    render(<MediaSearchAdd />);

    const input = screen.getByLabelText("Rechercher un média à suivre");
    expect(input.parentElement?.className).toContain("min-w-0");

    const chercher = screen.getByRole("button", { name: "Chercher" });
    expect(chercher.parentElement?.className).toContain("flex-wrap");
  });

  it("renders results after submitting and follows on click", () => {
    render(<MediaSearchAdd />);
    fireEvent.change(screen.getByLabelText("Rechercher un média à suivre"), {
      target: { value: "dune" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Chercher" }));

    expect(screen.getByText("Dune")).toBeInTheDocument();

    clickResultSuivre();
    // The candidate's card metadata (year/overview; poster_url is null → omitted)
    // is carried into the follow body so the watch-list card can show it (OBJ3).
    expect(followMutate).toHaveBeenCalledWith(
      {
        tvdb_id: 1,
        title: "Dune",
        kind: "show",
        overview: "Sur Arrakis.",
        year: 2021,
      },
      expect.anything(),
    );
  });

  it("resets the search after a successful follow (#19)", () => {
    // The follow succeeds synchronously so the onSuccess reset runs.
    followMutate.mockImplementation(
      (_body: unknown, opts?: { onSuccess?: (created: unknown) => void }) => {
        opts?.onSuccess?.({});
      },
    );
    render(<MediaSearchAdd />);
    const input = screen.getByLabelText("Rechercher un média à suivre");
    fireEvent.change(input, { target: { value: "dune" } });
    fireEvent.click(screen.getByRole("button", { name: "Chercher" }));
    expect(screen.getByText("Dune")).toBeInTheDocument();

    clickResultSuivre();

    // #19: the query + draft are cleared → the results collapse and the input
    // is empty, ready for the next search.
    expect(screen.queryByText("Dune")).not.toBeInTheDocument();
    expect((input as HTMLInputElement).value).toBe("");
  });
});

// The add-by-ID entry is merged into this search surface (#21) — it used to be a
// separate FollowedPanel accordion (ticket 336). No accordion to open now.
describe("MediaSearchAdd — add-by-id (merged surface, #21)", () => {
  it("is collapsed by default and expands on click (compact surface)", () => {
    render(<MediaSearchAdd />);
    // The header is always visible; the id fields/providers are hidden until expanded.
    const toggle = screen.getByRole("button", {
      name: /ou ajouter directement par ID/i,
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "TVDB" })).toBeNull();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "TVDB" })).toBeInTheDocument();
  });

  it("offers TVDB, TMDB and IMDB providers", () => {
    render(<MediaSearchAdd />);
    expandById();
    for (const p of ["TVDB", "TMDB", "IMDB"]) {
      expect(screen.getByRole("button", { name: p })).toBeInTheDocument();
    }
  });

  it("selecting IMDB switches the id field to the tt… placeholder", () => {
    render(<MediaSearchAdd />);
    expandById();
    fireEvent.click(screen.getByRole("button", { name: "IMDB" }));
    expect(screen.getByPlaceholderText("ex: tt0903747")).toBeInTheDocument();
    expect(screen.getByLabelText("ID IMDB")).toBeInTheDocument();
  });

  it("follows by TMDB id → sends tmdb_id", () => {
    render(<MediaSearchAdd />);
    expandById();
    fireEvent.click(screen.getByRole("button", { name: "TMDB" }));
    fireEvent.change(screen.getByLabelText("ID TMDB"), {
      target: { value: "1399" },
    });
    // query === "" here → no result cards, so « Suivre » is unambiguous.
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    expect(followMutate).toHaveBeenCalledTimes(1);
    expect(followMutate.mock.calls[0]?.[0]).toEqual({
      tmdb_id: 1399,
      kind: "show",
    });
  });

  it("follows by IMDB id → sends the tt string", () => {
    render(<MediaSearchAdd />);
    expandById();
    fireEvent.click(screen.getByRole("button", { name: "IMDB" }));
    fireEvent.change(screen.getByLabelText("ID IMDB"), {
      target: { value: "tt0903747" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    expect(followMutate).toHaveBeenCalledTimes(1);
    expect(followMutate.mock.calls[0]?.[0]).toEqual({
      imdb_id: "tt0903747",
      kind: "show",
    });
  });

  it("carries an optional title into the by-ID follow body", () => {
    render(<MediaSearchAdd />);
    expandById();
    fireEvent.click(screen.getByRole("button", { name: "TMDB" }));
    fireEvent.change(screen.getByLabelText("ID TMDB"), {
      target: { value: "1399" },
    });
    fireEvent.change(screen.getByLabelText("Titre (optionnel)"), {
      target: { value: "Game of Thrones" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    expect(followMutate.mock.calls[0]?.[0]).toEqual({
      tmdb_id: 1399,
      kind: "show",
      title: "Game of Thrones",
    });
  });

  it("disables Suivre for a malformed IMDB id", () => {
    render(<MediaSearchAdd />);
    expandById();
    fireEvent.click(screen.getByRole("button", { name: "IMDB" }));
    fireEvent.change(screen.getByLabelText("ID IMDB"), {
      target: { value: "0903747" },
    });
    expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
  });

  // ---- ACQUISITION-2 (ticket 250): inline field error on an invalid id -----

  it("affiche une erreur inline sous le champ pour un ID numérique invalide (ticket 250)", () => {
    render(<MediaSearchAdd />);
    expandById();
    // TVDB is the default provider; a negative number is rejected by
    // buildIdFollowBody (positive integers only).
    const input = screen.getByLabelText("ID TVDB");
    fireEvent.change(input, { target: { value: "-5" } });

    const error = screen.getByRole("alert");
    expect(error).toHaveTextContent(
      "Identifiant invalide — entrez un nombre entier positif.",
    );
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "acq-id-error");
    expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
  });

  it("affiche l'erreur au format IMDB pour un tt… malformé (ticket 250)", () => {
    render(<MediaSearchAdd />);
    expandById();
    fireEvent.click(screen.getByRole("button", { name: "IMDB" }));
    fireEvent.change(screen.getByLabelText("ID IMDB"), {
      target: { value: "0903747" },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Identifiant IMDB invalide — format attendu : tt1234567.",
    );
  });

  it("affiche l'erreur inline pour du texte non numérique et ne suit pas (ticket 250)", () => {
    render(<MediaSearchAdd />);
    expandById();
    // TVDB is the default provider. With the former type="number" field,
    // badInput text ("12e34") reported value "" while the garbage stayed
    // visible → no error, disabled button, silent no-op. The text field lets
    // the garbage reach state, and the digits-only gate rejects it (Number()
    // alone would coerce "12e34" into a bogus huge id).
    const input = screen.getByLabelText("ID TVDB");
    fireEvent.change(input, { target: { value: "12e34" } });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Identifiant invalide — entrez un nombre entier positif.",
    );
    expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
    expect(followMutate).not.toHaveBeenCalled();
  });

  it("affiche l'erreur inline pour un ID trop long qui perdrait sa précision et ne suit pas (ticket 250)", () => {
    render(<MediaSearchAdd />);
    expandById();
    // TVDB is the default provider. A 23-digit string passes the digits-only
    // gate AND Number.isInteger, but Number() has already mangled it
    // (JSON would emit 1e+23) — the safe-integer gate in buildIdFollowBody
    // must refuse it rather than follow a wrong id.
    const input = screen.getByLabelText("ID TVDB");
    fireEvent.change(input, { target: { value: "12345678901234567890123" } });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Identifiant invalide — entrez un nombre entier positif.",
    );
    expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
    expect(followMutate).not.toHaveBeenCalled();
  });

  it("garde le clavier numérique mobile via inputMode sur un champ type text (ticket 250)", () => {
    render(<MediaSearchAdd />);
    expandById();
    // ACQUISITION-2: type="text" so invalid text reaches state (no badInput
    // black hole), inputMode="numeric" so mobiles still open the keypad.
    const input = screen.getByLabelText("ID TVDB");
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveAttribute("inputmode", "numeric");
  });

  it("aucune erreur inline pour un ID valide ou un champ vide (ticket 250)", () => {
    render(<MediaSearchAdd />);
    expandById();
    // Empty field: disabled button but NO error (nothing typed yet).
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // Valid id: no error either.
    fireEvent.change(screen.getByLabelText("ID TVDB"), {
      target: { value: "255968" },
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("toasts a warning when the followed show comes back tvdb_unresolved", () => {
    followMutate.mockImplementation(
      (
        _body: unknown,
        opts?: { onSuccess?: (created: { tvdb_unresolved?: boolean }) => void },
      ) => {
        opts?.onSuccess?.({ tvdb_unresolved: true });
      },
    );
    render(<MediaSearchAdd />);
    expandById();
    fireEvent.click(screen.getByRole("button", { name: "TMDB" }));
    fireEvent.change(screen.getByLabelText("ID TMDB"), {
      target: { value: "1399" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    expect(vi.mocked(toast.warning)).toHaveBeenCalled();
  });
});

describe("carrousel de résultats (§12 mobile first, §8 rien en silence)", () => {
  /** Run a search so the results rail renders. */
  function search(): void {
    render(<MediaSearchAdd />);
    fireEvent.change(screen.getByLabelText("Rechercher un média à suivre"), {
      target: { value: "dune" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Chercher" }));
  }

  it("affiche le nombre TOTAL de résultats, pas le nombre de cartes rendues", () => {
    // §8: five rows out of eighty-one with no count reads as "that is all there
    // is" — the silence that made a mainstream film look absent.
    mediaSearchMock.mockReturnValue({
      data: {
        pages: [
          {
            total: 81,
            offset: 0,
            limit: 20,
            results: [
              {
                provider: "tmdb",
                provider_id: 969681,
                title: "Spider-Man : Brand New Day",
                year: 2026,
                kind: "movie",
                poster_url: null,
                overview: null,
                score: 0.92,
              },
            ],
          },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      hasNextPage: true,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
    });
    search();
    expect(screen.getByTestId("search-result-count")).toHaveTextContent(
      "81 résultats",
    );
  });

  it("le conteneur défile, et lui seul — la page ne déborde pas (§12)", () => {
    search();
    const rail = screen.getByTestId("search-rail");
    expect(rail.className).toContain("overflow-x-auto");
    expect(rail.className).toContain("snap-x");
  });

  it("les flèches sont masquées sous sm et présentes au-delà", () => {
    search();
    const previous = screen.getByRole("button", {
      name: "Résultats précédents",
    });
    const container = previous.parentElement;
    // Tailwind: hidden by default, flex from sm — the thumb scrolls on a phone,
    // where a pair of buttons would steal width from the cards.
    expect(container?.className).toContain("hidden");
    expect(container?.className).toContain("sm:flex");
  });

  it("charge la page suivante à l'approche du bord, sans bouton à viser", () => {
    const fetchNextPage = vi.fn();
    mediaSearchMock.mockReturnValue({
      data: {
        pages: [
          {
            total: 81,
            offset: 0,
            limit: 20,
            results: [
              {
                provider: "tmdb",
                provider_id: 1,
                title: "Dune",
                year: 2021,
                kind: "movie",
                poster_url: null,
                overview: null,
                score: 0.9,
              },
            ],
          },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      hasNextPage: true,
      isFetchingNextPage: false,
      fetchNextPage,
    });
    search();
    const rail = screen.getByTestId("search-rail");
    // jsdom reports zero-size elements, so drive the geometry explicitly.
    Object.defineProperty(rail, "scrollWidth", { value: 1000, writable: true });
    Object.defineProperty(rail, "clientWidth", { value: 400, writable: true });
    Object.defineProperty(rail, "scrollLeft", { value: 500, writable: true });
    fireEvent.scroll(rail);
    expect(fetchNextPage).toHaveBeenCalled();
  });

  it("ne recharge pas quand il n'y a plus de page", () => {
    const fetchNextPage = vi.fn();
    mediaSearchMock.mockReturnValue({
      data: {
        pages: [
          {
            total: 1,
            offset: 0,
            limit: 20,
            results: [
              {
                provider: "tmdb",
                provider_id: 1,
                title: "Dune",
                year: 2021,
                kind: "movie",
                poster_url: null,
                overview: null,
                score: 0.9,
              },
            ],
          },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage,
    });
    search();
    const rail = screen.getByTestId("search-rail");
    Object.defineProperty(rail, "scrollWidth", { value: 1000, writable: true });
    Object.defineProperty(rail, "clientWidth", { value: 400, writable: true });
    Object.defineProperty(rail, "scrollLeft", { value: 600, writable: true });
    fireEvent.scroll(rail);
    expect(fetchNextPage).not.toHaveBeenCalled();
  });
});
