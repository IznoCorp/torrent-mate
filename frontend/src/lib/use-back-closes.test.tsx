/**
 * useBackCloses — the Back gesture closes an in-page layer instead of
 * leaving the page (operator report: back from a Suivis sheet landed on
 * Maintenant).
 */

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { useState } from "react";
import {
  createMemoryRouter,
  RouterProvider,
  useLocation,
} from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { useBackCloses } from "./use-back-closes";

/** Minimal host: a button opens a « layer »; the hook wires Back to close. */
function Host(): React.ReactElement {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useBackCloses(open, () => {
    setOpen(false);
  });
  return (
    <div>
      <button
        type="button"
        onClick={() => {
          setOpen(true);
        }}
      >
        ouvrir
      </button>
      <button
        type="button"
        onClick={() => {
          setOpen(false);
        }}
      >
        fermer
      </button>
      <span data-testid="state">{open ? "open" : "closed"}</span>
      <span data-testid="path">
        {location.pathname}
        {location.search}
      </span>
    </div>
  );
}

function renderHost() {
  const router = createMemoryRouter(
    [{ path: "/acquisition", element: <Host /> }],
    { initialEntries: ["/acquisition?tab=suivis"] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe("useBackCloses", () => {
  afterEach(cleanup);

  it("Back ferme la couche et reste sur la même URL", async () => {
    const router = renderHost();

    fireEvent.click(screen.getByRole("button", { name: "ouvrir" }));
    expect(screen.getByTestId("state")).toHaveTextContent("open");
    // The marker entry duplicates the URL — the page did not move.
    expect(screen.getByTestId("path")).toHaveTextContent(
      "/acquisition?tab=suivis",
    );

    await act(async () => {
      await router.navigate(-1);
    });

    expect(screen.getByTestId("state")).toHaveTextContent("closed");
    expect(screen.getByTestId("path")).toHaveTextContent(
      "/acquisition?tab=suivis",
    );
  });

  it("une fermeture UI consomme l'entrée marqueur (pas de back fantôme)", () => {
    const router = renderHost();

    fireEvent.click(screen.getByRole("button", { name: "ouvrir" }));
    fireEvent.click(screen.getByRole("button", { name: "fermer" }));

    // The marker entry was consumed: one more Back leaves the page, proving
    // no stale same-URL step was left between the layer and the base entry.
    expect(screen.getByTestId("state")).toHaveTextContent("closed");
    expect(router.state.location.state).toBeNull();
    expect(screen.getByTestId("path")).toHaveTextContent(
      "/acquisition?tab=suivis",
    );
  });

  it("rouvrir après un Back repose un marqueur fonctionnel", async () => {
    const router = renderHost();

    fireEvent.click(screen.getByRole("button", { name: "ouvrir" }));
    await act(async () => {
      await router.navigate(-1);
    });
    fireEvent.click(screen.getByRole("button", { name: "ouvrir" }));
    expect(screen.getByTestId("state")).toHaveTextContent("open");

    await act(async () => {
      await router.navigate(-1);
    });
    expect(screen.getByTestId("state")).toHaveTextContent("closed");
    expect(screen.getByTestId("path")).toHaveTextContent(
      "/acquisition?tab=suivis",
    );
  });
});
