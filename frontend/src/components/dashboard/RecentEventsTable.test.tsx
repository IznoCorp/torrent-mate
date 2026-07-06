import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { EventMessage } from "@/api/events";
import { RecentEventsTable } from "@/components/dashboard/RecentEventsTable";

/** Build an ``EventMessage`` with a stream-id timestamp prefix. */
function makeEvent(ms: number, type: string): EventMessage {
  return { id: `${String(ms)}-0`, type, data: {} };
}

/** The type text of the first data row (row 0 is the header). */
function firstDataRowType(): string {
  const [, firstBody] = screen.getAllByRole("row");
  return firstBody?.textContent ?? "";
}

afterEach(cleanup);

describe("RecentEventsTable", () => {
  const events = [
    makeEvent(1_000, "Alpha"),
    makeEvent(3_000, "Charlie"),
    makeEvent(2_000, "Bravo"),
  ];

  it("trie par heure décroissante par défaut (le plus récent en premier)", () => {
    render(<RecentEventsTable events={events} />);
    expect(firstDataRowType()).toContain("Charlie");
  });

  it("réordonne par événement quand on clique l’en-tête « Événement »", () => {
    render(<RecentEventsTable events={events} />);

    fireEvent.click(screen.getByRole("button", { name: "Événement" }));

    // Ascending by event name → Alpha first.
    expect(firstDataRowType()).toContain("Alpha");
  });

  it("rend un badge de niveau par sévérité dans la colonne « Niveau »", () => {
    render(
      <RecentEventsTable
        events={[
          makeEvent(1_000, "PipelineStepErrored"),
          makeEvent(2_000, "DiskSpaceWarning"),
          makeEvent(3_000, "PipelineStepStarted"),
        ]}
      />,
    );
    // The severity → level badge text: error / warn / info.
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(screen.getByText("warn")).toBeInTheDocument();
    expect(screen.getByText("info")).toBeInTheDocument();
  });

  it("affiche un état vide sans événement", () => {
    render(<RecentEventsTable events={[]} />);
    expect(
      screen.getByText("Aucun événement pour l’instant."),
    ).toBeInTheDocument();
  });
});
