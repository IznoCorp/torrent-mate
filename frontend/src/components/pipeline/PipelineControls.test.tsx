import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { PipelineControls } from "@/components/pipeline/PipelineControls";
import type { components } from "@/api/schema";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    runPipeline: vi.fn(),
  };
});

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

type StatusResponse = components["schemas"]["StatusResponse"];

/** Idle status with watcher disabled. */
const IDLE_STATUS: StatusResponse = {
  state: "idle",
  paused: false,
  watcher_enabled: false,
};

/** Running status with watcher enabled. */
const RUNNING_STATUS: StatusResponse = {
  state: "running",
  run_uid: "abc123",
  step: "scrape",
  paused: false,
  watcher_enabled: true,
};

/** Paused status. */
const PAUSED_STATUS: StatusResponse = {
  state: "paused",
  run_uid: "abc123",
  step: "scrape",
  paused: true,
  watcher_enabled: true,
};

afterEach(cleanup);

function renderControls(status: StatusResponse): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <PipelineControls status={status} />
    </QueryClientProvider>
  );
  render(tree);
}

/** Opens the "Plus d'actions" dropdown if present. */
function openDropdown(): void {
  fireEvent.pointerDown(
    screen.getByRole("button", { name: /Plus d'actions/i }),
  );
}

describe("PipelineControls", () => {
  // ---- Idle state ----

  it("renders Démarrer and Auto-trigger, hides secondary actions when idle", () => {
    renderControls(IDLE_STATUS);

    expect(
      screen.getByRole("button", { name: /Démarrer/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /Auto-trigger/i }),
    ).toBeInTheDocument();

    // Secondary actions are not visible when idle — no dropdown trigger needed.
    expect(
      screen.queryByRole("button", { name: /Pause/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Reprendre/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Arrêter/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Plus d'actions/i }),
    ).not.toBeInTheDocument();
  });

  it("Démarrer is enabled when idle", () => {
    renderControls(IDLE_STATUS);
    expect(
      screen.getByRole("button", { name: /Démarrer/i }),
    ).not.toBeDisabled();
  });

  // ---- Running state ----

  it("renders Arrêter and dropdown trigger, hides other primary actions when running", () => {
    renderControls(RUNNING_STATUS);

    expect(
      screen.getByRole("button", { name: /Arrêter/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Plus d'actions/i }),
    ).toBeInTheDocument();

    // Primary actions for other states are not visible.
    expect(
      screen.queryByRole("button", { name: /Démarrer/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Reprendre/i }),
    ).not.toBeInTheDocument();
  });

  it("dropdown contains Pause when running", () => {
    renderControls(RUNNING_STATUS);
    openDropdown();
    expect(
      screen.getByRole("menuitem", { name: /Pause/i }),
    ).toBeInTheDocument();
  });

  it("Pause in dropdown is enabled when running", () => {
    renderControls(RUNNING_STATUS);
    openDropdown();
    expect(
      screen.getByRole("menuitem", { name: /Pause/i }),
    ).not.toHaveAttribute("aria-disabled", "true");
  });

  // ---- Paused state ----

  it("renders Reprendre and dropdown trigger, hides other primary actions when paused", () => {
    renderControls(PAUSED_STATUS);

    expect(
      screen.getByRole("button", { name: /Reprendre/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Plus d'actions/i }),
    ).toBeInTheDocument();

    // Primary actions for other states are not visible.
    expect(
      screen.queryByRole("button", { name: /Démarrer/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Pause/i }),
    ).not.toBeInTheDocument();
  });

  it("Reprendre is enabled when paused", () => {
    renderControls(PAUSED_STATUS);
    expect(
      screen.getByRole("button", { name: /Reprendre/i }),
    ).not.toBeDisabled();
  });

  it("dropdown contains Arrêter when paused", () => {
    renderControls(PAUSED_STATUS);
    openDropdown();
    expect(
      screen.getByRole("menuitem", { name: /Arrêter/i }),
    ).toBeInTheDocument();
  });

  // ---- Watcher switch ----

  it("reflects watcher_enabled in the Switch", () => {
    renderControls(RUNNING_STATUS);
    expect(
      screen.getByRole("switch", { name: /Auto-trigger/i }),
    ).toHaveAttribute("aria-checked", "true");
  });

  it("Auto-trigger switch is visible in every state", () => {
    renderControls(IDLE_STATUS);
    expect(
      screen.getByRole("switch", { name: /Auto-trigger/i }),
    ).toBeInTheDocument();

    cleanup();
    renderControls(RUNNING_STATUS);
    expect(
      screen.getByRole("switch", { name: /Auto-trigger/i }),
    ).toBeInTheDocument();

    cleanup();
    renderControls(PAUSED_STATUS);
    expect(
      screen.getByRole("switch", { name: /Auto-trigger/i }),
    ).toBeInTheDocument();
  });

  // ---- Dialogs ----

  it("opens the Démarrer dialog on click", () => {
    renderControls(IDLE_STATUS);
    fireEvent.click(screen.getByRole("button", { name: /Démarrer/i }));
    // The dialog title should be visible.
    expect(screen.getByText("Démarrer le pipeline")).toBeInTheDocument();
    // The dry-run switch inside the dialog.
    expect(
      screen.getByRole("switch", { name: /Dry-run/i }),
    ).toBeInTheDocument();
  });

  it("opens the Kill confirmation dialog on Arrêter click (running primary)", () => {
    renderControls(RUNNING_STATUS);
    fireEvent.click(screen.getByRole("button", { name: /Arrêter/i }));
    expect(screen.getByText("Arrêter le pipeline ?")).toBeInTheDocument();
  });

  it("opens the Kill confirmation dialog on Arrêter menu item click (paused dropdown)", () => {
    renderControls(PAUSED_STATUS);
    openDropdown();
    fireEvent.click(screen.getByRole("menuitem", { name: /Arrêter/i }));
    expect(screen.getByText("Arrêter le pipeline ?")).toBeInTheDocument();
  });

  // ---- Mutations (toasts, §6 queue) ----

  it("shows the backend error detail on a duplicate run (409)", async () => {
    // Arrange: stub runPipeline to reject with the French duplicate 409 (§6 —
    // the only refusal left is another PIPELINE run already in flight).
    const mod = await import("@/api/client");
    const mockedRun = mod.runPipeline as ReturnType<typeof vi.fn>;
    mockedRun.mockRejectedValueOnce(
      new ApiError(
        409,
        "Un run du pipeline est déjà en cours — relancer serait un doublon.",
      ),
    );

    vi.mocked(toast.error).mockClear();

    renderControls(IDLE_STATUS);

    // Open the run dialog.
    fireEvent.click(screen.getByRole("button", { name: /Démarrer/i }));
    expect(screen.getByText("Démarrer le pipeline")).toBeInTheDocument();

    // Click the confirmation button inside the dialog.
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Démarrer/i }));

    // Assert: the backend detail surfaced via toast.error.
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Un run du pipeline est déjà en cours — relancer serait un doublon.",
      );
    });

    // The dialog stays open so the user sees the error and can retry.
    expect(screen.getByText("Démarrer le pipeline")).toBeInTheDocument();
  });

  it("announces the visible queue when the launch is queued (§6)", async () => {
    // Arrange: the backend accepted (202) but a maintenance run holds the
    // lock — the launch waits in the visible pipeline-queue.
    const mod = await import("@/api/client");
    const mockedRun = mod.runPipeline as ReturnType<typeof vi.fn>;
    mockedRun.mockResolvedValueOnce({ run_uid: "queued123", queued: true });

    vi.mocked(toast.info).mockClear();
    vi.mocked(toast.error).mockClear();

    renderControls(IDLE_STATUS);

    fireEvent.click(screen.getByRole("button", { name: /Démarrer/i }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Démarrer/i }));

    await waitFor(() => {
      expect(toast.info).toHaveBeenCalledWith(
        "En file — un run de maintenance tient le verrou ; le pipeline démarrera à sa libération.",
      );
    });
    expect(toast.error).not.toHaveBeenCalled();
  });
});
