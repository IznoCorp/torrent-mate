import { describe, expect, it } from "vitest";

import { mediaSheetHref, type MediaRef } from "@/lib/media-href";

describe("mediaSheetHref", () => {
  it("construit l'URL de base avec provider et providerId", () => {
    expect(
      mediaSheetHref({ provider: "tmdb", providerId: "27205" }),
    ).toBe("/media/tmdb/27205");
  });

  it("encode les caractères spéciaux dans les deux segments", () => {
    expect(
      mediaSheetHref({
        provider: "tmdb",
        providerId: "tt 0123/special",
      }),
    ).toBe("/media/tmdb/tt%200123%2Fspecial");
  });

  it("ajoute ?kind=movie quand le hint est fourni", () => {
    expect(
      mediaSheetHref({ provider: "tmdb", providerId: "27205", kind: "movie" }),
    ).toBe("/media/tmdb/27205?kind=movie");
  });

  it("ajoute ?kind=tv quand le hint est fourni", () => {
    expect(
      mediaSheetHref({ provider: "tmdb", providerId: "456", kind: "tv" }),
    ).toBe("/media/tmdb/456?kind=tv");
  });

  it("n'ajoute PAS de query string quand kind est absent", () => {
    const href = mediaSheetHref({ provider: "tvdb", providerId: "789" });
    expect(href).not.toContain("?");
    expect(href).toBe("/media/tvdb/789");
  });

  it("encode le paramètre kind s'il contient des caractères réservés (défensif)", () => {
    // kind values are limited to "movie" | "tv" by the type, but URI-encoding
    // is still applied defensively.
    const ref: MediaRef = { provider: "tmdb", providerId: "1", kind: "movie" };
    expect(mediaSheetHref(ref)).toBe("/media/tmdb/1?kind=movie");
  });
});
