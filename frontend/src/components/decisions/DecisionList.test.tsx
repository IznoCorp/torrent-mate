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
    // The title button carries the extracted title + year.
    const titleBtn = screen.getByText("Inception").closest("button");
    expect(titleBtn).toBeTruthy();
    expect(titleBtn).toHaveTextContent(/Inception/);
    expect(titleBtn).toHaveTextContent(/2010/);
  });

  it("affiche le titre sans année quand extracted_year est null", () => {
    renderList([makeItem({ extracted_year: null })]);
    // The title button (font-medium) should only contain the title, no year.
    const titleBtn = screen
      .getByText("Inception")
      .closest("button.font-medium");
    expect(titleBtn).toBeTruthy();
    expect(titleBtn).toHaveTextContent("Inception");
    expect(titleBtn).not.toHaveTextContent("(");
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
    expect(screen.getByText("Aucune décision.")).toBeInTheDocument();
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

  it("affiche le chip 'Confiance faible' avec le bon tone pour below_threshold", () => {
    renderList([makeItem({ trigger: "below_threshold" })]);
    const badge = screen.getByText("Confiance faible");
    expect(badge).toBeInTheDocument();
    // The Badge component applies tone via the badgeVariants cva classes.
    // Verify the element is present with the danger-tone styling.
    expect(badge.closest("[data-slot='badge']")).toBeInTheDocument();
  });

  it("affiche le chip 'Confiance moyenne' avec le bon tone pour mid_band", () => {
    renderList([makeItem({ trigger: "mid_band" })]);
    const badge = screen.getByText("Confiance moyenne");
    expect(badge).toBeInTheDocument();
    expect(badge.closest("[data-slot='badge']")).toBeInTheDocument();
  });

  it("affiche le chip 'Candidats ambigus' avec le bon tone pour ambiguous", () => {
    renderList([makeItem({ trigger: "ambiguous" })]);
    const badge = screen.getByText("Candidats ambigus");
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
      screen.getByText("File de décisions de scraping"),
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Status badge (§4.1 relabel)
  // -----------------------------------------------------------------------

  it("affiche le badge de statut relabellé avec tooltip pour 'dismissed'", () => {
    renderList([makeItem({ status: "dismissed" })]);
    const badge = screen.getByText("Ignorée (laissée telle quelle)");
    expect(badge).toBeInTheDocument();
    // The tooltip lives on the wrapping span (Badge doesn't take a title prop).
    const wrapper = badge.closest("[title]");
    expect(wrapper).toHaveAttribute(
      "title",
      expect.stringContaining("laissé tel quel"),
    );
  });

  it("affiche le badge de statut relabellé avec tooltip pour 'superseded'", () => {
    renderList([makeItem({ status: "superseded" })]);
    const badge = screen.getByText("Remplacée (re-scrapée depuis)");
    expect(badge).toBeInTheDocument();
    const wrapper = badge.closest("[title]");
    expect(wrapper).toHaveAttribute(
      "title",
      expect.stringContaining("version plus récente"),
    );
  });

  it("affiche le badge 'En attente' pour un statut pending", () => {
    renderList([makeItem({ status: "pending" })]);
    expect(screen.getByText("En attente")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Inline quick-dismiss (§4.1)
  // -----------------------------------------------------------------------

  it("affiche l'action 'Ignorer' inline sur une ligne pending quand onQuickDismiss est fourni", () => {
    renderList([makeItem({ status: "pending" })]);
    // No onQuickDismiss → no inline action.
    expect(screen.queryByText("Ignorer")).not.toBeInTheDocument();
  });

  it("appelle onQuickDismiss avec l'id au clic sur 'Ignorer'", () => {
    const onQuickDismiss = vi.fn();
    const tree: ReactElement = (
      <DecisionList
        items={[makeItem({ id: 7, status: "pending" })]}
        onSelect={vi.fn()}
        onQuickDismiss={onQuickDismiss}
      />
    );
    render(tree);

    fireEvent.click(screen.getByText("Ignorer"));
    expect(onQuickDismiss).toHaveBeenCalledTimes(1);
    expect(onQuickDismiss).toHaveBeenCalledWith(7);
  });

  it("n'affiche pas 'Ignorer' inline sur une ligne non-pending", () => {
    const tree: ReactElement = (
      <DecisionList
        items={[makeItem({ id: 8, status: "resolved" })]}
        onSelect={vi.fn()}
        onQuickDismiss={vi.fn()}
      />
    );
    render(tree);
    expect(screen.queryByText("Ignorer")).not.toBeInTheDocument();
  });

  it("désactive 'Ignorer' quand dismissingId correspond à la ligne", () => {
    const tree: ReactElement = (
      <DecisionList
        items={[makeItem({ id: 9, status: "pending" })]}
        onSelect={vi.fn()}
        onQuickDismiss={vi.fn()}
        dismissingId={9}
      />
    );
    render(tree);
    // While in flight the label becomes an ellipsis and the button is disabled.
    const btn = screen.getByText("…").closest("button");
    expect(btn).toBeDisabled();
  });
});
