import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DisksPanel } from "@/components/maintenance/DisksPanel";

import type { DisksResponse } from "@/api/client";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeDisk(
  overrides: Partial<{
    id: string;
    label: string;
    mounted: boolean;
    free_gb: number;
    total_gb: number;
    used_pct: number;
  }> = {},
): DisksResponse["disks"][number] {
  return {
    id: "disk_1",
    label: "Disk 1",
    mounted: true,
    free_gb: 500.0,
    total_gb: 1000.0,
    used_pct: 50.0,
    ...overrides,
  };
}

function makeDisksResponse(
  disks: ReturnType<typeof makeDisk>[],
): DisksResponse {
  return { disks };
}

// ---------------------------------------------------------------------------
// Mock the client module
// ---------------------------------------------------------------------------

vi.mock("@/api/client", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    getDisks: vi.fn(),
  };
});

async function mockGetDisks() {
  const mod = await import("@/api/client");
  return mod.getDisks as ReturnType<typeof vi.fn>;
}

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <DisksPanel />
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

describe("DisksPanel", () => {
  it("affiche l'état de chargement", async () => {
    const fn = await mockGetDisks();
    // Never resolve — the hook should show loading.
    fn.mockReturnValue(new Promise<never>(() => undefined));
    renderPanel();
    expect(
      screen.getByText("Chargement des disques…"),
    ).toBeInTheDocument();
  });

  it("affiche l'état d'erreur", async () => {
    const fn = await mockGetDisks();
    fn.mockRejectedValue(new Error("boom"));
    renderPanel();

    expect(
      await screen.findByText("Erreur lors du chargement."),
    ).toBeInTheDocument();
  });

  it("affiche les données d'un disque monté avec espace suffisant", async () => {
    const fn = await mockGetDisks();
    fn.mockResolvedValue(
      makeDisksResponse([
        makeDisk({ id: "d1", label: "SSD Principal", free_gb: 800, total_gb: 1000, used_pct: 20 }),
      ]),
    );
    renderPanel();

    expect(await screen.findByText("SSD Principal")).toBeInTheDocument();
    expect(screen.getByText("800.0 Go")).toBeInTheDocument();
    expect(screen.getByText("libre / 1000.0 Go")).toBeInTheDocument();
    expect(screen.getByText("OK")).toBeInTheDocument();
  });

  it("affiche le statut 'Espace faible' quand l'espace libre ≤ 10%", async () => {
    const fn = await mockGetDisks();
    fn.mockResolvedValue(
      makeDisksResponse([
        makeDisk({ id: "d1", label: "Disque plein", free_gb: 50, total_gb: 1000, used_pct: 95 }),
      ]),
    );
    renderPanel();

    expect(await screen.findByText("Espace faible")).toBeInTheDocument();
  });

  it("affiche le statut 'Non monté' quand le disque est démonté", async () => {
    const fn = await mockGetDisks();
    fn.mockResolvedValue(
      makeDisksResponse([
        makeDisk({ id: "d1", label: "Disque débranché", mounted: false, free_gb: 0, total_gb: 0, used_pct: 100 }),
      ]),
    );
    renderPanel();

    expect(await screen.findByText("Non monté")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("affiche plusieurs disques", async () => {
    const fn = await mockGetDisks();
    fn.mockResolvedValue(
      makeDisksResponse([
        makeDisk({ id: "d1", label: "Disk 1" }),
        makeDisk({ id: "d2", label: "Disk 2" }),
      ]),
    );
    renderPanel();

    expect(await screen.findByText("Disk 1")).toBeInTheDocument();
    expect(screen.getByText("Disk 2")).toBeInTheDocument();
  });

  it("affiche l'état vide", async () => {
    const fn = await mockGetDisks();
    fn.mockResolvedValue(makeDisksResponse([]));
    renderPanel();

    expect(
      await screen.findByText("Aucun disque configuré."),
    ).toBeInTheDocument();
  });
});
