/**
 * Unit tests for MediaTimeline (webui-overhaul OBJ2A / OBJ1 shared timeline).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { StagingStageStep } from "@/api/client";
import { MediaTimeline } from "@/components/staging/MediaTimeline";

const STAGES: StagingStageStep[] = [
  { key: "arrival", label: "Arrivée", state: "done" },
  { key: "matching", label: "Matching", state: "blocked" },
  { key: "scraping", label: "Scraping", state: "active" },
  { key: "trailers", label: "Trailers", state: "pending" },
  { key: "verify", label: "Vérification", state: "skipped" },
];

afterEach(cleanup);

describe("MediaTimeline", () => {
  it("renders every stage label", () => {
    render(<MediaTimeline stages={STAGES} />);
    for (const s of STAGES) {
      expect(screen.getByText(s.label)).toBeInTheDocument();
    }
  });

  it("maps each state to its French label", () => {
    render(<MediaTimeline stages={STAGES} />);
    expect(screen.getByText("Fait")).toBeInTheDocument();
    expect(screen.getByText("Bloqué")).toBeInTheDocument();
    expect(screen.getByText("En cours")).toBeInTheDocument();
    expect(screen.getByText("En attente")).toBeInTheDocument();
    expect(screen.getByText("Non applicable")).toBeInTheDocument();
  });
});
