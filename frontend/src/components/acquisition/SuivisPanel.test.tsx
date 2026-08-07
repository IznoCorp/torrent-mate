/**
 * SuivisPanel — tests for the « Suivis » view with filter pills, three display
 * modes, and the mode switcher.
 *
 * The panel replaces the old FollowedPanel (two tab levels, two search fields).
 * Filter pills (Tout / Séries / Films / En pause) carry counts and the mode
 * switcher is pinned at the end with a hard divider (A9).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FollowedSeriesItem } from "@/api/acquisition";

import * as hooks from "@/hooks/useAcquisition";

import { SuivisPanel } from "./SuivisPanel";

// ── Fixtures ──────────────────────────────────────────────────────────────────

/** An active show with takeable episodes — urgency 0. */
function takeableShow(): FollowedSeriesItem {
  return {
    id: 1,
    title: "Silo",
    kind: "show",
    status: "a_recuperer",
    active: true,
    added_at: 1_750_000_000,
    wanted_pending: 3,
    wanted_grabbed: 0,
    year: 2023,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 400000, tmdb_id: 125910, imdb_id: null },
    a_recuperer_count: 1,
    owned_count: 23,
    aired_count: 24,
  };
}

/** An active show with nothing to do — a_jour, urgency 4. */
function upToDateShow(): FollowedSeriesItem {
  return {
    id: 2,
    title: "Shōgun",
    kind: "show",
    status: "a_jour",
    active: true,
    added_at: 1_740_000_000,
    owned_count: 10,
    aired_count: 10,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2024,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 421000, tmdb_id: 234567, imdb_id: null },
  };
}

/** An active show in acquisition — urgency 1. */
function inAcquisitionShow(): FollowedSeriesItem {
  return {
    id: 3,
    title: "Severance",
    kind: "show",
    status: "en_acquisition",
    active: true,
    added_at: 1_745_000_000,
    wanted_pending: 0,
    wanted_grabbed: 1,
    year: 2022,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 371980, tmdb_id: 95396, imdb_id: null },
    en_acquisition_count: 1,
    owned_count: 19,
    aired_count: 20,
  };
}

/** An active show waiting for a torrent — urgency 2. */
function waitingShow(): FollowedSeriesItem {
  return {
    id: 4,
    title: "From",
    kind: "show",
    status: "en_attente",
    active: true,
    added_at: 1_744_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2022,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 411000, tmdb_id: 123456, imdb_id: null },
    en_attente_count: 3,
    owned_count: 10,
    aired_count: 15,
  };
}

/** A non-verified show — urgency 3. */
function nonVerifieShow(): FollowedSeriesItem {
  return {
    id: 5,
    title: "Dark Matter",
    kind: "show",
    status: "non_verifie",
    active: true,
    added_at: 1_748_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2024,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 430000, tmdb_id: 345678, imdb_id: null },
  };
}

/** A movie follow — filter "Films". */
function movie(): FollowedSeriesItem {
  return {
    id: 6,
    title: "Dune",
    kind: "movie",
    status: "en_attente",
    active: true,
    added_at: 1_745_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2021,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: null, tmdb_id: 438631, imdb_id: "tt1160419" },
  };
}

/** A paused show — filtered by "En pause". Server truth: disabled ⟺ active=0. */
function pausedShow(): FollowedSeriesItem {
  return {
    id: 7,
    title: "The OA",
    kind: "show",
    status: "disabled",
    active: false,
    added_at: 1_720_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2016,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 305074, tmdb_id: 63355, imdb_id: null },
  };
}

/** An inactive show — active=false, should be excluded from all active counts. */
function inactiveShow(): FollowedSeriesItem {
  return {
    id: 8,
    title: "Inactive Show",
    kind: "show",
    status: "disabled",
    active: false,
    added_at: 1_710_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2020,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: null, tmdb_id: null, imdb_id: null },
  };
}

/** A show being verified — no verdict yet, badge should read "?". */
function verificationEnCoursShow(): FollowedSeriesItem {
  return {
    id: 10,
    title: "Verifying Show",
    kind: "show",
    status: "verification_en_cours",
    active: true,
    added_at: 1_750_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2025,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 500000, tmdb_id: 999999, imdb_id: null },
    owned_count: 0,
    aired_count: 0,
  };
}

/** A show with unknown catalogue (aired_count=null) but some owned episodes. */
function unknownCatalogueShow(): FollowedSeriesItem {
  return {
    id: 11,
    title: "Unknown Catalog",
    kind: "show",
    status: "en_attente",
    active: true,
    added_at: 1_750_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2024,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 500001, tmdb_id: 888888, imdb_id: null },
    owned_count: 5,
    aired_count: null,
  };
}

/** A takeable show with 22 missing episodes — the badge should read "22". */
function manyMissingShow(): FollowedSeriesItem {
  return {
    id: 9,
    title: "Batman",
    kind: "show",
    status: "a_recuperer",
    active: true,
    added_at: 1_750_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 1992,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 76168, tmdb_id: 1496, imdb_id: null },
    a_recuperer_count: 22,
    owned_count: 0,
    aired_count: 22,
  };
}

/** Full fixture — all items at once, sorted deliberately wrong to test sort. */
const FULL_ITEMS: readonly FollowedSeriesItem[] = [
  movie(),
  upToDateShow(),
  pausedShow(),
  waitingShow(),
  inAcquisitionShow(),
  inactiveShow(),
  takeableShow(),
  nonVerifieShow(),
  manyMissingShow(),
];

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Options for the followed hook mock. */
interface MockOpts {
  isLoading?: boolean;
  isError?: boolean;
  /** Set to true to return undefined data (loading with no cache). */
  noData?: boolean;
}

function mockFollowed(
  items: readonly FollowedSeriesItem[],
  opts?: MockOpts,
): void {
  vi.spyOn(hooks, "useFollowed").mockReturnValue({
    data: opts?.noData === true ? undefined : { items: [...items] },
    isLoading: opts?.isLoading ?? false,
    isError: opts?.isError ?? false,
  } as unknown as ReturnType<typeof hooks.useFollowed>);
}

function renderPanel(
  items: readonly FollowedSeriesItem[],
  opts?: MockOpts,
): void {
  mockFollowed(items, opts);
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SuivisPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Get the first element from a query result, narrowing away undefined. */
function first<T>(arr: readonly T[]): T {
  if (arr[0] == null) throw new Error("expected at least one element");
  return arr[0];
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("SuivisPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  // ── Filter pills ──────────────────────────────────────────────────────────

  it("les sous-onglets Séries/Films sont devenus des puces de filtre", async () => {
    renderPanel(FULL_ITEMS);
    // The old "tab" role is gone.
    expect(screen.queryByRole("tab", { name: "Séries" })).toBeNull();
    // Pills with counts.
    expect(
      await screen.findByRole("button", { name: /Tout\s*7/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Séries\s*6/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Films\s*1/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /En pause\s*2/ }),
    ).toBeInTheDocument();
  });

  it("n'a plus qu'UN champ, celui qui filtre (D2)", () => {
    renderPanel(FULL_ITEMS);
    expect(screen.getAllByRole("searchbox")).toHaveLength(1);
    expect(
      screen.getByPlaceholderText(/Filtrer par nom/),
    ).toBeInTheDocument();
  });

  it("le filtre « Séries » ne montre que les séries et exclut les films", () => {
    renderPanel(FULL_ITEMS);
    fireEvent.click(
      screen.getByRole("button", { name: /Séries\s*6/ }),
    );
    // Dune (film) is hidden; Silo (série) is visible.
    expect(screen.queryByText("Dune")).toBeNull();
    expect(screen.getByText("Silo")).toBeInTheDocument();
  });

  it("le filtre « Films » ne montre que les films", () => {
    renderPanel(FULL_ITEMS);
    fireEvent.click(
      screen.getByRole("button", { name: /Films\s*1/ }),
    );
    expect(screen.getByText("Dune")).toBeInTheDocument();
    expect(screen.queryByText("Silo")).toBeNull();
  });

  it("le filtre « En pause » ne montre que les suivis arrêtés", () => {
    renderPanel(FULL_ITEMS);
    fireEvent.click(
      screen.getByRole("button", { name: /En pause\s*2/ }),
    );
    // Paused rows are EXCLUDED from « Tout » but reachable here — pausing must
    // never make a follow vanish from every surface.
    expect(screen.getByText("The OA")).toBeInTheDocument();
    expect(screen.getByText("Inactive Show")).toBeInTheDocument();
    expect(screen.queryByText("Silo")).toBeNull();
  });

  it("« Tout » montre tout ce qui est actif", () => {
    renderPanel(FULL_ITEMS);
    // 8 active items should be visible (all except Inactive Show).
    fireEvent.click(screen.getByRole("button", { name: /Tout\s*7/ }));
    expect(screen.getByText("Silo")).toBeInTheDocument();
    expect(screen.getByText("Dune")).toBeInTheDocument();
    expect(screen.queryByText("Inactive Show")).toBeNull();
  });

  it("le filtre textuel réduit les résultats sans changer les compteurs de puce", () => {
    renderPanel(FULL_ITEMS);
    // The pill counts ANSWER "how many do I follow", not "how many match my search".
    fireEvent.change(screen.getByPlaceholderText(/Filtrer par nom/), {
      target: { value: "Shō" },
    });
    // Only Shōgun matches.
    expect(screen.getByText("Shōgun")).toBeInTheDocument();
    expect(screen.queryByText("Silo")).toBeNull();
    // But the pill counts haven't changed — they are the unfiltered truth.
    expect(
      screen.getByRole("button", { name: /Tout\s*7/ }),
    ).toBeInTheDocument();
  });

  // ── Sort order ────────────────────────────────────────────────────────────

  it("trie par urgence puis par titre (localeCompare fr)", async () => {
    renderPanel(FULL_ITEMS);
    // Urgency: a_recuperer(0) → en_acquisition(1) → verification_en_cours(2)
    // → en_attente(3) → non_verifie(4) → a_jour(5) — paused rows live behind
    // their own pill, not in this list.
    const cards = await screen.findAllByTestId("acq-card");
    const titles = cards.map((c) =>
      within(c).getByTestId("acq-card-title").textContent,
    );
    // Batman and Silo are both a_recuperer — "Batman" < "Silo" in localeCompare fr.
    expect(titles[0]).toBe("Batman");
    expect(titles[1]).toBe("Silo");
    // Severance is en_acquisition.
    expect(titles[2]).toBe("Severance");
    // From and Dune are en_attente — "Dune" < "From" in localeCompare.
    expect(titles[3]).toBe("Dune");
    expect(titles[4]).toBe("From");
    // Dark Matter is non_verifie.
    expect(titles[5]).toBe("Dark Matter");
    // Shōgun is a_jour.
    expect(titles[6]).toBe("Shōgun");
    expect(titles).toHaveLength(7);
  });

  // ── Display modes ─────────────────────────────────────────────────────────

  it("mode groupé : l'état monte dans l'en-tête et quitte les lignes (§12)", () => {
    renderPanel(FULL_ITEMS);
    const groupBtn = screen.getByRole("button", { name: /Groupé par état/ });
    act(() => {
      fireEvent.click(groupBtn);
    });

    // Section headers carry the status label.
    const section = screen.getByTestId("group-a_recuperer");
    expect(
      within(section).getByTestId("section-head"),
    ).toHaveTextContent("À récupérer");

    // Within a card, the status badge is absent.
    const card = first(within(section).getAllByTestId("acq-card"));
    expect(
      within(card).queryByText("À récupérer", { selector: "[data-slot=badge]" }),
    ).toBeNull();
  });

  // The panel used to carry its own GROUP_HEADER_LABEL map, duplicating the
  // labels meta.ts already owns. Deleting it left only ONE header label under
  // test (« À récupérer », above), and the tests that covered the others live
  // in FollowedPanel.test.tsx, which is deleted alongside the old FollowedPanel.
  // Expected strings are
  // LITERAL here on purpose: reading them from FOLLOW_STATUS_LABEL would make
  // the assertion tautological — the map and the expectation would move
  // together and a re-introduced local duplicate would sail through.
  it("mode groupé : CHAQUE en-tête porte le libellé partagé, aucun libellé local", () => {
    const EXPECTED: Readonly<Record<string, string>> = {
      a_recuperer: "À récupérer",
      en_acquisition: "En cours d'acquisition",
      en_attente: "En attente de torrent",
      non_verifie: "Non vérifié",
      a_jour: "À jour",
      disabled: "En pause",
    };

    renderPanel(FULL_ITEMS);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /Groupé par état/ }));
    });

    let checked = 0;
    for (const [status, label] of Object.entries(EXPECTED)) {
      const section = screen.queryByTestId(`group-${status}`);
      if (section === null) continue; // that status has no item in view
      expect(within(section).getByTestId("section-head")).toHaveTextContent(
        label,
      );
      checked += 1;
    }
    // Guard against the assertion loop silently covering nothing.
    expect(checked).toBeGreaterThanOrEqual(4);
  });

  it("mode grille : la pastille porte un NOMBRE, et rien à faire ⇒ pas de pastille", () => {
    renderPanel(FULL_ITEMS);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    // Silo: 1 episode takeable → badge "1".
    const siloTile = screen.getByTestId("tile-1");
    const siloBadge = siloTile.querySelector("[data-badge]");
    expect(siloBadge).toBeTruthy();
    expect(siloBadge?.textContent).toBe("1");

    // Shōgun: a_jour → NO badge.
    const shogunTile = screen.getByTestId("tile-2");
    expect(shogunTile.querySelector("[data-badge]")).toBeNull();

    // Dark Matter: non_verifie → badge "?".
    const darkMatterTile = screen.getByTestId("tile-5");
    const dmBadge = darkMatterTile.querySelector("[data-badge]");
    expect(dmBadge).toBeTruthy();
    expect(dmBadge?.textContent).toBe("?");
  });

  // A grid tile is a poster plus an optional badge — it carries NO status chip,
  // unlike a list row. So for a film the badge is the only signal there is, and
  // §5.2 fixes what its absence MEANS: « a follow with nothing to do carries no
  // badge at all ». Returning null for every film would therefore state, about
  // a film that needs attention, that it needs none. A film's gap cannot be
  // counted (no episode catalogue), so it is marked, not numbered.
  it("mode grille : un film qui demande attention est marqué, jamais compté", () => {
    renderPanel([movie()]); // Dune (id=6), status en_attente — actionable
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    const badge = screen.getByTestId("tile-6").querySelector("[data-badge]");
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toBe("!");
  });

  it("mode grille : un film sans rien à faire ne porte pas de pastille", () => {
    renderPanel([{ ...movie(), status: "a_jour" }]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    expect(
      screen.getByTestId("tile-6").querySelector("[data-badge]"),
    ).toBeNull();
  });

  it("mode grille : un film sans verdict porte « ? », pas « ! »", () => {
    renderPanel([{ ...movie(), status: "non_verifie" }]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    const badge = screen.getByTestId("tile-6").querySelector("[data-badge]");
    expect(badge?.textContent).toBe("?");
  });

  it("mode grille : aired_count absent ⇒ « ? », pas un nombre fabriqué", () => {
    renderPanel([unknownCatalogueShow()]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    // Unknown Catalog (id=11): aired_count=null, owned_count=5 →
    // "?" not "1" — honest ignorance (followFraction precedent).
    const tile = screen.getByTestId("tile-11");
    const badge = tile.querySelector("[data-badge]");
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toBe("?");
  });

  it("mode grille : verification_en_cours ⇒ « ? », pas de verdict", () => {
    renderPanel([verificationEnCoursShow()]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    // Verifying Show (id=10): verification_en_cours, aired_count=0, owned_count=0 →
    // would fabricate "1" from Math.max(1, 0-0) without the guard.
    const tile = screen.getByTestId("tile-10");
    const badge = tile.querySelector("[data-badge]");
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toBe("?");
  });

  // ── Switcher ──────────────────────────────────────────────────────────────
  // A9 mitigation: hard border-l divider + solid background, NEVER a gradient.

  it("le commutateur est séparé des puces par un séparateur, pas par un dégradé (A9)", () => {
    renderPanel(FULL_ITEMS);
    const group = screen.getByRole("group", { name: "Mode d'affichage" });
    expect(group.parentElement?.className).toMatch(/border-l/);
    expect(group.parentElement?.className).not.toMatch(/gradient/);
  });

  // ── Loading / error states ────────────────────────────────────────────────

  it("affiche « Chargement… » quand les données ne sont pas encore arrivées", () => {
    renderPanel([], { isLoading: true, noData: true });
    expect(screen.getByText(/Chargement/)).toBeInTheDocument();
  });

  it("ne montre pas « Aucun suivi » pendant le chargement", () => {
    renderPanel([], { isLoading: true, noData: true });
    expect(screen.queryByText(/Aucun suivi/)).toBeNull();
  });

  it("affiche une erreur visible en français quand la requête échoue", () => {
    renderPanel([], { isError: true });
    expect(
      screen.getByText(/Impossible de charger les suivis/),
    ).toBeInTheDocument();
  });

  it("affiche « Aucun suivi » seulement quand le chargement est terminé sans erreur", () => {
    renderPanel([]);
    expect(screen.getByText(/Aucun suivi/)).toBeInTheDocument();
  });

  // ── Detail sheet ──────────────────────────────────────────────────────────

  it("ouvre la fiche détail au tap sur une carte", () => {
    renderPanel([takeableShow()]);
    // Click the inner body button (aria-label="Silo") — the outer div is not interactive.
    const bodyBtn = screen.getByRole("button", { name: "Silo" });
    fireEvent.click(bodyBtn);
    // The detail sheet should be visible (FollowDetailSheet renders its content).
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("la fiche détail transmet le vrai statut et la vraie nature", async () => {
    const completeness = (kind: string) => ({
      data: {
        followed_id: 6,
        title: "X",
        kind,
        provider_catalog_empty: false,
        source: "cache",
        catalog_refreshed_at: 1_750_000_000,
        seasons: [],
      },
      isLoading: false,
      isError: false,
    });
    // kind: only a MOVIE sheet in a non-acquired status renders the §5
    // lifecycle sentence — a hardcoded "show" kind could never produce it.
    vi.spyOn(hooks, "useCompleteness").mockReturnValue(
      completeness("movie") as unknown as ReturnType<typeof hooks.useCompleteness>,
    );
    renderPanel([movie()]);
    fireEvent.click(screen.getByTestId("acq-card-title"));
    expect(
      await screen.findByText(/quittera automatiquement votre liste/),
    ).toBeInTheDocument();
    cleanup();

    // status: only a_recuperer produces the primary action.
    vi.spyOn(hooks, "useCompleteness").mockReturnValue(
      completeness("show") as unknown as ReturnType<typeof hooks.useCompleteness>,
    );
    renderPanel([takeableShow()]);
    fireEvent.click(screen.getByTestId("acq-card-title"));
    expect(
      await screen.findByText("Récupérer maintenant"),
    ).toBeInTheDocument();
  });

  // ── Default mode ──────────────────────────────────────────────────────────

  it("démarre en mode liste (A8)", () => {
    renderPanel(FULL_ITEMS);
    // Cards are present in list layout — the default mode.
    expect(screen.getAllByTestId("acq-card").length).toBeGreaterThan(0);
    // The "Liste" button should be active (aria-pressed=true).
    const listeBtn = screen.getByRole("button", { name: /Liste/ });
    expect(listeBtn).toBeInTheDocument();
    expect(listeBtn.getAttribute("aria-pressed")).toBe("true");
    // In liste mode, we should see status badges on cards (not the groupé header).
    const sections = screen.queryAllByTestId("section-head");
    expect(sections).toHaveLength(0); // No section headers in list mode.
  });
  // ── A10/A11/A12 — the gesture and kebab are MOUNTED ─────────────────────
  //
  // SwipeActions and the « ··· » menu once shipped fully built, fully tested,
  // and mounted NOWHERE — every arbitration they carry was unreachable. These
  // pin the mount itself: the component tests cannot see an absent call site.

  it("A10 — chaque carte liste vit dans un conteneur de balayage avec ses actions", () => {
    renderPanel([takeableShow()]);
    const container = screen.getByTestId("swipe-container");
    expect(container).toHaveAttribute("data-swipe");
    const labels = within(container)
      .getAllByTestId("swipe-action")
      .map((b) => b.textContent);
    // §9's 84 px pair for a série: suspend then remove.
    expect(labels).toEqual(["Pause", "Retirer"]);
  });

  it("A10 — le balayage d'une série en pause offre « Activer », pas une seconde pause", () => {
    renderPanel([pausedShow()]);
    fireEvent.click(screen.getByRole("button", { name: /En pause\s*1/ }));
    const container = screen.getByTestId("swipe-container");
    const labels = within(container)
      .getAllByTestId("swipe-action")
      .map((b) => b.textContent);
    expect(labels).toEqual(["Activer", "Retirer"]);
  });

  it("A10/§9 — « Retirer » par balayage passe par la confirmation avant d'agir", () => {
    const mutate = vi.fn();
    vi.spyOn(hooks, "useUnfollow").mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof hooks.useUnfollow>);

    renderPanel([takeableShow()]);
    const container = screen.getByTestId("swipe-container");
    const [, removeBtn] = within(container).getAllByTestId("swipe-action");
    if (removeBtn == null) throw new Error("unreachable");
    fireEvent.click(removeBtn);

    expect(mutate).not.toHaveBeenCalled();
    expect(screen.getByText("Retirer ce suivi ?")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("confirmer-le-retrait"));
    expect(mutate).toHaveBeenCalledWith(1);
  });

  it("A10 — « Pause » par balayage suspend réellement", () => {
    const mutate = vi.fn();
    vi.spyOn(hooks, "useUpdateFollow").mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof hooks.useUpdateFollow>);

    renderPanel([takeableShow()]);
    const container = screen.getByTestId("swipe-container");
    const [suspendBtn] = within(container).getAllByTestId("swipe-action");
    if (suspendBtn == null) throw new Error("unreachable");
    fireEvent.click(suspendBtn);

    expect(mutate).toHaveBeenCalledWith({ id: 1, body: { active: false } });
  });

  it("A11/A12 — au pointeur fin, le « ··· » existe et offre « Voir la fiche »", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
    renderPanel([takeableShow()]);

    const trigger = screen.getByRole("button", { name: "Actions pour Silo" });
    fireEvent.pointerDown(trigger);
    fireEvent.click(trigger);

    expect(screen.getByText("Voir la fiche")).toBeInTheDocument();
    expect(screen.getByText("Retirer le suivi")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
  it("mode grille : taper une tuile ouvre la fiche détail du suivi", () => {
    renderPanel([takeableShow()]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    fireEvent.click(screen.getByTestId("tile-1"));

    // The detail sheet mounts — the tile is the ONLY path to it in grid mode,
    // so an unwired handler would leave every tile a dead control (§11).
    expect(document.querySelector("[data-testid=sheet-meta], [role=dialog]")).not.toBeNull();
  });
});
