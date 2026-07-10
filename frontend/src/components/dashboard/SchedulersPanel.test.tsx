import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SchedulersPanel } from "@/components/dashboard/SchedulersPanel";

import type { SchedulersResponse, SchedulerItem } from "@/api/client";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<SchedulerItem> = {}): SchedulerItem {
  return {
    name: "personalscraper-grab",
    kind: "cron",
    display_name: "Récupération (grab)",
    schedule: "Tous les jours à 03:20 et 15:20",
    enabled: null,
    last_run_at: null,
    last_outcome: null,
    ...overrides,
  };
}

function makeResponse(schedulers: SchedulerItem[]): SchedulersResponse {
  return { schedulers };
}

// ---------------------------------------------------------------------------
// Mock the client module
// ---------------------------------------------------------------------------

vi.mock("@/api/client", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    getSchedulers: vi.fn(),
  };
});

async function mockGetSchedulers() {
  const mod = await import("@/api/client");
  return mod.getSchedulers as ReturnType<typeof vi.fn>;
}

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <SchedulersPanel />
    </QueryClientProvider>
  );
  render(tree);
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("SchedulersPanel", () => {
  it("rend une ligne par planificateur depuis la charge utile", async () => {
    const getSchedulers = await mockGetSchedulers();
    getSchedulers.mockResolvedValue(
      makeResponse([
        makeItem({
          name: "personalscraper-watch",
          kind: "watcher",
          display_name: "Surveillance des téléchargements",
          schedule: null,
          enabled: true,
          last_run_at: Math.floor(Date.now() / 1000) - 3600,
          last_outcome: null,
        }),
        makeItem({
          name: "personalscraper-grab",
          last_run_at: Math.floor(Date.now() / 1000) - 120,
          last_outcome: "success",
        }),
      ]),
    );

    renderPanel();

    expect(screen.getByText("Planificateurs")).toBeInTheDocument();
    expect(
      await screen.findByText("Surveillance des téléchargements"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Récupération (grab)")).toBeInTheDocument();

    // Kind badges.
    expect(screen.getByText("Surveillance")).toBeInTheDocument();
    expect(screen.getByText("Cron")).toBeInTheDocument();

    // Outcome tones: cron succeeded, watcher never carries an outcome.
    expect(screen.getByText("Réussi")).toBeInTheDocument();
    expect(screen.getByText("Jamais exécuté")).toBeInTheDocument();

    // Cron schedule string surfaces.
    expect(
      screen.getByText("Tous les jours à 03:20 et 15:20"),
    ).toBeInTheDocument();
    // Relative last-run for the recent cron run.
    expect(screen.getByText("il y a 2 min")).toBeInTheDocument();
  });

  it("affiche l’état de chargement", async () => {
    const getSchedulers = await mockGetSchedulers();
    // Never resolves → stays in loading state.
    getSchedulers.mockReturnValue(
      new Promise<SchedulersResponse>(() => {
        // intentionally never settles
      }),
    );

    renderPanel();

    expect(
      screen.getByText("Chargement des planificateurs…"),
    ).toBeInTheDocument();
  });

  it("affiche l’état d’erreur", async () => {
    const getSchedulers = await mockGetSchedulers();
    getSchedulers.mockRejectedValue(new Error("boom"));

    renderPanel();

    expect(
      await screen.findByText("Erreur lors du chargement."),
    ).toBeInTheDocument();
  });

  it("affiche l’état vide", async () => {
    const getSchedulers = await mockGetSchedulers();
    getSchedulers.mockResolvedValue(makeResponse([]));

    renderPanel();

    expect(await screen.findByText("Aucun planificateur.")).toBeInTheDocument();
  });
});
