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
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CompletenessResponse } from "@/api/acquisition";

import { CompletenessAccordion } from "./CompletenessAccordion";
import * as hooks from "@/hooks/useAcquisition";

// ── Season-grab mocks ──────────────────────────────────────────────────

const grabSeasonMock = vi.fn();
const toastSuccessMock = vi.fn();
const toastErrorMock = vi.fn();
const toastInfoMock = vi.fn();

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return {
    ...actual,
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    grabSeason: (...args: unknown[]) => grabSeasonMock(...args),
  };
});

vi.mock("sonner", () => ({
  toast: {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    success: (...args: unknown[]) => toastSuccessMock(...args),
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    error: (...args: unknown[]) => toastErrorMock(...args),
    // eslint-disable-next-line @typescript-eslint/no-unsafe-return
    info: (...args: unknown[]) => toastInfoMock(...args),
  },
}));

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
    expect(titleOf(4)).toContain("En attente de torrent");
    expect(titleOf(5)).toContain("Non vérifié");
    // « En attente de torrent » and « Non vérifié » must never read alike.
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
    // The season header surfaces the announced count so it is not dead wire data.
    expect(
      screen.getByText(/0\/1 en médiathèque · 1 annoncé/),
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
      "En attente de torrent",
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

describe("CompletenessAccordion — season grab button (R4)", () => {
  it("renders « Récupérer la saison » button for an incomplete season", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 1,
            queued: 0,
            total: 5,
            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "en_mediatheque",
                title: null,
                air_date: null,
              },
              { episode: 2, state: "en_attente", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    const btn = screen.getByRole("button", { name: /Récupérer la saison/ });
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  it("does NOT render the grab button when the season is fully owned", () => {
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 2,
            queued: 0,
            total: 2,
            announced: 0,
            episodes: [
              {
                episode: 1,
                state: "en_mediatheque",
                title: null,
                air_date: null,
              },
              {
                episode: 2,
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

    // « 2/2 en médiathèque » must not offer « Récupérer la saison » AT ALL —
    // a greyed-out button still proposes work that does not exist. It was
    // merely `disabled` before the operator flagged it.
    expect(
      screen.queryByRole("button", { name: /Récupérer la saison/ }),
    ).not.toBeInTheDocument();
    // The season's own readout is still there — only the dead action is gone.
    expect(screen.getByText("2/2 en médiathèque")).toBeInTheDocument();
  });

  it("disables the button while the mutation is pending", async () => {
    // Never-resolving promise keeps the mutation in pending state.
    grabSeasonMock.mockImplementation(() => new Promise(() => undefined));

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
              { episode: 1, state: "en_attente", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    const btn = screen.getByRole("button", { name: /Récupérer la saison/ });
    fireEvent.click(btn);

    // Button text changes to « Mise en file… » and is disabled.
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Mise en file/ }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Mise en file/ })).toBeDisabled();
  });

  // §5 (acq-run-visible): the 201 no longer toasts SUCCESS. Enqueuing a row is
  // not an acquisition; the success line belongs to the run's real, numbered
  // result. The launch is announced as information and the run is then followed.
  it("calls grabSeason with correct payload and ANNOUNCES the launch", async () => {
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 3,
      reused: false,
      run_started: true,
      run_uid: "run-xyz",
    });

    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 0,
            queued: 2,
            total: 5,
            announced: 0,
            episodes: [
              { episode: 1, state: "a_recuperer", title: null, air_date: null },
              { episode: 2, state: "a_recuperer", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    const btn = screen.getByRole("button", { name: /Récupérer la saison/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(grabSeasonMock).toHaveBeenCalledWith(7, 1);
    });

    await waitFor(() => {
      expect(toastInfoMock).toHaveBeenCalledWith(
        expect.stringContaining("Saison 1 lancée"),
      );
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("toasts an informational « déjà en file » when the season row is reused", async () => {
    // Review F8: a reused LIVE row (HTTP 200, reused=true) enqueues nothing —
    // the toast must say so instead of claiming a fresh grab.
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 3,
      reused: true,
    });

    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 0,
            queued: 2,
            total: 5,
            announced: 0,
            episodes: [
              { episode: 1, state: "a_recuperer", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    fireEvent.click(
      screen.getByRole("button", { name: /Récupérer la saison/ }),
    );

    await waitFor(() => {
      expect(toastInfoMock).toHaveBeenCalledWith("Saison 1 déjà en file");
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("toasts an error message when grabSeason rejects", async () => {
    grabSeasonMock.mockRejectedValue(new Error("Saison déjà en file"));

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
              { episode: 1, state: "en_attente", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    const btn = screen.getByRole("button", { name: /Récupérer la saison/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith("Saison déjà en file");
    });
  });

  // §5 (acq-run-visible): the absorbed count belongs to the LAUNCH line, which
  // is informational — the success line is reserved for the run's real result.
  it("shows absorbed count in the launch toast when episodes were absorbed", async () => {
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 7,
      season: 2,
      absorbed_count: 5,
      reused: false,
      run_started: true,
      run_uid: "run-xyz",
    });

    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 2,
            owned: 0,
            queued: 0,
            total: 8,
            announced: 0,
            episodes: [
              { episode: 1, state: "a_recuperer", title: null, air_date: null },
            ],
          },
        ],
      }),
    );
    renderOpen();

    const btn = screen.getByRole("button", { name: /Récupérer la saison/ });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(toastInfoMock).toHaveBeenCalledWith(
        expect.stringContaining("Saison 2 lancée — 5 épisodes absorbés"),
      );
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("does NOT render grab button when total is 0 (empty season)", () => {
    // total==0 means no aired episode — there is nothing to grab, so the
    // button is not rendered at all (it used to render, merely disabled).
    mockCompleteness(
      makeCompleteness({
        seasons: [
          {
            season: 1,
            owned: 0,
            queued: 0,
            total: 0,
            announced: 0,
            episodes: [],
          },
        ],
      }),
    );
    renderOpen();

    expect(
      screen.queryByRole("button", { name: /Récupérer la saison/ }),
    ).not.toBeInTheDocument();
  });
});

// ── §5 — « le déclenchement manuel montre le run » ─────────────────────

describe("CompletenessAccordion — le run manuel est montré (§5)", () => {
  /** Mock the tracked run the season grab hands back. */
  function mockTrackedRun(
    run: { ended_at?: number | null; outcome?: string; result?: Record<string, number> | null } | undefined,
  ): void {
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockReturnValue(
      run as unknown as ReturnType<typeof hooks.useTrackedAcquisitionRun>,
    );
  }

  const oneSeason = () =>
    makeCompleteness({
      seasons: [
        {
          season: 1,
          owned: 0,
          queued: 0,
          total: 5,
          announced: 0,
          episodes: [
            { episode: 1, state: "en_attente", title: null, air_date: null },
          ],
        },
      ],
    });

  it("annonce le lancement sans promettre le succès, puis suit le run", async () => {
    // §5 : un toast de SUCCÈS sur un 201 est un succès promis avant que le run
    // ait produit quoi que ce soit. Au lancement on informe ; le succès n'arrive
    // qu'avec le résultat chiffré.
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 3,
      reused: false,
      run_started: true,
      run_uid: "run-abc",
    });
    mockTrackedRun(undefined); // le run n'a pas encore fini
    mockCompleteness(oneSeason());
    renderOpen();

    fireEvent.click(screen.getByRole("button", { name: /Récupérer la saison/ }));

    await waitFor(() => {
      expect(toastInfoMock).toHaveBeenCalledWith(
        expect.stringContaining("Saison 1 lancée"),
      );
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("montre « Acquisition en cours… » tant que le run tourne", async () => {
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 0,
      reused: false,
      run_started: true,
      run_uid: "run-abc",
    });
    mockTrackedRun(undefined);
    mockCompleteness(oneSeason());
    renderOpen();

    fireEvent.click(screen.getByRole("button", { name: /Récupérer la saison/ }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Acquisition en cours/ }),
      ).toBeDisabled();
    });
  });

  it("toaste le résultat CHIFFRÉ quand le run se termine", async () => {
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 2,
      reused: false,
      run_started: true,
      run_uid: "run-abc",
    });
    // Le run est déjà terminé au premier rendu : le composant doit lire SON
    // résultat, pas répéter une promesse.
    mockTrackedRun({
      ended_at: 1_751_000_100,
      outcome: "success",
      result: { detected: 5, available: 3, grabbed: 2 },
    });
    mockCompleteness(oneSeason());
    renderOpen();

    fireEvent.click(screen.getByRole("button", { name: /Récupérer la saison/ }));

    await waitFor(() => {
      expect(toastSuccessMock).toHaveBeenCalledWith(
        expect.stringMatching(/Saison 1 terminée — .*5.*3.*2/),
      );
    });
  });

  it("dit « rien de nouveau » plutôt que d'inventer un succès", async () => {
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 0,
      reused: false,
      run_started: true,
      run_uid: "run-abc",
    });
    mockTrackedRun({ ended_at: 1_751_000_100, outcome: "success", result: {} });
    mockCompleteness(oneSeason());
    renderOpen();

    fireEvent.click(screen.getByRole("button", { name: /Récupérer la saison/ }));

    await waitFor(() => {
      expect(toastSuccessMock).toHaveBeenCalledWith(
        expect.stringContaining("rien de nouveau"),
      );
    });
  });

  it("remonte bruyamment un run mort — jamais un toast de succès", async () => {
    // §5 : « un toast de succès sur un run mort est interdit ; l'échec remonte
    // bruyamment ».
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 0,
      reused: false,
      run_started: true,
      run_uid: "run-abc",
    });
    mockTrackedRun({ ended_at: 1_751_000_100, outcome: "error", result: null });
    mockCompleteness(oneSeason());
    renderOpen();

    fireEvent.click(screen.getByRole("button", { name: /Récupérer la saison/ }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith(
        expect.stringContaining("Saison 1"),
      );
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("le dit quand AUCUN run n'a démarré — pas de run fantôme à suivre", async () => {
    // run_started=false : la ligne saison existe, mais rien ne tourne. Prétendre
    // le contraire serait exactement le mensonge que le §2 interdit.
    grabSeasonMock.mockResolvedValue({
      season_wanted_id: 42,
      season: 1,
      absorbed_count: 0,
      reused: false,
      run_started: false,
      run_uid: null,
    });
    mockTrackedRun(undefined);
    mockCompleteness(oneSeason());
    renderOpen();

    fireEvent.click(screen.getByRole("button", { name: /Récupérer la saison/ }));

    await waitFor(() => {
      expect(toastInfoMock).toHaveBeenCalledWith(
        expect.stringContaining("prochaine passe"),
      );
    });
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });
});
