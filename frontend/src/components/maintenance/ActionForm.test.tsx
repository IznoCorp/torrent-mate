import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ActionForm } from "@/components/maintenance/ActionForm";
import { Dialog, DialogContent } from "@/components/ui/dialog";

import { ApiError } from "@/api/client";
import type { MaintenanceAction, RunDetail } from "@/api/client";
import type { EventMessage } from "@/api/events";
import type { EventStreamState } from "@/hooks/useEventStream";
import { EventStreamContext } from "@/hooks/useEventStreamContext";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

type ActionOption = MaintenanceAction["options"][number];

function makeOption(overrides: Partial<ActionOption> = {}): ActionOption {
  return {
    name: "opt",
    type: "str",
    required: false,
    label: "Option",
    help: "Aide",
    default: null,
    enum_values: null,
    ...overrides,
  };
}

function makeAction(
  overrides: Partial<MaintenanceAction> = {},
): MaintenanceAction {
  return {
    id: "library-test",
    title: "Action test",
    description: "Description de test",
    category: "fix",
    risk: "write",
    long_running: false,
    dry_run: "unsupported",
    options: [],
    ...overrides,
  };
}

/** Build a complete {@link RunDetail} for a maintenance run, with overrides. */
function makeRunDetail(overrides: Partial<RunDetail> = {}): RunDetail {
  return {
    run_uid: "uid-1",
    trigger: "web",
    dry_run: false,
    started_at: "2026-07-06T10:00:00Z",
    ended_at: null,
    outcome: "running",
    duration_s: null,
    steps: [],
    error: null,
    kind: "maintenance",
    command: "library-test",
    options_json: null,
    output_tail: null,
    ...overrides,
  };
}

/** Build an ``EventMessage`` with a stream-id timestamp prefix. */
function makeEvent(
  ms: number,
  type: string,
  data?: Record<string, unknown>,
): EventMessage {
  return { id: `${String(ms)}-0`, type, data: data ?? {} };
}

/** A connected event-stream state carrying the given events. */
function makeStreamState(events: EventMessage[]): EventStreamState {
  return {
    events,
    connectionState: "connected",
    buildCommit: "abc1234",
    lastEventId: events[events.length - 1]?.id ?? null,
  };
}

// ---------------------------------------------------------------------------
// Mock the client module (runMaintenanceAction + getPipelineRunDetail)
// ---------------------------------------------------------------------------

vi.mock("@/api/client", async () => {
  const actual =
    await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    runMaintenanceAction: vi.fn(),
    getPipelineRunDetail: vi.fn(),
  };
});

async function mockRun() {
  const mod = await import("@/api/client");
  return mod.runMaintenanceAction as ReturnType<typeof vi.fn>;
}

async function mockDetail() {
  const mod = await import("@/api/client");
  return mod.getPipelineRunDetail as ReturnType<typeof vi.fn>;
}

function renderForm(
  action: MaintenanceAction,
  events: EventMessage[] = [],
): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <EventStreamContext.Provider value={makeStreamState(events)}>
        <Dialog open>
          <DialogContent>
            <ActionForm action={action} onClose={vi.fn()} />
          </DialogContent>
        </Dialog>
      </EventStreamContext.Provider>
    </QueryClientProvider>
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(async () => {
  vi.clearAllMocks();
  // jsdom does not implement scrollTo — RunLogFeed auto-scrolls, so stub it.
  Object.defineProperty(Element.prototype, "scrollTo", {
    value: vi.fn(),
    writable: true,
    configurable: true,
  });
  // Default: the polled run detail reports a still-running run (no output tail),
  // so the durable fallback stays hidden unless a test overrides the outcome.
  const detail = await mockDetail();
  detail.mockResolvedValue(makeRunDetail());
});

afterEach(cleanup);

describe("ActionForm — field generation", () => {
  it("génère un contrôle par type d'option", () => {
    renderForm(
      makeAction({
        dry_run: "unsupported",
        options: [
          makeOption({
            name: "title",
            type: "str",
            label: "Titre",
            help: "aide titre",
          }),
          makeOption({
            name: "count",
            type: "int",
            label: "Nombre",
            help: "aide nombre",
          }),
          makeOption({
            name: "force",
            type: "bool",
            label: "Forcer",
            help: "aide forcer",
            default: false,
          }),
          makeOption({
            name: "mode",
            type: "enum",
            label: "Mode",
            help: "aide mode",
            enum_values: ["quick", "full"],
          }),
        ],
      }),
    );

    // str → text input
    expect(screen.getByLabelText("Titre")).toHaveAttribute("type", "text");
    // int → number input
    expect(screen.getByLabelText("Nombre")).toHaveAttribute("type", "number");
    // bool → switch
    expect(screen.getByRole("switch", { name: "Forcer" })).toBeInTheDocument();
    // enum → select trigger (combobox)
    expect(screen.getByRole("combobox", { name: "Mode" })).toBeInTheDocument();
    // inline help text
    expect(screen.getByText("aide titre")).toBeInTheDocument();
    expect(screen.getByText("aide mode")).toBeInTheDocument();
  });
});

describe("ActionForm — required validation", () => {
  it("bloque la soumission tant qu'un champ requis est vide", async () => {
    const run = await mockRun();
    run.mockResolvedValue({ run_uid: "uid-1" });

    renderForm(
      makeAction({
        risk: "ro",
        options: [
          makeOption({
            name: "query",
            type: "str",
            required: true,
            label: "Requête",
            help: "terme",
          }),
        ],
      }),
    );

    // Submit with the required field empty → validation error, no request.
    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));
    expect(
      screen.getByText(/Champs requis manquants : Requête/),
    ).toBeInTheDocument();
    expect(run).not.toHaveBeenCalled();

    // Fill it, then submit → request fires with the typed option. The label
    // carries a "*" required marker, so match it loosely.
    fireEvent.change(screen.getByLabelText(/Requête/), {
      target: { value: "matrix" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));

    await waitFor(() => {
      expect(run).toHaveBeenCalledWith("library-test", {
        options: { query: "matrix" },
        dry_run: false,
      });
    });
    expect(await screen.findByText("Exécution démarrée")).toBeInTheDocument();
    expect(screen.getByText("uid-1")).toBeInTheDocument();
  });
});

describe("ActionForm — destructive dry-run-first flow", () => {
  it("verrouille Appliquer jusqu'à un dry-run réussi, re-verrouille à l'édition puis sur 428", async () => {
    const run = await mockRun();
    run
      .mockResolvedValueOnce({ run_uid: "dry-1" })
      .mockResolvedValueOnce({ run_uid: "dry-2" })
      .mockRejectedValueOnce(new ApiError(428, "Lancez un dry-run récent."));

    renderForm(
      makeAction({
        risk: "destructive",
        dry_run: "supported",
        options: [
          makeOption({
            name: "target",
            type: "str",
            label: "Cible",
            help: "chemin",
          }),
        ],
      }),
    );

    const apply = (): HTMLElement =>
      screen.getByRole("button", { name: "Appliquer" });

    // 1. Disabled initially.
    expect(apply()).toBeDisabled();

    // 2. A successful dry-run enables it.
    fireEvent.click(screen.getByRole("button", { name: "Dry-run" }));
    await waitFor(() => {
      expect(apply()).not.toBeDisabled();
    });

    // 3. Editing a field re-locks it (canonical options changed).
    fireEvent.change(screen.getByLabelText("Cible"), {
      target: { value: "/data/x" },
    });
    expect(apply()).toBeDisabled();

    // Re-run the dry-run for the new value to re-enable.
    fireEvent.click(screen.getByRole("button", { name: "Dry-run" }));
    await waitFor(() => {
      expect(apply()).not.toBeDisabled();
    });

    // 4. A 428 on Appliquer re-locks it and surfaces the backend detail.
    fireEvent.click(apply());
    await waitFor(() => {
      expect(screen.getByText("Lancez un dry-run récent.")).toBeInTheDocument();
    });
    expect(apply()).toBeDisabled();
  });
});

describe("ActionForm — run output feed", () => {
  it("affiche la zone de sortie (badge + run_uid + journal) après un 202", async () => {
    const run = await mockRun();
    run.mockResolvedValue({ run_uid: "uid-42" });

    renderForm(makeAction({ risk: "ro", dry_run: "unsupported" }));

    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));

    // Status badge + run_uid + the reused RunLogFeed journal all appear.
    expect(await screen.findByText("Exécution démarrée")).toBeInTheDocument();
    expect(screen.getByText("uid-42")).toBeInTheDocument();
    expect(screen.getByText(/Journal d.exécution/)).toBeInTheDocument();
  });

  it("surface les lignes live diffusées par la WS pour ce run_uid", async () => {
    const run = await mockRun();
    run.mockResolvedValue({ run_uid: "uid-live" });

    renderForm(makeAction({ risk: "ro", dry_run: "unsupported" }), [
      makeEvent(1_700_000_000_000, "maintenance.run_log", {
        run_uid: "uid-live",
        line: "Nettoyage du disque en cours",
        seq: 1,
      }),
      makeEvent(1_700_000_001_000, "maintenance.run_log", {
        run_uid: "autre-run",
        line: "Ligne d'un autre run",
        seq: 1,
      }),
    ]);

    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));

    // The line for this run appears; the one scoped to another run does not.
    expect(
      await screen.findByText("Nettoyage du disque en cours"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Ligne d'un autre run")).not.toBeInTheDocument();
  });

  it("affiche l'output_tail durable une fois le run terminé", async () => {
    const run = await mockRun();
    run.mockResolvedValue({ run_uid: "uid-done" });
    const detail = await mockDetail();
    detail.mockResolvedValue(
      makeRunDetail({
        run_uid: "uid-done",
        outcome: "success",
        ended_at: "2026-07-06T10:05:00Z",
        output_tail: "Ligne finale A\nLigne finale B",
      }),
    );

    renderForm(makeAction({ risk: "ro", dry_run: "unsupported" }));

    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));

    // The durable fallback renders the captured tail once the run is terminal.
    expect(await screen.findByText("Sortie capturée")).toBeInTheDocument();
    expect(screen.getByText("Ligne finale A")).toBeInTheDocument();
    expect(screen.getByText("Ligne finale B")).toBeInTheDocument();
  });

  it("masque la zone de sortie via « Fermer la sortie »", async () => {
    const run = await mockRun();
    run.mockResolvedValue({ run_uid: "uid-close" });

    renderForm(makeAction({ risk: "ro", dry_run: "unsupported" }));

    fireEvent.click(screen.getByRole("button", { name: "Exécuter" }));
    expect(await screen.findByText("uid-close")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Fermer la sortie" }));
    expect(screen.queryByText("uid-close")).not.toBeInTheDocument();
  });
});
