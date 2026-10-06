// The deck card's poster address comes from the server and lands in an `src`
// attribute: it is escaped like every other value the card prints, so a quote
// or an angle bracket in it never closes the attribute nor opens a tag.
import { describe, expect, it } from "vitest";
import type { Schemas } from "../../lib/contract-schemas";
import { escapeHtml } from "../../lib/markup-text";
import { deckCard } from "./discover-cards";

const HOSTILE = 'https://img.example.invalid/p.jpg" onerror="alert(1)"><script>x</script>';

/**
 * A suggestion carrying the given high-definition poster address.
 *
 * @param posterHighDefinition The address.
 * @returns The suggestion.
 */
function suggestionWith(posterHighDefinition: string): Schemas["Suggestion"] {
  return {
    title: "Silo",
    year: "2023",
    kind: "Série",
    rating: 8,
    poster: "",
    posterHighDefinition,
  } as unknown as Schemas["Suggestion"];
}

describe("deckCard's poster", () => {
  it("escapes a quote and an angle bracket in the address", () => {
    const markup = deckCard(suggestionWith(HOSTILE), 0, 0);
    expect(markup).toContain(`<img src="${escapeHtml(HOSTILE)}" alt="" loading="lazy">`);
    expect(markup).not.toContain("<script>");
    expect(markup).not.toContain('p.jpg" onerror');
  });
});
