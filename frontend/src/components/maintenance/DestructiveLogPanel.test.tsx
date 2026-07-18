import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DestructiveLogResponse } from "@/api/maintenance";
import { DestructiveLogPanel } from "@/components/maintenance/DestructiveLogPanel";

vi.mock("@/api/maintenance", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/maintenance")>("@/api/maintenance");
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
