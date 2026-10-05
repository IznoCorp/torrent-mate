// What the error surface says over a read the server refused (B-697, B-698, B-699).
//
// THE WIRE CARRIES A CODE AND THE INTERFACE CARRIES THE WORDS (i18n OPEN-1 B):
// the sheet's banner printed the v1 500's English developer line, « An
// unexpected error occurred. », under a French lead. Each case renders the
// surface over the exact body the server answers and asserts the reader's
// language, in both catalogues — and that no English line of the wire is drawn.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import i18next from "../i18n";
import en from "../i18n/en.json";
import fr from "../i18n/fr.json";
import { SurfaceError } from "./state-surfaces";

/** The v1 answer to an unhandled crash, as `http_v1/problem.py` builds it. */
const INTERNAL = {
  status: 500, title: "The server failed.", detail: "An unexpected error occurred.", code: "internal", params: {},
};

/** The v1 answer when `library.db` cannot be read. */
const UNAVAILABLE = {
  status: 503, title: "The library index cannot be read.", detail: "The library index cannot be read.",
  code: "library.unavailable", params: {},
};

/** A refusal with no code: a proxy's answer, or an operation whose lot has not landed its codes. */
const CODELESS = { status: 502, title: "Bad Gateway", detail: "upstream connect error" };

/**
 * Draws the surface over one failure, in one language.
 *
 * @param language The catalogue to say it in.
 * @param failure What the read was refused with.
 * @returns The surface's text as one reads it.
 */
function said(language: "fr" | "en", failure: unknown): string {
  void i18next.changeLanguage(language);
  const html = renderToStaticMarkup(createElement(SurfaceError, { subject: i18next.t("screens.media.sheetSubject"), failure }));
  // No DOM in this environment: the text is the markup without its tags.
  return html.replace(/<[^>]*>/g, "").replace(/&#x27;/g, "'").replace(/\s+/g, " ").trim();
}

afterEach(() => {
  void i18next.changeLanguage("fr");
});

describe("SurfaceError over a refused read", () => {
  it.each([["fr", fr], ["en", en]] as const)("says a 500 in the reader's words, never the wire's (%s)", (language, words) => {
    const text = said(language, INTERNAL);
    expect(text).toContain(words.refusals.internal);
    expect(text).not.toContain(INTERNAL.detail);
    expect(text).not.toContain(INTERNAL.title);
  });

  it.each([["fr", fr], ["en", en]] as const)("says an unreadable library as such (%s)", (language, words) => {
    const text = said(language, UNAVAILABLE);
    expect(text).toContain(words.refusals.library.unavailable);
    expect(text).not.toContain(UNAVAILABLE.detail);
  });

  // THE WORDS ARE PINNED LITERALLY: the cases above read the catalogue they assert, so a value
  // replaced by « XX » stayed green. The text is what the operator reads.
  it("says an unreadable library in these exact words, per language", () => {
    expect(said("fr", UNAVAILABLE)).toContain(
      "La médiathèque est indisponible : le serveur ne peut pas la lire pour le moment. Réessayez dans un instant.", // french-ok: the sentence the fr catalogue must carry
    );
    expect(said("en", UNAVAILABLE)).toContain(
      "The library is unavailable: the server cannot read it right now. Try again in a moment.",
    );
  });

  it.each([["fr", fr], ["en", en]] as const)("says a code-less refusal as a server failure (%s)", (language, words) => {
    const text = said(language, CODELESS);
    expect(text).toContain(words.refusals.internal);
    expect(text).not.toContain(CODELESS.detail);
  });

  it("keeps the timeout sentence for a read nobody answered", () => {
    const text = said("fr", new TypeError("Failed to fetch"));
    expect(text).toContain(fr.surfaces.error.body.replace(/\s+/g, " ").trim());
    expect(text).not.toContain("Failed to fetch");
  });
});
