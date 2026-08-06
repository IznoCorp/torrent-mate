import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { JourneyStrip, STAGES } from "./JourneyStrip";
import type { Stage } from "./JourneyStrip";

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

  it("une étape bloquée se distingue de « en cours » par autre chose que la couleur", () => {
    const { container } = render(<JourneyStrip stage="scrape" blocked />);
    const blockedDot = container.querySelector(
      '[data-station="scrape"] [aria-hidden="true"]',
    );
    expect(blockedDot).not.toBeNull();
    // Shape is the colour-blind differentiator (§14.3): the blocked dot is
    // square, not round, so it reads as "stopped" without relying on red.
    expect((blockedDot as HTMLElement).className).toMatch(/rounded-\[2px\]/);
    // Must NOT carry rounded-full — if it does, the radius was left in the
    // base string and two radius classes collide (which one wins is arbitrary).
    expect((blockedDot as HTMLElement).className).not.toMatch(/rounded-full/);
  });

  it("le point « en cours » n'a PAS le différenciateur structurel du point bloqué", () => {
    const { container } = render(<JourneyStrip stage="ingere" />);
    const nowDot = container.querySelector(
      '[data-station="ingere"] [aria-hidden="true"]',
    );
    expect(nowDot).not.toBeNull();
    // The "now" dot must be round — this proves rounded-full was moved into
    // each per-state branch rather than sitting in the base class string.
    expect((nowDot as HTMLElement).className).toMatch(/rounded-full/);
    // Must NOT carry the square radius — if it does, the two radius classes
    // collide (both emitted → Tailwind output order determines the winner).
    expect((nowDot as HTMLElement).className).not.toMatch(/rounded-\[2px\]/);
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

  it("une étape inconnue ne ment PAS — elle déclare « inconnue », pas « à venir »", () => {
    const { container } = render(
      <JourneyStrip stage={"bogus" as unknown as Stage} />,
    );
    // Must render the unknown marker, not five « à venir » stations.
    expect(
      container.querySelector("[data-station-unknown]"),
    ).not.toBeNull();
    // The screen-reader text must say « inconnue », never imply « pas faite ».
    expect(screen.getByText(/inconnue/)).toBeInTheDocument();
    // No station should claim « à venir » — because nothing is known.
    expect(screen.queryByText(/à venir/)).toBeNull();
  });
});
