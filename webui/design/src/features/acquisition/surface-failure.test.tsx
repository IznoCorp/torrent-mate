// The four Acquisition read surfaces over a read the server refused: each says why, in the reader's language.
//
// WHAT THIS HOLDS THAT `ui/state-surfaces.test.tsx` CANNOT: the wiring. The error surface words a failure it is
// handed; only the tab can hand it its read's `error`, and dropping `failure=` at any one of them silently
// brings back the timeout sentence over a server that answered (§ 13). Same pattern as
// `media/media-screen-failure.test.tsx`.
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import i18next from "../../i18n";

const UNAVAILABLE = {
  status: 503, title: "The library index cannot be read.", detail: "The library index cannot be read.",
  code: "library.unavailable", params: {},
};

/** A read that was refused, as the query hooks report it. */
const refused = { isError: true, isPending: false, isFetching: false, isPlaceholderData: false, data: undefined, error: UNAVAILABLE, refetch: vi.fn() };

/** What the cache still holds when a REFETCH is refused: TanStack v5 keeps the data and reports `isError` all the same. */
const cached = (address: unknown) =>
  address === "/api/v1/acquisition/to-handle" ? { inFlight: [], arrivals: [], blocked: [] } : address === "/api/v1/auth/me" ? undefined : [];

// EVERY READ BELOW THE SURFACE ANSWERS REFUSED: the surface under test names the one it reports. `holdsData` is the
// refused REFETCH, where the cache still holds what was drawn.
const reads = vi.hoisted(() => ({ holdsData: false }));
vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: (options: { queryKey: readonly unknown[] }) =>
    reads.holdsData ? { ...refused, data: cached(options.queryKey[0]) } : refused,
}));
// THE SERVER-RENDERED PASS has no snapshot to subscribe to: the version stands still.
vi.mock("../../lib/query-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/query-client")>()),
  useServerStateVersion: () => 0,
}));
// THE DISCOVER FEED WIRES A `resize` LISTENER when it is loaded, and this environment has no window.
vi.hoisted(() => {
  vi.stubGlobal("window", { addEventListener: () => undefined });
});
// THE PHASE IS THE TEST'S: "error" is what the harness names; "ready" is what a real refused read leaves, since
// nothing but the harness ever sets the error phase.
const screen = vi.hoisted(() => ({ phase: "error" }));
vi.mock("../../lib/store-access", () => ({
  useUiState: () => ({ phase: screen.phase, scen: "" }),
  useStoreContent: () => 0,
}));

/** The visible text of an element, whitespace folded. */
function textOf(element: ReactElement): string {
  void i18next.changeLanguage("fr");
  const html = renderToStaticMarkup(createElement(QueryClientProvider, { client: new QueryClient() }, element));
  return html.replace(/<[^>]*>/g, "").replace(/&#x27;/g, "'").replace(/\s+/g, " ");
}

// THE TWO SENTENCES, WRITTEN OUT: reading them from the catalogue would make the test agree with whatever the code says.
const REFUSAL =
  "La médiathèque est indisponible : le serveur ne peut pas la lire pour le moment. Réessayez dans un instant."; // french-ok: the 503 refusal sentence the screen must show
const TIMEOUT = "Le serveur n'a pas répondu dans le temps imparti."; // french-ok: the timeout sentence a refused read must NOT show

describe("the Acquisition tabs in their error phase", () => {
  it.each([
    ["NowTab", () => import("./now-tab").then((m) => m.NowTab)],
    ["FollowsTab", () => import("./follows-tab").then((m) => m.FollowsTab)],
    ["TodoTab", () => import("./todo-tab").then((m) => m.TodoTab)],
    ["DiscoverTab", () => import("./discover-tab").then((m) => m.DiscoverTab)],
  ])("%s says why the read was refused, not the timeout sentence", async (_name, load) => {
    const Tab = await load();
    const text = textOf(createElement(Tab));
    expect(text).toContain(REFUSAL);
    expect(text).not.toContain(TIMEOUT);
  });
});

describe("the Acquisition tabs over a real refused read (the phase is not \"error\")", () => {
  it.each([
    ["NowTab", () => import("./now-tab").then((m) => m.NowTab)],
    ["FollowsTab", () => import("./follows-tab").then((m) => m.FollowsTab)],
    ["TodoTab", () => import("./todo-tab").then((m) => m.TodoTab)],
    ["DiscoverTab", () => import("./discover-tab").then((m) => m.DiscoverTab)],
  ])("%s says why the read was refused, whatever the phase", async (_name, load) => {
    const Tab = await load();
    for (const phase of ["ready", "loading"]) {
      screen.phase = phase;
      try {
        const text = textOf(createElement(Tab));
        expect(text, phase).toContain(REFUSAL);
        expect(text, phase).not.toContain(TIMEOUT);
      } finally {
        screen.phase = "error";
      }
    }
  });
});

describe("the Acquisition tabs over a refused REFETCH (the cache still holds data)", () => {
  it.each([
    ["NowTab", () => import("./now-tab").then((m) => m.NowTab)],
    ["FollowsTab", () => import("./follows-tab").then((m) => m.FollowsTab)],
    ["TodoTab", () => import("./todo-tab").then((m) => m.TodoTab)],
    ["DiscoverTab", () => import("./discover-tab").then((m) => m.DiscoverTab)],
  ])("%s keeps the data drawn instead of taking the error face", async (_name, load) => {
    const Tab = await load();
    screen.phase = "ready";
    reads.holdsData = true;
    try {
      expect(textOf(createElement(Tab))).not.toContain(REFUSAL);
    } finally {
      reads.holdsData = false;
      screen.phase = "error";
    }
  });
});
