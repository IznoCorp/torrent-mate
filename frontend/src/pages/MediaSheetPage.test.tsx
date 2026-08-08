/**
 * MediaSheetPage — the « ‹ Retour » bar (operator report: on iPhone the
 * edge-swipe back is awkward; the fiche needs an explicit exit like the
 * add-media screen).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import MediaSheetPage from "./MediaSheetPage";

vi.mock("@/components/media/MediaSheet", () => ({
  MediaSheet: () => <div data-testid="media-sheet-stub" />,
}));

function renderPage(): ReturnType<typeof createMemoryRouter> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: "/media/:provider/:providerId", element: <MediaSheetPage /> },
      { path: "/acquisition", element: <div data-testid="acq-page" /> },
    ],
    { initialEntries: ["/media/tvdb/79175"] },
  );
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe("MediaSheetPage", () => {
  afterEach(cleanup);

  it("porte la barre « ‹ Retour » au-dessus de la fiche", () => {
    renderPage();
    const back = screen.getByRole("button", { name: "Retour" });
    expect(back).toHaveClass("fback");
    expect(screen.getByTestId("media-sheet-stub")).toBeInTheDocument();
  });

  it("sans historique applicatif, « Retour » replie vers /acquisition", () => {
    const router = renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Retour" }));
    expect(router.state.location.pathname).toBe("/acquisition");
  });
});
