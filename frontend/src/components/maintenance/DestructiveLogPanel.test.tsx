import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DestructiveLogResponse } from "@/api/maintenance";
import { DestructiveLogPanel } from "@/components/maintenance/DestructiveLogPanel";

vi.mock("@/api/maintenance", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/maintenance")>(
      "@/api/maintenance",
    );
  return {
    ...actual,
    getDestructiveLog: vi.fn(),
  };
});

async function mockGetLog() {
  const mod = await import("@/api/maintenance");
  return mod.getDestructiveLog as ReturnType<typeof vi.fn>;
}

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <DestructiveLogPanel />
    </QueryClientProvider>
  );
  render(tree);
}

const _RESP: DestructiveLogResponse = {
  entries: [
    {
      ts: 1_784_140_000,
      op: "overwrite",
      path: "/disk/Ferrari (2023)",
      actor: "dispatch",
      detail: "REPLACE film — écrasé par « Ferrari (2023) »",
      run_uid: null,
    },
    {
      ts: 1_784_139_000,
      op: "delete",
      path: "/disk/.actors",
      actor: "disk-clean",
      detail: null,
      run_uid: null,
    },
    {
      ts: 1_784_138_000,
      op: "metadata-refresh",
      path: "/disk/President Curtis (2026)",
      actor: "dispatch",
      detail:
        "MERGE série — métadonnées et visuels régénérés pour « President Curtis (2026) » (aucun épisode écrasé)",
      run_uid: null,
    },
  ],
};

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

describe("DestructiveLogPanel", () => {
  it("liste les suppressions avec libellé FR, chemin et raison", async () => {
    (await mockGetLog()).mockResolvedValue(_RESP);
    renderPanel();

    expect(
      await screen.findByText("Journal des suppressions"),
    ).toBeInTheDocument();
    // French op labels (not "overwrite"/"delete").
    expect(await screen.findByText("Écrasé")).toBeInTheDocument();
    expect(screen.getByText("Supprimé")).toBeInTheDocument();
    // Path + reason surfaced.
    expect(screen.getByText("/disk/Ferrari (2023)")).toBeInTheDocument();
    expect(
      screen.getByText("REPLACE film — écrasé par « Ferrari (2023) »"),
    ).toBeInTheDocument();
  });

  it("distingue une régénération de métadonnées d'une destruction", async () => {
    (await mockGetLog()).mockResolvedValue(_RESP);
    renderPanel();

    // The benign kind gets its own French label...
    const badge = await screen.findByText("Métadonnées");
    expect(badge).toBeInTheDocument();
    // ...and a neutral tone: it must NOT wear the destructive red, otherwise a
    // simple NFO/artwork refresh reads as a lost episode.
    expect(badge).toHaveClass("text-muted-foreground");
    expect(badge).not.toHaveClass("text-danger");
    // The destructive rows keep the alarming tone.
    expect(await screen.findByText("Écrasé")).toHaveClass("text-danger");
    expect(
      screen.getByText(
        "MERGE série — métadonnées et visuels régénérés pour « President Curtis (2026) » (aucun épisode écrasé)",
      ),
    ).toBeInTheDocument();
  });

  it("affiche un état vide avec EmptyState quand rien n'a été supprimé", async () => {
    (await mockGetLog()).mockResolvedValue({ entries: [] });
    renderPanel();

    expect(
      await screen.findByText("Aucune opération destructive"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Le journal des suppressions et remplacements apparaîtra ici.",
      ),
    ).toBeInTheDocument();
  });

  it("affiche une erreur lisible avec role=alert quand la requête échoue", async () => {
    (await mockGetLog()).mockRejectedValue(new Error("boom"));
    renderPanel();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Impossible de lire le journal des suppressions.",
    );
    expect(alert).toHaveTextContent("boom");
    expect(alert).toHaveClass("text-danger");
  });
});
