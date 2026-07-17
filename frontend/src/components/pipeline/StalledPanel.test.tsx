import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  StalledPanel,
  type StepReasonsEntry,
} from "@/components/pipeline/StalledPanel";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(cleanup);

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StalledPanel", () => {
  it("affiche le titre « Ce qui n'a pas avancé » avec les raisons par étape", () => {
    const stepReasons: StepReasonsEntry[] = [
      {
        step: "ingest",
        reasons: [
          "Film X : espace disque insuffisant",
          "Série Y : contenu source introuvable",
        ],
      },
      { step: "scrape", reasons: ["Film Z : aucun résultat TMDB"] },
    ];

    render(<StalledPanel stepReasons={stepReasons} />);

    // Title is always present when there are reasons.
    expect(screen.getByText("Ce qui n'a pas avancé")).toBeInTheDocument();

    // Every reason is rendered.
    expect(
      screen.getByText("Film X : espace disque insuffisant"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Série Y : contenu source introuvable"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Film Z : aucun résultat TMDB"),
    ).toBeInTheDocument();

    // French labels from STEP_LABEL are used as step group headings.
    expect(
      screen.getByText("Récupération des téléchargements"),
    ).toBeInTheDocument();
    expect(screen.getByText("Recherche des métadonnées")).toBeInTheDocument();
  });

  it("n'affiche rien quand stepReasons est vide", () => {
    const { container } = render(<StalledPanel stepReasons={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("utilise le nom brut de l'étape quand STEP_LABEL ne le connaît pas", () => {
    const stepReasons: StepReasonsEntry[] = [
      { step: "future_step", reasons: ["Raison inconnue"] },
    ];

    render(<StalledPanel stepReasons={stepReasons} />);

    // Fallback: renders the raw step identifier when no French label exists.
    expect(screen.getByText("future_step")).toBeInTheDocument();
    expect(screen.getByText("Raison inconnue")).toBeInTheDocument();
  });

  it("applique les classes CSS de type warning", () => {
    const stepReasons: StepReasonsEntry[] = [
      { step: "sort", reasons: ["Raison test"] },
    ];

    render(<StalledPanel stepReasons={stepReasons} />);

    // The warning card is the parent of the heading <p>.
    const heading = screen.getByText("Ce qui n'a pas avancé");
    const card = heading.parentElement;
    expect(card?.className).toContain("border-[var(--warning)]/30");
    expect(card?.className).toContain("bg-[var(--warning)]/10");
  });
});
