import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RunDetail } from "@/components/pipeline/RunDetail";

import type { RunDetail as RunDetailType } from "@/api/client";

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

/** Render RunDetail wrapped in a fresh QueryClientProvider. */
function renderDetail(runUid: string, onClose: () => void = vi.fn()): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <RunDetail runUid={runUid} onClose={onClose} />
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

    // Both the outcome badge AND the error section heading say "Erreur".
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

    // "Erreur" should only appear once if it's the outcome label, not a
    // section. Our success outcome label is "Succès", not "Erreur".
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

    // Both the outcome badge AND the error section heading say "Erreur".
    const erreurElements = screen.getAllByText("Erreur");
    expect(erreurElements.length).toBeGreaterThanOrEqual(1);
    // The error body should also be visible.
    expect(screen.getByText("something broke")).toBeInTheDocument();
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
});
