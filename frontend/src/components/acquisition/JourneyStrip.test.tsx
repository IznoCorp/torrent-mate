import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { JourneyStrip, STAGES } from "./JourneyStrip";

describe("JourneyStrip (§14.3)", () => {
  afterEach(cleanup);

  it("les étapes franchies, l'étape courante et celles à venir sont distinctes", () => {
    render(<JourneyStrip stage="ingere" />);
    expect(screen.getByText(/pris — franchie/)).toBeInTheDocument();
    expect(screen.getByText(/ingéré — en cours/)).toBeInTheDocument();
    expect(screen.getByText(/rangé — à venir/)).toBeInTheDocument();
  });

  it("une étape BLOQUÉE est un état à elle, ni « en cours » ni « à venir »", () => {
    render(<JourneyStrip stage="scrape" blocked />);
    expect(screen.getByText(/scrapé — bloquée/)).toBeInTheDocument();
    expect(screen.queryByText(/scrapé — en cours/)).toBeNull();
  });

  it("chaque étape est une piste de largeur égale qui tronque — anti-chevauchement par construction", () => {
    const { container } = render(<JourneyStrip stage="pris" />);
    const stations = container.querySelectorAll("[data-station]");
    expect(stations).toHaveLength(STAGES.length);
    stations.forEach((st) => {
      expect(st.className).toMatch(/min-w-0/);
      expect(st.className).toMatch(/flex-1/);
      const label = st.querySelector("[data-station-label]");
      expect(label?.className).toMatch(/truncate/);
    });
  });

  it("aucun libellé n'est un token machine (NE-DOIT-PAS-4)", () => {
    render(<JourneyStrip stage="telech" />);
    // "pris" is a real French word that intentionally equals its key — it is
    // not a machine token. The other four keys must never appear verbatim.
    const machineTokens = STAGES.filter((s) => s.key !== "pris").map((s) => s.key);
    for (const key of machineTokens) {
      expect(screen.queryByText(key, { exact: true })).toBeNull();
    }
  });
});
