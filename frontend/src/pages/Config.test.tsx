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
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import Config, { restartPollConfig } from "@/pages/Config";
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
  restart_configured: true,
  stale_files: [],
};

/** Mock status for read-only (staging). */
const readOnlyStatus = {
  role: "staging",
  read_only: true,
  restart_required: false,
  restart_configured: true,
  stale_files: [],
};

/** Mock status for restart required. */
const restartRequiredStatus = {
  role: "prod",
  read_only: false,
  restart_required: true,
  restart_configured: true,
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
  getConfigStatus: vi.fn(),
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

// Partial mock: keep ApiError (a real class used with `instanceof`) but stub the
// restart-outcome poll's status fetch.
vi.mock("@/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/client")>()),
  getConfigStatus: () => mocks.getConfigStatus(),
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
  // Default restart-poll status: not restart_required (poll resolves benignly).
  mocks.getConfigStatus.mockResolvedValue(defaultStatus);
}

/** Probe that surfaces the live URL search string for ?file= assertions. */
function LocationProbe(): ReactElement {
  const { search } = useLocation();
  return <div data-testid="loc-search">{search}</div>;
}

/** Render the Config page wrapped in providers (?file= deep-link support). */
function renderConfig(initialEntry = "/config"): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Config />
        <LocationProbe />
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
  // Shrink the restart-outcome poll window so real-timer tests are fast.
  restartPollConfig.attempts = 3;
  restartPollConfig.intervalMs = 5;
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  restartPollConfig.attempts = 10;
  restartPollConfig.intervalMs = 2000;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Config", () => {
  // ---- 1. Renders file list and auto-selects first file (G2) ------------
  it("affiche la liste des fichiers et auto-sélectionne le premier (G2)", async () => {
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    // File list entries are rendered. master.json5 may appear twice once
    // auto-selected (list button + editor header) — assert presence, not unicity.
    expect(screen.getAllByText("master.json5").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("secrets.json5")).toBeInTheDocument();
    expect(screen.getByText("local.json5")).toBeInTheDocument();

    // Owned keys as chips.
    expect(screen.getByText("max_retries")).toBeInTheDocument();
    expect(screen.getByText("api_key")).toBeInTheDocument();

    // First file is auto-selected (G2) — form renders, no placeholder.
    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });
    expect(
      screen.queryByText("Sélectionnez un fichier dans la liste pour l'éditer."),
    ).not.toBeInTheDocument();
  });

  // ---- 2. Read-only status -------------------------------------------------
  it("affiche la bannière lecture seule et désactive les contrôles", async () => {
    mocks.useConfigStatus.mockReturnValue(success(readOnlyStatus));
    renderConfig();

    expect(screen.getByText(/lecture seule/i)).toBeInTheDocument();

    // Select a file via the FileList button (accessible name includes file name).
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    fireEvent.click(
      screen.getByRole("button", { name: /master\.json5/ }),
    );

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
    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

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

    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

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

    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

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

  // ---- 7. Restart badge + shadowed badge on files --------------------------
  it("affiche les badges restart et shadowed dans la liste des fichiers", () => {
    renderConfig();

    // secrets.json5 owns api_key which has restart_impact=true → "restart" badge.
    expect(screen.getByText("restart")).toBeInTheDocument();
    // secrets.json5 has non-empty shadowed_keys → "shadowed" badge.
    expect(screen.getByText("shadowed")).toBeInTheDocument();
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
          {
            loc: [],
            msg: "Une clé au moins est obligatoire",
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

    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

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

  // ---- 11. Restart button hidden when restart_configured=false ------------
  it("cache le bouton de redémarrage quand restart_configured est false et affiche un hint", () => {
    mocks.useConfigStatus.mockReturnValue(
      success({
        ...restartRequiredStatus,
        restart_configured: false,
      }),
    );
    renderConfig();

    // The banner heading is still shown.
    expect(screen.getByText("Redémarrage requis")).toBeInTheDocument();
    // Button should NOT be present.
    expect(
      screen.queryByRole("button", { name: /redémarrer le daemon/i }),
    ).not.toBeInTheDocument();
    // Hint should be shown.
    expect(screen.getByText(/non configuré sur ce daemon/)).toBeInTheDocument();
  });

  // ---- 12. Restart click flow: confirm → POST → scheduled + polled-success -
  it("programme le restart puis confirme son succès via le poll /status", async () => {
    const restartAsync = vi.fn().mockResolvedValue({ status: "scheduled" });
    mocks.useRestartWeb.mockReturnValue({
      mutateAsync: restartAsync,
      isPending: false,
    });
    mocks.useConfigStatus.mockReturnValue(success(restartRequiredStatus));
    // The poll sees the daemon come back with restart no longer required.
    mocks.getConfigStatus.mockResolvedValue({
      ...restartRequiredStatus,
      restart_required: false,
      stale_files: [],
    });
    renderConfig();

    fireEvent.click(
      screen.getByRole("button", { name: /redémarrer le daemon/i }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Redémarrer" }));

    // Scheduled toast fires immediately (before the poll).
    await waitFor(() => {
      expect(restartAsync).toHaveBeenCalledTimes(1);
      expect(toast.success).toHaveBeenCalledWith(
        "Redémarrage programmé — la connexion va se couper puis se rétablir.",
      );
    });

    // The poll (tiny real-timer interval) sees the daemon restarted → success.
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Redémarrage effectué — configuration appliquée.",
      );
    });
  });

  // ---- 12b. Failed async restart: poll never clears → warning toast -------
  it("avertit quand le restart async ne se produit pas (poll expire)", async () => {
    const restartAsync = vi.fn().mockResolvedValue({ status: "scheduled" });
    mocks.useRestartWeb.mockReturnValue({
      mutateAsync: restartAsync,
      isPending: false,
    });
    mocks.useConfigStatus.mockReturnValue(success(restartRequiredStatus));
    // The daemon never restarts — status stays restart_required across polls.
    mocks.getConfigStatus.mockResolvedValue(restartRequiredStatus);
    renderConfig();

    fireEvent.click(
      screen.getByRole("button", { name: /redémarrer le daemon/i }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Redémarrer" }));

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith(
        "Le redémarrage ne semble pas avoir eu lieu — vérifiez le daemon (logs pm2).",
      );
    });
  });

  // ---- 13. 404 from restart endpoint → error toast -----------------------
  it("affiche un toast d'erreur quand le restart renvoie 404", async () => {
    const restartAsync = vi
      .fn()
      .mockRejectedValue(new ApiError(404, "Not Found"));
    mocks.useRestartWeb.mockReturnValue({
      mutateAsync: restartAsync,
      isPending: false,
    });
    mocks.useConfigStatus.mockReturnValue(success(restartRequiredStatus));
    renderConfig();

    fireEvent.click(
      screen.getByRole("button", { name: /redémarrer le daemon/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/redémarrer le daemon \?/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Redémarrer" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Redémarrage non configuré — PERSONALSCRAPER_PM2_NAME absent.",
      );
    });
  });

  // ---- 14. PUT warnings + restart_required → both toasts -----------------
  it("affiche les warnings et le hint restart_required après une sauvegarde réussie", async () => {
    const putAsync = vi.fn().mockResolvedValue({
      restart_required: true,
      warnings: ["Clé 'api_key' sera écrasée par local.json5"],
    });
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(
      success({
        name: "secrets.json5",
        values: { api_key: "old" },
        sha256: "def456",
        shadowed_keys: ["api_key"],
      }),
    );
    renderConfig();

    // Select secrets.json5.
    fireEvent.click(screen.getByRole("button", { name: /secrets\.json5/ }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("old")).toBeInTheDocument();
    });

    // Edit to trigger dirty.
    fireEvent.change(screen.getByDisplayValue("old"), {
      target: { value: "new_key" },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // Both warning and restart toasts should fire.
    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledWith(
        "Clé 'api_key' sera écrasée par local.json5",
      );
      expect(toast.warning).toHaveBeenCalledWith(
        "Redémarrage requis pour appliquer.",
      );
    });
  });

  // ---- 15. Shadowed-key warning chip for secrets.json5 -------------------
  it("affiche un avertissement de clé écrasée pour les fichiers avec shadowed_keys", async () => {
    mocks.useConfigFile.mockReturnValue(
      success({
        name: "secrets.json5",
        values: { api_key: "abc" },
        sha256: "def456",
        shadowed_keys: ["api_key"],
      }),
    );
    renderConfig();

    // Select secrets.json5.
    fireEvent.click(screen.getByRole("button", { name: /secrets\.json5/ }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("abc")).toBeInTheDocument();
    });

    // Shadowed warning chip should be visible.
    expect(
      screen.getByText(/écrasée par local.json5 — modification sans effet/i),
    ).toBeInTheDocument();
  });

  // ---- 16. 409 (ConfigLoadError) → toast carries the backend detail -----------
  it("affiche le détail backend dans le toast sur une erreur 409", async () => {
    const putAsync = vi
      .fn()
      .mockRejectedValue(
        new ApiError(409, "Overlay file not found: missing.json5"),
      );
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue("3"), {
      target: { value: "5" },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Overlay file not found: missing.json5",
      );
    });
  });

  // ---- 17. 422 plain-string detail (ConfigConflictError) → toast carries detail
  it("affiche le détail backend dans le toast sur une 422 non-parseable", async () => {
    const putAsync = vi
      .fn()
      .mockRejectedValue(
        new ApiError(
          422,
          "ConfigConflictError: key 'api_key' belongs to secrets.json5",
        ),
      );
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue("3"), {
      target: { value: "5" },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // extractValidationErrors returns null for a plain-string detail, so we
    // hit the fall-through toast — which must now surface err.detail.
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "ConfigConflictError: key 'api_key' belongs to secrets.json5",
      );
    });
  });

  // ---- 18. 403 (read-only) → toast carries backend detail ------------------
  it("affiche le détail backend dans le toast sur une erreur 403", async () => {
    const putAsync = vi.fn().mockRejectedValue(new ApiError(403, "read-only"));
    mocks.usePutConfigFile.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue("3"), {
      target: { value: "5" },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Enregistrer" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("read-only");
    });
  });

  // ---- 19. Mobile file selector renders + reflects selection (3.3) ---------
  it("affiche le sélecteur mobile avec l'option Secrets", async () => {
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    // The mobile selector is labelled with its current mode (Fichier by default).
    const mobileSelect = screen.getByRole("combobox", { name: "Section" });
    expect(mobileSelect).toBeInTheDocument();

    // First file is auto-selected — mobile selector reflects it.
    await waitFor(() => {
      expect(mobileSelect).toHaveTextContent("master.json5");
    });
  });
});

describe("Config — fichier adressable par URL (D3 / DOIT-10)", () => {
  it("ouvre l'éditeur du fichier indiqué par ?file= (deep-link)", async () => {
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig("/config?file=master.json5");

    // The editor opened on the deep-linked file, not the placeholder.
    await waitFor(() => {
      expect(screen.getByText("max_retries")).toBeInTheDocument();
    });
    expect(
      screen.queryByText("Sélectionnez un fichier dans la liste pour l'éditer."),
    ).not.toBeInTheDocument();
  });

  it("auto-sélectionne le premier fichier quand aucun ?file= n'est présent (G2)", async () => {
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();
    // Auto-select kicks in → editor opens, no placeholder.
    await waitFor(() => {
      expect(screen.getByDisplayValue("3")).toBeInTheDocument();
    });
    expect(
      screen.queryByText("Sélectionnez un fichier dans la liste pour l'éditer."),
    ).not.toBeInTheDocument();
  });

  it("n'écrase PAS un deep-link ?file= (G2 — auto-select guard)", async () => {
    // Load a DIFFERENT file via deep-link (secrets.json5 not master.json5).
    mocks.useConfigFile.mockReturnValue(
      success({
        name: "secrets.json5",
        values: { api_key: "deep-linked" },
        sha256: "def456",
        shadowed_keys: ["api_key"],
      }),
    );
    renderConfig("/config?file=secrets.json5");

    // The deep-linked file opens, NOT master.json5 (which is first in the list).
    await waitFor(() => {
      expect(screen.getByDisplayValue("deep-linked")).toBeInTheDocument();
    });
    // The first file should NOT have been auto-selected.
    expect(screen.queryByDisplayValue("3")).not.toBeInTheDocument();
  });

  it("écrit ?file=<nom> dans l'URL en sélectionnant un fichier (partageable)", () => {
    mocks.useConfigFile.mockReturnValue(success(masterFileContent));
    renderConfig();

    fireEvent.click(screen.getByRole("button", { name: /master\.json5/ }));

    expect(screen.getByTestId("loc-search")).toHaveTextContent(
      "?file=master.json5",
    );
  });
});

describe("Config — Secrets tab sibling (3.1)", () => {
  it("affiche l'onglet Secrets et permet de basculer", async () => {
    mocks.useConfigFile.mockReturnValue(
      success({
        name: "secrets.json5",
        values: { api_key: "abc" },
        sha256: "def456",
        shadowed_keys: ["api_key"],
      }),
    );
    renderConfig();

    // Switch to Secrets tab.
    const secretsTab = screen.getByRole("tab", { name: "Secrets" });
    expect(secretsTab).toBeInTheDocument();
    fireEvent.click(secretsTab);

    // SecretsTab content replaces FileList — empty catalog shows the empty
    // message (the default mock returns no secrets).
    await waitFor(() => {
      expect(
        screen.getByText("Aucun secret déclaré dans le catalogue."),
      ).toBeInTheDocument();
    });

    // FileList content should not be visible.
    expect(screen.queryByText("local.json5")).not.toBeInTheDocument();
  });

  it("affiche les secrets avec leur statut défini/non défini", async () => {
    mocks.useConfigSecrets.mockReturnValue(
      success({
        secrets: [
          { key: "TMDB_API_KEY", description: "Clé API TMDB", is_set: true },
          {
            key: "TVDB_API_KEY",
            description: "Clé API TVDB",
            is_set: false,
          },
        ],
      }),
    );
    renderConfig();

    // Switch to Secrets tab.
    fireEvent.click(screen.getByRole("tab", { name: "Secrets" }));

    await waitFor(() => {
      expect(screen.getByText("TMDB_API_KEY")).toBeInTheDocument();
      expect(screen.getByText("TVDB_API_KEY")).toBeInTheDocument();
      expect(screen.getByText("défini")).toBeInTheDocument();
      expect(screen.getByText("non défini")).toBeInTheDocument();
    });
  });

  it("le bouton de sauvegarde des secrets est désactivé sans modification", async () => {
    mocks.useConfigSecrets.mockReturnValue(
      success({
        secrets: [
          { key: "TMDB_API_KEY", description: "Clé API TMDB", is_set: false },
        ],
      }),
    );
    renderConfig();

    fireEvent.click(screen.getByRole("tab", { name: "Secrets" }));

    await waitFor(() => {
      const saveBtn = screen.getByRole("button", {
        name: "Enregistrer les secrets",
      });
      expect(saveBtn).toBeDisabled();
    });
  });
});
