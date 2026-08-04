import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MediaSheetResponse } from "@/api/media";
import {
  MediaSheet,
  type MediaSheetProps,
} from "@/components/media/MediaSheet";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const { getMediaSheetMock } = vi.hoisted(() => ({
  getMediaSheetMock: vi.fn(),
}));

vi.mock("@/api/media", () => ({
  getMediaSheet: getMediaSheetMock,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Base movie response. */
function movieResponse(
  overrides: Partial<MediaSheetResponse> = {},
): MediaSheetResponse {
  return {
    provider: "tmdb",
    provider_id: "27205",
    title: "Inception",
    year: 2010,
    poster_url: "https://image.tmdb.org/t/p/w500/inception.jpg",
    overview:
      "A thief who steals corporate secrets through dream-sharing technology...",
    director: "Christopher Nolan",
    genres: ["Action", "Science Fiction", "Thriller"],
    trailer_url: "https://www.youtube.com/watch?v=YoHD9XEInc0",
    kind: "movie",
    series_status: null,
    episode_count: null,
    seasons: [],
    ownership: {
      owned: true,
      seasons: [],
    },
    degraded_reason: null,
    ...overrides,
  };
}

/** Base TV response. */
function tvResponse(
  overrides: Partial<MediaSheetResponse> = {},
): MediaSheetResponse {
  return {
    provider: "tmdb",
    provider_id: "1399",
    title: "Game of Thrones",
    year: 2011,
    poster_url: "https://image.tmdb.org/t/p/w500/got.jpg",
    overview:
      "Seven noble families fight for control of the mythical land of Westeros.",
    director: null,
    genres: ["Sci-Fi & Fantasy", "Drama", "Action & Adventure"],
    trailer_url: "https://www.youtube.com/watch?v=KPLWWIOCOOQ",
    kind: "tv",
    series_status: "Ended",
    episode_count: 73,
    seasons: [
      { season_number: 1, episode_count: 10 },
      { season_number: 2, episode_count: 10 },
      { season_number: 3, episode_count: 10 },
    ],
    ownership: {
      owned: true,
      seasons: [
        {
          season_number: 1,
          episode_count: 10,
          owned_count: 10,
          aired_count: 10,
        },
        {
          season_number: 2,
          episode_count: 10,
          owned_count: 5,
          aired_count: 10,
        },
        {
          season_number: 3,
          episode_count: 10,
          owned_count: 0,
          aired_count: 10,
        },
      ],
    },
    degraded_reason: null,
    ...overrides,
  };
}

/** Minimal props for the component. */
function sheetProps(overrides: Partial<MediaSheetProps> = {}): MediaSheetProps {
  return {
    provider: "tmdb",
    providerId: "27205",
    ...overrides,
  };
}

/** Render {@link MediaSheet} wrapped in a retry-free QueryClientProvider. */
function renderSheet(props: MediaSheetProps): void {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={client}>
      <MediaSheet {...props} />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  getMediaSheetMock.mockReset();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("MediaSheet", () => {
  // --- Loading ---

  it("affiche le skeleton pendant le chargement", () => {
    // A promise that never resolves keeps the query in loading state.
    getMediaSheetMock.mockImplementation(() => new Promise(() => undefined));
    renderSheet(sheetProps());

    expect(screen.getByTestId("media-sheet-loading")).toBeInTheDocument();
  });

  // --- Error ---

  it("affiche ErrorState en cas d'erreur", async () => {
    getMediaSheetMock.mockImplementation(() =>
      Promise.reject(new Error("Network error")),
    );
    renderSheet(sheetProps());

    // The error state renders inside media-sheet (not the skeleton).
    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByText(/impossible de charger la fiche/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  // --- Degraded (D9) ---

  it("affiche le bandeau d'avertissement quand degraded_reason est présent", async () => {
    getMediaSheetMock.mockResolvedValue(
      movieResponse({
        degraded_reason:
          "TMDB injoignable après 3 tentatives — données partielles",
        director: null,
        overview: "",
        genres: [],
        trailer_url: null,
      }),
    );
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    // Warning banner.
    expect(screen.getByText(/source de données dégradée/i)).toBeInTheDocument();
    expect(
      screen.getByText(/TMDB injoignable après 3 tentatives/),
    ).toBeInTheDocument();

    // Title still shown.
    expect(
      screen.getByRole("heading", { name: "Inception" }),
    ).toBeInTheDocument();
  });

  // --- Movie (loaded) ---

  it("affiche la fiche complète d'un film", async () => {
    getMediaSheetMock.mockResolvedValue(movieResponse());
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    // Title + year.
    expect(
      screen.getByRole("heading", { name: "Inception" }),
    ).toBeInTheDocument();
    expect(screen.getByText("2010")).toBeInTheDocument();

    // Director.
    expect(screen.getByText("Christopher Nolan")).toBeInTheDocument();

    // Genres.
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Science Fiction")).toBeInTheDocument();
    expect(screen.getByText("Thriller")).toBeInTheDocument();

    // Synopsis.
    expect(screen.getByText(/dream-sharing technology/i)).toBeInTheDocument();

    // Trailer link.
    expect(screen.getByText("Voir sur YouTube")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /voir sur youtube/i }),
    ).toHaveAttribute("href", "https://www.youtube.com/watch?v=YoHD9XEInc0");

    // Ownership.
    expect(screen.getByText("Possédé")).toBeInTheDocument();
  });

  it("n'affiche PAS la section série pour un film", async () => {
    getMediaSheetMock.mockResolvedValue(movieResponse());
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    expect(screen.queryByText("Statut")).not.toBeInTheDocument();
    expect(screen.queryByText("Épisodes")).not.toBeInTheDocument();
  });

  // --- TV ---

  it("affiche la fiche d'une série avec statut, épisodes et saisons", async () => {
    getMediaSheetMock.mockResolvedValue(tvResponse());
    renderSheet(sheetProps({ provider: "tmdb", providerId: "1399" }));

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    // Series status.
    expect(screen.getByText("Statut")).toBeInTheDocument();
    expect(screen.getByText("Terminée")).toBeInTheDocument();

    // Episode count — "Épisodes" appears in both the info line and table headers.
    expect(screen.getAllByText("Épisodes").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("73")).toBeInTheDocument();

    // Seasons table — season numbers appear in both tables for series with ownership.
    expect(screen.getAllByText("S01").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("S02").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("S03").length).toBeGreaterThanOrEqual(1);

    // Ownership per season — S1 at 100% shows "Complète" (may also appear in both tables).
    expect(screen.getAllByText("Complète").length).toBeGreaterThanOrEqual(1);
  });

  // --- TV season with unknown episode count (§8) ---

  it("affiche « Épisodes inconnus » pour une saison avec episode_count === 0, jamais « Complète »", async () => {
    // A season with episode_count === 0 has no known catalog data (unaired /
    // future season).  owned_count >= 0 would trivially compute as "complete",
    // which is a confident label for data we do not have (§8).
    getMediaSheetMock.mockResolvedValue(
      tvResponse({
        ownership: {
          owned: true,
          seasons: [
            {
              season_number: 1,
              episode_count: 10,
              owned_count: 10,
              aired_count: 10,
            },
            {
              season_number: 2,
              episode_count: 0, // ← the key case
              owned_count: 0,
              aired_count: 0,
            },
          ],
        },
      }),
    );
    renderSheet(sheetProps({ provider: "tmdb", providerId: "1399" }));

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    // S01 is complete (10/10).
    expect(screen.getByText("Complète")).toBeInTheDocument();

    // S02 has 0 episodes → "Épisodes inconnus", never "Complète".
    expect(screen.getByText("Épisodes inconnus")).toBeInTheDocument();
    // Confidence check: the neutral badge must NOT claim "Complète" for S02.
    const completeBadges = screen.getAllByText("Complète");
    expect(completeBadges).toHaveLength(1); // only S01
  });

  // --- Missing director ---

  it("affiche « Réalisateur inconnu » quand le réalisateur est absent", async () => {
    getMediaSheetMock.mockResolvedValue(movieResponse({ director: null }));
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    expect(screen.getByText("Réalisateur inconnu")).toBeInTheDocument();
  });

  // --- No trailer ---

  it("n'affiche PAS la section bande-annonce quand trailer_url est absent", async () => {
    getMediaSheetMock.mockResolvedValue(movieResponse({ trailer_url: null }));
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    expect(screen.queryByText("Bande-annonce")).not.toBeInTheDocument();
    expect(screen.queryByText("Voir sur YouTube")).not.toBeInTheDocument();
  });

  // --- Ownership null (library unreachable, D5) ---

  it("affiche « État inconnu » quand ownership est null (pas « non possédé »)", async () => {
    getMediaSheetMock.mockResolvedValue(movieResponse({ ownership: null }));
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    expect(screen.getByText("État inconnu")).toBeInTheDocument();
    expect(screen.queryByText("Non possédé")).not.toBeInTheDocument();
  });

  // --- Ownership: non possédé (D5) ---

  it("affiche « Non possédé » quand owned est false", async () => {
    getMediaSheetMock.mockResolvedValue(
      movieResponse({
        ownership: { owned: false, seasons: [] },
      }),
    );
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    expect(screen.getByText("Non possédé")).toBeInTheDocument();
  });

  // --- kind hint passed through ---

  it("transmet le paramètre kind à l'appel API", async () => {
    getMediaSheetMock.mockResolvedValue(movieResponse());
    renderSheet(
      sheetProps({ provider: "tmdb", providerId: "27205", kind: "movie" }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    expect(getMediaSheetMock).toHaveBeenCalledWith("tmdb", "27205", {
      kind: "movie",
    });
  });

  // --- kind field controls series vs movie rendering ---

  it("traite une série avec catalog vide comme une série (pas comme un film)", async () => {
    // Top Chef Le Concours Parallèle scenario: kind="tv" but seasons=[],
    // series_status=null, episode_count=null. The old heuristic would guess
    // "movie" and print "Ce film n'est pas encore dans la médiathèque."
    getMediaSheetMock.mockResolvedValue(
      tvResponse({
        kind: "tv",
        series_status: null,
        episode_count: null,
        seasons: [],
        ownership: { owned: false, seasons: [] },
      }),
    );
    renderSheet(sheetProps({ provider: "tvdb", providerId: "475278" }));

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    // Must NOT say "Ce film" — this is a series, not a film.
    expect(
      screen.queryByText(/ce film n'est pas encore/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/ce film est présent/i)).not.toBeInTheDocument();

    // The ownership block renders the series case with empty seasons.
    expect(
      screen.getByText(/cette série n'est pas encore dans la médiathèque/i),
    ).toBeInTheDocument();
  });

  it("un kind=null n'affiche ni « film » ni série", async () => {
    // Degraded response — the server honestly says it doesn't know the kind.
    getMediaSheetMock.mockResolvedValue(
      movieResponse({
        kind: null,
        director: null,
        overview: "",
        genres: [],
        trailer_url: null,
        ownership: { owned: false, seasons: [] },
      }),
    );
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    // Must NOT claim "film".
    expect(
      screen.queryByText(/ce film n'est pas encore/i),
    ).not.toBeInTheDocument();

    // Must NOT show the series section — kind is unknown.
    expect(screen.queryByText("Statut")).not.toBeInTheDocument();
    expect(screen.queryByText("Épisodes")).not.toBeInTheDocument();

    // The unknown-kind message uses the neutral "ce média".
    expect(
      screen.getByText(/ce média n'est pas encore dans la médiathèque/i),
    ).toBeInTheDocument();
  });

  it("affiche « Possédé » pour un film avec kind='movie'", async () => {
    getMediaSheetMock.mockResolvedValue(
      movieResponse({
        kind: "movie",
        ownership: { owned: true, seasons: [] },
      }),
    );
    renderSheet(sheetProps());

    await waitFor(() => {
      expect(screen.getByTestId("media-sheet")).toBeInTheDocument();
    });

    // The movie sentence uses "Ce film".
    expect(
      screen.getByText(/ce film est présent dans la médiathèque/i),
    ).toBeInTheDocument();
  });
});
