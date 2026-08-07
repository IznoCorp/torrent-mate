/**
 * JourneyDetailSheet — the honesty rules the old journeys panel pinned,
 * re-pinned in their new home. Each rule once had a real incident behind it.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { JourneyItem } from "@/api/acquisition";

import { JourneyDetailSheet } from "./JourneyDetailSheet";

afterEach(cleanup);

function journey(over: Partial<JourneyItem> = {}): JourneyItem {
  return {
    info_hash: "feedbeef",
    followed_id: 1,
    decision_id: null,
    follow_title: "Silo",
    kind: "episode",
    season: 1,
    episode: 2,
    media_ref: { tvdb_id: 400000, tmdb_id: null, imdb_id: null },
    release_name: "Silo.S01E02.2160p.WEB-DL",
    status: "dispatched",
    stuck: false,
    resolution_state: null,
    resolution_trigger: null,
    estimated_stages: null,
    reconstructed_at: null,
    ingest_path: null,
    current_path: null,
    dispatch_path: "/d1/TV/Silo",
    grabbed_at: 1_750_000_000,
    ingested_at: null,
    scraped_at: null,
    dispatched_at: 1_750_100_000,
    grab_run_uid: "run-g1",
    ingest_run_uid: null,
    scrape_run_uid: null,
    dispatch_run_uid: null,
    ...over,
  };
}

function renderSheet(j: JourneyItem): void {
  render(
    <MemoryRouter>
      <JourneyDetailSheet journey={j} title="Silo" open onOpenChange={() => undefined} />
    </MemoryRouter>,
  );
}

describe("JourneyDetailSheet", () => {
  it("§14.2 — sur un parcours TERMINÉ, une étape sans date est FAITE, jamais « inconnue »", () => {
    renderSheet(journey());

    const stages = screen.getByTestId("journey-stages");
    // Ingéré and Scrapé have no timestamp but the journey dispatched: the
    // stage happened; only its instant is missing.
    expect(stages).toHaveTextContent("Ingéré");
    expect(stages.textContent).toContain("faite — instant non retrouvé");
    expect(stages.textContent).not.toContain("inconnue");
  });

  it("§13 — un instant ESTIMÉ porte « ≈ » et son aveu, jamais une fausse mesure", () => {
    renderSheet(
      journey({ ingested_at: 1_750_050_000, estimated_stages: "ingested" }),
    );

    const stages = screen.getByTestId("journey-stages");
    expect(stages.textContent).toContain("≈");
    expect(
      screen.getByTitle(/cette étape a bien eu lieu, mais son horodatage/),
    ).toBeInTheDocument();
  });

  it("un parcours EN VOL montre une étape non atteinte comme non atteinte", () => {
    renderSheet(journey({ dispatched_at: null, status: "grabbed" }));

    const stages = screen.getByTestId("journey-stages");
    expect(stages.textContent).not.toContain("faite — instant non retrouvé");
  });

  it("F3 — une étape datée à run connu pointe vers ce run", () => {
    renderSheet(journey());

    const link = screen.getByRole("link", {
      name: /Récupéré/,
    });
    expect(link).toHaveAttribute("href", "/pipeline?run=run-g1");
  });

  it("le nom de release est admis absent, jamais remplacé par un titre", () => {
    renderSheet(journey({ release_name: null }));

    expect(screen.getByTestId("journey-release")).toHaveTextContent(
      "Nom de release non enregistré",
    );
  });
});
