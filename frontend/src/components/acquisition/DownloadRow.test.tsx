/**
 * DownloadRow — the live-download row, including the honest ETA (addition B).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { AcquisitionDownload } from "@/api/acquisition";

import { DownloadRow } from "./DownloadRow";

afterEach(() => {
  cleanup();
});

function download(over: Partial<AcquisitionDownload> = {}): AcquisitionDownload {
  return {
    info_hash: "abc123",
    name: "FROM.S03E01.mkv",
    title: "FROM",
    kind: "episode",
    state: "downloading",
    progress: 0.78,
    size_bytes: 4_000_000_000,
    media_ref: { tvdb_id: 1, tmdb_id: null, imdb_id: null },
    season: 3,
    episode: 1,
    error_reason: null,
    eta_seconds: null,
    ...over,
  };
}

describe("DownloadRow — ETA (maquette « 12 min restantes »)", () => {
  it("affiche l'ETA en minutes quand le client la connaît", () => {
    render(<DownloadRow d={download({ eta_seconds: 720 })} />);
    expect(screen.getByText("12 min restantes")).toBeInTheDocument();
  });

  it("bascule en heures au-delà de 60 minutes", () => {
    render(<DownloadRow d={download({ eta_seconds: 4500 })} />);
    expect(screen.getByText("1 h 15 restantes")).toBeInTheDocument();
  });

  it("sous la minute, le dit sans inventer des secondes", () => {
    render(<DownloadRow d={download({ eta_seconds: 30 })} />);
    expect(screen.getByText("moins d'une minute restante")).toBeInTheDocument();
  });

  it("ETA inconnue → aucune mention (jamais de fausse promesse)", () => {
    render(<DownloadRow d={download({ eta_seconds: null })} />);
    expect(screen.queryByText(/restante/)).toBeNull();
  });

  it("pas d'ETA hors téléchargement actif", () => {
    render(
      <DownloadRow d={download({ state: "stalled", eta_seconds: 720 })} />,
    );
    expect(screen.queryByText(/restante/)).toBeNull();
  });
});
