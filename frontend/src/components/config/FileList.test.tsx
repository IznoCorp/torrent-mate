/**
 * FileList tests — restart-chip interaction (sub-phase 5.2).
 *
 * Verifies the tap-accessible restart badge microcopy, aria-expanded toggle,
 * and keyboard interaction on the file rows.
 */

/* eslint-disable @typescript-eslint/no-unsafe-return */
// ^ vi.mock factory returns hook mocks typed at the call-site.

import {
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FileList } from "@/components/config/FileList";

// ---------------------------------------------------------------------------
// Hook mocks
// ---------------------------------------------------------------------------

const mocks = {
  useConfigFiles: vi.fn(),
  useConfigSchema: vi.fn(),
  useConfigStatus: vi.fn(),
};

vi.mock("@/hooks/useConfig", () => ({
  useConfigFiles: () => mocks.useConfigFiles(),
  useConfigSchema: () => mocks.useConfigSchema(),
  useConfigStatus: () => mocks.useConfigStatus(),
}));

// ---------------------------------------------------------------------------
// Default mock data
// ---------------------------------------------------------------------------

/** Standard "success" query shape. */
function success<T>(data: T) {
  return { isLoading: false, isError: false, data, error: null };
}

const defaultFiles = {
  files: [
    {
      name: "paths.json5",
      owned_keys: ["paths.data_dir"],
      sha256: "abc123",
      mtime: 1_720_000_000,
      size: 512,
      shadowed_keys: [],
    },
    {
      name: "api.json5",
      owned_keys: ["apis.tmdb"],
      sha256: "def456",
      mtime: 1_720_000_000,
      size: 256,
      shadowed_keys: [],
    },
  ],
};

const defaultSchema = {
  json_schema: {},
  ownership: { "paths.data_dir": "paths.json5", "apis.tmdb": "api.json5" },
  restart_impact: { "paths.data_dir": true, "apis.tmdb": false },
};

const defaultStatus = {
  read_only: false,
  restart_configured: true,
  restart_required: false,
  role: "prod",
  stale_files: [],
};

/** Set all mocks to defaults. */
function setDefaultMocks(): void {
  mocks.useConfigFiles.mockReturnValue(success(defaultFiles));
  mocks.useConfigSchema.mockReturnValue(success(defaultSchema));
  mocks.useConfigStatus.mockReturnValue(success(defaultStatus));
}

/** Render the FileList component. */
function renderFileList(
  overrides: {
    dirtyFiles?: Set<string>;
    selected?: string | null;
    onSelect?: (name: string) => void;
  } = {},
): void {
  render(
    <FileList
      dirtyFiles={overrides.dirtyFiles ?? new Set()}
      selected={overrides.selected ?? null}
      onSelect={overrides.onSelect ?? vi.fn()}
    />,
  );
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

describe("FileList", () => {
  it("affiche la liste des fichiers", () => {
    renderFileList();

    expect(screen.getByText("paths.json5")).toBeInTheDocument();
    expect(screen.getByText("api.json5")).toBeInTheDocument();
  });

  // ── Restart chip interaction ──────────────────────────────────────────

  it("affiche le badge restart et la microcopie au tap (sub-phase 5.2)", () => {
    renderFileList();

    // The restart badge is a <button> inside paths.json5's row (only key
    // with restart_impact=true).
    const restartBtn = screen.getByRole("button", {
      name: "Redémarrage requis après modification",
    });
    expect(restartBtn).toBeInTheDocument();

    // aria-expanded starts as "false".
    expect(restartBtn).toHaveAttribute("aria-expanded", "false");

    // Tap the badge.
    fireEvent.click(restartBtn);

    // aria-expanded flips to "true".
    expect(restartBtn).toHaveAttribute("aria-expanded", "true");

    // Microcopy text is now visible.
    expect(
      screen.getByText("Redémarrage requis après modification"),
    ).toBeInTheDocument();
  });

  it("referme la microcopie au second tap (sub-phase 5.2)", () => {
    renderFileList();

    const restartBtn = screen.getByRole("button", {
      name: "Redémarrage requis après modification",
    });

    // First tap: open.
    fireEvent.click(restartBtn);
    expect(restartBtn).toHaveAttribute("aria-expanded", "true");

    // Second tap: close.
    fireEvent.click(restartBtn);
    expect(restartBtn).toHaveAttribute("aria-expanded", "false");
  });

  it("sélectionne le fichier au clavier Enter sur la rangée (sub-phase 5.2)", () => {
    const onSelect = vi.fn();
    renderFileList({ onSelect });

    // The file row is a div[role=button] (not a <button> — valid DOM, no
    // button-inside-button).  Query it via the text content rather than
    // getByRole("button") which would match the restart badge <button> too.
    const pathsRow = screen.getByText("paths.json5").closest('[role="button"]');
    expect(pathsRow).toBeInTheDocument();

    fireEvent.keyDown(pathsRow as HTMLElement, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("paths.json5");
  });

  it("ne propage pas le clic du badge restart à la rangée", () => {
    const onSelect = vi.fn();
    renderFileList({ onSelect });

    const restartBtn = screen.getByRole("button", {
      name: "Redémarrage requis après modification",
    });

    fireEvent.click(restartBtn);
    // The row onSelect must NOT be called — stopPropagation on the badge.
    expect(onSelect).not.toHaveBeenCalled();
  });
});
