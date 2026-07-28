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
import { EPISODE_STATE_LABEL } from "./meta";

afterEach(cleanup);

describe("EpisodeStateLegende", () => {
  it("lists exactly the states of EPISODE_STATE_LABEL (no drift)", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    const labels = Object.values(EPISODE_STATE_LABEL);
    // Every label present…
    for (const label of labels) {
      expect(within(legend).getByText(label)).toBeInTheDocument();
    }
    // …and NOTHING beyond them: one chip (the swatch) per state, so the legend
    // can neither omit a state nor invent one. Drift in the maps = failure here.
    const chips = legend.querySelectorAll('[data-slot="badge"]');
    expect(chips).toHaveLength(labels.length);
  });

  it("renders each entry as a coloured chip carrying its label", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    // The chip IS the swatch: each badge shows its label as its text.
    const chips = Array.from(legend.querySelectorAll('[data-slot="badge"]'));
    const chipTexts = chips.map((c) => c.textContent.trim());
    for (const label of Object.values(EPISODE_STATE_LABEL)) {
      expect(chipTexts).toContain(label);
    }
  });
});
