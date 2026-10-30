// The sheet screen over a read the server refused: it says why, in the reader's language (B-697, B-698, B-699).
//
// WHAT THIS HOLDS THAT `ui/state-surfaces.test.tsx` CANNOT: the wiring. The surface
// words a failure it is handed; only the screen can hand it `sheetRead.error`, and
// dropping `failure=` there silently brings back the timeout sentence over a
// server that answered.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider, type UseQueryResult } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import i18next from "../../i18n";
import fr from "../../i18n/fr.json";

const UNAVAILABLE = {
  status: 503, title: "The library index cannot be read.", detail: "The library index cannot be read.",
  code: "library.unavailable", params: {},
};

/** A read that was refused, as the query hooks report it. */
const refused = { isError: true, isPending: false, isFetching: false, isPlaceholderData: false, data: undefined, error: UNAVAILABLE, refetch: vi.fn() } as unknown as UseQueryResult;

vi.mock("@tanstack/react-router", () => ({ useParams: () => ({ provider: "tvdb", id: "403245" }) }));
vi.mock("../../lib/store-access", () => ({ useStoreContent: () => 0 }));
// THE SURFACES BELOW THE ERROR BANNER are not under test and each reads its own stores.
vi.mock("./media-hero", () => ({ MediaHero: () => null }));
vi.mock("./media-cast", () => ({ MediaCast: () => null }));
vi.mock("./media-details", () => ({ MediaDetails: () => null }));
vi.mock("./media-library-facts", () => ({ MediaLibraryFacts: () => null }));
vi.mock("../acquisition/decision-block", () => ({ DecisionBlock: () => null }));
vi.mock("./queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./queries")>()),
  useMediaSheet: () => refused,
  // THE SEASONS READ LANDED: only the sheet's own banner may carry the reason.
  useMediaSeasons: () => ({ ...refused, isError: false, error: null }),
  useFollowCompleteness: () => ({ ...refused, isError: false, error: null }),
}));

describe("MediaScreen in its error phase", () => {
  it("says why the sheet read was refused, not the timeout sentence", async () => {
    const { MediaScreen } = await import("./media-screen");
    void i18next.changeLanguage("fr");
    const html = renderToStaticMarkup(
      createElement(
        QueryClientProvider,
        { client: new QueryClient() },
        createElement(MediaScreen, { readFollows: () => [], crossSeed: () => null }),
      ),
    );
    const text = html.replace(/<[^>]*>/g, "").replace(/&#x27;/g, "'").replace(/\s+/g, " ");
    expect(text).toContain(fr.refusals.library.unavailable);
    expect(text).not.toContain(fr.surfaces.error.body.replace(/\s+/g, " ").trim());
  });
});
