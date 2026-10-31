// A poster's address is data, and the markup spelling draws it inert (N9 of the K2-11 correction round).
//
// WHAT MAKES THIS NON-VACUOUS. The label beside it was escaped and the address
// was not: an address carrying a double quote closed `src` and wrote the rest as
// attributes of the picture — an `onerror` handler among them — now that v1
// serves the address from a provider and from the library's folders.
import { describe, expect, it } from "vitest";
import { posterArtworkMarkup } from "./poster";

describe("a poster's markup", () => {
  it("draws an address carrying a double quote inert", () => {
    const markup = posterArtworkMarkup({ source: 'poster.webp" onerror="alert(1)', icon: "", label: "Silo" });
    expect(markup).toBe('<img src="poster.webp&quot; onerror=&quot;alert(1)" alt="" loading="lazy">');
    expect(markup).not.toContain('" onerror="');
  });
});
