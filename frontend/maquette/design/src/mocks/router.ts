// Matching a request to the operation the contract declares for it.
//
// The table is keyed by the contract's own path templates —
// `/api/media/{provider}/{providerId}` — so a route this layer answers and a
// route the contract declares cannot drift apart without a guard seeing it.

/** One request, as a handler receives it. */
export type MockRequest = {
  /** The path, without its query. */
  path: string;
  /** The values the path template captured, by name. */
  parameters: Record<string, string>;
  /** The query, already parsed. */
  query: URLSearchParams;
  /** The parsed body, or undefined when there was none. */
  body: unknown;
};

/** What a handler answers with: a payload, or a payload and a status. */
export type MockAnswer = unknown;

/** One operation this layer answers. */
export type MockRoute = {
  /** The contract's own operationId — the key the scenario names it by. */
  operationId: string;
  /** The method, upper case. */
  method: string;
  /** The contract's path template. */
  template: string;
  /** What it answers. */
  handle: (request: MockRequest) => MockAnswer;
};

/**
 * Matches one path against one template, capturing its parameters.
 *
 * @param template The contract's path template.
 * @param path The path a request asked for.
 * @returns The captured parameters, or null when they are different routes.
 */
export function match(
  template: string,
  path: string,
): Record<string, string> | null {
  const wanted = template.split("/");
  const asked = path.split("/");
  if (wanted.length !== asked.length) return null;
  const parameters: Record<string, string> = {};
  for (let index = 0; index < wanted.length; index += 1) {
    const segment = wanted[index];
    if (segment.startsWith("{") && segment.endsWith("}")) {
      parameters[segment.slice(1, -1)] = decodeURIComponent(asked[index]);
      continue;
    }
    if (segment !== asked[index]) return null;
  }
  return parameters;
}

/**
 * Finds the route that answers one request.
 *
 * A LITERAL SEGMENT WINS OVER A PARAMETER. `/api/decisions/` and
 * `/api/decisions/{decisionId}` are different lengths and cannot collide, but
 * the rule is stated rather than relied on by accident: a table whose answer
 * depends on its own declaration order is a table nobody can reorder safely.
 *
 * @param routes Every route the layer answers.
 * @param method The method asked for.
 * @param path The path asked for.
 * @returns The route and its captured parameters, or null.
 */
export function resolve(
  routes: MockRoute[],
  method: string,
  path: string,
): { route: MockRoute; parameters: Record<string, string> } | null {
  const candidates: { route: MockRoute; parameters: Record<string, string> }[] = [];
  for (const route of routes) {
    if (route.method !== method) continue;
    const parameters = match(route.template, path);
    if (parameters !== null) candidates.push({ route, parameters });
  }
  if (candidates.length === 0) return null;
  candidates.sort(
    (left, right) =>
      Object.keys(left.parameters).length - Object.keys(right.parameters).length,
  );
  return candidates[0];
}
