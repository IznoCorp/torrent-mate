/**
 * posterThumb — provider thumbnail rewriting (operator report: the Suivis
 * list was slow; full-size posters were the bulk of the payload).
 */

import { describe, expect, it } from "vitest";

import { posterThumb } from "./poster-thumb";

describe("posterThumb", () => {
  it("TVDB legacy : insère _t avant l'extension", () => {
    expect(
      posterThumb("https://artworks.thetvdb.com/banners/posters/275274-2.jpg"),
    ).toBe("https://artworks.thetvdb.com/banners/posters/275274-2_t.jpg");
  });

  it("TVDB v4 : insère _t avant l'extension", () => {
    expect(
      posterThumb(
        "https://artworks.thetvdb.com/banners/v4/series/403245/posters/64432dea72673.jpg",
      ),
    ).toBe(
      "https://artworks.thetvdb.com/banners/v4/series/403245/posters/64432dea72673_t.jpg",
    );
  });

  it("TVDB déjà en _t : inchangé (pas de _t_t)", () => {
    const thumb =
      "https://artworks.thetvdb.com/banners/posters/275274-2_t.jpg";
    expect(posterThumb(thumb)).toBe(thumb);
  });

  it("TMDB : remplace la taille par w342 quelle que soit la variante", () => {
    expect(
      posterThumb("https://image.tmdb.org/t/p/w500/h1IuzRiwnyyc.jpg"),
    ).toBe("https://image.tmdb.org/t/p/w342/h1IuzRiwnyyc.jpg");
    expect(
      posterThumb("https://image.tmdb.org/t/p/original/h1IuzRiwnyyc.jpg"),
    ).toBe("https://image.tmdb.org/t/p/w342/h1IuzRiwnyyc.jpg");
  });

  it("hôte inconnu et null : passent inchangés", () => {
    expect(posterThumb("https://example.com/p.jpg")).toBe(
      "https://example.com/p.jpg",
    );
    expect(posterThumb(null)).toBeNull();
  });
});
