import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ActionCatalog } from "@/components/maintenance/ActionCatalog";

import type { ActionsResponse, MaintenanceAction } from "@/api/client";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeAction(
  overrides: Partial<MaintenanceAction> = {},
): MaintenanceAction {
  return {
    id: "library-search",
    title: "Rechercher",
    description: "Recherche dans l'index",
    category: "query",
    risk: "ro",
    long_running: false,
    dry_run: "unsupported",
    options: [],
    ...overrides,
  };
}

function makeActionsResponse(): ActionsResponse {
  return {
    actions: [
      makeAction(),
      makeAction({
        id: "library-index",
        title: "Indexer",
        description: "Scanne les disques",
        category: "scan",
        risk: "write",
        long_running: true,
        dry_run: "supported",
      }),
      makeAction({
        id: "library-clean-disk",
        title: "Nettoyer le disque",
        description: "Supprime les fichiers indésirables",
        category: "clean",
        risk: "destructive",
        long_running: true,
        dry_run: "supported",
      }),
    ],
    category_counts: { query: 1, scan: 1, clean: 1 },
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
    getActions: vi.fn(),
  };
});

async function mockGetActions() {
  const mod = await import("@/api/client");
  return mod.getActions as ReturnType<typeof vi.fn>;
}

function renderCatalog(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <ActionCatalog />
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

describe("ActionCatalog", () => {
  it("affiche l'état de chargement", async () => {
    const fn = await mockGetActions();
    fn.mockReturnValue(new Promise<never>(() => undefined));
    renderCatalog();
    expect(screen.getByText("Chargement des actions…")).toBeInTheDocument();
  });

  it("affiche l'état d'erreur", async () => {
    const fn = await mockGetActions();
    fn.mockRejectedValue(new Error("boom"));
    renderCatalog();

    expect(
      await screen.findByText("Erreur lors du chargement."),
    ).toBeInTheDocument();
  });

  it("groupe les actions par catégorie avec leur décompte", async () => {
    const fn = await mockGetActions();
    fn.mockResolvedValue(makeActionsResponse());
    renderCatalog();

    // Category headers with their FR label.
    expect(await screen.findByText("Requêtes")).toBeInTheDocument();
    expect(screen.getByText("Scans")).toBeInTheDocument();
    expect(screen.getByText("Nettoyage")).toBeInTheDocument();

    // Each single-action category shows a count badge of 1.
    const requetes = screen
      .getByText("Requêtes")
      .closest("button") as HTMLElement;
    expect(within(requetes).getByText("1")).toBeInTheDocument();
  });

  it("affiche les badges de risque et l'indicateur long", async () => {
    const fn = await mockGetActions();
    fn.mockResolvedValue(makeActionsResponse());
    renderCatalog();

    expect(await screen.findByText("Lecture seule")).toBeInTheDocument();
    expect(screen.getByText("Écriture")).toBeInTheDocument();
    expect(screen.getByText("Destructif")).toBeInTheDocument();
    // Two long-running actions (scan + clean).
    expect(screen.getAllByText("long")).toHaveLength(2);
  });

  it("ouvre le formulaire dans une modale au clic sur une action", async () => {
    const fn = await mockGetActions();
    fn.mockResolvedValue(makeActionsResponse());
    renderCatalog();

    fireEvent.click(await screen.findByText("Indexer"));

    const dialog = await screen.findByRole("dialog");
    // The write form renders its submit button.
    expect(
      within(dialog).getByRole("button", { name: "Exécuter (dry-run)" }),
    ).toBeInTheDocument();
  });

  it("replie une catégorie au clic sur son en-tête", async () => {
    const fn = await mockGetActions();
    fn.mockResolvedValue(makeActionsResponse());
    renderCatalog();

    // Card visible while expanded.
    expect(await screen.findByText("Rechercher")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Requêtes"));

    expect(screen.queryByText("Rechercher")).not.toBeInTheDocument();
  });
});
