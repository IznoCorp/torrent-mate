/**
 * DownloadsPanel — A4 tests: a grabbed torrent's live progress renders (title +
 * bar + state), the fail-soft ``client_available=false`` shows a soft note (not
 * an empty "no downloads"), and the empty case renders the idle state.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AcquisitionDownloadsResponse } from "@/api/acquisition";

import { DownloadsPanel } from "./DownloadsPanel";
import * as hooks from "@/hooks/useAcquisition";

function mockDownloads(
  data: AcquisitionDownloadsResponse | undefined,
  isLoading = false,
): void {
  vi.spyOn(hooks, "useDownloads").mockReturnValue({
    data,
    isLoading,
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof hooks.useDownloads>);
}

function renderPanel(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <DownloadsPanel />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("DownloadsPanel (A4)", () => {
  it("renders a download row with title, percent and state", () => {
    mockDownloads({
      client_available: true,
      downloads: [
        {
          media_ref: { tvdb_id: null, tmdb_id: 1184918, imdb_id: null },
          title: "Le Robot sauvage",
          kind: "movie",
          season: null,
          episode: null,
          info_hash: "abc",
          name: "Robot.mkv",
          progress: 0.33,
          state: "downloading",
          size_bytes: 999_000_000,
        },
      ],
    });
    renderPanel();

    expect(screen.getByText("Le Robot sauvage")).toBeInTheDocument();
    expect(screen.getByText("33 %")).toBeInTheDocument();
    expect(screen.getByText("Téléchargement")).toBeInTheDocument();
    // The progress bar reports the numeric value for assistive tech.
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "33",
    );
  });

  it("formats an episode row as 'Title SxxEyy'", () => {
    mockDownloads({
      client_available: true,
      downloads: [
        {
          media_ref: { tvdb_id: 1, tmdb_id: null, imdb_id: null },
          title: "Rick and Morty",
          kind: "episode",
          season: 9,
          episode: 6,
          info_hash: "def",
          name: "RaM.S09E06.mkv",
          progress: 1,
          state: "seeding",
          size_bytes: 0,
        },
      ],
    });
    renderPanel();

    expect(screen.getByText("Rick and Morty S09E06")).toBeInTheDocument();
    expect(screen.getByText("Terminé (partage)")).toBeInTheDocument();
  });

  it("shows a soft note when the torrent client is unavailable (fail-soft)", () => {
    mockDownloads({
      client_available: false,
      downloads: [
        {
          media_ref: { tvdb_id: null, tmdb_id: 1184918, imdb_id: null },
          title: "Le Robot sauvage",
          kind: "movie",
          season: null,
          episode: null,
          info_hash: "abc",
          name: "",
          progress: 0,
          state: "missing",
          size_bytes: 0,
        },
      ],
    });
    renderPanel();

    expect(screen.getByText(/Client torrent injoignable/)).toBeInTheDocument();
    expect(screen.getByText("Introuvable")).toBeInTheDocument();
    // The grabbed item is still listed, not hidden.
    expect(screen.getAllByText("Le Robot sauvage").length).toBeGreaterThan(0);
  });

  it("renders the idle empty state when there is nothing grabbed", () => {
    mockDownloads({ client_available: true, downloads: [] });
    renderPanel();

    expect(
      screen.getByText("Aucun téléchargement en cours"),
    ).toBeInTheDocument();
  });
});
