// The Système page over a read the server refused: it says why, in the reader's language.
//
// WHAT THIS HOLDS THAT `ui/state-surfaces.test.tsx` CANNOT: the wiring. The error surface words a failure it is
// handed; only the screen can hand it its read's `error`, and dropping `failure=` there silently brings back the
// timeout sentence over a server that answered (§ 13). Same pattern as `media/media-screen-failure.test.tsx`.
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import i18next from "../../i18n";
import fr from "../../i18n/fr.json";

const UNAVAILABLE = {
  status: 503, title: "The library index cannot be read.", detail: "The library index cannot be read.",
  code: "library.unavailable", params: {},
};

/** A read that was refused, as the query hooks report it. */
const refused = { isError: true, isPending: false, isFetching: false, isPlaceholderData: false, data: undefined, error: UNAVAILABLE, refetch: vi.fn() };

// EVERY READ BELOW THE SURFACE ANSWERS REFUSED: the surface under test names the one it reports.
vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: () => refused,
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

const TIMEOUT = fr.surfaces.error.body.replace(/\s+/g, " ").trim();

describe("SystemPage in its error phase", () => {
  it("says why the reads were refused, not the timeout sentence", async () => {
    const { SystemPage } = await import("./page");
    const text = textOf(createElement(SystemPage));
    expect(text).toContain(fr.refusals.library.unavailable);
    expect(text).not.toContain(TIMEOUT);
  });
});
