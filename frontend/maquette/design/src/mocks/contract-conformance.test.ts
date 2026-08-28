// What the layer ANSWERS, held against what the contract declares.
//
// THE HOLE THIS FILLS, and `check-mock-seeds.py` names it in its own words:
// « handlers, so a handler ignoring its seed passes here ». That guard reads
// SEEDS. A payload a handler composes — a listing's `matching` and `loaded`, a
// card built by `takeQueued`, a sheet assembled from five families — touches no
// seed, so the two required fields this lot added to the listing were checked by
// nothing but the surface that happened to read them.
//
// Measured consequence, before this file existed: dropping `matching` from the
// listing handler makes `getNextPageParam` compare `held < undefined`, which is
// `false`, so the list ends after one page under an end mark that says the
// library is exhausted — and every guard stays green.
//
// WHAT IT HOLDS, and it is deliberately narrow: every REQUIRED property of a
// declared response is present in the answer. Not types, not formats, not
// extra properties — a full validator here would be a second implementation of
// the contract, and the value is in the one question no reader was asking.
import { describe, expect, it } from "vitest";
import contract from "../../../contract/openapi.json";
import { routes } from "./handlers";
import { resetMockState } from "./state";
import type { MockRequest } from "./router";

type Shape = {
  required?: string[];
  properties?: Record<string, unknown>;
  $ref?: string;
  type?: string;
  items?: Shape;
};

const CONTRACT = contract as unknown as {
  paths: Record<string, Record<string, {
    operationId?: string;
    parameters?: { name: string; in: string; required?: boolean }[];
    responses: Record<string, { content?: Record<string, { schema?: Shape }> }>;
  }>>;
  components: { schemas: Record<string, Shape> };
};

/** Follows a `$ref` to the shape it names. */
function resolved(shape: Shape | undefined): Shape | undefined {
  if (shape?.$ref === undefined) return shape;
  const name = shape.$ref.split("/").pop() as string;
  return CONTRACT.components.schemas[name];
}

/** The success response's shape for one operation, or undefined. */
function successShape(operation: {
  responses: Record<string, { content?: Record<string, { schema?: Shape }> }>;
}): Shape | undefined {
  const answer = operation.responses["200"] ?? operation.responses["201"];
  return resolved(answer?.content?.["application/json"]?.schema);
}

/** A value for each path parameter, taken from what the layer really holds. */
const KNOWN_VALUE: Record<string, string> = {
  mediaId: "Backrooms 2026",
  title: "Silo",
  folder: "Backrooms.2026.MULTi.2160p.WEB-DL",
  provider: "tmdb",
  providerId: "1",
  infoHash: "0".repeat(40),
  actionId: "library-status",
  settingId: "paths.torrent_complete_dir",
  key: "paths.torrent_complete_dir",
  name: "personalscraper-search",
  id: "1",
};

describe("every answer carries what the contract requires of it", () => {
  const table = routes();

  it("has a corpus, and it is the whole table", () => {
    // A FLOOR, because « every route conformed » and « no route was read » are
    // the same green line otherwise.
    expect(table.length).toBeGreaterThanOrEqual(40);
  });

  for (const route of table) {
    if (route.method !== "GET") continue;
    const declared = CONTRACT.paths[route.template]?.[route.method.toLowerCase()];
    it(`${route.operationId} answers every required field`, () => {
      expect(declared).toBeDefined();
      const shape = successShape(declared!);
      if (shape === undefined) return;

      resetMockState();
      const parameters: Record<string, string> = {};
      for (const segment of route.template.split("/")) {
        if (segment.startsWith("{")) {
          const name = segment.slice(1, -1);
          parameters[name] = KNOWN_VALUE[name] ?? "1";
        }
      }
      const query = new URLSearchParams();
      for (const parameter of declared!.parameters ?? []) {
        if (parameter.in === "query" && parameter.required === true) {
          query.set(parameter.name, KNOWN_VALUE[parameter.name] ?? "1");
        }
      }
      const request: MockRequest = {
        path: route.template, parameters, query, body: undefined,
      };
      const answered = route.handle(request);

      const wanted = shape.type === "array"
        ? resolved(shape.items)
        : shape;
      const required = wanted?.required ?? [];
      if (required.length === 0) return;

      // An ARRAY answer is held on its FIRST element: the contract describes
      // what an element is, and an empty list is a legitimate answer that says
      // nothing about the shape.
      const subject = Array.isArray(answered) ? answered[0] : answered;
      if (subject === undefined || subject === null) return;
      const missing = required.filter(
        (field) => !(field in (subject as Record<string, unknown>)));
      expect(missing, `${route.operationId} is missing ${missing.join(", ")}`)
        .toEqual([]);
    });
  }
});
