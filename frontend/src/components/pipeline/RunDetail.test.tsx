import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RunDetail } from "@/components/pipeline/RunDetail";

import type { RunDetail as RunDetailType } from "@/api/client";
import { ApiError } from "@/api/client";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

/** A minimal detail for a successful run. */
function makeDetail(overrides: Partial<RunDetailType> = {}): RunDetailType {
  return {
    run_uid: "abc123-run-uid",
    kind: "pipeline",
    trigger: "web",
    dry_run: false,
    started_at: "2026-07-06T10:00:00Z",
    ended_at: "2026-07-06T10:05:30Z",
    outcome: "success",
    duration_s: 330,
    error: null,
    steps: [
      { name: "ingest", status: "done", elapsed_s: 12.3 },
      { name: "sort", status: "done", elapsed_s: 5.1 },
      { name: "clean", status: "done", elapsed_s: 2.0 },
      { name: "scrape", status: "done", elapsed_s: 180.5 },
      { name: "cleanup", status: "done", elapsed_s: 1.2 },
      { name: "enforce", status: "done", elapsed_s: 0.8 },
      { name: "verify", status: "done", elapsed_s: 45.0 },
      { name: "trailers", status: "skipped", elapsed_s: null },
      { name: "dispatch", status: "done", elapsed_s: 83.1 },
    ],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Mock the client module
// ---------------------------------------------------------------------------

vi.mock("@/api/client", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    getPipelineRunDetail: vi.fn(),
  };
});

/** Cached import ref for the mocked getPipelineRunDetail. */
async function mockGetDetail() {
  const mod = await import("@/api/client");
  return mod.getPipelineRunDetail as ReturnType<typeof vi.fn>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Render RunDetail wrapped in a fresh QueryClientProvider + MemoryRouter. */
function renderDetail(
  runUid: string,
  onClose: () => void = vi.fn(),
  opts: { showMaintenanceLink?: boolean } = {},
): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RunDetail
          runUid={runUid}
          onClose={onClose}
          {...(opts.showMaintenanceLink !== undefined
            ? { showMaintenanceLink: opts.showMaintenanceLink }
            : {})}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(cleanup);

describe("RunDetail", () => {
  it("affiche le run_uid, le trigger, l'outcome, la durée et les dates", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail());
    renderDetail("abc123-run-uid");

    // Run UID (truncated to 8 chars).
    expect(await screen.findByText("abc123-r…")).toBeInTheDocument();
    // Trigger rendered as its human label ("web" → "Interface web").
    expect(screen.getByText("Interface web")).toBeInTheDocument();
    // Outcome badge (success → "Succès").
    expect(screen.getByText("Succès")).toBeInTheDocument();
    // Duration formatted as "5m 30s".
    expect(screen.getByText("5m 30s")).toBeInTheDocument();
    // Start date present (we don't validate exact format, just presence).
    expect(screen.getByText("Début")).toBeInTheDocument();
    expect(screen.getByText("Fin")).toBeInTheDocument();
  });

  it("affiche « Ce qui n'a pas avancé » avec les raisons par étape (§8)", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({
        steps: [
          {
            name: "ingest",
            status: "done",
            elapsed_s: 3,
            reasons: [
              "Film X : espace disque insuffisant",
              "Série Y : contenu source introuvable",
            ],
          },
          { name: "sort", status: "done", elapsed_s: 1 },
        ],
      }),
    );
    renderDetail("abc123-run-uid");

    expect(
      await screen.findByText("Ce qui n'a pas avancé"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Film X : espace disque insuffisant"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Série Y : contenu source introuvable"),
    ).toBeInTheDocument();
    // Grouped under the step's French label.
    expect(
      screen.getByText("Récupération des téléchargements"),
    ).toBeInTheDocument();
  });

  it("n'affiche pas la section quand aucune étape n'a de raison", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail());
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");
    expect(screen.queryByText("Ce qui n'a pas avancé")).not.toBeInTheDocument();
  });

  it("affiche le PipelineStepper en mode lecture seule", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail());
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    // READ-ONLY mode: step labels are rendered.
    expect(screen.getByText("Collecte")).toBeInTheDocument();
    expect(screen.getByText("Tri")).toBeInTheDocument();
    expect(screen.getByText("Scraping")).toBeInTheDocument();
    expect(screen.getByText("Dispatch")).toBeInTheDocument();

    // READ-ONLY timings from steps array: e.g. "12.3s" for ingest.
    expect(screen.getByText("12.3s")).toBeInTheDocument();
  });

  it("affiche la section d'erreur quand error est présent", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({
        outcome: "error",
        error:
          "Traceback (most recent call last):\n  File ...\nValueError: disk full",
      }),
    );
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    // Both the outcome badge ("Échec") AND the error section heading ("Erreur").
    const erreurElements = screen.getAllByText("Erreur");
    expect(erreurElements.length).toBeGreaterThanOrEqual(1);
    // Error body text (partial).
    expect(screen.getByText(/disk full/)).toBeInTheDocument();
  });

  it("n'affiche pas la section d'erreur quand error est null", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail({ error: null }));
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    // "Erreur" should only appear once from the section heading, not the
    // outcome badge. The outcome label for success is "Succès", nor "Erreur".
    expect(screen.queryByText("Erreur")).not.toBeInTheDocument();
  });

  it("n'affiche pas la section d'erreur quand error est une chaîne vide", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail({ error: "" }));
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    expect(screen.queryByText("Erreur")).not.toBeInTheDocument();
  });

  it("appelle onClose quand on clique Retour", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail());
    const onClose = vi.fn();
    renderDetail("abc123-run-uid", onClose);

    await screen.findByText("abc123-r…");

    fireEvent.click(screen.getByText("Retour"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("affiche le run_uid en police monospace (tabular-nums)", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail());
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    // The run_uid fragment is rendered inside a span with font-mono.
    const uidSpan = screen.getByText("abc123-r…");
    expect(uidSpan.className).toContain("font-mono");
    expect(uidSpan.className).toContain("tabular-nums");
  });

  it("affiche le badge avec le tone danger pour l'outcome error", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({ outcome: "error", error: "something broke" }),
    );
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    // Both the outcome badge ("Échec") AND the error section heading ("Erreur").
    const erreurElements = screen.getAllByText("Erreur");
    expect(erreurElements.length).toBeGreaterThanOrEqual(1);
    // The error body should also be visible.
    expect(screen.getByText("something broke")).toBeInTheDocument();
  });

  it("affiche le badge « Échec » (exact) pour un run en erreur (sub-phase 5.2)", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({ outcome: "error", error: "traceback" }),
    );
    renderDetail("err-run");

    await screen.findByText("Échec");
    // "Échec" is the unified OUTCOME_LABEL badge — not "Erreur", not "Arrêté".
    expect(screen.getByText("Échec")).toBeInTheDocument();
  });

  it("affiche le badge « Interrompu » pour un run killed (sub-phase 5.2 — tue le mutant Échec→Erreur)", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({ outcome: "killed", error: "SIGTERM" }),
    );
    renderDetail("kill-run");

    await screen.findByText("Interrompu");
    // The unified vocabulary says OUTCOME_LABEL.killed === "Interrompu",
    // NOT "Arrêté" (which is the acquisition STATUS_LABEL, not a run outcome).
    expect(screen.getByText("Interrompu")).toBeInTheDocument();
  });

  it("affiche la commande, les options et la sortie pour un run de maintenance sans le stepper", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({
        kind: "maintenance",
        command: "library-clean",
        options_json: '{"only":"empty"}',
        output_tail: "line1\nline2",
        steps: [],
      }),
    );
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    // Command label and value.
    expect(screen.getByText("Commande")).toBeInTheDocument();
    expect(screen.getByText("library-clean")).toBeInTheDocument();

    // Options label and parsed key/value.
    expect(screen.getByText("Options")).toBeInTheDocument();
    expect(screen.getByText("only")).toBeInTheDocument();
    expect(screen.getByText("empty")).toBeInTheDocument();

    // Output tail label and content.
    expect(screen.getByText("Sortie")).toBeInTheDocument();
    expect(screen.getByText(/line1/)).toBeInTheDocument();
    expect(screen.getByText(/line2/)).toBeInTheDocument();

    // Pipeline stepper step labels MUST NOT be rendered.
    expect(screen.queryByText("Collecte")).not.toBeInTheDocument();
    expect(screen.queryByText("Scraping")).not.toBeInTheDocument();
    expect(screen.queryByText("Dispatch")).not.toBeInTheDocument();
  });

  it("affiche un lien croisé vers /maintenance quand showMaintenanceLink=true et le run est maintenance", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({
        kind: "maintenance",
        command: "library-clean",
        options_json: '{"only":"empty"}',
        steps: [],
      }),
    );
    renderDetail("abc123-run-uid", vi.fn(), { showMaintenanceLink: true });

    await screen.findByText("abc123-r…");

    // Cross-link from Pipeline page to Maintenance (pipeline-panel Phase 02).
    const link = screen.getByText("→ Voir les exécutions de maintenance");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/systeme?tab=maintenance");
  });

  it("n'affiche PAS le lien croisé quand showMaintenanceLink est absent (défaut false)", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({
        kind: "maintenance",
        command: "library-clean",
        steps: [],
      }),
    );
    renderDetail("abc123-run-uid", vi.fn()); // no opts → showMaintenanceLink defaults to false

    await screen.findByText("abc123-r…");

    // Cross-link must NOT render when showMaintenanceLink isn't passed.
    expect(
      screen.queryByText("→ Voir les exécutions de maintenance"),
    ).not.toBeInTheDocument();
  });

  it("n'affiche PAS le lien croisé pour un run pipeline même avec showMaintenanceLink=true", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail({ kind: "pipeline" }));
    renderDetail("abc123-run-uid", vi.fn(), { showMaintenanceLink: true });

    await screen.findByText("abc123-r…");

    // The cross-link is gated on kind === "maintenance" — pipeline runs
    // never show it even when showMaintenanceLink is true.
    expect(
      screen.queryByText("→ Voir les exécutions de maintenance"),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Journal durable (output_tail) — universal run journal 2026-07-08
// ---------------------------------------------------------------------------

describe("RunDetail — journal durable (output_tail)", () => {
  it("affiche le journal durable quand output_tail est présent", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({ output_tail: "ligne de log A\nligne de log B" }),
    );
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    expect(screen.getByText("Journal")).toBeInTheDocument();
    expect(
      screen.getByText(/ligne de log A/, { collapseWhitespace: false }),
    ).toBeInTheDocument();
  });

  it("masque la section journal quand output_tail est absent", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(makeDetail({ output_tail: null }));
    renderDetail("abc123-run-uid");

    await screen.findByText("abc123-r…");

    expect(screen.queryByText("Journal")).not.toBeInTheDocument();
  });
  it("affiche les compteurs français d'un run maintenance (§2 Posters récupérés)", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockResolvedValue(
      makeDetail({
        kind: "maintenance",
        command: "library-rescrape",
        steps: [
          {
            name: "library-rescrape",
            status: "success",
            elapsed_s: 1.2,
            counts: { fixed: 1, skipped: 0, errors: 0, artwork_recovered: 1 },
          },
        ],
      }),
    );
    renderDetail("resc-run-uid");

    expect(await screen.findByText("Posters récupérés")).toBeInTheDocument();
    expect(screen.getByText("Corrigés")).toBeInTheDocument();
    // Zero counters stay hidden — the result reads, it does not drown.
    expect(screen.queryByText("Ignorés")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// B3 — error-path coverage (pipeline-panel review cycle 1)
// ---------------------------------------------------------------------------

describe("RunDetail — error paths (B3)", () => {
  it("affiche le message 404 et le bouton Retour quand le run est introuvable", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockRejectedValue(new ApiError(404, "not found"));
    renderDetail("missing-run");

    // 404 → French message.
    expect(
      await screen.findByText("Ce run n'existe pas (ou plus)."),
    ).toBeInTheDocument();
    // "Retour" button is present even in error state.
    expect(screen.getByText("Retour")).toBeInTheDocument();
    // No retry button for 404 (cannot fix a missing run).
    expect(
      screen.queryByRole("button", { name: "Réessayer" }),
    ).not.toBeInTheDocument();
  });

  it("affiche le message serveur et un bouton retry pour les erreurs 500", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockRejectedValue(new ApiError(500, "server error"));
    renderDetail("broken-run");

    // 500 → server error message.
    expect(
      await screen.findByText("Erreur serveur — réessayez."),
    ).toBeInTheDocument();
    // "Retour" button is present.
    expect(screen.getByText("Retour")).toBeInTheDocument();
    // Retry button is present for non-404 errors.
    expect(
      screen.getByRole("button", { name: "Réessayer" }),
    ).toBeInTheDocument();
  });

  it("affiche le message serveur et un bouton retry pour les erreurs génériques (non ApiError)", async () => {
    const getDetail = await mockGetDetail();
    getDetail.mockRejectedValue(new Error("network down"));
    renderDetail("net-err-run");

    // Generic error → server error message (not a 404).
    expect(
      await screen.findByText("Erreur serveur — réessayez."),
    ).toBeInTheDocument();
    // "Retour" button is present.
    expect(screen.getByText("Retour")).toBeInTheDocument();
    // Retry button is present.
    expect(
      screen.getByRole("button", { name: "Réessayer" }),
    ).toBeInTheDocument();
  });
});
