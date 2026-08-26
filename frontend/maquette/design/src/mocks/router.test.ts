// The mock layer's routing table, tested where a browser rule cannot reach.
//
// `resolve` has two branches no named state has ever driven: it THROWS on a
// table that matches one address two ways, and `match` decodes a segment
// without throwing on one it cannot. Both are correctness the whole layer
// rests on, and both were written from reasoning rather than from a failure
// somebody saw — which is exactly the code a unit test is for.
//
// WHAT THIS FILE DOES NOT READ: whether the real table is unambiguous. That is
// the `routes()` assertion below, and it is deliberately a separate test — a
// helper proved on tables this file wrote is a helper proved on the cases
// somebody chose (B-093's shape).
import { describe, expect, it } from "vitest";
import { match, resolve, type MockRoute } from "./router";
import { routes } from "./handlers";

/**
 * Builds a route that answers nothing, for testing the matcher alone.
 *
 * @param method The method.
 * @param template The contract's path template.
 * @returns A route whose handler is never called here.
 */
function route(method: string, template: string): MockRoute {
  return { operationId: template, method, template, handle: () => null };
}

describe("match", () => {
  it("captures a template's parameters by name", () => {
    expect(match("/api/media/{provider}/{providerId}", "/api/media/tmdb/1396")).toEqual({
      provider: "tmdb",
      providerId: "1396",
    });
  });

  it("refuses a path of a different length", () => {
    expect(match("/api/media/{provider}", "/api/media/tmdb/1396")).toBeNull();
  });

  it("refuses a literal segment that differs", () => {
    expect(match("/api/library/items", "/api/library/recent")).toBeNull();
  });

  it("decodes a captured segment", () => {
    expect(match("/api/follows/{title}", "/api/follows/Silo%20%282023%29")).toEqual({
      title: "Silo (2023)",
    });
  });

  // A malformed escape makes `decodeURIComponent` throw, and `match` runs for
  // EVERY route of matching length before it is known which one wins — so one
  // bad segment would reject the whole request instead of answering a named
  // failure. The seeded titles already carry a per-cent sign.
  it("answers with the raw segment rather than throwing on a malformed escape", () => {
    expect(match("/api/follows/{title}", "/api/follows/100%")).toEqual({
      title: "100%",
    });
  });
});

describe("resolve", () => {
  it("answers null when nothing matches", () => {
    expect(resolve([route("GET", "/api/library/items")], "GET", "/api/nothing")).toBeNull();
  });

  it("does not match across methods", () => {
    expect(resolve([route("GET", "/api/library/items")], "DELETE", "/api/library/items"))
      .toBeNull();
  });

  // A literal segment wins over a parameter, which for two routes of equal
  // length is « fewer captured parameters wins ». Declared in the losing order
  // on purpose: a table that answered from whichever came first would pass
  // this test written the other way round.
  it("prefers a literal segment over a parameter", () => {
    const table = [route("GET", "/api/media/{provider}"), route("GET", "/api/media/recent")];
    expect(resolve(table, "GET", "/api/media/recent")?.route.template)
      .toBe("/api/media/recent");
  });

  // Two routes matching one address equally well is a defect in the TABLE, and
  // answering from whichever was declared first is a table nobody can reorder
  // safely. It throws, and the message names both templates.
  it("throws on an ambiguous table rather than picking", () => {
    const table = [route("GET", "/api/{a}/items"), route("GET", "/api/library/{b}")];
    expect(() => resolve(table, "GET", "/api/library/items"))
      .toThrowError(/ambiguous.*\/api\/\{a\}\/items.*\/api\/library\/\{b\}/s);
  });
});

describe("the table the layer actually serves", () => {
  // The test above proves the DETECTOR. This one asks the detector about the
  // real table — the two are different questions, and only this one can fail
  // because someone added a route.
  it("answers every one of its own addresses unambiguously", () => {
    const table = routes();
    expect(table.length).toBeGreaterThan(0);
    for (const declared of table) {
      // A template stands in for its own addresses: substituting a value for
      // each parameter yields a real path the table must resolve one way.
      const path = declared.template.replace(/\{[^}]+\}/g, "x");
      expect(() => resolve(table, declared.method, path)).not.toThrow();
    }
  });

  it("declares no two routes with the same method and template", () => {
    const seen = routes().map((declared) => `${declared.method} ${declared.template}`);
    expect(new Set(seen).size).toBe(seen.length);
  });
});
