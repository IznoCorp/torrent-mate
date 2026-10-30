// The Trackers surfaces over a read the server refused: each says why, in the reader's language.
//
// WHAT THIS HOLDS THAT `ui/state-surfaces.test.tsx` CANNOT: the wiring. The error surface words a failure it is
// handed; only the screen can hand it its read's `error`, and dropping `failure=` there silently brings back the
// timeout sentence over a server that answered (§ 13). Same pattern as `media/media-screen-failure.test.tsx`.
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

/** A read that answered, with nothing to show. */
const answered = { isError: false, isPending: false, isFetching: false, isPlaceholderData: false, data: undefined, error: null, refetch: vi.fn() };

// BY DEFAULT EVERY READ BELOW THE SURFACE ANSWERS REFUSED; `onlyRefused` narrows that to one address, so a test can
// refuse the LAST read of a `??` chain alone.
const reads = vi.hoisted(() => ({ onlyRefused: undefined as string | undefined }));
vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: (options: { queryKey: readonly unknown[] }) =>
    reads.onlyRefused === undefined || reads.onlyRefused === options.queryKey[0] ? refused : answered,
}));
// THE SERVER-RENDERED PASS has no snapshot to subscribe to: the version stands still.
vi.mock("../../lib/query-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/query-client")>()),
  useServerStateVersion: () => 0,
}));
// THE SCREEN IS DRIVEN INTO ITS ERROR PHASE, as the harness names it.
vi.mock("../../lib/store-access", () => ({
  useUiState: () => ({ phase: "error", scen: "" }),
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

describe("the Trackers tabs over a refused read", () => {
  it.each([
    ["TorrentsTab", () => import("./torrents-tab").then((m) => m.TorrentsTab)],
    ["TrackersTab", () => import("./trackers-tab").then((m) => m.TrackersTab)],
  ])("%s says why the read was refused, not the timeout sentence", async (_name, load) => {
    const Tab = await load();
    const text = textOf(createElement(Tab));
    expect(text).toContain(REFUSAL);
    expect(text).not.toContain(TIMEOUT);
  });

  it("TorrentsTab names the refusal when only the LAST read of its chain (the obligations) is refused", async () => {
    reads.onlyRefused = "/api/v1/acquisition/obligations";
    try {
      const { TorrentsTab } = await import("./torrents-tab");
      const text = textOf(createElement(TorrentsTab));
      expect(text).toContain(REFUSAL);
      expect(text).not.toContain(TIMEOUT);
    } finally {
      reads.onlyRefused = undefined;
    }
  });
});
