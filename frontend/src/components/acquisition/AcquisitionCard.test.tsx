import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AcquisitionCard } from "./AcquisitionCard";

const base = { title: "Silo", posterUrl: null, onOpen: vi.fn() };

describe("AcquisitionCard", () => {
  afterEach(cleanup);

  it("expose DEUX cibles distinctes : l'affiche et le corps (A13)", () => {
    const onOpen = vi.fn();
    const onPoster = vi.fn();
    render(<AcquisitionCard {...base} onOpen={onOpen} onPoster={onPoster} />);

    // Poster button carries aria-label="Fiche de Silo"
    fireEvent.click(screen.getByRole("button", { name: /Fiche de Silo/i }));
    expect(onPoster).toHaveBeenCalledOnce();
    expect(onOpen).not.toHaveBeenCalled();

    // Body button carries aria-label="Silo" (explicit, resolution 3)
    fireEvent.click(screen.getByRole("button", { name: "Silo" }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("§11 exception — sans onPoster, l'affiche n'est PAS un bouton", () => {
    render(<AcquisitionCard {...base} />);
    expect(screen.queryByRole("button", { name: /Fiche de/i })).toBeNull();
  });

  it("§11 — sans onOpen, le corps n'est PAS un bouton (aucun faux contrôle)", () => {
    render(
      <AcquisitionCard title="Silo" posterUrl={null} />,
    );
    // The body must not be a <button>.
    expect(screen.queryByRole("button", { name: "Silo" })).toBeNull();
    // The title is still visible, inside a non-interactive element.
    expect(screen.getByTestId("acq-card-title")).toHaveTextContent("Silo");
  });

  it("R3 — la ligne du titre ne contient QUE le titre", () => {
    render(
      <AcquisitionCard {...base} meta={<span data-testid="chip">Nouveau</span>} />,
    );
    const titleLine = screen.getByTestId("acq-card-title");
    expect(titleLine).toHaveTextContent("Silo");
    expect(within(titleLine).queryByTestId("chip")).toBeNull();
  });

  it("R2 — la frise est sur sa propre ligne, hors de la rangée du haut", () => {
    render(<AcquisitionCard {...base} strip={<div data-testid="strip" />} />);
    const top = screen.getByTestId("acq-card-top");
    expect(within(top).queryByTestId("strip")).toBeNull();
    expect(screen.getByTestId("strip")).toBeInTheDocument();
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

  it("le « ··· » est rendu au doigt AUSSI (arbitrage opérateur, remplace A11)", () => {
    // The operator reversed the earlier touch-rejection: the kebab is the one
    // visible affordance for a card's actions, on EVERY pointer — the touch
    // chevron is gone with it.
    stubPointer(false);
    render(
      <AcquisitionCard {...base} menu={<button data-testid="kebab">···</button>} />,
    );

    expect(screen.getByTestId("kebab")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("R1 — au pointeur fin, le « ··· » est rendu DANS la carte (il voyage avec elle au balayage)", () => {
    stubPointer(true);
    render(
      <AcquisitionCard {...base} menu={<button data-testid="kebab">···</button>} />,
    );

    const card = screen.getByTestId("acq-card");
    expect(within(card).getByTestId("kebab")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("§12 — la raison enroule et n'est jamais tronquée par nowrap", () => {
    render(<AcquisitionCard {...base} reason="titre ambigu — 3 candidats proposés" />);
    const reason = screen.getByText(/titre ambigu/);
    expect(reason.className).not.toMatch(/whitespace-nowrap/);
    expect(reason.className).toMatch(/line-clamp-2/);
  });

  it("le sous-titre, lui, tronque sur une ligne", () => {
    render(<AcquisitionCard {...base} subtitle="S02E05 · 1080p WEB-DL · 42 sources" />);
    const sub = screen.getByText(/S02E05/);
    expect(sub.className).toMatch(/truncate/);
  });
});
