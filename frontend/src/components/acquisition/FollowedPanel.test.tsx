/**
 * FollowedPanel — Phase 02 tests: compact rows (72 px poster, mono completeness,
 * DropdownMenu actions), synopsis absent, CompletenessAccordion preserved.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FollowedSeriesItem } from "@/api/acquisition";
import { ApiError } from "@/api/client";

// The « Récupérer maintenant » action posts through the API module directly
// (no hook), so the endpoint itself is stubbed; everything else stays real.
const { grabMock, followMock, toastMock } = vi.hoisted(() => ({
  grabMock: vi.fn(),
  followMock: vi.fn(),
  toastMock: {
    info: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock("@/api/acquisition", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/acquisition")>();
  return {
    ...actual,
    triggerFollowedGrab: (id: number): Promise<{ run_uid: string }> =>
      grabMock(id) as Promise<{ run_uid: string }>,
  };
});

vi.mock("sonner", () => ({ toast: toastMock }));

// Inert hook mocks: the panel's mutations/queries never fire in these render
// tests — only the markup derived from the `data` prop is under test.
vi.mock("@/hooks/useAcquisition", () => ({
  useFollow: () => ({ mutate: followMock, isPending: false }),
  useUpdateFollow: () => ({ mutate: vi.fn(), isPending: false }),
  useUnfollow: () => ({ mutate: vi.fn(), isPending: false }),
  useCompleteness: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
  useTrackedAcquisitionRun: () => undefined,
}));

vi.mock("@/hooks/useSchedulers", () => ({
  useSchedulers: () => ({ data: undefined }),
}));

import { FollowedPanel } from "./FollowedPanel";

/** A fully-typed followed item, with the five-state counters nulled (no catalog). */
function makeItem(
  overrides: Partial<FollowedSeriesItem> = {},
): FollowedSeriesItem {
  return {
    id: 1,
    title: "House of the Dragon",
    kind: "show",
    active: true,
    added_at: 1_719_792_000,
    cadence: { interval_minutes: 60 },
    cadence_tier: null,
    next_search_at: null,
    quality_profile: null,
    wanted_pending: 0,
    wanted_grabbed: 0,
    season_count: 2,
    year: 2022,
    overview: null,
    poster_url: null,
    media_ref: { tvdb_id: 371572, tmdb_id: null, imdb_id: null },
    status: "a_jour",
    priming_running: false,
    tvdb_unresolved: false,
    aired_count: null,
    owned_count: null,
    a_recuperer_count: null,
    en_acquisition_count: null,
    en_attente_count: null,
    non_verifie_count: null,
    movie_facts: null,
    ...overrides,
  };
}

function renderPanel(items: readonly FollowedSeriesItem[]): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <FollowedPanel
        data={items}
        isLoading={false}
        isError={false}
        error={null}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FollowedPanel — compact rows (Phase 02)", () => {
  it("renders the a_recuperer status badge as « À récupérer »", () => {
    renderPanel([makeItem({ status: "a_recuperer" })]);

    expect(screen.getByText("À récupérer")).toBeInTheDocument();
  });

  it("renders completeness as NN/NN in font-mono tabular-nums", () => {
    renderPanel([
      makeItem({
        status: "a_recuperer",
        aired_count: 18,
        owned_count: 15,
        a_recuperer_count: 3,
      }),
    ]);

    // Compact row: completeness is "15/18" — no verbose "en médiathèque".
    const completeSpan = screen.getByText("15/18");
    expect(completeSpan).toBeInTheDocument();
    // The completeness node must carry font-mono AND tabular-nums classes.
    expect(completeSpan.className).toContain("font-mono");
    expect(completeSpan.className).toContain("tabular-nums");
    expect(screen.queryByText(/en médiathèque/)).not.toBeInTheDocument();
  });

  it("shows '—' for completeness when aired_count is null (no catalog)", () => {
    renderPanel([
      makeItem({
        id: 1,
        title: "Silo",
        status: "a_recuperer",
        aired_count: 10,
        owned_count: 9,
        a_recuperer_count: 1,
      }),
      // aired_count null = no cached catalog → "—" for completeness.
      makeItem({ id: 2, title: "Top Chef" }),
    ]);

    expect(screen.getByText("9/10")).toBeInTheDocument();
    // Top Chef has no catalog — completeness renders "—".
    expect(screen.getByText("—")).toBeInTheDocument();
    // No verbose "en médiathèque" caption anywhere.
    expect(screen.queryByText(/en médiathèque/)).not.toBeInTheDocument();
  });

  it("omits the synopsis (overview) from the compact row (E3)", () => {
    renderPanel([
      makeItem({
        overview:
          "An internal succession war within House Targaryen at the height of its power.",
      }),
    ]);

    // The overview text must NOT appear in the compact row.
    expect(
      screen.queryByText(/internal succession war/),
    ).not.toBeInTheDocument();
  });

  it("renders a poster thumb at ~72 px via DS MediaPoster", () => {
    renderPanel([makeItem()]);

    // The DS MediaPoster is always rendered (with initials fallback when
    // poster_url is null). It renders a div[role="img"] with aria-label.
    const poster = screen.getByRole("img", { name: "House of the Dragon" });
    expect(poster).toBeInTheDocument();
    // The item title is also rendered in the row.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
  });

  it("renders a DropdownMenu trigger for each active row", () => {
    renderPanel([makeItem()]);

    // The ⋯ button opens the actions dropdown.
    expect(
      screen.getByRole("button", { name: "Actions pour House of the Dragon" }),
    ).toBeInTheDocument();
  });

  it("renders the CompletenessAccordion below a series row", () => {
    renderPanel([makeItem({ kind: "show" })]);

    // The accordion trigger is still present below the compact row.
    expect(screen.getByText("Détail par épisode")).toBeInTheDocument();
  });

  it("does NOT render the CompletenessAccordion for movies", () => {
    renderPanel([makeItem({ kind: "movie", title: "Ferrari" })]);

    expect(screen.queryByText("Détail par épisode")).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — les cinq états sur la carte (phase 8)", () => {
  it.each([
    ["a_jour", "À jour"],
    ["a_recuperer", "À récupérer"],
    ["en_acquisition", "En cours d'acquisition"],
    ["en_attente", "En attente"],
    ["non_verifie", "Non vérifié"],
    ["verification_en_cours", "Vérification en cours"],
  ])("affiche %s comme « %s »", (status, label) => {
    renderPanel([makeItem({ status: status as FollowedSeriesItem["status"] })]);

    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("affiche « En pause » pour un suivi désactivé (section repliée)", () => {
    // A disabled follow lives in the retired section, which carries no chip —
    // the vocabulary still owns the label, exercised through the map.
    renderPanel([makeItem({ active: false, status: "disabled" })]);

    expect(screen.getByText("Suivis retirés (1)")).toBeInTheDocument();
  });

  it("explique l'état en infobulle (En attente ≠ Non vérifié)", () => {
    renderPanel([
      makeItem({ id: 1, title: "Silo", status: "en_attente" }),
      makeItem({ id: 2, title: "Furious", status: "non_verifie" }),
    ]);

    const attente = screen.getByText("En attente").closest("[title]");
    const nonVerifie = screen.getByText("Non vérifié").closest("[title]");
    expect(attente?.getAttribute("title")).toMatch(/rien de conforme/);
    expect(nonVerifie?.getAttribute("title")).toMatch(/[Pp]as encore vérifié/);
    expect(attente?.getAttribute("title")).not.toBe(
      nonVerifie?.getAttribute("title"),
    );
  });

  it("affiche les compteurs par état, jamais le compteur wanted_pending brut", () => {
    renderPanel([
      makeItem({
        status: "a_recuperer",
        aired_count: 18,
        owned_count: 12,
        a_recuperer_count: 3,
        en_acquisition_count: 1,
        en_attente_count: 1,
        non_verifie_count: 1,
        // The lying counter: 9 rows queued while only 6 episodes are not owned.
        wanted_pending: 9,
      }),
    ]);

    expect(
      screen.getByText(
        "3 à récupérer · 1 en cours d'acquisition · 1 en attente · 1 non vérifié",
      ),
    ).toBeInTheDocument();
    // The raw wanted_pending chip is gone — it knew nothing about ownership.
    expect(screen.queryByText("9 en attente")).not.toBeInTheDocument();
  });

  it("n'affiche aucun compteur quand tout est en médiathèque", () => {
    renderPanel([
      makeItem({
        status: "a_jour",
        aired_count: 10,
        owned_count: 10,
        a_recuperer_count: 0,
        en_acquisition_count: 0,
        en_attente_count: 0,
        non_verifie_count: 0,
      }),
    ]);

    expect(screen.getByText("10/10")).toBeInTheDocument();
    expect(screen.queryByText(/à récupérer/)).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — statut film sur ownership (D2-B)", () => {
  it("n'affiche aucune fraction pour un film (son état EST la pastille)", () => {
    renderPanel([
      makeItem({
        kind: "movie",
        title: "Ferrari",
        status: "a_jour",
        movie_facts: {
          owned: true,
          wanted_status: null,
          last_search_outcome: null,
          last_search_found: null,
        },
      }),
    ]);

    expect(screen.getByText("Acquis")).toBeInTheDocument();
    // No "1/1", and no "—" either: a film is not a completeness fraction.
    expect(screen.queryByText("—")).not.toBeInTheDocument();
    expect(screen.queryByText("1/1")).not.toBeInTheDocument();
  });

  it("garde le libellé partagé pour un film à récupérer", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "a_recuperer" }),
    ]);

    expect(screen.getByText("À récupérer")).toBeInTheDocument();
  });

  it("dit en français pourquoi un film attend, jamais le jeton machine", () => {
    renderPanel([
      makeItem({
        kind: "movie",
        title: "Ferrari",
        status: "en_attente",
        movie_facts: {
          owned: false,
          wanted_status: "pending",
          last_search_outcome: "all_filtered",
          last_search_found: 0,
        },
      }),
    ]);

    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.getByText("rien de conforme au profil")).toBeInTheDocument();
    expect(screen.queryByText(/all_filtered/)).not.toBeInTheDocument();
  });

  it("libelle un film en médiathèque « Acquis » (pas « À jour »)", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "a_jour" }),
    ]);

    expect(screen.getByText("Acquis")).toBeInTheDocument();
    expect(screen.queryByText("À jour")).not.toBeInTheDocument();
  });

  it("garde les libellés série pour une série à jour", () => {
    renderPanel([makeItem({ kind: "show", status: "a_jour" })]);

    // The movie override must not leak into series cards.
    expect(screen.getByText("À jour")).toBeInTheDocument();
    expect(screen.queryByText("Acquis")).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — suivis retirés (revue mobile 2026-07-15)", () => {
  it("un suivi retiré quitte la grille et apparaît dans la section repliée", () => {
    renderPanel([
      makeItem(),
      makeItem({
        id: 7,
        title: "Le Robot sauvage",
        kind: "movie",
        active: false,
      }),
    ]);

    // Grid: only the active follow renders as a compact row.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
    // Retired section: collapsed summary with count + reactivate control.
    expect(screen.getByText("Suivis retirés (1)")).toBeInTheDocument();
    expect(screen.getByText(/Le Robot sauvage/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Réactiver" }),
    ).toBeInTheDocument();
    // The active row has a dropdown trigger; the retired item does not.
    expect(
      screen.getByRole("button", { name: "Actions pour House of the Dragon" }),
    ).toBeInTheDocument();
  });

  it("aucune section retirés quand tout est actif", () => {
    renderPanel([makeItem()]);
    expect(screen.queryByText(/Suivis retirés/)).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — « Récupérer maintenant » (phase 8 / §6)", () => {
  it("n'offre l'action que là où quelque chose est réellement récupérable", () => {
    renderPanel([
      makeItem({ id: 1, title: "Silo", status: "a_recuperer" }),
      makeItem({ id: 2, title: "Furious", status: "en_attente" }),
      makeItem({ id: 3, title: "Top Chef", status: "a_jour" }),
    ]);

    expect(
      screen.getAllByRole("button", { name: /Récupérer maintenant/ }),
    ).toHaveLength(1);
  });

  it("passe en « En file » sur un 202, sans toast de succès (NE-DOIT-PAS-1)", async () => {
    grabMock.mockResolvedValueOnce({ run_uid: "run-1" });
    renderPanel([makeItem({ id: 4, title: "Silo", status: "a_recuperer" })]);

    fireEvent.click(
      screen.getByRole("button", { name: /Récupérer maintenant/ }),
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /En file/ })).toBeDisabled();
    });
    expect(grabMock).toHaveBeenCalledWith(4);
    expect(toastMock.success).not.toHaveBeenCalled();
    expect(toastMock.error).not.toHaveBeenCalled();
  });

  it("traite le seul refus permis (409) comme « déjà en cours », pas une erreur", async () => {
    grabMock.mockRejectedValueOnce(
      new ApiError(409, "A matching acquisition run is already in flight"),
    );
    renderPanel([makeItem({ id: 5, title: "Silo", status: "a_recuperer" })]);

    fireEvent.click(
      screen.getByRole("button", { name: /Récupérer maintenant/ }),
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /En file/ })).toBeInTheDocument();
    });
    // §6 / NE-DOIT-PAS-3: the duplicate of the same action is an information.
    expect(toastMock.error).not.toHaveBeenCalled();
    expect(toastMock.info).toHaveBeenCalledWith(
      "Récupération déjà en cours pour ce titre.",
    );
  });

  it("remonte bruyamment une vraie erreur (NE-DOIT-PAS-5)", async () => {
    grabMock.mockRejectedValueOnce(new ApiError(500, "boom"));
    renderPanel([makeItem({ id: 6, title: "Silo", status: "a_recuperer" })]);

    fireEvent.click(
      screen.getByRole("button", { name: /Récupérer maintenant/ }),
    );

    await waitFor(() => {
      expect(toastMock.error).toHaveBeenCalledWith("boom");
    });
    // A failed launch leaves the action available — nothing was queued.
    expect(
      screen.getByRole("button", { name: /Récupérer maintenant/ }),
    ).toBeEnabled();
  });
});

describe("FollowedPanel — add-by-id provider selector (ticket 336)", () => {
  function openAddForm(): void {
    renderPanel([]);
    fireEvent.click(screen.getByRole("button", { name: "Ajouter par ID" }));
  }

  it("offers TVDB, TMDB and IMDB providers", () => {
    openAddForm();
    for (const p of ["TVDB", "TMDB", "IMDB"]) {
      expect(screen.getByRole("button", { name: p })).toBeInTheDocument();
    }
  });

  it("selecting IMDB switches the id field to the tt… placeholder", () => {
    openAddForm();
    fireEvent.click(screen.getByRole("button", { name: "IMDB" }));
    expect(screen.getByPlaceholderText("ex: tt0903747")).toBeInTheDocument();
    expect(screen.getByLabelText("ID IMDB")).toBeInTheDocument();
  });

  it("follows by TMDB id → sends tmdb_id", () => {
    openAddForm();
    fireEvent.click(screen.getByRole("button", { name: "TMDB" }));
    fireEvent.change(screen.getByLabelText("ID TMDB"), {
      target: { value: "1399" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    expect(followMock).toHaveBeenCalledTimes(1);
    expect(followMock.mock.calls[0]?.[0]).toEqual({ tmdb_id: 1399, kind: "show" });
  });

  it("follows by IMDB id → sends the tt string", () => {
    openAddForm();
    fireEvent.click(screen.getByRole("button", { name: "IMDB" }));
    fireEvent.change(screen.getByLabelText("ID IMDB"), {
      target: { value: "tt0903747" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    expect(followMock).toHaveBeenCalledTimes(1);
    expect(followMock.mock.calls[0]?.[0]).toEqual({
      imdb_id: "tt0903747",
      kind: "show",
    });
  });

  it("disables Suivre for a malformed IMDB id", () => {
    openAddForm();
    fireEvent.click(screen.getByRole("button", { name: "IMDB" }));
    fireEvent.change(screen.getByLabelText("ID IMDB"), {
      target: { value: "0903747" },
    });
    expect(screen.getByRole("button", { name: "Suivre" })).toBeDisabled();
  });
});

describe("FollowedPanel — tvdb_unresolved warning (ticket 336 review)", () => {
  it("shows a « Sans ID TVDB » warning badge for an unresolved show", () => {
    renderPanel([makeItem({ tvdb_unresolved: true })]);
    expect(screen.getByText("Sans ID TVDB")).toBeInTheDocument();
  });

  it("does not show the warning for a resolved show", () => {
    renderPanel([makeItem({ tvdb_unresolved: false })]);
    expect(screen.queryByText("Sans ID TVDB")).not.toBeInTheDocument();
  });

  it("toasts a warning when a followed show comes back tvdb_unresolved", () => {
    followMock.mockImplementation(
      (_body: unknown, opts?: { onSuccess?: (item: FollowedSeriesItem) => void }) => {
        opts?.onSuccess?.(makeItem({ tvdb_unresolved: true }));
      },
    );
    renderPanel([]);
    fireEvent.click(screen.getByRole("button", { name: "Ajouter par ID" }));
    fireEvent.click(screen.getByRole("button", { name: "TMDB" }));
    fireEvent.change(screen.getByLabelText("ID TMDB"), {
      target: { value: "1399" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suivre" }));
    expect(toastMock.warning).toHaveBeenCalled();
  });
});
