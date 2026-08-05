/**
 * OverviewPanel (provenance F5) — the « état de la machine » rollup.
 *
 * Proves the panel renders the aggregate tiles from GET /overview, deep-links the
 * actionable ones, and shows an empty state when the spine is empty.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getOverviewMock } = vi.hoisted(() => ({ getOverviewMock: vi.fn() }));

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return { ...actual, getOverview: getOverviewMock };
});

import { OverviewPanel } from "./OverviewPanel";

function renderPanel(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OverviewPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OverviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("renders the rollup tiles and deep-links the actionable ones", async () => {
    getOverviewMock.mockResolvedValue({
      by_status: { grabbed: 2, ingested: 1, scraped: 0, dispatched: 5 },
      in_flight: 3,
      stuck: 1,
      awaiting_resolution: 2,
      watcher_enabled: true,
      last_successful_run_at: 1_700_000_000,
    });
    renderPanel();

    expect(await screen.findByText("En vol")).toBeInTheDocument();
    expect(screen.getByText("Bloqués")).toBeInTheDocument();
    expect(screen.getByText("En attente de résolution")).toBeInTheDocument();
    expect(screen.getByText("Dispatchés")).toBeInTheDocument();

    // The « Bloqués » tile deep-links to the Parcours detail, FILTERED to the stuck ones.
    expect(
      screen.getByLabelText("Voir les items bloqués").closest("a"),
    ).toHaveAttribute("href", "/acquisition?tab=parcours&etape=bloques");
    // « En attente de résolution » deep-links to the decisions deck.
    expect(
      screen.getByLabelText("Voir les décisions en attente").closest("a"),
    ).toHaveAttribute("href", "/medias");
    expect(screen.getByText(/Veille active/)).toBeInTheDocument();
  });

  it("still renders tiles when the spine is empty but decisions are pending (no under-count)", async () => {
    getOverviewMock.mockResolvedValue({
      by_status: {},
      in_flight: 0,
      stuck: 0,
      awaiting_resolution: 3, // manual-drop decisions, NO spine row
      watcher_enabled: true,
      last_successful_run_at: null,
    });
    renderPanel();
    // Must NOT show the empty state — the 3 pending decisions need attention.
    expect(
      await screen.findByText("En attente de résolution"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Rien en vol")).toBeNull();
  });

  it("§12 — the whole tile is the touch target, and the four tiles share one height", async () => {
    // `<Link>` renders an `<a>`, which is `display: inline` by default: inside the
    // `grid grid-cols-2` the clickable box collapsed to the inline run of content and the
    // card never stretched to its grid track. On a phone that means aiming at a fraction
    // of the tile, next to a fourth tile (« Dispatchés », link-less) that WAS full height —
    // the ragged row the operator photographed. §12: cibles tactiles atteignables.
    getOverviewMock.mockResolvedValue({
      by_status: { grabbed: 2, ingested: 1, scraped: 0, dispatched: 5 },
      in_flight: 3,
      stuck: 1,
      awaiting_resolution: 2,
      watcher_enabled: true,
      last_successful_run_at: 1_700_000_000,
    });
    renderPanel();

    const labels = [
      "Voir les parcours en vol",
      "Voir les items bloqués",
      "Voir les décisions en attente",
    ];
    for (const label of labels) {
      const anchor = (await screen.findByLabelText(label)).closest("a");
      expect(anchor).not.toBeNull();
      // A block-level, full-height anchor: the touch target IS the card.
      expect(anchor).toHaveClass("block", "h-full");
      // …and the card really is inside that anchor, not merely beside it.
      expect(anchor?.querySelector(".ps-stat")).not.toBeNull();
    }

    // Every tile — linked or not — stretches to the grid track, so the row is even.
    const tiles = document.querySelectorAll(".ps-stat");
    expect(tiles).toHaveLength(4);
    for (const tile of tiles) {
      expect(tile).toHaveClass("h-full");
    }
  });

  it("§2/DOIT-10 — les QUATRE tuiles mènent à LEURS items, par une URL", async () => {
    // « Dispatchés » n'avait aucun lien : une tuile qui annonce 56 sans donner accès à
    // ces 56 est un cul-de-sac (NE-DOIT-PAS-9), et les trois autres pointaient vers la
    // liste ENTIÈRE — cliquer « Bloqués · 1 » ouvrait 58 cartes indifférenciées.
    getOverviewMock.mockResolvedValue({
      by_status: { grabbed: 2, ingested: 1, scraped: 0, dispatched: 56 },
      in_flight: 3,
      stuck: 1,
      awaiting_resolution: 2,
      watcher_enabled: true,
      last_successful_run_at: 1_700_000_000,
    });
    renderPanel();

    const attendus: [string, string][] = [
      ["Voir les parcours en vol", "/acquisition?tab=parcours&etape=en-vol"],
      ["Voir les items bloqués", "/acquisition?tab=parcours&etape=bloques"],
      ["Voir les décisions en attente", "/medias"],
      [
        "Voir les acquisitions rangées",
        "/acquisition?tab=parcours&etape=ranges",
      ],
    ];
    for (const [label, href] of attendus) {
      const anchor = (await screen.findByLabelText(label)).closest("a");
      expect(anchor).not.toBeNull();
      expect(anchor).toHaveAttribute("href", href);
      // La tuile entière reste la cible tactile (§12).
      expect(anchor).toHaveClass("block", "h-full");
      expect(anchor?.querySelector(".ps-stat")).not.toBeNull();
    }
  });

  it("shows an empty state when EVERY pillar is zero", async () => {
    getOverviewMock.mockResolvedValue({
      by_status: {},
      in_flight: 0,
      stuck: 0,
      awaiting_resolution: 0,
      watcher_enabled: true,
      last_successful_run_at: null,
    });
    renderPanel();
    expect(await screen.findByText("Rien en vol")).toBeInTheDocument();
  });
});
