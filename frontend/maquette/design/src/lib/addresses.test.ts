// The address model, tested where a browser rule cannot reach.
//
// D1 lives in this file: the path carries the identity, the query carries the
// state. Every browser rule that walks an address proves ONE journey through
// it; these prove the table itself — including the cases no named state
// drives, which is where a naming convention quietly stops being one.
//
// WHAT THIS FILE DOES NOT READ: whether the router mounts what the table
// names. That is `screen_addresses.py`, in a browser, and it must stay there —
// a table can be right about a path the router does not serve.
import { describe, expect, it } from "vitest";
import {
  addressOf,
  destinationOf,
  dialsOfPage,
  HOME_PAGE,
  isScreenPath,
  NOT_FOUND_PAGE,
  PAGE_OF_PATH,
  PAGE_PATHS,
  screenParentOf,
  SIGN_IN_PATH,
  withoutPanel,
  withPanel,
} from "./addresses";

describe("the page table", () => {
  it("is a bijection — no two pages share a path", () => {
    expect(Object.keys(PAGE_OF_PATH).length).toBe(Object.keys(PAGE_PATHS).length);
  });

  it("round-trips every page through its own path", () => {
    for (const [page, path] of Object.entries(PAGE_PATHS)) {
      expect(PAGE_OF_PATH[path]).toBe(page);
    }
  });

  it("gives the home page a path of its own", () => {
    expect(PAGE_PATHS[HOME_PAGE]).toBeDefined();
  });
});

describe("screenParentOf", () => {
  // D1b rule 3: a cold link poses the REAL parent under the screen, read off
  // the surface the screen's opener is emitted from — never the home page by
  // default, which is the reading phase 11 of L05 struck.
  it("names the library under a media sheet", () => {
    expect(screenParentOf("/media/tmdb/1396")).toBe("lib");
  });

  it("names the arrivals under a resolution", () => {
    expect(screenParentOf("/resolution/Some.Folder.2026")).toBe("arr");
  });

  it("answers undefined for a page's own path", () => {
    expect(screenParentOf("/media")).toBeUndefined();
  });

  it("answers undefined for an address nobody serves", () => {
    expect(screenParentOf("/nothing/at/all")).toBeUndefined();
  });

  // A `$segment` stands for any ONE non-empty segment, so a screen path with
  // the wrong number of segments is not that screen.
  it("does not match a screen path of the wrong depth", () => {
    expect(screenParentOf("/media/tmdb")).toBeUndefined();
  });

  it("agrees with isScreenPath in both directions", () => {
    for (const path of ["/media/tmdb/1396", "/media", "/nothing", "/resolution/x"]) {
      expect(isScreenPath(path)).toBe(screenParentOf(path) !== undefined);
    }
  });
});

describe("withoutPanel", () => {
  it("takes the panel parameter off and keeps the rest verbatim", () => {
    expect(withoutPanel("?sort=recent&panel=follows%3ASilo&tab=now"))
      .toBe("?sort=recent&tab=now");
  });

  it("answers the empty string when nothing is left", () => {
    expect(withoutPanel("?panel=follows%3ASilo")).toBe("");
  });

  it("accepts a query with no leading question mark", () => {
    expect(withoutPanel("sort=recent")).toBe("?sort=recent");
  });

  it("drops empty pairs rather than emitting a bare separator", () => {
    expect(withoutPanel("?&sort=recent&")).toBe("?sort=recent");
  });

  it("is a no-op on a query that carries no panel", () => {
    expect(withoutPanel("?sort=recent")).toBe("?sort=recent");
  });
});

describe("withPanel", () => {
  it("appends the panel to what is already there", () => {
    expect(withPanel("?sort=recent", "follows:Silo"))
      .toBe("?sort=recent&panel=follows%3ASilo");
  });

  it("replaces a panel already set rather than adding a second", () => {
    const once = withPanel("?panel=follows%3AOther", "follows:Silo");
    expect(once).toBe("?panel=follows%3ASilo");
  });

  it("round-trips with withoutPanel", () => {
    const start = "?sort=recent&tab=now";
    expect(withoutPanel(withPanel(start, "follows:Silo"))).toBe(start);
  });

  // Re-serialising an address that is only being passed through changes it,
  // which is why the kept pairs are kept as WRITTEN and not re-encoded.
  it("leaves an already-encoded pair exactly as it was written", () => {
    expect(withPanel("?q=star%20wars", "follows:Silo"))
      .toBe("?q=star%20wars&panel=follows%3ASilo");
  });
});

describe("dialsOfPage", () => {
  it("has dials to give at all", () => {
    // A CORPUS FLOOR, and it is not decoration: the hold below asserts inside
    // `for (const parameter of dialsOfPage(page))`, so emptying the dials table
    // — the whole query-state half of the address model — satisfied it in
    // silence. Proven by mutation: `return []` left 25 tests green.
    const total = Object.keys(PAGE_PATHS)
      .reduce((count, page) => count + dialsOfPage(page).length, 0);
    expect(total).toBeGreaterThanOrEqual(5);
  });

  it("gives a page only its own dials", () => {
    for (const page of Object.keys(PAGE_PATHS)) {
      for (const parameter of dialsOfPage(page)) {
        // A dial belongs to ONE page — that is what keeps `/media?tab=follows`
        // from existing. Asked from the other side: no other page claims it.
        const others = Object.keys(PAGE_PATHS)
          .filter((other) => other !== page)
          .flatMap((other) => dialsOfPage(other));
        expect(others).not.toContain(parameter);
      }
    }
  });
});

describe("destinationOf", () => {
  it("resolves a page's own path to that page", () => {
    expect(destinationOf("/media", "").page).toBe("lib");
  });

  it("resolves the bare root to the home page", () => {
    expect(destinationOf("/", "").page).toBe(HOME_PAGE);
  });

  it("resolves a screen's path to the page underneath it", () => {
    const landed = destinationOf("/media/tmdb/1396", "");
    expect(landed.page).toBe("lib");
    expect(landed.screen).toBe(true);
  });

  it("raises the sign-in over the home page rather than over nothing", () => {
    const landed = destinationOf(SIGN_IN_PATH, "");
    expect(landed.signIn).toBe(true);
    expect(landed.page).toBe(HOME_PAGE);
  });

  // Keeping only the path is still a rewrite: the first write of that state
  // gives back a link the operator never typed, with everything after the `?`
  // silently gone.
  it("keeps an unknown address exactly as it was asked for, query included", () => {
    const landed = destinationOf("/nothing", "?q=1");
    expect(landed.page).toBe(NOT_FOUND_PAGE);
    expect(landed.notFound).toBe("/nothing?q=1");
  });

  it("round-trips a page through addressOf and back", () => {
    for (const page of Object.keys(PAGE_PATHS)) {
      expect(destinationOf(addressOf(page, {}), "").page).toBe(page);
    }
  });
});
