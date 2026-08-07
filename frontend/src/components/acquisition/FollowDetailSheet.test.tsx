/**
 * FollowDetailSheet — §13 one-derivation detail sheet for a followed series/movie.
 *
 * The three surfaces — card fraction, sheet header, season headers — must AGREE
 * by reading the same derivation (§5.4). The card↔sheet crossing is covered by a
 * backend test (tests/web/acquisition/test_completeness_truth_agreement.py); the
 * frontend tests verify the sheet-header↔season agreement and the layout order.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompletenessResponse } from "@/api/acquisition";
import type { FollowStatus, MediaKind } from "@/components/acquisition/meta";

import { FollowDetailSheet, seasonCounts } from "./FollowDetailSheet";
import * as hooks from "@/hooks/useAcquisition";

// Capture navigation.
const navigateMock = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => navigateMock,
  } as typeof actual;
});

// ── Fixtures ──────────────────────────────────────────────────────────────

/**
 * ``silo`` — S01 10/10 (all owned), S02 15 eps: 13 owned, 1 à récupérer,
 * 1 annoncé. Aggregate: 23/24.
 */
function silo(): CompletenessResponse {
  const s01Owned = Array.from({ length: 10 }, (_, i) => ({
    episode: i + 1,
    state: "en_mediatheque" as const,
    title: `S01E${String(i + 1).padStart(2, "0")}`,
    air_date: `2023-0${String(Math.ceil((i + 1) / 4))}-${String((i % 4) * 7 + 1).padStart(2, "0")}`,
  }));

  const s02Episodes = [
    ...Array.from({ length: 13 }, (_, i) => ({
      episode: i + 1,
      state: "en_mediatheque" as const,
      title: `S02E${String(i + 1).padStart(2, "0")}`,
      air_date: `2024-0${String(Math.ceil((i + 1) / 5))}-${String((i % 5) * 6 + 1).padStart(2, "0")}`,
    })),
    { episode: 14, state: "a_recuperer" as const, title: "The Missing", air_date: "2024-06-08" },
    { episode: 15, state: "annonce" as const, title: "The Future", air_date: "2099-01-01" },
  ];

  return {
    followed_id: 42,
    title: "Silo",
    kind: "show",
    provider_catalog_empty: false,
    source: "cache",
    catalog_refreshed_at: 1_750_000_000,
    seasons: [
      {
        season: 2,
        owned: 13,
        queued: 1,
        total: 14,
        announced: 1,
        episodes: s02Episodes,
      },
      {
        season: 1,
        owned: 10,
        queued: 0,
        total: 10,
        announced: 0,
        episodes: s01Owned,
      },
    ],
  };
}

/**
 * ``americanDad`` — 21 seasons (proven in prod), most-recent S21 incomplete,
 * S19 complete.  Seasons arrive ASCENDING from the API (1, 2, …, 21) so the
 * component's explicit sort is what puts S21 first — the test proves the sort,
 * not the fixture's luck.
 */
function americanDad(): CompletenessResponse {
  const seasons = Array.from({ length: 21 }, (_, i) => {
    const n = i + 1; // season number: 1, 2, …, 21 (ascending — sort must invert)
    // Season 21: incomplete (owned != aired). Others: complete.
    const incomplete = n === 21;
    const episodeCount = 15 + (n % 3);
    const owned = incomplete ? episodeCount - 1 : episodeCount;
    const episodes = Array.from({ length: episodeCount }, (_, ei) => ({
      episode: ei + 1,
      state: incomplete && ei === episodeCount - 1
        ? ("a_recuperer" as const)
        : ("en_mediatheque" as const),
      title: `S${String(n).padStart(2, "0")}E${String(ei + 1).padStart(2, "0")}`,
      air_date: null,
    }));
    return {
      season: n,
      owned,
      queued: incomplete ? 1 : 0,
      total: episodeCount,
      announced: 0,
      episodes,
    };
  });

  return {
    followed_id: 99,
    title: "American Dad!",
    kind: "show",
    provider_catalog_empty: false,
    source: "cache",
    catalog_refreshed_at: 1_750_000_000,
    seasons,
  };
}

/** ``movieNotOwned`` — a film that is *not* yet in the médiathèque (§5). */
function movieNotOwned(): CompletenessResponse {
  return {
    followed_id: 7,
    title: "Inception",
    kind: "movie",
    provider_catalog_empty: false,
    source: "cache",
    catalog_refreshed_at: null,
    seasons: [],
  };
}

/** ``unresolved`` — a follow that could not be resolved to a provider id (§11). */
function unresolved(): CompletenessResponse {
  return {
    followed_id: 999,
    title: "Série Mystère",
    kind: "show",
    provider_catalog_empty: false,
    source: "unknown",
    catalog_refreshed_at: null,
    seasons: [],
  };
}

// ── Helpers ───────────────────────────────────────────────────────────────

function mockCompleteness(data: CompletenessResponse): void {
  vi.spyOn(hooks, "useCompleteness").mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof hooks.useCompleteness>);
}

function renderSheet(
  fixture: CompletenessResponse,
  opts?: { readonly status?: FollowStatus; readonly kind?: MediaKind; readonly mediaHref?: string | null },
): void {
  mockCompleteness(fixture);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <FollowDetailSheet
          followedId={fixture.followed_id}
          status={opts?.status ?? "a_jour"}
          kind={opts?.kind ?? (fixture.kind as MediaKind)}
          mediaHref={opts?.mediaHref}
          open={true}
          onOpenChange={vi.fn()}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
  navigateMock.mockReset();
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe("seasonCounts — la dérivation unique (§13)", () => {
  it("compte possédés = en_mediatheque, diffusés = tout sauf annonce", () => {
    const eps = [
      { state: "en_mediatheque" as const },
      { state: "en_mediatheque" as const },
      { state: "a_recuperer" as const },
      { state: "annonce" as const },
    ];
    const r = seasonCounts(eps);
    expect(r.owned).toBe(2);
    expect(r.aired).toBe(3); // 4 total − 1 annonce
  });

  it("exclut 'annonce' du dénominateur — un épisode futur ne peut pas manquer", () => {
    const eps = [
      { state: "annonce" as const },
      { state: "annonce" as const },
    ];
    const r = seasonCounts(eps);
    expect(r.owned).toBe(0);
    expect(r.aired).toBe(0);
  });

  it("retourne (0, 0) pour une saison vide", () => {
    expect(seasonCounts([])).toEqual({ owned: 0, aired: 0 });
  });
});

describe("FollowDetailSheet", () => {
  it("§13 — l'en-tête et la somme des saisons disent le même nombre", async () => {
    renderSheet(silo());
    // Sheet meta reads the aggregate of ALL seasons through seasonCounts.
    expect(await screen.findByTestId("sheet-meta")).toHaveTextContent("23/24 en médiathèque");
    // Per-season fractions read the SAME function.
    const perSeason = screen.getAllByTestId("season-fraction").map((n) => n.textContent);
    const owned = perSeason.reduce((a, t) => a + Number(t.split("/")[0]), 0);
    const aired = perSeason.reduce((a, t) => a + Number(t.split("/")[1]), 0);
    // The two surfaces AGREE — not just each non-empty.
    expect(`${String(owned)}/${String(aired)}`).toBe("23/24");
  });

  it("un épisode annoncé n'est pas diffusé : il ne peut pas manquer au dénominateur", async () => {
    renderSheet(silo());
    // S02: 13 owned, 14 aired (the 15th episode is 'annonce' → excluded from aired).
    expect(await screen.findByTestId("season-2-fraction")).toHaveTextContent("13/14");
  });

  it("gros catalogue : la saison la plus récente est en tête (le tri, pas la chance du fixture)", async () => {
    renderSheet(americanDad());
    const names = (await screen.findAllByTestId("season-name")).map((n) => n.textContent);
    // The fixture arrives ASCENDING (1→21) — the sort puts S21 first.
    expect(names[0]).toBe("Saison 21");
  });

  it("une saison complète est repliée, une incomplète est ouverte et signalée", async () => {
    renderSheet(americanDad());
    // S21 is incomplete (owned=14, aired=15).
    expect(await screen.findByTestId("season-21")).toHaveAttribute("open");
    expect(within(screen.getByTestId("season-21")).getByText(/1 manquant/)).toBeInTheDocument();
    // S19 is complete — no open attribute.
    expect(screen.getByTestId("season-19")).not.toHaveAttribute("open");
  });

  it("la légende est AU-DESSUS de la matrice", async () => {
    renderSheet(americanDad());
    const legend = await screen.findByTestId("episode-legend");
    const first = screen.getByTestId("season-21");
    // legend precedes the first season in document order.
    expect(
      legend.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("l'écran s'ouvre sur l'état, pas sur sept boutons", async () => {
    renderSheet(silo());
    const legend = await screen.findByTestId("episode-legend");
    const secondary = screen.getByTestId("secondary-actions");
    // Legend comes BEFORE secondary actions — state before actions.
    expect(
      legend.compareDocumentPosition(secondary) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("§5.3 — 'a_recuperer' affiche 'Récupérer maintenant' comme action primaire", async () => {
    renderSheet(silo(), { status: "a_recuperer" });
    expect(await screen.findByTestId("primary-action")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Récupérer maintenant" })).toBeInTheDocument();
  });

  it("§5.3 — 'a_jour' n'affiche PAS d'action primaire (rien à récupérer)", async () => {
    renderSheet(silo(), { status: "a_jour" });
    await screen.findByTestId("sheet-meta");
    expect(screen.queryByTestId("primary-action")).toBeNull();
  });

  it("§5 — la fiche d'un film non acquis annonce le retrait automatique", async () => {
    renderSheet(movieNotOwned(), { kind: "movie" });
    expect(await screen.findByText(/quittera votre liste/)).toBeInTheDocument();
  });

  it("§11 — sans identifiant résolu, 'Voir la fiche' est absent et une phrase l'explique", async () => {
    renderSheet(unresolved());
    expect(screen.queryByTestId("voir-la-fiche")).toBeNull();
    expect(await screen.findByText(/n'a pas pu être résolu/)).toBeInTheDocument();
  });

  it("« Voir la fiche » est absent quand mediaHref est null, même pour un suivi résolu", async () => {
    // mediaHref null → le bouton ne doit pas être présent.
    // Le reste des actions secondaires (pause, remove) reste visible.
    renderSheet(silo(), { mediaHref: null });
    await screen.findByTestId("sheet-meta");
    expect(screen.queryByTestId("voir-la-fiche")).toBeNull();
    // Les autres actions secondaires sont toujours présentes.
    expect(screen.getByTestId("secondary-actions")).toBeInTheDocument();
  });

  it("« Voir la fiche » navigue vers le href media quand mediaHref est fourni (task 11, A12)", async () => {
    navigateMock.mockReset();
    renderSheet(silo(), { mediaHref: "/media/tvdb/400000?kind=tv" });
    await screen.findByTestId("voir-la-fiche");
    fireEvent.click(screen.getByTestId("voir-la-fiche"));
    expect(navigateMock).toHaveBeenCalledTimes(1);
    expect(navigateMock.mock.calls[0]?.[0]).toBe("/media/tvdb/400000?kind=tv");
  });
});
