import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MediaRow } from "./MediaRow";

const base = { title: "Silo", posterUrl: null, onOpen: vi.fn() };

describe("MediaRow", () => {
  afterEach(cleanup);

  it("expose DEUX cibles distinctes : l'affiche et le corps (A13)", () => {
    const onOpen = vi.fn();
    const onPoster = vi.fn();
    render(<MediaRow {...base} onOpen={onOpen} onPoster={onPoster} />);

    // Poster button carries aria-label="Fiche de Silo"
    fireEvent.click(screen.getByRole("button", { name: /Fiche de Silo/i }));
    expect(onPoster).toHaveBeenCalledOnce();
    expect(onOpen).not.toHaveBeenCalled();

    // Body button carries aria-label="Silo" (explicit, resolution 3)
    fireEvent.click(screen.getByRole("button", { name: "Silo" }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("§11 exception — sans onPoster, l'affiche n'est PAS un bouton", () => {
    render(<MediaRow {...base} />);
    expect(screen.queryByRole("button", { name: /Fiche de/i })).toBeNull();
  });

  it("§11 — sans onOpen, le corps n'est PAS un bouton (aucun faux contrôle)", () => {
    render(
      <MediaRow title="Silo" posterUrl={null} />,
    );
    // The body must not be a <button>.
    expect(screen.queryByRole("button", { name: "Silo" })).toBeNull();
    // The title is still visible, inside a non-interactive element.
    expect(screen.getByTestId("acq-card-title")).toHaveTextContent("Silo");
  });

  it("R3 — la ligne du titre ne contient QUE le titre", () => {
    render(
      <MediaRow {...base} facts={[{ kind: "note", text: "Nouveau" }]} />,
    );
    const titleLine = screen.getByTestId("acq-card-title");
    expect(titleLine).toHaveTextContent("Silo");
    expect(titleLine).not.toHaveTextContent("Nouveau");
  });

  it("R2 — la frise est sur sa propre ligne, hors de la rangée du haut", () => {
    const { container } = render(<MediaRow {...base} journey={{ stage: "taken" }} />);
    const top = screen.getByTestId("acq-card-top");
    // The strip is the card's last block, a sibling of the top row.
    const trailingStrip = container.querySelector('[data-testid="acq-card"] > :last-child');
    expect(trailingStrip).not.toBeNull();
    expect(top.contains(trailingStrip)).toBe(false);
  });

  it("le panneau ne prend QUE des faits : une note, une puce, une jauge", () => {
    render(
      <MediaRow
        {...base}
        facts={[
          { kind: "fraction", text: "5/8" },
          { kind: "chip", tone: "warning", text: "En attente" },
          { kind: "fresh" },
        ]}
      />,
    );
    expect(screen.getByText("5/8")).toBeInTheDocument();
    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.getByTestId("chip-nouveau")).toBeInTheDocument();
  });

  /** Make matchMedia report a fine pointer, or a touch one. */
  function stubPointer(fine: boolean): void {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: fine,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    );
  }

  it("aucun « ··· » sur la carte (opérateur : tap accidentel, redondant avec le panel)", () => {
    // The kebab is gone on every pointer — the card's actions live in the
    // detail sheet (tap) and the swipe panes.
    stubPointer(true);
    render(<MediaRow {...base} />);
    expect(screen.queryByText("···")).toBeNull();
    vi.unstubAllGlobals();
  });

  it("§12 — la raison enroule et n'est jamais tronquée par nowrap", () => {
    render(<MediaRow {...base} reason="titre ambigu — 3 candidats proposés" />);
    const reason = screen.getByText(/titre ambigu/);
    expect(reason.className).not.toMatch(/whitespace-nowrap/);
    expect(reason.className).toMatch(/line-clamp-2/);
  });

  it("le sous-titre, lui, tronque sur une ligne", () => {
    render(<MediaRow {...base} subtitle="S02E05 · 1080p WEB-DL · 42 sources" />);
    const sub = screen.getByText(/S02E05/);
    expect(sub.className).toMatch(/truncate/);
  });
});
