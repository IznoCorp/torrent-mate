// What a tracker's failed write says under its row (B-697, B-698, B-699 family).
//
// A 500 on the config write printed the wire's English developer line, « An
// unexpected error occurred. », under a French lead. The 422 is the tracker's
// own message and stays data.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import i18next from "../../i18n";
import fr from "../../i18n/fr.json";
import { WriteRefusalLine } from "./trackers-tab";

/**
 * Draws the line over one failed write.
 *
 * @param refusal What the write earned.
 * @returns The line's text as one reads it.
 */
function said(refusal: Parameters<typeof WriteRefusalLine>[0]["refusal"]): string {
  const html = renderToStaticMarkup(createElement(WriteRefusalLine, { refusal }));
  // No DOM in this environment: the text is the markup without its tags.
  return html.replace(/<[^>]*>/g, "").replace(/&#x27;/g, "'").replace(/\s+/g, " ").trim();
}

afterEach(() => {
  void i18next.changeLanguage("fr");
});

describe("WriteRefusalLine", () => {
  it("words a 500 in the reader's language, never the wire's English line", () => {
    const text = said({ status: 500, detail: "An unexpected error occurred.", code: "internal", params: {} });
    expect(text).toContain(fr.refusals.internal);
    expect(text).not.toContain("An unexpected error occurred.");
  });

  it("words a failure that carries no code the interface knows", () => {
    const text = said({ status: 403, detail: "Forbidden by policy." });
    expect(text).toContain(fr.refusals.internal);
    expect(text).not.toContain("Forbidden by policy.");
  });

  it("keeps the 422's detail: it is the tracker's own message", () => {
    expect(said({ status: 422, detail: "Tracker unreachable since Monday." })).toContain("Tracker unreachable since Monday.");
  });
});
