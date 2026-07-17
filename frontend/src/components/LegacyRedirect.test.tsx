import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LegacyRedirect } from "@/components/LegacyRedirect";

/** Build a memory router whose ONLY route is the redirect under test.
 *  The actual target route does not need to exist — we assert the URL that
 *  {@link LegacyRedirect} navigates to by reading `location.pathname` +
 *  `location.search` after the render commits. */
function renderRedirect(initialEntries: string[], to: string) {
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <>
            <LegacyRedirect to={to} />
            {/* A fallback so the redirect has somewhere to land. */}
            <div data-testid="landed">Landed at {to}</div>
          </>
        ),
      },
    ],
    { initialEntries },
  );

  render(<RouterProvider router={router} />);
  return router;
}

describe("LegacyRedirect", () => {
  it("forwards a single query parameter (?media=X)", () => {
    const router = renderRedirect(["/scraping?media=tt0123456"], "/medias");

    expect(router.state.location.pathname).toBe("/medias");
    expect(router.state.location.search).toBe("?media=tt0123456");
  });

  it("forwards multiple query parameters (?media=X&decision=N)", () => {
    const router = renderRedirect(
      ["/scraping?media=tt9999999&decision=42"],
      "/medias",
    );

    expect(router.state.location.pathname).toBe("/medias");
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get("media")).toBe("tt9999999");
    expect(params.get("decision")).toBe("42");
  });

  it("preserves encoded special characters in query values", () => {
    const router = renderRedirect(
      ["/scraping?q=hello%20world&filter=a%2Bb"],
      "/medias",
    );

    expect(router.state.location.pathname).toBe("/medias");
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get("q")).toBe("hello world");
    expect(params.get("filter")).toBe("a+b");
  });

  it("does NOT append a trailing '?' when there are no params", () => {
    const router = renderRedirect(["/scraping"], "/medias");

    expect(router.state.location.pathname).toBe("/medias");
    expect(router.state.location.search).toBe("");
  });

  it("does NOT append '?' when search is the empty string", () => {
    const router = renderRedirect(["/scraping?"], "/medias");

    expect(router.state.location.pathname).toBe("/medias");
    // `useSearchParams` on an empty query yields zero entries → no suffix.
    expect(router.state.location.search).toBe("");
  });

  it("uses replace navigation (no history entry for the legacy path)", () => {
    const router = renderRedirect(["/scraping?media=tt1234567"], "/medias");

    // The history stack should only have the final location.
    expect(router.state.location.pathname).toBe("/medias");
    expect(router.state.navigation.state).toBe("idle");
  });
});
