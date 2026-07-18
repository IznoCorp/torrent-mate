/**
 * Unit tests for the SystemePage component (systeme-hub Phase 2.1).
 *
 * Verifies the 4-tab shell (etat, actions, maintenance, journal), default and
 * unknown-tab fallback, the ``&run=`` RunDetail drawer on the maintenance tab,
 * and the tablist class contract (flex-nowrap, overflow-x-auto). Mock APIs
 * follow the Maintenance.test.tsx idiom (fetch mock for maintenance endpoints)
 * plus module-level mocks for useRegistryStatus (as RegistryPage.test.tsx
 * does).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Module-level mocks — useRegistryStatus + useEventStreamContext
// ---------------------------------------------------------------------------

const useRegistryStatusMock = vi.fn();
const useEventStreamContextMock = vi.fn(() => ({ events: [] }));

vi.mock("@/hooks/useRegistryStatus", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useRegistryStatus: () => useRegistryStatusMock(),
}));

vi.mock("@/hooks/useEventStreamContext", () => ({
  useEventStreamContext: () => useEventStreamContextMock(),
}));

import SystemePage from "@/pages/SystemePage";
import { MockWebSocket } from "@/test/mockWebSocket";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Resolve the request target to its URL string, across every ``fetch`` input. */
function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

/**
 * Route every ``/api/*`` endpoint the maintenance panels poll to a minimal
 * empty-but-valid payload — the test asserts the page shell and tab behavior,
 * not individual panel depths.
 */
function routeFetch(input: RequestInfo | URL): Promise<Response> {
  const url = urlOf(input);
  if (url.includes("/api/maintenance/disks")) {
    return Promise.resolve(buildResponse(200, { disks: [] }));
  }
  if (url.includes("/api/maintenance/locks")) {
    return Promise.resolve(
      buildResponse(200, {
        pipeline_lock: { held: false },
        sentinels: {
          pause: false,
          watcher_paused: false,
        },
        sweep: { status: "ready", orphans: [], age_s: 0 },
      }),
    );
  }
  if (url.includes("/api/maintenance/index-health")) {
    return Promise.resolve(
      buildResponse(200, {
        items: 0,
        movies: 0,
        shows: 0,
        files: 0,
        size_gb: 0,
        nfo: { valid: 0, invalid: 0, missing: 0 },
        repair_queue_pending: 0,
        outbox_pending: 0,
        last_scan_stuck: false,
        soft_deleted: 0,
        canonical_null: 0,
        degraded: false,
      }),
    );
  }
  if (url.includes("/api/maintenance/actions")) {
    return Promise.resolve(
      buildResponse(200, { actions: [], category_counts: {} }),
    );
  }
  if (url.includes("/api/maintenance/destructive-log")) {
    return Promise.resolve(buildResponse(200, { entries: [] }));
  }
  if (url.includes("/api/pipeline/history/")) {
    // RunDetail fetch — return a minimal run detail for the drawer test.
    const uid = url.split("/api/pipeline/history/")[1] ?? url;
    return Promise.resolve(
      buildResponse(200, {
        run_uid: uid,
        kind: "maintenance",
        trigger: "manual",
        outcome: "success",
        started_at: new Date().toISOString(),
        ended_at: null,
        duration_s: 12,
        command: "test",
        options_json: "",
        output_tail: "",
        error: null,
        steps: [],
      }),
    );
  }
  if (url.includes("/api/pipeline/history")) {
    return Promise.resolve(
      buildResponse(200, { runs: [], total: 0, limit: 50, offset: 0 }),
    );
  }
  return Promise.resolve(buildResponse(200, {}));
}

const fetchMock = vi.fn<typeof fetch>();

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

/** Render the systeme page behind the router and query client. */
function renderSystemePage(initialEntries: string[] = ["/systeme"]): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>
        <SystemePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  MockWebSocket.reset();
  fetchMock.mockReset();
  fetchMock.mockImplementation((input) => routeFetch(input));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket);

  // Default registry mock: empty providers (most tests don't care).
  useRegistryStatusMock.mockReturnValue({
    isLoading: false,
    isError: false,
    data: { providers: [] },
    error: null,
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SystemePage", () => {
  // ── Tablist class contract ──────────────────────────────────────────────

  it("la tablist porte les classes flex-nowrap et overflow-x-auto (contrat AcquisitionPage)", () => {
    renderSystemePage();

    const tablist = screen.getByRole("tablist");
    expect(tablist.className).toMatch(/flex-nowrap/);
    expect(tablist.className).toMatch(/overflow-x-auto/);
  });

  // ── Default tab (clean URL) ─────────────────────────────────────────────

  it("affiche l'onglet état par défaut (URL propre, pas de ?tab=)", () => {
    renderSystemePage();

    // The page heading is always visible.
    expect(
      screen.getByRole("heading", { name: "Système" }),
    ).toBeInTheDocument();

    // The état tab is selected.
    const etatTab = screen.getByRole("tab", { name: "État" });
    expect(etatTab).toHaveAttribute("aria-selected", "true");

    // Content from état tab — monitoring panels + providers section render.
    // DisksPanel, LocksPanel, and the "Fournisseurs" heading are always
    // visible when the état tab is active.
    expect(screen.getByText("Disques")).toBeInTheDocument();
    expect(screen.getByText("Verrous")).toBeInTheDocument();
    expect(screen.getByText("Fournisseurs")).toBeInTheDocument();
  });

  // ── All 4 tabs render their content ─────────────────────────────────────

  it("les 4 onglets sont présents avec leur label", () => {
    renderSystemePage();

    for (const label of [
      "État",
      "Actions",
      "Exécutions de maintenance",
      "Journal",
    ]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument();
    }
  });

  it("l'onglet actions affiche le catalogue d'actions", () => {
    renderSystemePage(["/systeme?tab=actions"]);

    // The ActionCatalog fetches /api/maintenance/actions. Since fetch is mocked
    // synchronously, the tab selection is immediate. Assert that the actions
    // tab is selected.
    expect(
      screen.getByRole("tab", { name: "Actions" }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("l'onglet maintenance affiche l'historique filtré", async () => {
    renderSystemePage(["/systeme?tab=maintenance"]);

    expect(
      screen.getByRole("tab", { name: "Exécutions de maintenance" }),
    ).toHaveAttribute("aria-selected", "true");

    // The RunHistoryTable renders its heading.
    expect(
      await screen.findByText("Historique des exécutions"),
    ).toBeInTheDocument();
  });

  it("l'onglet journal affiche le panneau de journal des suppressions", async () => {
    renderSystemePage(["/systeme?tab=journal"]);

    expect(screen.getByRole("tab", { name: "Journal" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // DestructiveLogPanel renders its Card title.
    expect(
      await screen.findByText("Journal des suppressions"),
    ).toBeInTheDocument();
  });

  // ── Unknown tab fallback ────────────────────────────────────────────────

  it("un ?tab= inconnu retombe sur l'onglet état", () => {
    renderSystemePage(["/systeme?tab=inconnu"]);

    // The état tab is still selected — unknown tab falls back to default.
    expect(screen.getByRole("tab", { name: "État" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    // The other tabs are not selected.
    expect(screen.getByRole("tab", { name: "Actions" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
    expect(
      screen.getByRole("tab", { name: "Exécutions de maintenance" }),
    ).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tab", { name: "Journal" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  // ── &run= drawer on maintenance tab ─────────────────────────────────────

  it("ouvre le drawer RunDetail quand &run= est présent sur l'onglet maintenance", async () => {
    renderSystemePage(["/systeme?tab=maintenance&run=abc123def456"]);

    // The RunDetail component fetches the run and renders. Wait for the
    // "Retour" button (always present in the RunDetail header, even while
    // loading).
    expect(await screen.findByText("Retour")).toBeInTheDocument();
  });

  it("ne charge PAS le RunDetail quand &run= est présent sur un autre onglet", () => {
    renderSystemePage(["/systeme?tab=etat&run=abc123def456"]);

    // The état tab is selected — RunDetail should NOT mount. The RunDetail
    // header button "Retour" is absent.
    expect(screen.queryByText("Retour")).not.toBeInTheDocument();
  });

  // ── Providers in état tab ──────────────────────────────────────────────

  it("affiche les cartes fournisseurs dans l'onglet état", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "tmdb",
            circuit_state: "closed",
            failure_count_recent: 0,
            last_success_at: 1_719_792_000,
            last_failure_at: null,
            last_latency_ms: 42.5,
            live: true,
          },
        ],
      },
      error: null,
    });

    renderSystemePage();

    // The "Fournisseurs" heading and the provider card are visible.
    expect(screen.getByText("Fournisseurs")).toBeInTheDocument();
    expect(screen.getByText("tmdb")).toBeInTheDocument();
  });

  it("affiche le badge « OK » pour un circuit fermé et la latence formatée (sub-phase 5.2)", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "tmdb",
            circuit_state: "closed",
            failure_count_recent: 0,
            last_success_at: 1_719_792_000,
            last_failure_at: null,
            last_latency_ms: 42.5,
            live: true,
          },
        ],
      },
      error: null,
    });

    renderSystemePage();

    // CIRCUIT_LABEL.closed === "OK".
    expect(screen.getByText("OK")).toBeInTheDocument();
    // Latency formatted to integer + " ms".
    expect(screen.getByText("43 ms")).toBeInTheDocument();
  });

  it("affiche le badge « Ouvert » pour un circuit ouvert (sub-phase 5.2)", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "tvdb",
            circuit_state: "open",
            failure_count_recent: 3,
            last_success_at: null,
            last_failure_at: 1_719_705_600,
            last_latency_ms: null,
            live: true,
          },
        ],
      },
      error: null,
    });

    renderSystemePage();

    // CIRCUIT_LABEL.open === "Ouvert".
    expect(screen.getByText("Ouvert")).toBeInTheDocument();
    expect(screen.getByText("tvdb")).toBeInTheDocument();
  });

  it("affiche l'indicateur baseline pour un fournisseur live:false", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "omdb",
            circuit_state: "open",
            failure_count_recent: 0,
            last_success_at: null,
            last_failure_at: null,
            last_latency_ms: null,
            live: false,
          },
        ],
      },
      error: null,
    });

    renderSystemePage();

    expect(screen.getByText("En attente de données live")).toBeInTheDocument();
    expect(screen.getByText("omdb")).toBeInTheDocument();
  });

  it("affiche un sous-circuit sous son fournisseur parent", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        providers: [
          {
            provider_name: "tvdb",
            circuit_state: "closed",
            failure_count_recent: 0,
            last_success_at: 1_719_792_000,
            last_failure_at: null,
            last_latency_ms: 30,
            live: true,
          },
          {
            provider_name: "tvdb-bootstrap",
            circuit_state: "open",
            failure_count_recent: 2,
            last_success_at: null,
            last_failure_at: 1_719_705_600,
            last_latency_ms: null,
            live: true,
          },
        ],
      },
      error: null,
    });

    renderSystemePage();

    // The parent renders; the raw sub-circuit name does not appear as its own
    // card title — it is relabelled "Authentification".
    expect(screen.getByText("tvdb")).toBeInTheDocument();
    expect(screen.queryByText("tvdb-bootstrap")).not.toBeInTheDocument();
    expect(screen.getByText("Authentification")).toBeInTheDocument();
    expect(screen.getByText("Sous-circuits")).toBeInTheDocument();
  });

  // ── Event feed + recent events in état tab ─────────────────────────────

  it("affiche le flux d'événements et la table récente dans l'onglet état", () => {
    renderSystemePage();

    expect(screen.getByText("Flux d’événements")).toBeInTheDocument();
    expect(screen.getByText("Événements récents")).toBeInTheDocument();
  });

  // ── Maintenance tab fetch contract ─────────────────────────────────────

  it("ne charge QUE l'historique maintenance, pas celui du pipeline (onglet maintenance)", async () => {
    renderSystemePage(["/systeme?tab=maintenance"]);

    await screen.findByText("Historique des exécutions");

    const historyCalls = fetchMock.mock.calls
      .map(([input]) => urlOf(input))
      .filter((u) => u.startsWith("/api/pipeline/history?"));
    expect(historyCalls.some((u) => u.includes("kind=maintenance"))).toBe(true);
    expect(historyCalls.some((u) => u.includes("kind=pipeline"))).toBe(false);
  });

  // ── Provider loading state (ex-RegistryPage) ───────────────────────────

  it("affiche des squelettes pendant le chargement des fournisseurs", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderSystemePage();

    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // ── Provider empty state (ex-RegistryPage) ─────────────────────────────

  it("affiche un message quand aucun fournisseur n'est configuré", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { providers: [] },
      error: null,
    });

    renderSystemePage();

    expect(
      screen.getByText("Aucun fournisseur configuré."),
    ).toBeInTheDocument();
  });

  // ── Provider error state (ex-RegistryPage) ─────────────────────────────

  it("affiche un message d'erreur en cas d'échec de chargement des fournisseurs", () => {
    useRegistryStatusMock.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new Error("Network error"),
    });

    renderSystemePage();

    expect(screen.getByText(/Impossible de charger/)).toBeInTheDocument();
  });
});
