import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CandidateCard } from "@/components/decisions/CandidateCard";

import type { DecisionCandidate } from "@/api/decisions";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCandidate(
  overrides: Partial<DecisionCandidate> = {},
): DecisionCandidate {
  return {
    provider: "tmdb",
    provider_id: 123,
    title: "Inception",
    year: 2010,
    score: 0.85,
    poster_url: "https://example.com/poster.jpg",
    overview: "A thief who steals corporate secrets...",
    ...overrides,
  };
}

function renderCard(
  candidate: DecisionCandidate,
  isSelected = false,
  onClick = vi.fn(),
): void {
  const tree: ReactElement = (
    <CandidateCard
      candidate={candidate}
      isSelected={isSelected}
      onClick={onClick}
    />
  );
  render(tree);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(cleanup);

describe("CandidateCard", () => {
  it("affiche le titre et l'année du candidat", () => {
    renderCard(makeCandidate());
    expect(screen.getByText("Inception")).toBeInTheDocument();
    expect(screen.getByText("2010")).toBeInTheDocument();
  });

  it("affiche le titre sans année quand year est null", () => {
    renderCard(makeCandidate({ year: null }));
    expect(screen.getByText("Inception")).toBeInTheDocument();
    expect(screen.queryByText("2010")).not.toBeInTheDocument();
  });

  it("affiche le badge du fournisseur (TMDB)", () => {
    renderCard(makeCandidate({ provider: "tmdb" }));
    expect(screen.getByText("TMDB")).toBeInTheDocument();
  });

  it("affiche le badge du fournisseur (TVDB)", () => {
    renderCard(makeCandidate({ provider: "tvdb" }));
    expect(screen.getByText("TVDB")).toBeInTheDocument();
  });

  it("affiche le score en pourcentage", () => {
    renderCard(makeCandidate({ score: 0.85 }));
    expect(screen.getByText(/85.*%/)).toBeInTheDocument();
  });

  it("clamp le score à 0–100 %", () => {
    // Score > 1 is clamped to 100.
    renderCard(makeCandidate({ score: 1.5 }));
    expect(screen.getByText(/100.*%/)).toBeInTheDocument();
  });

  it("déclenche onClick au clic", () => {
    const onClick = vi.fn();
    renderCard(makeCandidate(), false, onClick);

    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("déclenche onClick au clavier (Enter)", () => {
    const onClick = vi.fn();
    renderCard(makeCandidate(), false, onClick);

    fireEvent.keyDown(screen.getByRole("button"), { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("déclenche onClick au clavier (Espace)", () => {
    const onClick = vi.fn();
    renderCard(makeCandidate(), false, onClick);

    fireEvent.keyDown(screen.getByRole("button"), { key: " " });
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("applique l'état sélectionné (ring)", () => {
    renderCard(makeCandidate(), true);
    const card = screen.getByRole("button");
    expect(card).toHaveAttribute("aria-pressed", "true");
    expect(card.className).toContain("ring-2");
  });

  it("n'applique pas l'état sélectionné quand non sélectionné", () => {
    renderCard(makeCandidate(), false);
    const card = screen.getByRole("button");
    expect(card).toHaveAttribute("aria-pressed", "false");
  });

  it("affiche l'image poster quand l'URL est fournie", () => {
    renderCard(makeCandidate({ poster_url: "https://example.com/poster.jpg" }));
    const img = screen.getByAltText("Affiche de Inception");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("loading", "lazy");
  });

  it("affiche le fallback quand poster_url est null", () => {
    renderCard(makeCandidate({ poster_url: null }));
    expect(screen.getByText("Aucune affiche")).toBeInTheDocument();
    expect(
      screen.queryByAltText("Affiche de Inception"),
    ).not.toBeInTheDocument();
  });

  it("affiche le fallback après une erreur de chargement du poster", () => {
    renderCard(makeCandidate({ poster_url: "https://example.com/broken.jpg" }));
    const img = screen.getByAltText("Affiche de Inception");
    fireEvent.error(img);
    expect(screen.getByText("Aucune affiche")).toBeInTheDocument();
    expect(
      screen.queryByAltText("Affiche de Inception"),
    ).not.toBeInTheDocument();
  });

  it("affiche la barre de score avec la bonne couleur pour un score élevé", () => {
    renderCard(makeCandidate({ score: 0.9 }));
    // High score → bg-success (green).  The bar is a sibling of the score
    // label row — navigate up to the shared container first.
    const container = screen.getByText(/90.*%/).parentElement?.parentElement;
    const bar = container?.querySelector(".h-full.rounded-full");
    expect(bar).toBeTruthy();
    expect((bar as HTMLElement).className).toContain("bg-success");
  });

  it("affiche la barre de score avec la bonne couleur pour un score moyen", () => {
    renderCard(makeCandidate({ score: 0.5 }));
    // Medium score → bg-warning (amber)
    const container = screen.getByText(/50.*%/).parentElement?.parentElement;
    const bar = container?.querySelector(".h-full.rounded-full");
    expect(bar).toBeTruthy();
    expect((bar as HTMLElement).className).toContain("bg-warning");
  });

  it("affiche la barre de score avec la bonne couleur pour un score faible", () => {
    renderCard(makeCandidate({ score: 0.2 }));
    // Low score → bg-destructive (red)
    const container = screen.getByText(/20.*%/).parentElement?.parentElement;
    const bar = container?.querySelector(".h-full.rounded-full");
    expect(bar).toBeTruthy();
    expect((bar as HTMLElement).className).toContain("bg-destructive");
  });

  it("affiche le provider brut quand il est inconnu", () => {
    renderCard(
      makeCandidate({ provider: "imdb" as unknown as "tmdb" | "tvdb" }),
    );
    // Falls back to the raw provider string, uppercased or as-is.
    expect(screen.getByText("imdb")).toBeInTheDocument();
  });
});
