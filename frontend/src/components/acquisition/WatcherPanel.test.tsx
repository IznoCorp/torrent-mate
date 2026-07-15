/**
 * WatcherPanel — §5 guard tests: the manual "Détecter maintenant" trigger must
 * NOT toast success on the 202; it tracks the run to its numeric result and
 * toasts only once the run has actually ended (« un toast de succès sur un run
 * mort est interdit »).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { toastSuccess, toastInfo, toastError, triggerDetectMock } = vi.hoisted(
  () => ({
    toastSuccess: vi.fn(),
    toastInfo: vi.fn(),
    toastError: vi.fn(),
    triggerDetectMock: vi.fn(),
  }),
);

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

vi.mock("@/api/client", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, setWatcher: vi.fn() };
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
      data: { watcher_enabled: true, last_successful_run_at: null, recent_runs: [], deferred: [] },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    // The run is still running (no ended_at) → no success toast yet.
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockReturnValue(undefined);
    triggerDetectMock.mockResolvedValue({ run_uid: "run-1" });

    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /Détecter maintenant/ }));

    await waitFor(() => {
      expect(triggerDetectMock).toHaveBeenCalledTimes(1);
    });
    expect(toastInfo).toHaveBeenCalledWith("Détection lancée…");
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("toasts the NUMERIC result once the tracked run ends", async () => {
    vi.spyOn(hooks, "useAcquisitionStatus").mockReturnValue({
      data: { watcher_enabled: true, last_successful_run_at: null, recent_runs: [], deferred: [] },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof hooks.useAcquisitionStatus>);
    // Once a run is tracked, the hook reports it ENDED with a numeric result.
    vi.spyOn(hooks, "useTrackedAcquisitionRun").mockImplementation((runUid) =>
      runUid == null
        ? undefined
        : ({
            run_uid: runUid,
            started_at: 1,
            ended_at: 2,
            outcome: "success",
            command: "follow-detect",
            trigger: "web",
            result: { detected: 3, enqueued: 2 },
          }),
    );
    triggerDetectMock.mockResolvedValue({ run_uid: "run-1" });

    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /Détecter maintenant/ }));

    // The success toast carries the numeric result, never a bare "lancée".
    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalledWith(
        expect.stringContaining("3 détecté(s), 2 mis en file"),
      );
    });
  });
});
