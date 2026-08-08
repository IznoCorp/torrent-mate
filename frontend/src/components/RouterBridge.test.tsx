/**
 * RouterBridge scroll behavior — entering a page starts at the top
 * (operator report: opening a media sheet kept the previous scroll).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RouterBridge } from "./RouterBridge";

describe("RouterBridge — ScrollRestoration", () => {
  afterEach(cleanup);

  it("naviguer vers une nouvelle page remonte en haut", async () => {
    const scrollSpy = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const qc = new QueryClient();
    const router = createMemoryRouter(
      [
        {
          element: <RouterBridge />,
          children: [
            { path: "/a", element: <div>page A</div> },
            { path: "/b", element: <div>page B</div> },
          ],
        },
      ],
      { initialEntries: ["/a"] },
    );
    render(
      <QueryClientProvider client={qc}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    scrollSpy.mockClear();

    await act(async () => {
      await router.navigate("/b");
    });

    // ScrollRestoration scrolls the fresh page to the top on a push.
    expect(scrollSpy).toHaveBeenCalledWith(0, 0);
    scrollSpy.mockRestore();
  });
});
