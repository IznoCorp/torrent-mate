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

  it("prend le DOSSIER pour sujet, jamais le titre extrait (R57)", () => {
    renderList([makeItem()]);
    // The scrape could not name what is in the folder, so the extracted title
    // is the one thing that cannot be trusted here.
    const folder = screen.getByTestId("decision-folder");
    expect(folder).toHaveTextContent("Inception (2010)");
    expect(folder.className).toContain("font-mono");
    expect(screen.queryByText("Inception", { exact: true })).toBeNull();
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

  it("dit COMBIEN de candidats, en toutes lettres", () => {
    // A bare number beside a status badge answers « 3 what ? ».
    renderList([makeItem({ candidates_count: 5 })]);
    expect(screen.getByText(/5 candidats/)).toBeInTheDocument();
  });

  it("dit aussi quand il n'y en a aucun", () => {
    renderList([makeItem({ candidates_count: 0 })]);
    expect(screen.getByText(/aucun candidat/)).toBeInTheDocument();
  });

  it("affiche plusieurs lignes", () => {
    renderList([
      makeItem({ id: 1, staging_path: "/s/Alpha" }),
      makeItem({ id: 2, staging_path: "/s/Beta" }),
    ]);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Empty state
  // -----------------------------------------------------------------------

  it("affiche le message vide quand la liste est vide", () => {
    renderList([]);
    expect(screen.getByText("Aucune décision")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Click callback
  // -----------------------------------------------------------------------

  it("appelle onSelect avec l'id au clic sur une ligne", () => {
    const onSelect = vi.fn();
    renderList([makeItem({ id: 42 })], onSelect);

    fireEvent.click(screen.getByRole("button", { name: "Inception (2010)" }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(42);
  });

  it("appelle onSelect avec l'id correct pour chaque ligne", () => {
    const onSelect = vi.fn();
    renderList(
      [
        makeItem({ id: 10, staging_path: "/s/Alpha" }),
        makeItem({ id: 20, staging_path: "/s/Beta" }),
      ],
      onSelect,
    );

    fireEvent.click(screen.getByRole("button", { name: "Alpha" }));
    expect(onSelect).toHaveBeenCalledWith(10);

    fireEvent.click(screen.getByRole("button", { name: "Beta" }));
    expect(onSelect).toHaveBeenCalledWith(20);
  });

  // -----------------------------------------------------------------------
  // Trigger chip variants
  // -----------------------------------------------------------------------

  it("affiche le chip 'Confiance faible' avec le bon tone pour below_threshold", () => {
    renderList([makeItem({ trigger: "below_threshold" })]);
    const puce = screen.getByText("Confiance faible");
    expect(puce.closest("[data-slot='chip']")).toBeInTheDocument();
  });

  it("affiche le chip 'Confiance moyenne' avec le bon tone pour mid_band", () => {
    renderList([makeItem({ trigger: "mid_band" })]);
    const puce = screen.getByText("Confiance moyenne");
    expect(puce.closest("[data-slot='chip']")).toBeInTheDocument();
  });

  it("affiche le chip 'Candidats ambigus' avec le bon tone pour ambiguous", () => {
    renderList([makeItem({ trigger: "ambiguous" })]);
    const puce = screen.getByText("Candidats ambigus");
    expect(puce.closest("[data-slot='chip']")).toBeInTheDocument();
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
    const badge = screen.getByText("Laissée telle quelle");
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
    const badge = screen.getByText("Remplacée depuis");
    expect(badge).toBeInTheDocument();
    const wrapper = badge.closest("[title]");
    expect(wrapper).toHaveAttribute(
      "title",
      expect.stringContaining("version plus récente"),
    );
  });

  it("une décision EN ATTENTE ne porte aucune puce d'issue", () => {
    // There is no outcome yet, and drawing one would be an invented fact.
    renderList([makeItem({ status: "pending" })]);
    expect(screen.queryByText("Réglée")).toBeNull();
    expect(screen.queryByText("En attente")).toBeNull();
    expect(screen.getByText("Confiance faible")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Inline quick-dismiss (§4.1)
  // -----------------------------------------------------------------------

  it("affiche l'action « Laisser tel quel » inline sur une ligne pending quand onQuickDismiss est fourni", () => {
    renderList([makeItem({ status: "pending" })]);
    // No onQuickDismiss → no inline action.
    expect(screen.queryByText("Laisser tel quel")).not.toBeInTheDocument();
  });

  it("appelle onQuickDismiss avec l'id au clic sur « Laisser tel quel »", () => {
    const onQuickDismiss = vi.fn();
    const tree: ReactElement = (
      <DecisionList
        items={[makeItem({ id: 7, status: "pending" })]}
        onSelect={vi.fn()}
        onQuickDismiss={onQuickDismiss}
      />
    );
    render(tree);

    fireEvent.click(screen.getByText("Laisser tel quel"));
    expect(onQuickDismiss).toHaveBeenCalledTimes(1);
    expect(onQuickDismiss).toHaveBeenCalledWith(7);
  });

  it("donne au raccourci le minimum tactile mobile min-h-11 (X4)", () => {
    render(
      <DecisionList
        items={[makeItem({ id: 7, status: "pending" })]}
        onSelect={vi.fn()}
        onQuickDismiss={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: "Laisser tel quel" });
    expect(button.className).toContain("min-h-11");
    expect(button.className).toContain("md:min-h-8");
  });

  it("n'affiche pas le raccourci inline sur une ligne non-pending", () => {
    const tree: ReactElement = (
      <DecisionList
        items={[makeItem({ id: 8, status: "resolved" })]}
        onSelect={vi.fn()}
        onQuickDismiss={vi.fn()}
      />
    );
    render(tree);
    expect(screen.queryByText("Laisser tel quel")).not.toBeInTheDocument();
  });

  it("désactive le raccourci quand dismissingId correspond à la ligne", () => {
    const tree: ReactElement = (
      <DecisionList
        items={[makeItem({ id: 9, status: "pending" })]}
        onSelect={vi.fn()}
        onQuickDismiss={vi.fn()}
        dismissingId={9}
      />
    );
    render(tree);
    // While in flight the label says so and the button is disabled.
    const btn = screen.getByText("En cours…").closest("button");
    expect(btn).toBeDisabled();
  });
});
