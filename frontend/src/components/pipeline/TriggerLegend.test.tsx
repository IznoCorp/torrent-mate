/**
 * TriggerLegend tests (pipeline-panel Phase 02).
 *
 * Asserts the tap-accessible trigger-legend popover:
 * - Closed by default (content not in the DOM).
 * - Opens on click/tap of the ``?`` button (accessible name).
 * - Lists every known trigger from {@link TRIGGER_INFO}.
 * - Is NOT hover-only — mouseover does not open it (DOIT-9).
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TriggerLegend } from "@/components/pipeline/TriggerLegend";

afterEach(cleanup);

describe("TriggerLegend", () => {
  it("is closed by default — popover content is not in the DOM", () => {
    render(<TriggerLegend />);

    // The popover heading ("Déclencheurs") must not be present when closed.
    expect(screen.queryByText("Déclencheurs")).not.toBeInTheDocument();
    // Trigger labels from TRIGGER_INFO must also be absent.
    expect(screen.queryByText("Fin de téléchargement")).not.toBeInTheDocument();
  });

  it("opens on tap/click of the ? button and lists every known trigger", async () => {
    render(<TriggerLegend />);

    // The ? button is discoverable via its accessible name.
    // Radix DropdownMenuTrigger listens for pointerdown, not click.
    fireEvent.pointerDown(
      screen.getByRole("button", { name: "Légende des déclencheurs" }),
      { button: 0, pointerType: "mouse" },
    );

    await waitFor(() => {
      // Popover heading is now visible inside the portal.
      expect(screen.getByText("Déclencheurs")).toBeInTheDocument();
    });

    // Every known trigger label + its meaning MUST appear in the popover
    // (TRIGGER_INFO insertion order — automatic triggers first, manual/CLI
    // last).
    expect(screen.getByText("Fin de téléchargement")).toBeInTheDocument();
    expect(
      screen.getByText("Lancé automatiquement à la fin d'un téléchargement."),
    ).toBeInTheDocument();

    expect(screen.getByText("Filet de sécurité")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Passage périodique de rattrapage (intervalle minimal).",
      ),
    ).toBeInTheDocument();

    expect(screen.getByText("Planifié")).toBeInTheDocument();
    expect(
      screen.getByText("Déclenché par une tâche planifiée (cron)."),
    ).toBeInTheDocument();

    expect(screen.getByText("Interface web")).toBeInTheDocument();
    expect(
      screen.getByText("Lancé manuellement depuis l'interface web."),
    ).toBeInTheDocument();

    expect(screen.getByText("Ligne de commande")).toBeInTheDocument();
    expect(screen.getByText("Lancé en ligne de commande.")).toBeInTheDocument();

    expect(screen.getByText("Manuel")).toBeInTheDocument();
    expect(screen.getByText("Déclenché manuellement.")).toBeInTheDocument();
  });

  it("is NOT hover-only — mouseover does not open the popover (DOIT-9)", async () => {
    render(<TriggerLegend />);

    const trigger = screen.getByRole("button", {
      name: "Légende des déclencheurs",
    });

    // A mouseover/mouseenter must NOT open the popover — it is tap/click-driven
    // (DOIT-9: never hover-only). The DropdownMenu trigger only responds to
    // pointerdown, which maps cleanly to click/tap.
    fireEvent.mouseOver(trigger);
    fireEvent.mouseEnter(trigger);
    expect(screen.queryByText("Déclencheurs")).not.toBeInTheDocument();

    // pointerDown DOES open it — confirms the interaction model is tap/click,
    // not hover.
    fireEvent.pointerDown(trigger, { button: 0, pointerType: "mouse" });

    await waitFor(() => {
      expect(screen.getByText("Déclencheurs")).toBeInTheDocument();
    });
  });
});
