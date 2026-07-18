/**
 * SecretsTab tests (S4 config-editor — sub-phase 6.2).
 *
 * Mirrors Config.test.tsx conventions: mock the hooks module, stub
 * mutations, assert toast behaviour.
 */

/* eslint-disable @typescript-eslint/no-unsafe-return */
// ^ vi.mock factory returns hook mocks typed at the call-site.

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { SecretsTab } from "@/components/config/SecretsTab";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Default mock data
// ---------------------------------------------------------------------------

const defaultSecrets = {
  secrets: [
    { key: "TMDB_API_KEY", is_set: true, description: "TMDB API key" },
    { key: "QBITTORRENT_PASS", is_set: false, description: "qBittorrent password" },
  ],
};

// ---------------------------------------------------------------------------
// Hook mocks
// ---------------------------------------------------------------------------

const mocks = {
  useConfigSecrets: vi.fn(),
  usePutConfigSecrets: vi.fn(),
};

vi.mock("@/hooks/useConfig", () => ({
  useConfigSecrets: () => mocks.useConfigSecrets(),
  usePutConfigSecrets: () => mocks.usePutConfigSecrets(),
  useConfigSchema: vi.fn(),
  useConfigFiles: vi.fn(),
  useConfigFile: vi.fn(),
  useConfigStatus: vi.fn(),
  usePutConfigFile: vi.fn(),
  useRestartWeb: vi.fn(),
  useValidateConfig: vi.fn(),
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

/** Set all mocks to defaults (secrets loaded, mutation idle). */
function setDefaultMocks(): void {
  mocks.useConfigSecrets.mockReturnValue(success(defaultSecrets));
  mocks.usePutConfigSecrets.mockReturnValue(idleMutation());
}

/** Render the SecretsTab component. */
function renderSecretsTab(readOnly = false): void {
  render(<SecretsTab readOnly={readOnly} />);
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

describe("SecretsTab", () => {
  // ---- 1. Renders the secret key list -------------------------------------
  it("affiche la liste des clés de secret avec leurs badges", () => {
    renderSecretsTab();

    expect(screen.getByText("TMDB_API_KEY")).toBeInTheDocument();
    expect(screen.getByText("QBITTORRENT_PASS")).toBeInTheDocument();

    // Badges.
    expect(screen.getByText("défini")).toBeInTheDocument();
    expect(screen.getByText("non défini")).toBeInTheDocument();
  });

  // ---- 2. FR description override (sub-phase 5.2) --------------------------

  it("affiche la description FR « Clé API TMDB » au lieu de l'EN brute (sub-phase 5.2)", () => {
    renderSecretsTab();

    // The backend returns description "TMDB API key" for TMDB_API_KEY.
    // The FR_DESCRIPTIONS map must override it to "Clé API TMDB".
    expect(screen.getByText("Clé API TMDB")).toBeInTheDocument();
    // The raw EN description must NOT be rendered.
    expect(screen.queryByText("TMDB API key")).not.toBeInTheDocument();
  });

  // ---- 3. Empty catalog ---------------------------------------------------
  it("affiche un message quand aucun secret n'est déclaré", () => {
    mocks.useConfigSecrets.mockReturnValue(success({ secrets: [] }));
    renderSecretsTab();

    expect(
      screen.getByText("Aucun secret déclaré dans le catalogue."),
    ).toBeInTheDocument();
  });

  // ---- 3. Save button disabled without edits ------------------------------
  it("désactive le bouton Enregistrer tant qu'aucune valeur n'est saisie", () => {
    renderSecretsTab();

    const saveBtn = screen.getByRole("button", {
      name: "Enregistrer les secrets",
    });
    expect(saveBtn).toBeDisabled();
  });

  // ---- 4. Save button enabled after typing a value ------------------------
  it("active le bouton Enregistrer après saisie d'une valeur", async () => {
    renderSecretsTab();

    // Find the input for the first key and type into it.
    const inputs = screen.getAllByPlaceholderText(/••••/);
    const tmdbInput = inputs[0];
    if (!tmdbInput) throw new Error("missing first input");
    fireEvent.change(tmdbInput, { target: { value: "new-key" } });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Enregistrer les secrets" }),
      ).toBeEnabled();
    });
  });

  // ---- 5. Read-only mode disables inputs and button -----------------------
  it("désactive les contrôles en mode lecture seule", () => {
    renderSecretsTab(true);

    const saveBtn = screen.getByRole("button", {
      name: "Enregistrer les secrets",
    });
    expect(saveBtn).toBeDisabled();

    const inputs = screen.getAllByPlaceholderText(/••••/);
    for (const input of inputs) {
      expect(input).toBeDisabled();
    }
  });

  // ---- 6. Loading state ---------------------------------------------------
  it("affiche l'état de chargement", () => {
    mocks.useConfigSecrets.mockReturnValue(loading);
    renderSecretsTab();

    expect(screen.getByText("Chargement des secrets…")).toBeInTheDocument();
  });

  // ---- 7. 422 rejection → toast carries backend detail --------------------
  it("affiche le détail backend dans le toast sur une erreur 422", async () => {
    const putAsync = vi
      .fn()
      .mockRejectedValue(
        new ApiError(422, "Caractère interdit dans la clé 'TMDB_API_KEY'"),
      );
    mocks.usePutConfigSecrets.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    renderSecretsTab();

    // Type into the first key input.
    const inputs = screen.getAllByPlaceholderText(/••••/);
    const firstInput = inputs[0];
    if (!firstInput) throw new Error("missing first input");
    fireEvent.change(firstInput, { target: { value: "bad\nkey" } });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Enregistrer les secrets" }),
      ).toBeEnabled();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Enregistrer les secrets" }),
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Caractère interdit dans la clé 'TMDB_API_KEY'",
      );
    });
  });

  // ---- 8. Non-ApiError → generic message ----------------------------------
  it("affiche le message générique sur une erreur non-ApiError", async () => {
    const putAsync = vi
      .fn()
      .mockRejectedValue(new Error("Network error"));
    mocks.usePutConfigSecrets.mockReturnValue({
      mutateAsync: putAsync,
      isPending: false,
    });
    renderSecretsTab();

    // Type into the first key input.
    const inputs = screen.getAllByPlaceholderText(/••••/);
    const firstInput = inputs[0];
    if (!firstInput) throw new Error("missing first input");
    fireEvent.change(firstInput, { target: { value: "abc123" } });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Enregistrer les secrets" }),
      ).toBeEnabled();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Enregistrer les secrets" }),
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Échec de l’enregistrement des secrets.",
      );
    });
  });
});
