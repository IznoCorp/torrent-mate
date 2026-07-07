import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LocksPanel } from "@/components/maintenance/LocksPanel";

import type { LocksResponse } from "@/api/client";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function makeLockState(
  overrides: Partial<{
    held: boolean;
    pid: number | null;
    pid_alive: boolean;
    stale: boolean;
    age_s: number | null;
  }> = {},
): LocksResponse["pipeline_lock"] {
  return {
    held: false,
    pid: null,
    pid_alive: false,
    stale: false,
    age_s: null,
    ...overrides,
  };
}

function makeSentinels(
  overrides: Partial<{
    pause: boolean;
    pause_age_s: number | null;
    watcher_paused: boolean;
    watcher_paused_age_s: number | null;
  }> = {},
): LocksResponse["sentinels"] {
  return {
    pause: false,
    pause_age_s: null,
    watcher_paused: false,
    watcher_paused_age_s: null,
    ...overrides,
  };
}

function makeLocksResponse(
  overrides: Partial<{
    pipeline_lock: LocksResponse["pipeline_lock"];
    sentinels: LocksResponse["sentinels"];
    tmp_orphans: LocksResponse["tmp_orphans"];
  }> = {},
): LocksResponse {
  return {
    pipeline_lock: makeLockState(),
    sentinels: makeSentinels(),
    tmp_orphans: [],
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
    getLocks: vi.fn(),
  };
});

async function mockGetLocks() {
  const mod = await import("@/api/client");
  return mod.getLocks as ReturnType<typeof vi.fn>;
}

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <LocksPanel />
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

describe("LocksPanel", () => {
  it("affiche l'état de chargement", async () => {
    const fn = await mockGetLocks();
    fn.mockReturnValue(new Promise<never>(() => undefined));
    renderPanel();
    expect(
      screen.getByText("Chargement des verrous…"),
    ).toBeInTheDocument();
  });

  it("affiche l'état d'erreur", async () => {
    const fn = await mockGetLocks();
    fn.mockRejectedValue(new Error("boom"));
    renderPanel();

    expect(
      await screen.findByText("Erreur lors du chargement."),
    ).toBeInTheDocument();
  });

  it("affiche 'Libre' quand le verrou n'est pas tenu", async () => {
    const fn = await mockGetLocks();
    fn.mockResolvedValue(makeLocksResponse());
    renderPanel();

    expect(await screen.findByText("Pipeline lock")).toBeInTheDocument();
    expect(screen.getByText("Libre")).toBeInTheDocument();
  });

  it("affiche 'Pris' avec le PID quand le verrou est tenu par un processus vivant", async () => {
    const fn = await mockGetLocks();
    fn.mockResolvedValue(
      makeLocksResponse({
        pipeline_lock: makeLockState({ held: true, pid: 12345, pid_alive: true }),
      }),
    );
    renderPanel();

    expect(await screen.findByText("Pris — PID 12345")).toBeInTheDocument();
  });

  it("affiche 'Verrou obsolète' quand le verrou est stale", async () => {
    const fn = await mockGetLocks();
    fn.mockResolvedValue(
      makeLocksResponse({
        pipeline_lock: makeLockState({ held: true, pid: 99999, pid_alive: false, stale: true }),
      }),
    );
    renderPanel();

    expect(await screen.findByText("Verrou obsolète")).toBeInTheDocument();
  });

  it("affiche les sentinelles avec leur âge", async () => {
    const fn = await mockGetLocks();
    fn.mockResolvedValue(
      makeLocksResponse({
        sentinels: makeSentinels({ pause: true, pause_age_s: 3600, watcher_paused: true, watcher_paused_age_s: 120 }),
      }),
    );
    renderPanel();

    await screen.findByText("Sentinelles");
    expect(screen.getByText(/Activée.*1 h 00 min/)).toBeInTheDocument();
    expect(screen.getByText(/Désactivé.*2 min/)).toBeInTheDocument();
  });

  it("affiche les sentinelles inactives", async () => {
    const fn = await mockGetLocks();
    fn.mockResolvedValue(makeLocksResponse());
    renderPanel();

    await screen.findByText("Sentinelles");
    expect(screen.getByText("Inactive")).toBeInTheDocument();
    expect(screen.getByText("Actif")).toBeInTheDocument();
  });

  it("affiche le décompte d'orphelins et permet l'expansion", async () => {
    const fn = await mockGetLocks();
    fn.mockResolvedValue(
      makeLocksResponse({
        tmp_orphans: [
          { path: "/tmp/_tmp_dispatch_abc", prefix: "_tmp_dispatch_", age_s: 300 },
          { path: "/tmp/_tmp_ingest_xyz", prefix: "_tmp_ingest_", age_s: 600 },
        ],
      }),
    );
    renderPanel();

    const toggle = await screen.findByText("Orphelins tmp (2)");
    expect(toggle).toBeInTheDocument();

    // Expand the orphans list.
    fireEvent.click(toggle);
    expect(screen.getByText(/_tmp_dispatch_abc/)).toBeInTheDocument();
    expect(screen.getByText(/_tmp_ingest_xyz/)).toBeInTheDocument();
    expect(screen.getByText("— 5 min")).toBeInTheDocument();
    expect(screen.getByText("— 10 min")).toBeInTheDocument();
  });

  it("affiche 'Aucun' dans la liste d'orphelins vide", async () => {
    const fn = await mockGetLocks();
    fn.mockResolvedValue(makeLocksResponse());
    renderPanel();

    const toggle = await screen.findByText("Orphelins tmp (0)");
    fireEvent.click(toggle);
    expect(screen.getByText("Aucun.")).toBeInTheDocument();
  });
});
