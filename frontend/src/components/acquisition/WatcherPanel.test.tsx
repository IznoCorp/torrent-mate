/**
 * WatcherPanel — §5 guard tests: the manual "Détecter maintenant" trigger must
 * NOT toast success on the 202; it tracks the run to its numeric result and
 * toasts only once the run has actually ended (« un toast de succès sur un run
 * mort est interdit »).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const {
  toastSuccess,
  toastInfo,
  toastError,
  triggerDetectMock,
  setWatcherMock,
} = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastInfo: vi.fn(),
  toastError: vi.fn(),
  triggerDetectMock: vi.fn(),
  setWatcherMock: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: toastSuccess, info: toastInfo, error: toastError },
}));

vi.mock("@/api/acquisition", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/acquisition")>(
      "@/api/acquisition",
    );
  return {
    ...actual,
    triggerDetect: (): Promise<{ run_uid: string }> =>
      triggerDetectMock() as Promise<{ run_uid: string }>,
  };
});

vi.mock("@/api/pipeline", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/pipeline")>("@/api/pipeline");
  return {
    ...actual,
    setWatcher: (body: { enabled: boolean }): Promise<unknown> =>
      setWatcherMock(body) as Promise<unknown>,
  };
});

import { WatcherPanel } from "./WatcherPanel";
import * as hooks from "@/hooks/useAcquisition";

function renderPanel(): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <WatcherPanel />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("WatcherPanel — §5 detect trigger", () => {
  it("does NOT toast success on the 202, only 'lancée'", async () => {
    vi.spyOn(hooks, "useAcquisitionStatus").mockReturnValue({
      data: {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [],
        deferred: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    // The run is still running (no ended_at) → no success toast yet.
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockReturnValue(undefined);
    triggerDetectMock.mockResolvedValue({ run_uid: "run-1" });

    renderPanel();
    fireEvent.click(
      screen.getByRole("button", { name: /Détecter maintenant/ }),
    );

    await waitFor(() => {
      expect(triggerDetectMock).toHaveBeenCalledTimes(1);
    });
    expect(toastInfo).toHaveBeenCalledWith("Détection lancée…");
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("toasts the NUMERIC result once the tracked run ends", async () => {
    vi.spyOn(hooks, "useAcquisitionStatus").mockReturnValue({
      data: {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [],
        deferred: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    // Once a run is tracked, the hook reports it ENDED with a numeric result.
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockImplementation((runUid) =>
      runUid == null
        ? undefined
        : {
            run_uid: runUid,
            started_at: 1,
            ended_at: 2,
            outcome: "success",
            command: "follow-detect",
            trigger: "web",
            result: { detected: 3, enqueued: 2 },
          },
    );
    triggerDetectMock.mockResolvedValue({ run_uid: "run-1" });

    renderPanel();
    fireEvent.click(
      screen.getByRole("button", { name: /Détecter maintenant/ }),
    );

    // The success toast carries the numeric result, never a bare "lancée".
    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalledWith(
        expect.stringContaining("3 détecté(s), 2 mis en file"),
      );
    });
  });
});

// ---------------------------------------------------------------------------
// Recent-run badge assertions (sub-phase 5.2)
// ---------------------------------------------------------------------------

describe("WatcherPanel — toggle feedback (X3)", () => {
  function mockStatus(): void {
    vi.spyOn(hooks, "useAcquisitionStatus").mockReturnValue({
      data: {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [],
        deferred: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockReturnValue(undefined);
  }

  it("toasts the new state when the toggle write lands", async () => {
    mockStatus();
    setWatcherMock.mockResolvedValue({});

    renderPanel();
    fireEvent.click(screen.getByRole("switch", { name: /Activé/ }));

    await waitFor(() => {
      expect(setWatcherMock).toHaveBeenCalledWith({ enabled: false });
    });
    expect(toastSuccess).toHaveBeenCalledWith("Watcher désactivé.");
  });

  it("toasts an error when the toggle write fails (no silent snap-back)", async () => {
    mockStatus();
    setWatcherMock.mockRejectedValue(new Error("boom"));

    renderPanel();
    fireEvent.click(screen.getByRole("switch", { name: /Activé/ }));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith(
        "Impossible de désactiver le watcher.",
      );
    });
    expect(toastSuccess).not.toHaveBeenCalled();
  });
});

describe("WatcherPanel — recent-run outcome badges (sub-phase 5.2)", () => {
  it("affiche « Échec » pour un run récent en erreur", () => {
    vi.spyOn(hooks, "useAcquisitionStatus").mockReturnValue({
      data: {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [
          {
            run_uid: "err-run-1",
            command: "follow-detect",
            started_at: 1_720_000_000,
            ended_at: 1_720_000_010,
            outcome: "error",
            result: null,
          },
        ],
        deferred: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockReturnValue(undefined);

    renderPanel();

    // The unified OUTCOME_LABEL maps error → "Échec" (NOT "Erreur").
    expect(screen.getByText("Échec")).toBeInTheDocument();
  });

  it("ne rend jamais un outcome inconnu brut — français + brut en title (X7)", () => {
    vi.spyOn(hooks, "useAcquisitionStatus").mockReturnValue({
      data: {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [
          {
            run_uid: "weird-run-1",
            command: "follow-detect",
            started_at: 1_720_000_000,
            ended_at: 1_720_000_010,
            outcome: "weird_new_outcome",
            result: null,
          },
        ],
        deferred: [{ name: "Some.Torrent", reason: "weird_new_reason" }],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockReturnValue(undefined);

    renderPanel();

    // Unknown outcome: French fallback, raw token only in the title.
    expect(screen.queryByText("weird_new_outcome")).not.toBeInTheDocument();
    const badge = screen.getByText("État inconnu");
    expect(badge.closest("[title]")).toHaveAttribute(
      "title",
      "weird_new_outcome",
    );

    // Unknown deferral reason: same contract.
    expect(screen.queryByText(/weird_new_reason/)).not.toBeInTheDocument();
    const reason = screen.getByText(/raison inconnue/);
    expect(reason.closest("[title]")).toHaveAttribute(
      "title",
      "weird_new_reason",
    );
  });
});

describe("WatcherPanel — repli mobile de la colonne Résultat (ACQUISITION-4, ticket 250)", () => {
  // Mobile-truth rule: structural class-presence check only — jsdom does not
  // lay out; the 390px proof happens post-deploy in Chrome.
  it("la colonne Résultat porte hidden md:table-cell (en-tête et cellule)", () => {
    // This file has no global auto-cleanup — drop the previous tests' DOM so
    // the single-table queries below stay unambiguous.
    cleanup();
    vi.spyOn(hooks, "useAcquisitionStatus").mockReturnValue({
      data: {
        watcher_enabled: true,
        last_successful_run_at: null,
        recent_runs: [
          {
            run_uid: "ok-run-1",
            command: "follow-detect",
            started_at: 1_720_000_000,
            ended_at: 1_720_000_010,
            outcome: "success",
            result: null,
          },
        ],
        deferred: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockReturnValue(undefined);

    renderPanel();

    const th = screen.getByRole("columnheader", { name: "Résultat" });
    expect(th.className).toContain("hidden");
    expect(th.className).toContain("md:table-cell");
    // The matching data cell collapses with it.
    const cell = document.querySelector("td.hidden");
    expect(cell).not.toBeNull();
    expect(cell?.className).toContain("md:table-cell");

    // The always-visible columns carry no collapse class.
    for (const name of ["Type", "Démarré", "État"]) {
      const head = screen.getByRole("columnheader", { name });
      expect(head.className).not.toContain("hidden");
    }
  });
});
