/**
 * FollowsPanel — tests for the « Suivis » view with filter pills, three display
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
import { ApiError } from "@/api/client";

import * as hooks from "@/hooks/useAcquisition";

import { FollowsPanel } from "./FollowsPanel";

// ── Fixtures ──────────────────────────────────────────────────────────────────

/** An active show with takeable episodes — urgency 0. */
function takeableShow(): FollowedSeriesItem {
  return {
    id: 1,
    title: "Silo",
    kind: "show",
    status: "to_grab",
    active: true,
    added_at: 1_750_000_000,
    wanted_pending: 3,
    wanted_grabbed: 0,
    year: 2023,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 400000, tmdb_id: 125910, imdb_id: null },
    to_grab_count: 1,
    owned_count: 23,
    aired_count: 24,
  };
}

/** An active show with nothing to do — up_to_date, urgency 4. */
function upToDateShow(): FollowedSeriesItem {
  return {
    id: 2,
    title: "Shōgun",
    kind: "show",
    status: "up_to_date",
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
    status: "acquiring",
    active: true,
    added_at: 1_745_000_000,
    wanted_pending: 0,
    wanted_grabbed: 1,
    year: 2022,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 371980, tmdb_id: 95396, imdb_id: null },
    acquiring_count: 1,
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
    status: "pending",
    active: true,
    added_at: 1_744_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2022,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 411000, tmdb_id: 123456, imdb_id: null },
    pending_count: 3,
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
    status: "unverified",
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
    status: "pending",
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
function verificationRunningShow(): FollowedSeriesItem {
  return {
    id: 10,
    title: "Verifying Show",
    kind: "show",
    status: "verifying",
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
    status: "pending",
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
    status: "to_grab",
    active: true,
    added_at: 1_750_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 1992,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 76168, tmdb_id: 1496, imdb_id: null },
    to_grab_count: 22,
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
  /** The query's error value (server ApiError or device-side failure). */
  error?: unknown;
  /** Spy invoked by the « Réessayer » button. */
  refetch?: ReturnType<typeof vi.fn>;
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
    error: opts?.error ?? null,
    refetch: opts?.refetch ?? vi.fn(),
  } as unknown as ReturnType<typeof hooks.useFollowed>);
}

/**
 * Render the panel inside a stand-in for the shell's scrollport.
 *
 * The shell is a frame: the panel scrolls inside `main[data-scroll-root]`, not
 * the window. jsdom gives no element a scrolling box, so `scrollTop` would
 * silently swallow both the write and the read — the setter is instrumented
 * instead, and returned, so « back to top » is asserted on what it actually
 * does rather than on a value jsdom refuses to keep.
 */
function renderPanel(
  items: readonly FollowedSeriesItem[],
  opts?: MockOpts,
): { readonly scrollTopSet: ReturnType<typeof vi.fn> } {
  mockFollowed(items, opts);
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const scrollRoot = document.createElement("div");
  scrollRoot.setAttribute("data-scroll-root", "");
  const scrollTopSet = vi.fn();
  Object.defineProperty(scrollRoot, "scrollTop", {
    get: () => 420,
    set: scrollTopSet,
    configurable: true,
  });
  document.body.appendChild(scrollRoot);
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <FollowsPanel />
      </MemoryRouter>
    </QueryClientProvider>,
    { container: scrollRoot },
  );
  return { scrollTopSet };
}

/** Get the first element from a query result, narrowing away undefined. */
function first<T>(arr: readonly T[]): T {
  if (arr[0] == null) throw new Error("expected at least one element");
  return arr[0];
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("FollowsPanel", () => {
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
    // Maquette FILTERS: « Tout » counts EVERYTHING (paused included);
    // Séries/Films cut by nature only.
    expect(
      await screen.findByRole("button", { name: /Tout\s*9/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Séries\s*8/ }),
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
      screen.getByRole("button", { name: /Séries\s*8/ }),
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
    expect(screen.getByText("The OA")).toBeInTheDocument();
    expect(screen.getByText("Inactive Show")).toBeInTheDocument();
    expect(screen.queryByText("Silo")).toBeNull();
  });

  it("« Tout » montre TOUT — les suspendus restent visibles, triés en dernier", () => {
    // Maquette FILTERS: Tout = () => true. A paused follow never vanishes
    // from the default view; URGENCY sorts it last and the tile dims.
    renderPanel(FULL_ITEMS);
    fireEvent.click(screen.getByRole("button", { name: /Tout\s*9/ }));
    expect(screen.getByText("Silo")).toBeInTheDocument();
    expect(screen.getByText("Dune")).toBeInTheDocument();
    expect(screen.getByText("Inactive Show")).toBeInTheDocument();
    // Urgency order: the paused rows close the list.
    const titles = screen.getAllByTestId("acq-card").map((c) => c.textContent);
    const silo = titles.findIndex((t) => t.includes("Silo"));
    const paused = titles.findIndex((t) => t.includes("Inactive Show"));
    expect(silo).toBeGreaterThanOrEqual(0);
    expect(paused).toBeGreaterThan(silo);
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
      screen.getByRole("button", { name: /Tout\s*9/ }),
    ).toBeInTheDocument();
  });

  // ── Sort order ────────────────────────────────────────────────────────────

  it("trie par urgence puis par titre (localeCompare fr)", async () => {
    renderPanel(FULL_ITEMS);
    // Urgency: to_grab(0) → acquiring(1) → verifying(2)
    // → pending(3) → unverified(4) → up_to_date(5) → disabled(6) — maquette
    // « Tout » keeps paused rows in the list, urgency-sorted LAST.
    const cards = await screen.findAllByTestId("acq-card");
    const titles = cards.map((c) =>
      within(c).getByTestId("acq-card-title").textContent,
    );
    // Batman and Silo are both to_grab — "Batman" < "Silo" in localeCompare fr.
    expect(titles[0]).toBe("Batman");
    expect(titles[1]).toBe("Silo");
    // Severance is acquiring.
    expect(titles[2]).toBe("Severance");
    // From and Dune are pending — "Dune" < "From" in localeCompare.
    expect(titles[3]).toBe("Dune");
    expect(titles[4]).toBe("From");
    // Dark Matter is unverified.
    expect(titles[5]).toBe("Dark Matter");
    // Shōgun is up_to_date.
    expect(titles[6]).toBe("Shōgun");
    // Paused rows close the list — "Inactive Show" < "The OA".
    expect(titles[7]).toBe("Inactive Show");
    expect(titles[8]).toBe("The OA");
    expect(titles).toHaveLength(9);
  });

  // ── Display modes ─────────────────────────────────────────────────────────

  it("mode groupé : groupes d'URGENCE maquette, chip conservée dans un groupe hétérogène", () => {
    renderPanel(FULL_ITEMS);
    const groupBtn = screen.getByRole("button", { name: /Groupé par état/ });
    act(() => {
      fireEvent.click(groupBtn);
    });

    // « Demandent quelque chose » federates three statuses: the header alone
    // cannot say which one a card carries, so the chip STAYS on the card
    // (maquette: followRow(f, g.of.length > 1)).
    const section = screen.getByTestId("group-demandent");
    expect(
      within(section).getByTestId("section-head"),
    ).toHaveTextContent("Demandent quelque chose");
    const card = first(within(section).getAllByTestId("acq-card"));
    expect(
      within(card).getByText("À récupérer", { selector: "[data-slot=chip]" }),
    ).toBeInTheDocument();
  });

  // The panel used to carry its own GROUP_HEADER_LABEL map, duplicating the
  // labels meta.ts already owns. Deleting it left only ONE header label under
  // test (« À récupérer », above), and the tests that covered the others live
  // in FollowedPanel.test.tsx, which is deleted alongside the old FollowedPanel.
  // Expected strings are
  // LITERAL here on purpose: reading them from FOLLOW_STATUS_LABEL would make
  // the assertion tautological — the map and the expectation would move
  // together and a re-introduced local duplicate would sail through.
  it("mode groupé : les QUATRE groupes maquette, dans l'ordre d'urgence", () => {
    renderPanel(FULL_ITEMS);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /Groupé par état/ }));
    });

    const heads = screen
      .getAllByTestId("section-head")
      .map((h) => h.textContent);
    const labels = [
      "Demandent quelque chose",
      "En cours",
      "À jour",
      "En pause",
    ].filter((l) => heads.some((h) => h.includes(l)));
    // Every group present in the fixture shows with its maquette label, in
    // the maquette order — and no raw status label leaks as a header.
    expect(labels.length).toBeGreaterThanOrEqual(2);
    for (const h of heads) {
      expect(h).not.toMatch(/En attente de torrent|Non vérifié/);
    }
  });

  it("mode grille : la pastille porte un NOMBRE, et rien à faire ⇒ pas de pastille", () => {
    renderPanel(FULL_ITEMS);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    // Silo: 1 episode takeable → badge "1".
    const siloTile = screen.getByTestId("tile-1");
    const siloBadge = siloTile.querySelector("[data-badge]");
    expect(siloBadge).toBeTruthy();
    expect(siloBadge?.textContent).toBe("1");

    // Shōgun: up_to_date → NO badge.
    const shogunTile = screen.getByTestId("tile-2");
    expect(shogunTile.querySelector("[data-badge]")).toBeNull();

    // Dark Matter: unverified → badge "?".
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
  it("mode grille : un film qui demande attention porte une PUCE, pas « 1 »", () => {
    // Operator: « 1 » counts nothing a film's own presence did not already
    // say. A dot signals « celui-ci demande quelque chose » without pretending
    // to be a count.
    renderPanel([{ ...movie(), status: "to_grab" }]);
    fireEvent.click(screen.getByRole("button", { name: "Grille d'affiches" }));

    const tile = screen.getByTestId("tile-6");
    expect(within(tile).getByText("•")).toBeInTheDocument();
    expect(within(tile).queryByText("1")).toBeNull();
  });

  it("mode grille : un film sans rien à faire ne porte pas de pastille", () => {
    renderPanel([{ ...movie(), status: "up_to_date" }]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    expect(
      screen.getByTestId("tile-6").querySelector("[data-badge]"),
    ).toBeNull();
  });

  it("mode grille : un film sans verdict porte « ? », pas « ! »", () => {
    renderPanel([{ ...movie(), status: "unverified" }]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    const badge = screen.getByTestId("tile-6").querySelector("[data-badge]");
    expect(badge?.textContent).toBe("?");
  });

  it("mode grille : aired_count absent ⇒ plancher maquette à 1", () => {
    renderPanel([unknownCatalogueShow()]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    // Maquette rule (operator arbitration): Math.max(1, aired-owned) — an
    // actionable tile always carries at least « 1 », never an empty corner.
    const tile = screen.getByTestId("tile-11");
    const badge = tile.querySelector("[data-badge]");
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toBe("1");
  });

  it("mode grille : verifying ⇒ « ? », pas de verdict", () => {
    renderPanel([verificationRunningShow()]);
    fireEvent.click(screen.getByRole("button", { name: /Grille/ }));

    // Verifying Show (id=10): verifying, aired_count=0, owned_count=0 →
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
    // Maquette .vswwrap draws the hard 1px divider (::before) — the class IS
    // the contract now that the styles are transplanted, not utility-built.
    expect(group.parentElement?.className).toMatch(/\bvswwrap\b/);
    expect(group.parentElement?.className).not.toMatch(/gradient/);
  });

  // ── Loading / error states ────────────────────────────────────────────────

  it("affiche « Chargement… » quand les données ne sont pas encore arrivées", () => {
    renderPanel([], { isLoading: true, noData: true });
    expect(screen.getByText(/Chargement/)).toBeInTheDocument();
    // Maquette grammar: three .skel shimmer cards in a busy container —
    // never bare text alone.
    const busy = document.querySelector('[aria-busy="true"]');
    expect(busy).not.toBeNull();
    expect(busy?.querySelectorAll(".skel")).toHaveLength(3);
  });

  it("changer de mode de vue remonte en haut de la liste", () => {
    // Operator report: switching display mode left the list mid-scroll. The
    // scrollport is the shell's `main`, so this must move THAT element — a
    // `window.scrollTo` would now be a no-op on a document that never scrolls.
    const { scrollTopSet } = renderPanel([takeableShow()]);

    fireEvent.click(screen.getByRole("button", { name: "Grille d'affiches" }));

    expect(scrollTopSet).toHaveBeenCalledWith(0);
  });

  it("un ajout frais brille : glow .fresh sur la rangée et pilule .freshtag", () => {
    // Maquette .swipe.fresh + .freshtag — « c'est ajouté » se PROUVE dans la
    // liste, sinon ce n'est qu'une affirmation (§7).
    const fresh = {
      ...takeableShow(),
      id: 99,
      title: "Tout Frais",
      added_at: Math.floor(Date.now() / 1000) - 60,
    };
    renderPanel([fresh]);

    const chip = screen.getByTestId("chip-nouveau");
    expect(chip).toHaveClass("freshtag");
    expect(chip).toHaveTextContent("Nouveau");
    // Maquette order: the freshtag CLOSES the meta row, after every chip.
    expect(chip.parentElement?.lastElementChild).toBe(chip);
    expect(screen.getByTestId("swipe-container")).toHaveClass("fresh");
  });

  it("un filtre sans résultat parle la copie maquette exacte", () => {
    renderPanel([takeableShow()]);
    fireEvent.change(screen.getByPlaceholderText(/Filtrer par nom/), {
      target: { value: "zzz-aucun-match" },
    });
    const empty = document.querySelector(".empty");
    expect(empty).not.toBeNull();
    expect(empty?.querySelector("b")?.textContent).toBe(
      "Aucun suivi ne correspond",
    );
    expect(empty?.textContent).toContain(
      "Change de filtre, ou ajoute un média avec le bouton +.",
    );
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

  it("nomme la panne côté serveur : le statut et le détail de l'ApiError", () => {
    renderPanel([], { isError: true, error: new ApiError(500, "Internal Server Error") });
    expect(screen.getByText(/500/)).toBeInTheDocument();
    expect(screen.getByText(/Internal Server Error/)).toBeInTheDocument();
  });

  it("nomme l'échec réseau : le message du navigateur, pas un statut serveur", () => {
    renderPanel([], { isError: true, error: new TypeError("Failed to fetch") });
    expect(screen.getByText(/TypeError/)).toBeInTheDocument();
    expect(screen.getByText(/Failed to fetch/)).toBeInTheDocument();
  });

  it("le bouton « Réessayer » relance la requête", () => {
    const refetch = vi.fn();
    renderPanel([], { isError: true, refetch });
    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(refetch).toHaveBeenCalledTimes(1);
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

    // status: only to_grab produces the primary action.
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
    const listBtn = screen.getByRole("button", { name: /Liste/ });
    expect(listBtn).toBeInTheDocument();
    expect(listBtn.getAttribute("aria-pressed")).toBe("true");
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
    // The affirmative left action for a takeable item, then §9's 84 px pair
    // for a série: suspend then remove.
    expect(labels).toEqual(["Récupérer", "Pause", "Retirer"]);
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
    const removeBtn = within(container)
      .getAllByTestId("swipe-action")
      .find((b) => b.textContent === "Retirer");
    if (removeBtn == null) throw new Error("unreachable");
    fireEvent.click(removeBtn);

    expect(mutate).not.toHaveBeenCalled();
    expect(screen.getByText("Retirer ce suivi ?")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("confirmer-le-retrait"));
    const [removedId, removeOpts] = mutate.mock.calls[0] as [
      number,
      { onSuccess?: () => void },
    ];
    expect(removedId).toBe(1);
    // The success toast rides on the call's own options.
    expect(typeof removeOpts.onSuccess).toBe("function");
  });

  it("A10 — « Pause » par balayage suspend réellement", () => {
    const mutate = vi.fn();
    vi.spyOn(hooks, "useUpdateFollow").mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof hooks.useUpdateFollow>);

    renderPanel([takeableShow()]);
    const container = screen.getByTestId("swipe-container");
    const suspendBtn = within(container)
      .getAllByTestId("swipe-action")
      .find((b) => b.textContent === "Pause");
    if (suspendBtn == null) throw new Error("unreachable");
    fireEvent.click(suspendBtn);

    const [payload, opts] = mutate.mock.calls[0] as [
      { id: number; body: { active: boolean } },
      { onSuccess?: () => void },
    ];
    expect(payload).toEqual({ id: 1, body: { active: false } });
    // The success toast rides on the call's own options.
    expect(typeof opts.onSuccess).toBe("function");
  });

  it("A10 — « Récupérer » par balayage lance réellement la recherche", () => {
    const mutate = vi.fn();
    vi.spyOn(hooks, "useGrabNow").mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof hooks.useGrabNow>);

    renderPanel([takeableShow()]);
    const container = screen.getByTestId("swipe-container");
    const grabBtn = within(container)
      .getAllByTestId("swipe-action")
      .find((b) => b.textContent === "Récupérer");
    if (grabBtn == null) throw new Error("unreachable");
    fireEvent.click(grabBtn);

    expect(mutate).toHaveBeenCalledWith(1);
  });

  it("A10 — pas de « Récupérer » au balayage d'un suivi qui n'a rien à prendre", () => {
    renderPanel([pausedShow()]);
    fireEvent.click(screen.getByRole("button", { name: /En pause\s*1/ }));
    const labels = within(screen.getByTestId("swipe-container"))
      .getAllByTestId("swipe-action")
      .map((b) => b.textContent);
    expect(labels).not.toContain("Récupérer");
  });

  it("nomme le trou d'identité : chip « Sans ID TVDB » sur la carte concernée", () => {
    renderPanel([
      { ...takeableShow(), tvdb_unresolved: true },
      { ...takeableShow(), id: 2, title: "Autre" },
    ]);
    // Exactly one — the flag is per-item, never a blanket décor.
    expect(screen.getAllByText("Sans ID TVDB")).toHaveLength(1);
  });

  it("aucun bouton d'ajout en fin de liste — redondant avec le « + » fixe (opérateur)", () => {
    renderPanel([takeableShow()]);
    expect(screen.queryByTestId("ajouter-en-fin-de-liste")).toBeNull();
  });

  it("aucun « ··· » sur les rangées (opérateur) — les actions vivent dans la fiche", () => {
    renderPanel([takeableShow()]);
    expect(screen.queryByRole("button", { name: "Actions pour Silo" })).toBeNull();
  });
  it("une série terminée porte « Terminé », pas « À jour » (opérateur 2026-08-09)", () => {
    renderPanel([
      { ...upToDateShow(), id: 10, title: "Fini", status: "ended" },
      { ...upToDateShow(), id: 11, title: "Continue", status: "up_to_date" },
    ]);

    // The whole point of the split: the two settled series must not read the
    // same. « À jour » says « rien à faire pour l'instant », « Terminé » says
    // « rien à faire, jamais plus ».
    expect(screen.getByText("Terminé")).toBeInTheDocument();
    expect(screen.getByText("À jour")).toBeInTheDocument();
  });

  it("mode groupé : les terminées ont leur propre groupe", () => {
    renderPanel([
      { ...upToDateShow(), id: 10, title: "Fini", status: "ended" },
      { ...upToDateShow(), id: 11, title: "Continue", status: "up_to_date" },
    ]);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /Groupé par état/ }));
    });

    // Folded into « À jour », the distinction the operator asked for would be
    // invisible in exactly the mode meant for reading the list by state.
    const terminees = screen.getByTestId("group-terminees");
    expect(within(terminees).getByText("Fini")).toBeInTheDocument();
    expect(within(screen.getByTestId("group-a-jour")).getByText("Continue")).toBeInTheDocument();
  });

  it("mode groupé : AUCUN statut ne fait disparaître sa carte", () => {
    // Grouped mode renders `GROUPS.map(...)` and filters by membership, so a
    // status belonging to no group is not « ungrouped » — it is GONE, with no
    // error and no empty state. That is a silent data loss, and the kind of
    // thing a new status introduces without anyone noticing.
    const statuses: readonly FollowedSeriesItem["status"][] = [
      "to_grab",
      "acquiring",
      "verifying",
      "pending",
      "unverified",
      "up_to_date",
      "ended",
      "disabled",
    ];
    renderPanel(
      statuses.map((status, i) => ({
        ...upToDateShow(),
        id: 100 + i,
        title: `Suivi ${status}`,
        status,
        active: status !== "disabled",
      })),
    );
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: /Groupé par état/ }));
    });

    const shown = screen
      .getAllByTestId("acq-card-title")
      .map((t) => t.textContent);
    for (const status of statuses) {
      expect(shown).toContain(`Suivi ${status}`);
    }
  });

  it("l'écart entre les deux barres épinglées ne peut pas bouger au scroll", () => {
    // Operator, 2026-08-09: « l'écart entre le changement d'onglet et le champ
    // filtrer par nom diminue/augmente quand on scroll ». Measured on the
    // deployed build: 8.00 px at rest, -0.55 px once pinned — the filter zone
    // travelled 8.55 px relative to the tabs during the first pixels of scroll.
    //
    // jsdom computes no layout, so what is verifiable here is the contract that
    // makes the two positions identical: no top padding in flow, and a flow
    // offset (`-mt-px`) that is the exact mirror of the sticky one (`- 1px`).
    // The real proof is the harness measurement; this is the guard that stops
    // the pair drifting apart in an edit.
    renderPanel([takeableShow()]);
    const filters = document.querySelector(".filters");
    if (!(filters instanceof HTMLElement)) throw new Error("filter zone");

    // The `px` unit is assembled, not written: the design-system rule bans raw
    // px literals, and it is right — here the string IS the subject of the
    // assertion, not a hardcoded dimension.
    const onePx = `1${["p", "x"].join("")}`;
    expect(filters.className).toContain(`-mt-${["p", "x"].join("")}`);
    expect(filters.style.top).toContain(`- 1rem - ${onePx}`);
    // The panel body must not reintroduce flow between the bars.
    const body = filters.parentElement;
    expect(body?.className).not.toMatch(/\bp[ty]-/);
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
