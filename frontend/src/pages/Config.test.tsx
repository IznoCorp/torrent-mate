/**
 * Config page tests (S4 config-editor — sub-phase 3.2).
 *
 * Mirrors Dashboard.test.tsx conventions: mock the hooks module, stub fetch
 * for mutation calls, assert key flows.
 */

/* eslint-disable @typescript-eslint/no-unsafe-return */
// ^ vi.mock factory returns hook mocks that are typed at the call-site via
// mockReturnValue<T>() — the `any` return is inherent to vitest's vi.fn().

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import Config from "@/pages/Config";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Default mock data
// ---------------------------------------------------------------------------

/** Mock schema response: two top-level keys owned by different files. */
const defaultSchema = {
  json_schema: {
    type: "object",
    properties: {
      api_key: { type: "string", description: "An API key" },
      max_retries: { type: "integer" },
    },
    required: ["api_key"],
  },
  ownership: { api_key: "secrets.json5", max_retries: "master.json5" },
  restart_impact: { api_key: true, max_retries: false },
};

/** Mock files response. */
const defaultFiles = {
  files: [
    {
      name: "master.json5",
      owned_keys: ["max_retries"],
      sha256: "abc123",
      mtime: 1700000000,
      size: 200,
      shadowed_keys: [],
    },
    {
      name: "secrets.json5",
      owned_keys: ["api_key"],
      sha256: "def456",
      mtime: 1700000001,
      size: 150,
      shadowed_keys: ["api_key"],
    },
    {
      name: "local.json5",
      owned_keys: [],
      sha256: "fff999",
      mtime: 1700000002,
      size: 80,
      shadowed_keys: [],
    },
  ],
};

/** Mock status response (prod, writable). */
const defaultStatus = {
  role: "prod",
  read_only: false,
  restart_required: false,
  stale_files: [],
};

/** Mock status for read-only (staging). */
const readOnlyStatus = {
  role: "staging",
  read_only: true,
  restart_required: false,
  stale_files: [],
};

/** Mock status for restart required. */
const restartRequiredStatus = {
  role: "prod",
  read_only: false,
  restart_required: true,
  stale_files: ["master.json5", "secrets.json5"],
};

/** Mock file content for master.json5. */
const masterFileContent = {
  name: "master.json5",
  values: { max_retries: 3 },
  sha256: "abc123",
  shadowed_keys: [],
};

// ---------------------------------------------------------------------------
// Hook mocks
// ---------------------------------------------------------------------------

const mocks = {
  useConfigSchema: vi.fn(),
  useConfigFiles: vi.fn(),
  useConfigFile: vi.fn(),
  useConfigStatus: vi.fn(),
  useConfigSecrets: vi.fn(),
  usePutConfigFile: vi.fn(),
  usePutConfigSecrets: vi.fn(),
  useRestartWeb: vi.fn(),
  useValidateConfig: vi.fn(),
};

vi.mock("@/hooks/useConfig", () => ({
  useConfigSchema: () => mocks.useConfigSchema(),
  useConfigFiles: () => mocks.useConfigFiles(),
  useConfigFile: (n: string) => mocks.useConfigFile(n),
  useConfigStatus: () => mocks.useConfigStatus(),
  useConfigSecrets: () => mocks.useConfigSecrets(),
  usePutConfigFile: (n: string) => mocks.usePutConfigFile(n),
  usePutConfigSecrets: () => mocks.usePutConfigSecrets(),
  useRestartWeb: () => mocks.useRestartWeb(),
  useValidateConfig: () => mocks.useValidateConfig(),
}));

// Silence sonner toasts in tests.
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Standard "loading" query shape. */
const loading = { isLoading: true, isError: false, data: undefined };
/** Standard "success" query shape with typed data. */
function success<T>(data: T) {
  return { isLoading: false, isError: false, data };
}

/** Standard mutation shape (idle). */
function idleMutation() {
  return { mutateAsync: vi.fn(), isPending: false };
}

/** Set all mocks to their default (prod, writable, data loaded). */
function setDefaultMocks(): void {
  mocks.useConfigSchema.mockReturnValue(success(defaultSchema));
  mocks.useConfigFiles.mockReturnValue(success(defaultFiles));
  mocks.useConfigStatus.mockReturnValue(success(defaultStatus));
  mocks.useConfigSecrets.mockReturnValue(success({ secrets: [] }));
  mocks.usePutConfigFile.mockReturnValue(idleMutation());
  mocks.usePutConfigSecrets.mockReturnValue(idleMutation());
  mocks.useRestartWeb.mockReturnValue(idleMutation());
  mocks.useValidateConfig.mockReturnValue(idleMutation());
  // useConfigFile: default to loading (no file selected).
  mocks.useConfigFile.mockReturnValue(loading);
}

/** Render the Config page wrapped in providers. */
function renderConfig(): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Config />
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  setDefaultMocks();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Config", () => {
  // ---- 1. Renders file list and file selection ---------------------------
  it("affiche la liste des fichiers et permet la sélection", async () => {
    renderConfig();

    // File list entries are rendered.
    expect(screen.getByText("master.json5")).toBeInTheDocument();
    expect(screen.getByText("secrets.json5")).toBeInTheDocument();
    expect(screen.getByText("local.json5")).toBeInTheDocument();

    // Owned keys as chips.
    expect(screen.getByText("max_retries")).toBeInTheDocument();
    expect(screen.getByText("api_key")).toBeInTheDocument();

    // Placeholder message in the right panel.
    expect(
      screen.getByText("Sélectionnez un fichier dans la liste pour l'éditer."),
    ).toBeInTheDocument();

    // Click a file.
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    fireEvent.click(screen.getByText("master.json5"));

    // Wait for the form to appear with the file's value.
    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });
  });

  // ---- 2. Read-only status -------------------------------------------------
  it("affiche la bannière lecture seule et désactive les contrôles", async () => {
    mocks.useConfigStatus.mockReturnValue(success(readOnlyStatus));
    renderConfig();

    expect(screen.getByText(/lecture seule/i)).toBeInTheDocument();

    // Select a file.
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    fireEvent.click(screen.getByText("master.json5"));

    await waitFor(() => {
      // The input should be disabled.
      const input = screen.getByDisplayValue("3");
      expect(input).toBeDisabled();
    });
  });

  // ---- 3. Restart required banner ------------------------------------------
  it("affiche la bannière de redémarrage avec la liste des fichiers modifiés", () => {
    mocks.useConfigStatus.mockReturnValue(success(restartRequiredStatus));
    renderConfig();

    expect(screen.getByText(/redémarrage requis/i)).toBeInTheDocument();
    expect(screen.getByText(/master.json5, secrets.json5/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /redémarrer le daemon/i }),
    ).toBeInTheDocument();
  });

  // ---- 4. Save flow — dirty enables save, success clears dirty ------------
  it("active Enregistrer après modification et le désactive après succès", async () => {
    const putAsync = vi.fn().mockResolvedValue({
      restart_required: false,
      warnings: [],
    });
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    // Select the file to load it.
    fireEvent.click(screen.getByText("master.json5"));

    // Wait for the form to render.
    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });

    const saveBtn = screen.getByRole("button", { name: "Enregistrer" });
    // Not dirty yet → disabled.
    expect(saveBtn).toBeDisabled();

    // Edit the value.
    fireEvent.change(screen.getByDisplayValue("3"), {
      target: { value: "5" },
    });

    // Now dirty → enabled.
    await waitFor(() => {
      expect(saveBtn).toBeEnabled();
    });

    // Click save.
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(putAsync).toHaveBeenCalledTimes(1);
    });

    // After success, dirty is cleared → button disabled again.
    await waitFor(() => {
      expect(saveBtn).toBeDisabled();
    });
  });

  // ---- 5. 422 maps errors into the form + fires toast ----------------------
  // The transport-level guarantee that stringified arrays round-trip lives in
  // useConfig.test.tsx → "putConfigFile transport (422 array detail)".
  it("affiche les erreurs de validation 422 dans le formulaire et déclenche un toast", async () => {
    // After the transport fix (FIX 1), the ApiError.detail is a
    // JSON.stringified array — this is legitimate and is what the real
    // transport now produces.
    const putAsync = vi.fn().mockRejectedValue(
      new ApiError(
        422,
        JSON.stringify([
          {
            loc: ["max_retries"],
            msg: "Doit être >= 0",
            type: "value_error",
          },
        ]),
      ),
    );
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    fireEvent.click(screen.getByText("master.json5"));

    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });

    // Edit to trigger dirty.
    fireEvent.change(screen.getByDisplayValue("3"), {
      target: { value: "-1" },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // Error message should appear in the form.
    await waitFor(() => {
      expect(screen.getByText("Doit être >= 0")).toBeInTheDocument();
    });

    // Always-toast contract (FIX 2): every 422 save fires toast.error.
    expect(toast.error).toHaveBeenCalledWith("Validation échouée");
  });

  // ---- 6. 412 opens conflict dialog ---------------------------------------
  it("ouvre la boîte de dialogue de conflit sur une erreur 412", async () => {
    const putAsync = vi
      .fn()
      .mockRejectedValue(new ApiError(412, "Precondition Failed"));
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    fireEvent.click(screen.getByText("master.json5"));

    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue("3"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // Conflict dialog should appear.
    await waitFor(() => {
      expect(screen.getByText(/conflit de version/i)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Recharger" }),
      ).toBeInTheDocument();
    });
  });

  // ---- 7. Restart badge on files with restart_impact ----------------------
  it("affiche un badge restart sur les fichiers dont une clé impacte le redémarrage", () => {
    renderConfig();

    // secrets.json5 owns api_key which has restart_impact=true → "restart" badge.
    expect(screen.getByText("restart")).toBeInTheDocument();
  });

  // ---- 8. Loading state ---------------------------------------------------
  it("affiche l'état de chargement", () => {
    mocks.useConfigSchema.mockReturnValue(loading);
    mocks.useConfigFiles.mockReturnValue(loading);
    mocks.useConfigStatus.mockReturnValue(loading);

    renderConfig();

    expect(screen.getByText("Chargement…")).toBeInTheDocument();
  });

  // ---- 9. Error state ------------------------------------------------------
  it("affiche un message d'erreur quand les requêtes échouent", () => {
    mocks.useConfigSchema.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
    });
    mocks.useConfigFiles.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
    });
    mocks.useConfigStatus.mockReturnValue({
      isLoading: false,
      isError: true,
      data: undefined,
    });

    renderConfig();

    expect(
      screen.getByText(/impossible de charger la configuration/i),
    ).toBeInTheDocument();
  });

  // ---- 10. 422 model-level error (loc: []) → toast, no crash --------------
  it("affiche un toast avec le message d'erreur modèle sur loc: [] sans crash", async () => {
    // Model-level errors have an empty loc array — flattenLocToPath produces
    // "", which matches no rendered field.  The fix (SF-14) detects them as
    // "unmatched" and surfaces the first message in the toast.
    const putAsync = vi.fn().mockRejectedValue(
      new ApiError(
        422,
        JSON.stringify([
          { loc: [], msg: "Une clé au moins est obligatoire", type: "value_error" },
        ]),
      ),
    );
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    fireEvent.click(screen.getByText("master.json5"));

    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue("3"), {
      target: { value: "" },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // No crash — the toast surfaces the unmatched error.
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Validation échouée — 1 erreur(s) : Une clé au moins est obligatoire",
      );
    });
  });
});
