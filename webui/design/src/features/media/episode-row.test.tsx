// What an episode's row draws when the catalogue gives it no title.
//
// WHAT MAKES THIS NON-VACUOUS. The row is asserted on its whole `textContent`,
// so a placeholder, a « null », or the blank that used to stand before the
// title all fail it; the title element is asserted absent as well, and a
// titled row beside it proves the same assertion can see a title.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import "../../i18n";
import "../../lib/unit-words";
import MEDIA_SHEETS from "../../mocks/seeds/media-sheets.json";
import { dateLabel } from "./format";
import { episodeDate, episodeTitle } from "./variants";
import { EpisodeRow } from "./episode-row";

/**
 * Draws one episode's row, in the library state.
 *
 * @param episode The episode, as the sheet lists it; its title may be null.
 * @returns The row's markup, and its text as one reads it.
 */
function draw(
  episode: { number: number; title: string | null; airDate?: string | null },
): { html: string; text: string } {
  const html = renderToStaticMarkup(createElement(EpisodeRow, { episode, state: "in_library" }));
  // No DOM in this environment: the text is the markup without its tags.
  const text = html.replace(/<[^>]*>/g, "").trim();
  return { html, text };
}

describe("EpisodeRow", () => {
  it("is drawn from a seeded episode the catalogue gives no title", () => {
    const seeded = Object.values(MEDIA_SHEETS)
      .flatMap((sheet) => Object.values((sheet as { episodes?: Record<string, { number: number; title: string | null; airDate?: string }[]> }).episodes ?? {}))
      .flat()
      .find((episode) => episode.title === null);
    expect(seeded).toBeDefined();
    const { text } = draw(seeded!);
    expect(text).not.toContain("null");
    expect(text.startsWith(`E${String(seeded!.number).padStart(2, "0")} `)).toBe(true);
  });

  it("draws the number and the date alone when the episode has no title", () => {
    const { html, text } = draw({ number: 3, title: null, airDate: "2026-01-05" });
    expect(text).toBe(`E03 ${dateLabel("2026-01-05")}`);
    expect(html).not.toContain(episodeTitle());
    expect(html).not.toContain("null");
  });

  it("keeps the date at the row's right edge when the episode has no title", () => {
    const untitled = draw({ number: 3, title: null, airDate: "2026-01-05" }).html;
    expect(untitled).toContain(episodeDate({ untitled: true }));
    expect(untitled).toContain("ml-auto");
  });

  it("still draws a title when the catalogue gives one", () => {
    const { html, text } = draw({ number: 3, title: "Pilot", airDate: "2026-01-05" });
    expect(text).toBe(`E03 Pilot ${dateLabel("2026-01-05")}`);
    expect(html).toContain(episodeTitle());
  });
});
