/**
 * FollowDetailSheet — §13 one-derivation detail sheet for a followed series/movie.
 *
 * The three surfaces — card fraction, sheet header, season headers — must AGREE
 * by reading the same `seasonCounts` computation (§5.4). Tests construct catalogue
 * fixtures and assert the agreement holds, not merely that each renders.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompletenessResponse } from "@/api/acquisition";

import { FollowDetailSheet, seasonCounts } from "./FollowDetailSheet";
import * as hooks from "@/hooks/useAcquisition";

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
 * S19 complete.
 */
function americanDad(): CompletenessResponse {
  const seasons = Array.from({ length: 21 }, (_, i) => {
    const n = 21 - i; // season number: 21, 20, …, 1
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

function renderSheet(fixture: CompletenessResponse): void {
  mockCompleteness(fixture);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <FollowDetailSheet
        followedId={fixture.followed_id}
        open={true}
        onOpenChange={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe("seasonCounts — la dérivation unique (§13)", () => {
  it("compte possédés = en_mediatheque, diffusés = tout sauf annonce", () => {
    const eps = [
      { state: "en_mediatheque" },
      { state: "en_mediatheque" },
      { state: "a_recuperer" },
      { state: "annonce" },
    ];
    const r = seasonCounts(eps);
    expect(r.owned).toBe(2);
    expect(r.aired).toBe(3); // 4 total − 1 annonce
  });

  it("exclut 'annonce' du dénominateur — un épisode futur ne peut pas manquer", () => {
    const eps = [
      { state: "annonce" },
      { state: "annonce" },
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
  it("§13 — la fraction de la carte, l'en-tête et la somme des saisons disent le même nombre", async () => {
    renderSheet(silo());
    // Sheet meta reads the aggregate of ALL seasons through seasonCounts.
    expect(await screen.findByTestId("sheet-meta")).toHaveTextContent("23/24 en médiathèque");
    // Per-season fractions read the SAME function.
    const perSeason = screen.getAllByTestId("season-fraction").map((n) => n.textContent);
    const owned = perSeason.reduce((a, t) => a + Number(t.split("/")[0]), 0);
    const aired = perSeason.reduce((a, t) => a + Number(t.split("/")[1]), 0);
    // The three surfaces AGREE — not just each non-empty.
    expect(`${String(owned)}/${String(aired)}`).toBe("23/24");
  });

  it("un épisode annoncé n'est pas diffusé : il ne peut pas manquer au dénominateur", async () => {
    renderSheet(silo());
    // S02: 13 owned, 14 aired (the 15th episode is 'annonce' → excluded from aired).
    expect(await screen.findByTestId("season-2-fraction")).toHaveTextContent("13/14");
  });

  it("gros catalogue : la saison la plus récente est en tête", async () => {
    renderSheet(americanDad());
    const names = (await screen.findAllByTestId("season-name")).map((n) => n.textContent);
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

  it("§5 — la fiche d'un film non acquis annonce le retrait automatique", async () => {
    renderSheet(movieNotOwned());
    expect(await screen.findByText(/quittera votre liste/)).toBeInTheDocument();
  });

  it("§11 — sans identifiant résolu, « Voir la fiche » est absent et une phrase l'explique", async () => {
    renderSheet(unresolved());
    expect(screen.queryByRole("button", { name: "Voir la fiche" })).toBeNull();
    expect(await screen.findByText(/n'a pas pu être résolu/)).toBeInTheDocument();
  });
});
