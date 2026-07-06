import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { PipelineControls } from "@/components/pipeline/PipelineControls";
import type { components } from "@/api/schema";

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

describe("PipelineControls", () => {
  it("renders the Démarrer, Pause, Reprendre, Arrêter buttons and Auto-trigger switch", () => {
    renderControls(IDLE_STATUS);

    expect(
      screen.getByRole("button", { name: /Démarrer/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Pause/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Reprendre/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Arrêter/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: /Auto-trigger/i }),
    ).toBeInTheDocument();
  });

  it("disables Pause and Reprendre when idle", () => {
    renderControls(IDLE_STATUS);
    expect(screen.getByRole("button", { name: /Pause/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Reprendre/i })).toBeDisabled();
    // Démarrer should be enabled when idle.
    expect(
      screen.getByRole("button", { name: /Démarrer/i }),
    ).not.toBeDisabled();
  });

  it("disables Démarrer and enables Pause when running", () => {
    renderControls(RUNNING_STATUS);
    expect(screen.getByRole("button", { name: /Démarrer/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Pause/i })).not.toBeDisabled();
  });

  it("enables Reprendre and disables Pause when paused", () => {
    renderControls(PAUSED_STATUS);
    expect(
      screen.getByRole("button", { name: /Reprendre/i }),
    ).not.toBeDisabled();
    expect(screen.getByRole("button", { name: /Pause/i })).toBeDisabled();
  });

  it("reflects watcher_enabled in the Switch", () => {
    renderControls(RUNNING_STATUS);
    expect(
      screen.getByRole("switch", { name: /Auto-trigger/i }),
    ).toHaveAttribute("aria-checked", "true");
  });

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

  it("opens the Kill confirmation dialog on click", () => {
    renderControls(RUNNING_STATUS);
    fireEvent.click(screen.getByRole("button", { name: /Arrêter/i }));
    expect(screen.getByText("Arrêter le pipeline ?")).toBeInTheDocument();
  });
});
