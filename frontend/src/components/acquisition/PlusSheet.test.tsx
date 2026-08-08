/**
 * PlusSheet — the secondary acquisition surface.
 *
 * Watcher and Obligations left the tab bar to live behind « Plus ». Each panel
 * covers its own behaviour in its own test file; what is pinned HERE is that
 * both are still REACHABLE, and that the drawer says where the ranking profiles
 * went. Losing a panel from this drawer would otherwise remove a feature
 * silently — the tab that used to expose it no longer exists to notice.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlusSheet } from "./PlusSheet";

// Partial mock: only the two data hooks the panels read. Everything else in
// that module stays real, so a future panel dependency fails loudly here rather
// than silently rendering an empty drawer.
vi.mock("@/hooks/useAcquisition", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/hooks/useAcquisition")>();
  return {
    ...actual,
    useObligations: () => ({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
    }),
    useAcquisitionStatus: () => ({
      data: {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [],
        deferred: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    }),
    useTrackedAcquisitionRun: () => undefined,
  };
});

afterEach(() => {
  cleanup();
});

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderSheet(open = true): void {
  render(
    <MemoryRouter>
      <QueryClientProvider client={makeQueryClient()}>
        <PlusSheet open={open} onOpenChange={vi.fn()} />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("PlusSheet", () => {
  it("reaches both secondary surfaces — watcher and obligations, one tap deep", () => {
    // Maquette grammar: the sheet RESTS as two .sact summary rows; each
    // expands its full panel. Reachability is pinned THROUGH the tap —
    // losing a panel would still fail here.
    renderSheet();

    expect(
      screen.getByRole("heading", { name: /Veille et obligations/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Veille/ }));
    expect(screen.getByText("État du watcher")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Obligations de partage/ }),
    );
    // Text that ONLY ObligationsPanel renders. A looser matcher here silently
    // matched the drawer's own description — the assertion then survived
    // deleting the panel, which is the vacuous test this guard exists to avoid.
    expect(
      screen.getByText("Aucune obligation de seed enregistrée."),
    ).toBeInTheDocument();
  });

  it("résume la veille et les obligations avec les données réelles", () => {
    renderSheet();

    // watcher_enabled: true + no last run → active, no fake timestamp.
    expect(
      screen.getByRole("button", { name: "Veille active" }),
    ).toBeInTheDocument();
    // Zero obligations → honest zeros, maquette wording.
    expect(
      screen.getByRole("button", {
        name: "Obligations de partage · 0 en cours, 0 non respectée",
      }),
    ).toBeInTheDocument();
  });

  it("says where the ranking profiles went, rather than letting them vanish", () => {
    // They moved to the Config page. A feature that changes address must say so
    // at the address it left, or the operator concludes it was removed.
    renderSheet();

    expect(screen.getByText(/profils de\s+classement/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Config/ })).toHaveAttribute(
      "href",
      "/config?tab=classement",
    );
  });

  it("renders nothing while closed", () => {
    renderSheet(false);

    expect(
      screen.queryByRole("heading", { name: /Veille et obligations/i }),
    ).not.toBeInTheDocument();
  });
});
