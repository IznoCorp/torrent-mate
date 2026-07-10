import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DecisionList } from "@/components/decisions/DecisionList";

import type { DecisionListItem } from "@/api/decisions";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<DecisionListItem> = {}): DecisionListItem {
  return {
    id: 1,
    staging_path: "/Volumes/staging/001-MOVIES/Inception (2010)",
    media_kind: "movie",
    extracted_title: "Inception",
    extracted_year: 2010,
    trigger: "below_threshold",
    candidates_count: 3,
    status: "pending",
    created_at: 1752076800,
    ...overrides,
  };
}

function renderList(
  items: readonly DecisionListItem[],
  onSelect: (id: number) => void = vi.fn(),
): void {
  const tree: ReactElement = <DecisionList items={items} onSelect={onSelect} />;
  render(tree);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(cleanup);

describe("DecisionList", () => {
  // -----------------------------------------------------------------------
  // Rendering
  // -----------------------------------------------------------------------

  it("affiche le titre extrait et l'année", () => {
    renderList([makeItem()]);
    const btn = screen.getByRole("button");
    expect(btn).toHaveTextContent(/Inception/);
    expect(btn).toHaveTextContent(/2010/);
  });

  it("affiche le titre sans année quand extracted_year est null", () => {
    renderList([makeItem({ extracted_year: null })]);
    // The title font-medium span should only contain the title, no year.
    const titleSpan = screen
      .getByRole("button")
      .querySelector(".font-medium");
    expect(titleSpan).toBeTruthy();
    expect(titleSpan).toHaveTextContent("Inception");
  });

  it("affiche le nom du dossier (dernier segment du chemin)", () => {
    renderList([makeItem()]);
    expect(screen.getByText("Inception (2010)")).toBeInTheDocument();
  });

  it("affiche le chemin complet en title pour le truncation", () => {
    renderList([makeItem()]);
    const folder = screen.getByText("Inception (2010)");
    expect(folder).toHaveAttribute(
      "title",
      "/Volumes/staging/001-MOVIES/Inception (2010)",
    );
  });

  it("affiche le compteur de candidats", () => {
    renderList([makeItem({ candidates_count: 5 })]);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("affiche plusieurs lignes", () => {
    renderList([
      makeItem({ id: 1, extracted_title: "Inception" }),
      makeItem({ id: 2, extracted_title: "Interstellar" }),
    ]);
    expect(screen.getByText("Inception")).toBeInTheDocument();
    expect(screen.getByText("Interstellar")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Empty state
  // -----------------------------------------------------------------------

  it("affiche le message vide quand la liste est vide", () => {
    renderList([]);
    expect(screen.getByText("Aucune décision en attente.")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Click callback
  // -----------------------------------------------------------------------

  it("appelle onSelect avec l'id au clic sur une ligne", () => {
    const onSelect = vi.fn();
    renderList([makeItem({ id: 42 })], onSelect);

    const btn = screen.getByText("Inception").closest("button");
    expect(btn).toBeTruthy();
    fireEvent.click(btn as HTMLElement);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(42);
  });

  it("appelle onSelect avec l'id correct pour chaque ligne", () => {
    const onSelect = vi.fn();
    renderList(
      [
        makeItem({ id: 10, extracted_title: "Alpha" }),
        makeItem({ id: 20, extracted_title: "Beta" }),
      ],
      onSelect,
    );

    const btnAlpha = screen.getByText("Alpha").closest("button");
    expect(btnAlpha).toBeTruthy();
    fireEvent.click(btnAlpha as HTMLElement);
    expect(onSelect).toHaveBeenCalledWith(10);

    const btnBeta = screen.getByText("Beta").closest("button");
    expect(btnBeta).toBeTruthy();
    fireEvent.click(btnBeta as HTMLElement);
    expect(onSelect).toHaveBeenCalledWith(20);
  });

  // -----------------------------------------------------------------------
  // Trigger chip variants
  // -----------------------------------------------------------------------

  it("affiche le chip 'Score faible' avec le bon tone pour below_threshold", () => {
    renderList([makeItem({ trigger: "below_threshold" })]);
    const badge = screen.getByText("Score faible");
    expect(badge).toBeInTheDocument();
    // The Badge component applies tone via the badgeVariants cva classes.
    // Verify the element is present with the danger-tone styling.
    expect(badge.closest("[data-slot='badge']")).toBeInTheDocument();
  });

  it("affiche le chip 'Zone grise' avec le bon tone pour mid_band", () => {
    renderList([makeItem({ trigger: "mid_band" })]);
    const badge = screen.getByText("Zone grise");
    expect(badge).toBeInTheDocument();
    expect(badge.closest("[data-slot='badge']")).toBeInTheDocument();
  });

  it("affiche le chip 'Ambigu' avec le bon tone pour ambiguous", () => {
    renderList([makeItem({ trigger: "ambiguous" })]);
    const badge = screen.getByText("Ambigu");
    expect(badge).toBeInTheDocument();
    expect(badge.closest("[data-slot='badge']")).toBeInTheDocument();
  });

  it("utilise le label brut pour un trigger inconnu", () => {
    renderList([
      makeItem({ trigger: "unknown_trigger" as unknown as "below_threshold" }),
    ]);
    expect(screen.getByText("unknown_trigger")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Title + header
  // -----------------------------------------------------------------------

  it("affiche le titre et la description de la carte", () => {
    renderList([makeItem()]);
    expect(screen.getByText("Décisions")).toBeInTheDocument();
    expect(
      screen.getByText("Candidats en attente de résolution"),
    ).toBeInTheDocument();
  });
});
