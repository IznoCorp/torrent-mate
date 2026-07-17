import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { LastRunDigest } from "@/components/controle/LastRunDigest";
import type { LastPipelineRun } from "@/hooks/useLastPipelineRun";
import type { InterpretedLine } from "@/components/pipeline/interpretRun";

afterEach(() => {
  cleanup();
});

/** Build a minimal LastPipelineRun with the given fields. */
function lastRun(overrides: Partial<LastPipelineRun> = {}): LastPipelineRun {
  return {
    runUid: "abc123",
    lines: [] as InterpretedLine[],
    stepReasons: [],
    isLoading: false,
    trigger: "web",
    startedAt: new Date(Date.now() - 120_000).toISOString(),
    endedAt: new Date(Date.now() - 60_000).toISOString(),
    outcome: "completed",
    totalProcessed: 3,
    totalSkipped: 78,
    ...overrides,
  };
}

/** Render the digest card inside a router (the Link needs it). */
function renderDigest(run: LastPipelineRun | null = lastRun()): void {
  render(
    <MemoryRouter>
      <LastRunDigest lastRun={run} />
    </MemoryRouter>,
  );
}

describe("LastRunDigest", () => {
  it("affiche le titre et le badge du trigger", () => {
    renderDigest();

    expect(screen.getByText("Dernier run")).toBeInTheDocument();
    // trigger "web" label is "Interface web"
    expect(screen.getByText("Interface web")).toBeInTheDocument();
  });

  it("affiche le temps relatif et le résumé des compteurs", () => {
    renderDigest();

    // Age relative — "Lancé" + "il y a N min" rendered as adjacent elements.
    expect(screen.getByText(/il y a \d+ min/)).toBeInTheDocument();
    // Counts: 3 traités · 78 ignorés
    expect(screen.getByText("3 traités · 78 ignorés")).toBeInTheDocument();
  });

  it("contient un lien vers le détail du run", () => {
    renderDigest();

    const link = screen.getByRole("link", { name: /Voir le détail/ });
    expect(link).toHaveAttribute("href", "/pipeline?run=abc123");
  });

  it("affiche un état vide quand il n'y a pas de run", () => {
    renderDigest({
      runUid: null,
      lines: [],
      stepReasons: [],
      isLoading: false,
      trigger: null,
      startedAt: null,
      endedAt: null,
      outcome: null,
      totalProcessed: 0,
      totalSkipped: 0,
    });

    expect(
      screen.getByText("Aucun run enregistré pour le moment."),
    ).toBeInTheDocument();
    // No link when there's no run.
    expect(
      screen.queryByRole("link", { name: /Voir le détail/ }),
    ).not.toBeInTheDocument();
  });

  it("affiche le détail même quand les compteurs sont à zéro", () => {
    renderDigest(
      lastRun({ totalProcessed: 0, totalSkipped: 0 }),
    );

    expect(screen.getByText("Aucune action")).toBeInTheDocument();
    // Link is still present.
    expect(
      screen.getByRole("link", { name: /Voir le détail/ }),
    ).toBeInTheDocument();
  });

  it("affiche null comme un état vide", () => {
    renderDigest(null);

    expect(
      screen.getByText("Aucun run enregistré pour le moment."),
    ).toBeInTheDocument();
  });

  it("affiche le bon libellé pour un trigger unknown", () => {
    renderDigest(lastRun({ trigger: "unknown_source" }));

    // Unknown triggers pass through verbatim.
    expect(screen.getByText("unknown_source")).toBeInTheDocument();
  });
});
