/**
 * InterpretedRunFeed — segment rendering tests (X5/PIPELINE-8).
 *
 * The interpreted narrative embeds machine tokens (item / disk / provider /
 * dest names) inside French prose; these tests pin that the tokens render in
 * ``font-mono`` spans at the render site, and that segment-less lines (step
 * headers, persisted summaries) still fall back to the flat text.
 */

import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";

import type { EventStreamState } from "@/hooks/useEventStream";
import { EventStreamContext } from "@/hooks/useEventStreamContext";
import { InterpretedRunFeed } from "@/components/pipeline/InterpretedRunFeed";
import type { InterpretedLine } from "@/components/pipeline/interpretRun";

/** An empty, connected stream state (the precomputed-lines path ignores it). */
const EMPTY_STREAM: EventStreamState = {
  events: [],
  connectionState: "connected",
  buildCommit: "abc1234",
  lastEventId: null,
};

/** Render the feed with precomputed lines inside the required provider. */
function renderFeed(lines: readonly InterpretedLine[]): void {
  const tree: ReactElement = (
    <EventStreamContext.Provider value={EMPTY_STREAM}>
      <InterpretedRunFeed lines={lines} />
    </EventStreamContext.Provider>
  );
  render(tree);
}

afterEach(cleanup);

describe("InterpretedRunFeed — segments mono (X5/PIPELINE-8)", () => {
  it("rend les tokens machine en font-mono dans la prose française", () => {
    renderFeed([
      {
        step: "dispatch",
        tone: "success",
        text: "Rangé sur Disk2 : The Movie (2024)",
        segments: [
          { text: "Rangé" },
          { text: " sur " },
          { text: "Disk2", mono: true },
          { text: " : " },
          { text: "The Movie (2024)", mono: true },
        ],
      },
    ]);

    // Machine tokens are mono…
    expect(screen.getByText("Disk2").className).toContain("font-mono");
    expect(screen.getByText("The Movie (2024)").className).toContain(
      "font-mono",
    );
    // …the French prose is not.
    expect(screen.getByText("Rangé").className).not.toContain("font-mono");
  });

  it("retombe sur le texte plat pour une ligne sans segments", () => {
    renderFeed([
      {
        step: "ingest",
        tone: "info",
        text: "Récupération des téléchargements…",
      },
    ]);

    expect(
      screen.getByText("Récupération des téléchargements…"),
    ).toBeInTheDocument();
  });
});
