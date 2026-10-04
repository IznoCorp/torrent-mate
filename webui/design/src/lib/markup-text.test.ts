// The two markup-string helpers, held on the shapes their readers write.
//
// WHAT MAKES THIS NON-VACUOUS. `escapeHtml` is asserted on a value carrying
// every character it must rewrite AND one it must leave alone, so a pattern
// that escaped nothing, or everything, fails; `svgIcon` is asserted on the
// default stroke and on an explicit one, which is the only branch it has.
import { describe, expect, it } from "vitest";
import { escapeHtml, svgIcon } from "./markup-text";

describe("escapeHtml", () => {
  it("writes the four markup characters as entities and leaves the rest", () => {
    expect(escapeHtml(`Tom & "Jerry" <1994> it's`)).toBe(
      "Tom &amp; &quot;Jerry&quot; &lt;1994&gt; it's",
    );
  });

  it("turns a value that is not a string into its string first", () => {
    expect(escapeHtml(2023)).toBe("2023");
  });
});

describe("svgIcon", () => {
  it("draws a stroke of 2 when none is given", () => {
    expect(svgIcon("<path/>")).toBe(
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path/></svg>',
    );
  });

  it("draws the stroke it is given", () => {
    expect(svgIcon("<path/>", 3)).toContain('stroke-width="3"');
  });
});
