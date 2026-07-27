/**
 * Unit tests for {@link DecisionDetail} (scrape-arbiter §4.2).
 *
 * Mocks the API layer, ``RunLogFeed``, and ``sonner`` toasts, then exercises
 * every interaction path: render, search override, candidate selection, resolve,
 * dismiss, and error surfaces (409 / 410).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import type {
  DecisionCandidate,
  DecisionDetail as DecisionDetailType,
} from "@/api/decisions";
import {
  resolveDecision,
  searchDecisionCandidates,
  dismissDecision,
} from "@/api/decisions";
import { DecisionDetail } from "@/components/decisions/DecisionDetail";

// ---------------------------------------------------------------------------
// Mock: API layer
// ---------------------------------------------------------------------------

vi.mock("@/api/decisions", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/decisions")>("@/api/decisions");
  return {
    ...actual,
    resolveDecision: vi.fn(),
    searchDecisionCandidates: vi.fn(),
    dismissDecision: vi.fn(),
  };
});

const resolveDecisionMock = vi.mocked(resolveDecision);
const searchDecisionCandidatesMock = vi.mocked(searchDecisionCandidates);
const dismissDecisionMock = vi.mocked(dismissDecision);

// ---------------------------------------------------------------------------
// Mock: run-detail poll (getPipelineRunDetail) — preserve the real ApiError.
// ---------------------------------------------------------------------------

vi.mock("@/api/pipeline", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/pipeline")>("@/api/pipeline");
  return { ...actual, getPipelineRunDetail: vi.fn() };
});

import { getPipelineRunDetail } from "@/api/pipeline";
const getPipelineRunDetailMock = vi.mocked(getPipelineRunDetail);

// ---------------------------------------------------------------------------
// Mock: RunLogFeed
// ---------------------------------------------------------------------------

vi.mock("@/components/pipeline/RunLogFeed", () => ({
  RunLogFeed: ({ runUid }: { runUid: string }) => (
    <div data-testid="run-log-feed" data-run-uid={runUid}>
      RunLogFeed
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Mock: sonner toast
// ---------------------------------------------------------------------------

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCandidate(
  overrides: Partial<DecisionCandidate> = {},
): DecisionCandidate {
  return {
    provider: "tmdb",
    provider_id: 123,
    title: "Inception",
    year: 2010,
    score: 0.85,
    poster_url: "https://example.com/poster.jpg",
    overview: "A dream within a dream.",
    ...overrides,
  };
}

function makeDecision(
  overrides: Partial<DecisionDetailType> = {},
): DecisionDetailType {
  return {
    id: 1,
    media_kind: "movie",
    extracted_title: "Test Movie",
    extracted_year: 2024,
    staging_path: "/staging/001-MOVIES/Test Movie (2024)",
    trigger: "below_threshold",
    candidates: [
      makeCandidate(),
      makeCandidate({
        provider: "tvdb",
        provider_id: 456,
        title: "Test Movie (TV)",
      }),
    ],
    candidates_count: 2,
    status: "pending",
    created_at: 1_750_000_000,
    resolution_json: null,
    ...overrides,
  };
}

/** Build a minimal RunDetail with a given outcome for the completion-poll mock. */
function makeRunDetail(
  outcome: "success" | "error" | "killed" | "running",
): Awaited<ReturnType<typeof getPipelineRunDetail>> {
  return {
    run_uid: "run-abc-123",
    outcome,
    kind: "maintenance",
    dry_run: false,
    started_at: "2026-07-10T00:00:00Z",
    ended_at: outcome === "running" ? null : "2026-07-10T00:01:00Z",
    trigger: "web",
    steps: [],
  };
}

function renderDetail(decision: DecisionDetailType, onHandled = vi.fn()): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <DecisionDetail decision={decision} onDecisionHandled={onHandled} />
    </QueryClientProvider>
  );
  render(tree);
}

/**
 * Return the first CandidateCard DOM element.
 *
 * CandidateCards render with ``aria-pressed`` (either true or false), which
 * distinguishes them from the page's other ``role="button"`` elements
 * (``<Button>`` components).  Throws if no cards are in the DOM.
 */
function firstCandidateCard(): HTMLElement {
  const cards = document.querySelectorAll("[aria-pressed]");
  if (cards.length === 0) throw new Error("No candidate cards rendered");
  const first = cards[0];
  if (!(first instanceof HTMLElement)) throw new Error("Not an HTMLElement");
  return first;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DecisionDetail", () => {
  // ---- Render ----------------------------------------------------------------

  it("affiche le titre extrait et l'année", () => {
    renderDetail(makeDecision());
    expect(screen.getByText("Test Movie")).toBeInTheDocument();
    expect(screen.getByText("(2024)")).toBeInTheDocument();
  });

  it("affiche « — » quand extracted_year est null", () => {
    renderDetail(makeDecision({ extracted_year: null }));
    expect(screen.getByText("(—)")).toBeInTheDocument();
  });

  it("affiche le badge de déclencheur", () => {
    renderDetail(makeDecision({ trigger: "mid_band" }));
    expect(screen.getByText("Confiance moyenne")).toBeInTheDocument();
  });

  it("affiche l'explication du déclencheur", () => {
    renderDetail(makeDecision({ trigger: "ambiguous" }));
    expect(
      screen.getByText(/Plusieurs correspondances sont possibles/),
    ).toBeInTheDocument();
  });

  it("affiche la grille de candidats", () => {
    renderDetail(makeDecision());
    // Two candidates rendered via CandidateCard
    expect(screen.getByText("Inception")).toBeInTheDocument();
    expect(screen.getAllByText("2010")).toHaveLength(2);
  });

  it("affiche le message quand il n'y a aucun candidat", () => {
    renderDetail(makeDecision({ candidates: [], candidates_count: 0 }));
    expect(
      screen.getByText("Aucun candidat disponible pour cette décision."),
    ).toBeInTheDocument();
  });

  it("affiche une décision résolue en lecture seule (sans re-scrape)", () => {
    // Regression: an already-resolved decision must show its result, not the
    // candidate picker + "Choisir" (which hit a confusing "not pending" 409).
    renderDetail(
      makeDecision({
        status: "resolved",
        resolution_json: { provider: "tmdb", provider_id: 550, via: "pick" },
      }),
    );
    expect(screen.getByText("Résolue")).toBeInTheDocument();
    expect(screen.getByText("Correspondance retenue")).toBeInTheDocument();
    expect(screen.getByText(/TMDB #550/)).toBeInTheDocument();
    // No resolve/dismiss controls on a closed decision.
    expect(
      screen.queryByRole("button", { name: "Choisir" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Re-chercher" }),
    ).not.toBeInTheDocument();
  });

  it("affiche le formulaire de recherche manuelle avec les valeurs extraites", () => {
    renderDetail(
      makeDecision({ extracted_title: "Inception", extracted_year: 2010 }),
    );
    expect(screen.getByLabelText("Titre")).toHaveValue("Inception");
    // The year input has type="number" — DOM value is a Number, not a string.
    expect(screen.getByLabelText("Année")).toHaveValue(2010);
  });

  // ---- Candidate selection ---------------------------------------------------

  it("sélectionne un candidat au clic", () => {
    const onHandled = vi.fn();
    renderDetail(makeDecision(), onHandled);

    const card = firstCandidateCard();
    fireEvent.click(card);
    expect(card).toHaveAttribute("aria-pressed", "true");
  });

  // ---- Search override -------------------------------------------------------

  it("lance une recherche manuelle et remplace les candidats", async () => {
    const freshCandidates = [
      makeCandidate({
        provider: "tmdb",
        provider_id: 999,
        title: "New Match",
        score: 0.95,
      }),
    ];

    searchDecisionCandidatesMock.mockResolvedValueOnce({
      candidates: freshCandidates,
    });

    renderDetail(makeDecision());

    const titleInput = screen.getByLabelText("Titre");
    fireEvent.change(titleInput, { target: { value: "New Match" } });

    fireEvent.click(screen.getByText("Re-chercher"));

    await waitFor(() => {
      expect(screen.getByText("New Match")).toBeInTheDocument();
    });

    // Old candidate should be gone
    expect(screen.queryByText("Inception")).not.toBeInTheDocument();
  });

  it("affiche une erreur quand le titre de recherche est vide", async () => {
    renderDetail(makeDecision({ extracted_title: "" }));

    const titleInput = screen.getByLabelText("Titre");
    fireEvent.change(titleInput, { target: { value: "" } });

    fireEvent.click(screen.getByText("Re-chercher"));

    await waitFor(() => {
      expect(
        screen.getByText("Le titre de recherche ne peut pas être vide."),
      ).toBeInTheDocument();
    });
  });

  it("affiche une erreur 502 sur échec du fournisseur", async () => {
    searchDecisionCandidatesMock.mockRejectedValueOnce(
      new ApiError(502, "Provider down"),
    );

    renderDetail(makeDecision());

    fireEvent.click(screen.getByText("Re-chercher"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Le fournisseur de métadonnées est indisponible. Réessayez plus tard.",
      );
    });
  });

  it("résout un candidat issu d'une recherche via 'search_override' (F09)", async () => {
    const freshCandidates = [
      makeCandidate({
        provider: "tmdb",
        provider_id: 999,
        title: "New Match",
        score: 0.95,
      }),
    ];
    searchDecisionCandidatesMock.mockResolvedValueOnce({
      candidates: freshCandidates,
    });
    resolveDecisionMock.mockResolvedValueOnce({ run_uid: "run-ov" });

    renderDetail(makeDecision());

    fireEvent.change(screen.getByLabelText("Titre"), {
      target: { value: "New Match" },
    });
    fireEvent.click(screen.getByText("Re-chercher"));

    await waitFor(() => {
      expect(screen.getByText("New Match")).toBeInTheDocument();
    });

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    await waitFor(() => {
      expect(resolveDecisionMock).toHaveBeenCalledWith(1, {
        provider: "tmdb",
        provider_id: 999,
        via: "search_override",
      });
    });
  });

  // ---- Resolve ---------------------------------------------------------------

  it("lance le re-scraping sur le candidat sélectionné", async () => {
    resolveDecisionMock.mockResolvedValueOnce({ run_uid: "run-abc-123" });

    renderDetail(makeDecision());

    // Select the first candidate
    fireEvent.click(firstCandidateCard());

    fireEvent.click(screen.getByText("Choisir"));

    await waitFor(() => {
      // A candidate picked from the original queue snapshot resolves via 'pick'
      // (F09 — the via provenance is now sent to the backend).
      expect(resolveDecisionMock).toHaveBeenCalledWith(1, {
        provider: "tmdb",
        provider_id: 123,
        via: "pick",
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("run-log-feed")).toBeInTheDocument();
      expect(screen.getByTestId("run-log-feed")).toHaveAttribute(
        "data-run-uid",
        "run-abc-123",
      );
    });

    expect(toast.success).toHaveBeenCalledWith(
      "Résolu — le média poursuit son pipeline jusqu'au dispatch.",
    );
  });

  it("un 409 = décision déjà en cours (le verrou pipeline met en FILE, ne 409 plus — 2026-07-15)", async () => {
    // Since the resolve queue, a held pipeline.lock never reaches the client
    // as a 409: the runner waits (visible « En file » state). The single
    // remaining 409 is the same-decision idempotence guard.
    resolveDecisionMock.mockRejectedValueOnce(
      new ApiError(409, "This decision is already resolving"),
    );

    renderDetail(makeDecision());

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("Cette décision est déjà en cours"),
      );
    });
    // The old pipeline-lock wording must be gone for good.
    expect(toast.error).not.toHaveBeenCalledWith(
      expect.stringContaining("Un pipeline est en cours"),
    );
  });

  it("gère le 410 sur resolve en notifiant la page parent", async () => {
    const onHandled = vi.fn();
    resolveDecisionMock.mockRejectedValueOnce(new ApiError(410, "Superseded"));

    renderDetail(makeDecision(), onHandled);

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Cette décision a été remplacée par une version plus récente.",
      );
      expect(onHandled).toHaveBeenCalled();
    });
  });

  it("désactive le bouton Choisir quand aucun candidat n'est sélectionné", () => {
    renderDetail(makeDecision());
    expect(screen.getByText("Choisir")).toBeDisabled();
  });

  // ---- Dismiss ---------------------------------------------------------------

  it("ignore la décision et appelle onDecisionHandled", async () => {
    dismissDecisionMock.mockResolvedValueOnce({
      id: 1,
      status: "dismissed",
      media_kind: "movie",
      extracted_title: "Test Movie",
      extracted_year: 2024,
      staging_path: "/staging/001-MOVIES/Test Movie (2024)",
      trigger: "below_threshold",
      candidates: [],
      candidates_count: 0,
      created_at: 1_750_000_000,
      resolution_json: null,
    });

    const onHandled = vi.fn();
    renderDetail(makeDecision(), onHandled);

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(dismissDecisionMock).toHaveBeenCalledWith(1);
    });

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("Décision ignorée.");
      expect(onHandled).toHaveBeenCalled();
    });
  });

  it("gère le 410 sur dismiss", async () => {
    const onHandled = vi.fn();
    dismissDecisionMock.mockRejectedValueOnce(new ApiError(410, "Superseded"));

    renderDetail(makeDecision(), onHandled);
    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Cette décision a été remplacée par une version plus récente.",
      );
      expect(onHandled).toHaveBeenCalled();
    });
  });

  // ---- Resolve with RunLogFeed -----------------------------------------------

  it("affiche le RunLogFeed après un resolve réussi", async () => {
    resolveDecisionMock.mockResolvedValueOnce({ run_uid: "run-xyz-789" });

    renderDetail(makeDecision());

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    await waitFor(() => {
      expect(screen.getByTestId("run-log-feed")).toHaveAttribute(
        "data-run-uid",
        "run-xyz-789",
      );
    });

    expect(screen.getByText("Re-scraping en cours")).toBeInTheDocument();
  });

  // ---- Terminal-outcome badge + failure toast (SF1) --------------------------

  it("affiche le badge succès quand le run se termine avec 'success' (SF1)", async () => {
    resolveDecisionMock.mockResolvedValueOnce({ run_uid: "run-abc-123" });
    getPipelineRunDetailMock.mockResolvedValue(makeRunDetail("success"));

    renderDetail(makeDecision());

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    await waitFor(() => {
      expect(screen.getByText("Re-scraping terminé")).toBeInTheDocument();
    });
    // A successful run must NOT surface the danger label nor a failure toast.
    expect(screen.queryByText("Re-scraping échoué")).not.toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalledWith(
      expect.stringContaining("re-scraping a échoué"),
    );
  });

  it("affiche le badge danger + un toast d'échec sur un run 'error' terminal (SF1)", async () => {
    resolveDecisionMock.mockResolvedValueOnce({ run_uid: "run-abc-123" });
    getPipelineRunDetailMock.mockResolvedValue(makeRunDetail("error"));

    renderDetail(makeDecision());

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    // The terminal-error outcome surfaces the DANGER badge (not the neutral
    // "terminé" that used to masquerade as success).
    await waitFor(() => {
      expect(screen.getByText("Re-scraping échoué")).toBeInTheDocument();
    });
    expect(screen.queryByText("Re-scraping terminé")).not.toBeInTheDocument();

    // …and fires a single failure toast.
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("re-scraping a échoué"),
      );
    });
  });

  it("affiche le badge danger sur un run 'killed' terminal (SF1)", async () => {
    resolveDecisionMock.mockResolvedValueOnce({ run_uid: "run-abc-123" });
    getPipelineRunDetailMock.mockResolvedValue(makeRunDetail("killed"));

    renderDetail(makeDecision());

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    await waitFor(() => {
      expect(screen.getByText("Re-scraping échoué")).toBeInTheDocument();
    });
  });

  it("surface une erreur quand le suivi du run échoue en boucle (stuck-poll, SF1)", async () => {
    resolveDecisionMock.mockResolvedValueOnce({ run_uid: "run-abc-123" });
    // The run-detail GET persistently 404s (row never written) — the poll must
    // stop and surface a failure rather than spin "en cours" forever.
    getPipelineRunDetailMock.mockRejectedValue(new ApiError(404, "not found"));

    renderDetail(makeDecision());

    fireEvent.click(firstCandidateCard());
    fireEvent.click(screen.getByText("Choisir"));

    // runQuery uses retry: 2 (a fresh run row may briefly 404 before the runner
    // writes it), so allow for the retry backoff before the error settles.
    await waitFor(
      () => {
        expect(toast.error).toHaveBeenCalledWith(
          expect.stringContaining("Impossible de suivre le re-scraping"),
        );
      },
      { timeout: 8000 },
    );
    // The stuck poll resolves to a failed terminal state (danger badge), not an
    // eternal "en cours".
    await waitFor(
      () => {
        expect(screen.getByText("Re-scraping échoué")).toBeInTheDocument();
      },
      { timeout: 8000 },
    );
  });

  // ---- Dismissed local state -------------------------------------------------

  it("affiche le message de décision ignorée après dismiss réussi", async () => {
    dismissDecisionMock.mockResolvedValueOnce({
      id: 1,
      status: "dismissed",
      media_kind: "movie",
      extracted_title: "Test Movie",
      extracted_year: 2024,
      staging_path: "/staging/001-MOVIES/Test Movie (2024)",
      trigger: "below_threshold",
      candidates: [],
      candidates_count: 0,
      created_at: 1_750_000_000,
      resolution_json: null,
    });

    renderDetail(makeDecision());

    fireEvent.click(screen.getByText("Ignorer"));

    await waitFor(() => {
      expect(
        screen.getByText("Cette décision a été ignorée."),
      ).toBeInTheDocument();
    });
  });
});
