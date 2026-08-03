/**
 * EpisodeStateLegende — the colour key derives from the vocabulary maps (#9).
 *
 * The load-bearing assertion: the legend lists EXACTLY the keys of
 * `EPISODE_STATE_LABEL`, with its labels — no hardcoded copy, no missing state.
 * A state added to (or removed from) the single-source maps must change the
 * legend automatically, so a drift here is a test failure rather than a silent
 * mismatch between a chip's colour and the key beneath the matrix.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EpisodeStateLegende } from "./EpisodeStateLegende";
import { EPISODE_LEGEND_ORDER, EPISODE_STATE_LABEL } from "./meta";

afterEach(cleanup);

describe("EpisodeStateLegende", () => {
  it("lists exactly the states of EPISODE_LEGEND_ORDER (no drift)", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    const labels = EPISODE_LEGEND_ORDER.map((s) => EPISODE_STATE_LABEL[s]);
    // Every label present…
    for (const label of labels) {
      expect(within(legend).getByText(label)).toBeInTheDocument();
    }
    // …and NOTHING beyond them: one chip (the swatch) per state, so the legend
    // can neither omit a state nor invent one. Drift in the maps = failure here.
    const chips = legend.querySelectorAll('[data-slot="badge"]');
    expect(chips).toHaveLength(labels.length);
  });

  it("walks the lifecycle order the operator reads, left to right", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    // Unknown → announced → searched-but-nothing → takeable → being taken →
    // owned. Pinned as an ORDERED list: a reshuffle is a regression, not a
    // detail (the legend is how the operator learns the flow).
    const chipTexts = Array.from(
      legend.querySelectorAll('[data-slot="badge"]'),
    ).map((c) => c.textContent.trim());
    expect(chipTexts).toEqual([
      "Non vérifié",
      "Annoncé",
      "En attente de torrent",
      "À récupérer",
      "En cours d'acquisition",
      "En médiathèque",
    ]);
  });

  it("never prints the absorbed state as a legend entry of its own", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    // An absorbed episode renders as « En cours d'acquisition » — listing it
    // would print that same chip twice for one operator-facing state.
    expect(
      within(legend).getAllByText("En cours d'acquisition"),
    ).toHaveLength(1);
    expect(within(legend).queryByText(/Absorb/)).not.toBeInTheDocument();
  });

  it("renders each entry as a coloured chip carrying its label", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    // The chip IS the swatch: each badge shows its label as its text.
    const chips = Array.from(legend.querySelectorAll('[data-slot="badge"]'));
    const chipTexts = chips.map((c) => c.textContent.trim());
    for (const state of EPISODE_LEGEND_ORDER) {
      expect(chipTexts).toContain(EPISODE_STATE_LABEL[state]);
    }
  });
});
