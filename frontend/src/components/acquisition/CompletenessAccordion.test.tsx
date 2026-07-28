/**
 * CompletenessAccordion — the §5 per-season / per-episode matrix.
 *
 * Covers the P0-B.1 provenance caption (dated « Catalogue du JJ/MM/AAAA »), the
 * five per-episode states (phase 8), the in-motion season caption and the
 * honest empty state served when no catalog has ever been written.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompletenessResponse } from "@/api/acquisition";

import { CompletenessAccordion } from "./CompletenessAccordion";
import * as hooks from "@/hooks/useAcquisition";

/** Epoch seconds of the detect pass in the cache fixture. */
const REFRESHED_AT = 1_751_000_000;

/** A one-season completeness payload (source/refreshed_at set per test). */
function makeCompleteness(
  overrides: Partial<CompletenessResponse> = {},
): CompletenessResponse {
  return {
    followed_id: 7,
    title: "House of the Dragon",
    kind: "show",
    provider_catalog_empty: false,
    seasons: [
      {
        season: 1,
        owned: 1,
        queued: 0,
        total: 2,

        announced: 0,
        episodes: [
          {
            episode: 1,
            state: "en_mediatheque",
            title: "The Heirs of the Dragon",
            air_date: "2022-08-21",
          },
          { episode: 2, state: "en_attente", title: null, air_date: null },
        ],
      },
    ],
    source: "cache",
    catalog_refreshed_at: REFRESHED_AT,
    ...overrides,
  };
}

function mockCompleteness(data: CompletenessResponse): void {
  vi.spyOn(hooks, "useCompleteness").mockReturnValue({
    data,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof hooks.useCompleteness>);
}

/** Render the accordion and open it (the query is mocked, so no fetch fires). */
function renderOpen(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <CompletenessAccordion followedId={7} title="House of the Dragon" />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Détail par épisode/ }));
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("CompletenessAccordion catalog caption (P0-B.1)", () => {
  it("captions the dated cached catalog when source is cache", () => {
    mockCompleteness(
      makeCompleteness({
        source: "cache",
        catalog_refreshed_at: REFRESHED_AT,
      }),
    );
    renderOpen();

    // Same formatting path as the component — locale-stable expectation.
    const expected = new Date(REFRESHED_AT * 1000).toLocaleDateString("fr-FR");
    expect(screen.getByText(`Catalogue du ${expected}`)).toBeInTheDocument();
    // The matrix itself still renders above the caption.
    expect(screen.getByText("Saison 1")).toBeInTheDocument();
  });

  it("captions nothing when the catalog provenance is unknown", () => {
    // The "live" provenance died with the synchronous provider poll
    // (acq-states phase 5): an unknown catalog claims NOTHING.
    mockCompleteness(
      makeCompleteness({ source: "unknown", catalog_refreshed_at: null }),
    );
    renderOpen();

    expect(screen.queryByText(/Catalogue du /)).not.toBeInTheDocument();
    expect(
      screen.queryByText("Catalogue interrogé en direct"),
    ).not.toBeInTheDocument();
  });
});

describe("CompletenessAccordion — les cinq états par épisode (phase 8)", () => {
  it("peint chaque état avec son libellé français en infobulle", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 1,
            queued: 2,
            total: 5,

            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "en_mediatheque",
                title: null,
                air_date: null,
              },
              { episode: 2, state: "a_recuperer", title: null, air_date: null },
              {
                episode: 3,
                state: "en_acquisition",
                title: null,
                air_date: null,
              },
              { episode: 4, state: "en_attente", title: null, air_date: null },
              { episode: 5, state: "non_verifie", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    const titleOf = (episode: number): string =>
      screen
        .getByText(`E${String(episode)}`)
        .closest("[title]")
        ?.getAttribute("title") ?? "";

    expect(titleOf(1)).toContain("En médiathèque");
    expect(titleOf(2)).toContain("À récupérer");
    expect(titleOf(3)).toContain("En cours d'acquisition");
    expect(titleOf(4)).toContain("En attente");
    expect(titleOf(5)).toContain("Non vérifié");
    // « En attente » and « Non vérifié » must never read alike.
    expect(titleOf(4)).toMatch(/rien de conforme/);
    expect(titleOf(5)).toMatch(/[Pp]as encore vérifié/);
    // Never the raw machine token (NE-DOIT-PAS-4).
    expect(
      screen.queryByText(/non_verifie|a_recuperer/),
    ).not.toBeInTheDocument();
  });

  it("légende la saison avec ce qui est EN COURS, pas une file", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 3,
            queued: 2,
            total: 6,

            announced: 0,
            episodes: [
              { episode: 1, state: "a_recuperer", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    expect(
      screen.getByText(/3\/6 en médiathèque · 2 en cours/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/en file/)).not.toBeInTheDocument();
  });

  it("n'affiche aucun compteur de mouvement quand rien ne bouge", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 6,
            queued: 0,
            total: 6,

            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "en_mediatheque",
                title: null,
                air_date: null,
              },
            ],
          },
        ],
      }),
    );
    renderOpen();

    expect(screen.getByText("6/6 en médiathèque")).toBeInTheDocument();
  });
});

describe("CompletenessAccordion — le motif d'attente (phase 8)", () => {
  it("dit en français pourquoi les épisodes attendent, sous les pastilles", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 0,
            queued: 0,
            total: 3,

            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "en_attente",
                title: null,
                air_date: null,
                last_search_outcome: "all_filtered",
              },
              {
                episode: 2,
                state: "en_attente",
                title: null,
                air_date: null,
                last_search_outcome: "all_filtered",
              },
              {
                episode: 3,
                state: "en_attente",
                title: null,
                air_date: null,
                last_search_outcome: "no_candidates",
              },
            ],
          },
        ],
      }),
    );
    renderOpen();

    // Grouped by reason, visible WITHOUT hovering (a phone has no hover).
    expect(
      screen.getByText("E1, E2 — rien de conforme au profil"),
    ).toBeInTheDocument();
    expect(screen.getByText("E3 — aucun résultat")).toBeInTheDocument();
    // The machine verdict never reaches the operator.
    expect(screen.queryByText(/all_filtered|no_candidates/)).toBeNull();
  });

  it("explique aussi un « Non vérifié » causé par une panne (panne ≠ absence)", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 0,
            queued: 0,
            total: 1,

            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "non_verifie",
                title: null,
                air_date: null,
                last_search_outcome: "trackers_unavailable",
              },
            ],
          },
        ],
      }),
    );
    renderOpen();

    expect(screen.getByText("E1 — trackers injoignables")).toBeInTheDocument();
  });

  it("n'ajoute aucune ligne quand rien n'attend", () => {
    mockCompleteness(makeCompleteness());
    renderOpen();

    expect(screen.queryByText(/ — aucun résultat/)).toBeNull();
  });
});

describe("CompletenessAccordion — catalogue inconnu (phase 8)", () => {
  it("dit qu'il ne sait pas encore, au lieu d'une matrice ou d'un « aucune saison »", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [],
        source: "unknown",
        catalog_refreshed_at: null,
      }),
    );
    renderOpen();

    expect(
      screen.getByText(/Catalogue pas encore vérifié/),
    ).toBeInTheDocument();
    // Never the assertive « nothing aired » on zero knowledge.
    expect(
      screen.queryByText("Aucune saison diffusée."),
    ).not.toBeInTheDocument();
  });

  it("garde « Aucune saison diffusée » quand le catalogue est connu et vide", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [],
        source: "cache",
        catalog_refreshed_at: REFRESHED_AT,
      }),
    );
    renderOpen();

    expect(screen.getByText("Aucune saison diffusée.")).toBeInTheDocument();
    expect(
      screen.queryByText(/Catalogue pas encore vérifié/),
    ).not.toBeInTheDocument();
  });
});

describe("CompletenessAccordion — annonce, legend, date popover (episode-states)", () => {
  it("renders an announced (future) episode chip", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 2,
            owned: 0,
            queued: 0,
            total: 1,
            announced: 1,
            episodes: [
              {
                episode: 3,
                state: "en_mediatheque",
                title: null,
                air_date: "2024-01-01",
              },
              {
                episode: 4,
                state: "annonce",
                title: "The Future",
                air_date: "2099-01-01",
              },
            ],
          },
        ],
      }),
    );
    renderOpen();

    // Both chips render, the future one included (the read-model now surfaces it).
    expect(
      screen.getByRole("button", { name: /E4 — Annoncé/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /E3 — En médiathèque/ }),
    ).toBeInTheDocument();
  });

  it("shows the legend below the matrix, one entry per episode state", () => {
    mockCompleteness(makeCompleteness());
    renderOpen();

    const legend = screen.getByLabelText("Légende des statuts d'épisode");
    // The legend lists every state label — derived from meta.ts, not hardcoded.
    for (const label of [
      "En médiathèque",
      "À récupérer",
      "En cours d'acquisition",
      "En attente",
      "Non vérifié",
      "Annoncé",
    ]) {
      expect(within(legend).getByText(label)).toBeInTheDocument();
    }
  });

  it("opens « Diffusé le … » on an aired chip (click, portalled)", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 1,
            queued: 0,
            total: 1,
            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "en_mediatheque",
                title: null,
                air_date: "2022-08-21",
              },
            ],
          },
        ],
      }),
    );
    renderOpen();

    fireEvent.click(
      screen.getByRole("button", { name: /E1 — En médiathèque/ }),
    );
    const dialog = screen.getByRole("dialog", { name: /E1 — En médiathèque/ });
    // French long date, never the ISO token.
    expect(dialog).toHaveTextContent("Diffusé le 21 août 2022");
    expect(dialog).not.toHaveTextContent("2022-08-21");
  });

  it("opens « Sortie prévue le … » on an announced chip", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 2,
            owned: 0,
            queued: 0,
            total: 0,
            announced: 1,
            episodes: [
              {
                episode: 5,
                state: "annonce",
                title: null,
                air_date: "2099-08-03",
              },
            ],
          },
        ],
      }),
    );
    renderOpen();

    fireEvent.click(screen.getByRole("button", { name: /E5 — Annoncé/ }));
    const dialog = screen.getByRole("dialog", { name: /E5 — Annoncé/ });
    expect(dialog).toHaveTextContent("Sortie prévue le 3 août 2099");
  });

  it("closes the date popover on Escape and returns focus to the chip", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 1,
            queued: 0,
            total: 1,
            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "en_mediatheque",
                title: null,
                air_date: "2022-08-21",
              },
            ],
          },
        ],
      }),
    );
    renderOpen();

    const chip = screen.getByRole("button", { name: /E1 — En médiathèque/ });
    fireEvent.click(chip);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(chip).toHaveFocus();
  });
});
