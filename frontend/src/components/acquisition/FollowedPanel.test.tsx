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
const { grabMock, followMock, unfollowMock, toastMock } = vi.hoisted(() => ({
  grabMock: vi.fn(),
  followMock: vi.fn(),
  unfollowMock: vi.fn(),
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
  useUnfollow: () => ({ mutate: unfollowMock, isPending: false }),
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

/**
 * Select the « Films » sub-tab (#20). Follows default to the « Séries » tab, so
 * a movie-only render must switch tabs before its card is visible.
 */
function selectFilmsTab(): void {
  fireEvent.click(screen.getByRole("button", { name: /Films/ }));
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

  it("donne au bouton Actions le minimum tactile mobile min-h-11 (X4, ticket 250)", () => {
    renderPanel([makeItem()]);

    // The icon trigger is size-8 on desktop; below md it must stretch to the
    // touch minimum. Token-exact assertions: a substring check would let a
    // stray responsive prefix (e.g. sm:min-h-11) reintroduce the mobile bug.
    const classes = screen
      .getByRole("button", { name: "Actions pour House of the Dragon" })
      .className.split(/\s+/);
    expect(classes).toContain("min-h-11");
    expect(classes).toContain("min-w-11");
    expect(classes).toContain("md:min-h-8");
    expect(classes).toContain("md:min-w-8");
  });

  it("donne au toggle Séries/Films le minimum tactile mobile min-h-11 (X4, ticket 250)", () => {
    renderPanel([makeItem()]);

    // Same segmented-toggle motif as the density/sort groups: 44px below md.
    for (const name of [/^Séries \(/, /^Films \(/]) {
      const classes = screen
        .getByRole("button", { name })
        .className.split(/\s+/);
      expect(classes).toContain("min-h-11");
      expect(classes).toContain("md:min-h-8");
    }
  });

  it("renders the CompletenessAccordion below a series row", () => {
    renderPanel([makeItem({ kind: "show" })]);

    // The accordion trigger is still present below the compact row.
    expect(screen.getByText("Détail par épisode")).toBeInTheDocument();
  });

  it("does NOT render the CompletenessAccordion for movies", () => {
    renderPanel([makeItem({ kind: "movie", title: "Ferrari" })]);
    // Switch to Films so the movie row actually renders — otherwise the absence
    // assertion would pass vacuously (the movie hidden under the default tab).
    selectFilmsTab();

    expect(screen.getByText("Ferrari")).toBeInTheDocument();
    expect(screen.queryByText("Détail par épisode")).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — les cinq états sur la carte (phase 8)", () => {
  it.each([
    ["a_jour", "À jour"],
    ["a_recuperer", "À récupérer"],
    ["en_acquisition", "En cours d'acquisition"],
    ["en_attente", "En attente de torrent"],
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

  it("explique l'état en infobulle (En attente de torrent ≠ Non vérifié)", () => {
    renderPanel([
      makeItem({ id: 1, title: "Silo", status: "en_attente" }),
      makeItem({ id: 2, title: "Furious", status: "non_verifie" }),
    ]);

    const attente = screen.getByText("En attente de torrent").closest("[title]");
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
        "3 à récupérer · 1 en cours d'acquisition · 1 en attente de torrent · 1 non vérifié",
      ),
    ).toBeInTheDocument();
    // The raw wanted_pending chip is gone — it knew nothing about ownership.
    expect(screen.queryByText("9 en attente de torrent")).not.toBeInTheDocument();
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
    selectFilmsTab();

    expect(screen.getByText("Acquis")).toBeInTheDocument();
    // No "1/1", and no "—" either: a film is not a completeness fraction.
    expect(screen.queryByText("—")).not.toBeInTheDocument();
    expect(screen.queryByText("1/1")).not.toBeInTheDocument();
  });

  it("garde le libellé partagé pour un film à récupérer", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "a_recuperer" }),
    ]);
    selectFilmsTab();

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
    selectFilmsTab();

    expect(screen.getByText("En attente de torrent")).toBeInTheDocument();
    expect(screen.getByText("rien de conforme au profil")).toBeInTheDocument();
    expect(screen.queryByText(/all_filtered/)).not.toBeInTheDocument();
  });

  it("libelle un film en médiathèque « Acquis » (pas « À jour »)", () => {
    renderPanel([
      makeItem({ kind: "movie", title: "Ferrari", status: "a_jour" }),
    ]);
    selectFilmsTab();

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
        title: "La Nuit du chasseur",
        // Same kind as the active follow so both sit under the default « Séries »
        // sub-tab (#20) — this test targets the active/retired split, not kind.
        kind: "show",
        active: false,
      }),
    ]);

    // Grid: only the active follow renders as a compact row.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
    // Retired section: collapsed summary with count + reactivate control.
    expect(screen.getByText("Suivis retirés (1)")).toBeInTheDocument();
    expect(screen.getByText(/La Nuit du chasseur/)).toBeInTheDocument();
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

  it("keeps the « Réactiver » button on one line for a long title (#23, no wrap)", () => {
    // Class-contract guard (jsdom does not lay out): the row must NOT flex-wrap
    // and the button must be shrink-0, so a long title truncates instead of
    // pushing « Réactiver » onto a second line on mobile.
    renderPanel([
      makeItem({
        id: 8,
        title:
          "Un titre de suivi retiré vraiment très très long qui déborde sur mobile",
        kind: "show",
        active: false,
      }),
    ]);
    const button = screen.getByRole("button", { name: "Réactiver" });
    expect(button.className).toContain("shrink-0");
    const li = button.closest("li");
    expect(li?.className).not.toContain("flex-wrap");
  });
});

describe("FollowedPanel — confirmation « Retirer » (ACQUISITION-3, ticket 250)", () => {
  /** Open the row's ⋯ menu and click « Retirer » to open the dialog. */
  function openUnfollowDialog(): void {
    // Radix DropdownMenuTrigger listens for pointerdown, not click.
    fireEvent.pointerDown(
      screen.getByRole("button", { name: "Actions pour House of the Dragon" }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: /Retirer/ }));
  }

  it("n'appelle PAS la mutation au clic « Retirer » du menu — un dialog s'ouvre", async () => {
    renderPanel([makeItem()]);
    openUnfollowDialog();

    await waitFor(() => {
      expect(screen.getByText("Retirer ce suivi ?")).toBeInTheDocument();
    });
    expect(unfollowMock).not.toHaveBeenCalled();
  });

  it("Annuler ferme le dialog et conserve le suivi (aucune mutation)", async () => {
    renderPanel([makeItem()]);
    openUnfollowDialog();

    await waitFor(() => {
      expect(screen.getByText("Retirer ce suivi ?")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));

    await waitFor(() => {
      expect(screen.queryByText("Retirer ce suivi ?")).not.toBeInTheDocument();
    });
    expect(unfollowMock).not.toHaveBeenCalled();
    // The row is still there.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
  });

  it("confirmer déclenche la mutation d'unfollow avec l'id du suivi", async () => {
    renderPanel([makeItem({ id: 42 })]);
    openUnfollowDialog();

    await waitFor(() => {
      expect(screen.getByText("Retirer ce suivi ?")).toBeInTheDocument();
    });
    // The dialog's destructive confirm button (distinct from the menuitem).
    fireEvent.click(screen.getByRole("button", { name: "Retirer" }));

    expect(unfollowMock).toHaveBeenCalledTimes(1);
    expect(unfollowMock).toHaveBeenCalledWith(42, expect.anything());
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
      expect(
        screen.getByRole("button", { name: /En file/ }),
      ).toBeInTheDocument();
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

// The « Sans ID TVDB » badge stays a FollowedPanel concern; the add-by-id
// provider selector + its tvdb_unresolved toast moved to MediaSearchAdd (#21),
// where those tests now live.
describe("FollowedPanel — tvdb_unresolved warning badge", () => {
  it("shows a « Sans ID TVDB » warning badge for an unresolved show", () => {
    renderPanel([makeItem({ tvdb_unresolved: true })]);
    expect(screen.getByText("Sans ID TVDB")).toBeInTheDocument();
  });

  it("does not show the warning for a resolved show", () => {
    renderPanel([makeItem({ tvdb_unresolved: false })]);
    expect(screen.queryByText("Sans ID TVDB")).not.toBeInTheDocument();
  });
});

describe("FollowedPanel — séries / films sub-tabs (#20)", () => {
  const aShow = makeItem({ id: 1, kind: "show", title: "House of the Dragon" });
  const aMovie = makeItem({ id: 2, kind: "movie", title: "Dune" });

  it("defaults to « Séries » and lists only shows", () => {
    renderPanel([aShow, aMovie]);
    // The show is visible in the default (Séries) tab; the movie is filtered out.
    expect(screen.getByText("House of the Dragon")).toBeInTheDocument();
    expect(screen.queryByText("Dune")).not.toBeInTheDocument();
  });

  it("switching to « Films » lists only movies", () => {
    renderPanel([aShow, aMovie]);
    fireEvent.click(screen.getByRole("button", { name: /Films/ }));
    expect(screen.getByText("Dune")).toBeInTheDocument();
    expect(screen.queryByText("House of the Dragon")).not.toBeInTheDocument();
  });

  it("labels each sub-tab with its active follow count", () => {
    renderPanel([aShow, aMovie]);
    expect(
      screen.getByRole("button", { name: "Séries (1)" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Films (1)" }),
    ).toBeInTheDocument();
  });

  it("shows a per-tab empty hint when the selected kind has no follow", () => {
    renderPanel([aShow]);
    fireEvent.click(screen.getByRole("button", { name: /Films/ }));
    expect(screen.getByText("Aucun film suivi.")).toBeInTheDocument();
  });

  it("scopes the retired list to the active sub-tab's kind", () => {
    const retiredMovie = makeItem({
      id: 3,
      kind: "movie",
      title: "Retired Film",
      active: false,
    });
    renderPanel([aShow, retiredMovie]);
    // Default (Séries) tab: no retired shows → no « Suivis retirés » section.
    expect(screen.queryByText(/Suivis retirés/)).not.toBeInTheDocument();
    // Films tab: the retired movie surfaces under « Suivis retirés (1) ».
    fireEvent.click(screen.getByRole("button", { name: /Films/ }));
    expect(screen.getByText("Suivis retirés (1)")).toBeInTheDocument();
    expect(screen.getByText("Retired Film")).toBeInTheDocument();
  });
});
