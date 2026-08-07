/**
 * EpisodeStateLegende — the colour key derives from the vocabulary maps (#9).
 *
 * The load-bearing assertion: the legend lists EXACTLY the keys of
 * `EPISODE_STATE_LABEL`, with its labels — no hardcoded copy, no missing state.
 * A state added to (or removed from) the single-source maps must change the
 * legend automatically, so a drift here is a test failure rather than a silent
 * mismatch between a cell's colour and the key beneath the matrix.
 *
 * The legend entries are SQUARE swatches + plain labels (the matrix cells are
 * squares, and a key drawn with a different shape than what it explains
 * misleads) — an entry is a `<span>` holding an `<i>` swatch and its text.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EpisodeStateLegende } from "./EpisodeStateLegende";
import { EPISODE_LEGEND_ORDER, EPISODE_STATE_LABEL } from "./meta";

afterEach(cleanup);

/** The legend's entries, in DOM order: the spans that carry an `<i>` swatch. */
function entries(legend: HTMLElement): HTMLElement[] {
  return Array.from(legend.querySelectorAll("span")).filter(
    (sp) => sp.querySelector("i") != null,
  );
}

describe("EpisodeStateLegende", () => {
  it("lists exactly the states of EPISODE_LEGEND_ORDER (no drift)", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    const labels = EPISODE_LEGEND_ORDER.map((s) => EPISODE_STATE_LABEL[s]);
    // Every label present…
    for (const label of labels) {
      expect(within(legend).getByText(label)).toBeInTheDocument();
    }
    // …and NOTHING beyond them: one swatch entry per state, so the legend
    // can neither omit a state nor invent one. Drift in the maps = failure here.
    expect(entries(legend)).toHaveLength(labels.length);
  });

  it("walks the lifecycle order the operator reads, left to right", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    // Unknown → announced → searched-but-nothing → takeable → being taken →
    // owned. Pinned as an ORDERED list: a reshuffle is a regression, not a
    // detail (the legend is how the operator learns the flow).
    const texts = entries(legend).map((c) => c.textContent.trim());
    expect(texts).toEqual([
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
    // would print that same swatch twice for one operator-facing state.
    expect(
      within(legend).getAllByText("En cours d'acquisition"),
    ).toHaveLength(1);
    expect(within(legend).queryByText(/Absorb/)).not.toBeInTheDocument();
  });

  it("renders each entry as a SQUARE swatch carrying its label", () => {
    render(<EpisodeStateLegende />);
    const legend = screen.getByLabelText("Légende des statuts d'épisode");

    for (const entry of entries(legend)) {
      const swatch = entry.querySelector("i");
      // Square, not a dot: rounded-[2px] is the maquette's 2 px corner —
      // rounded-full here would redraw the key as circles again.
      expect(swatch?.className).toContain("rounded-[2px]");
      expect(swatch?.className).not.toContain("rounded-full");
    }
  });
});
