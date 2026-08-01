/**
 * RestartRequiredBanner tests (CONFIG-5, ticket 250).
 *
 * The banner is a pure presentational component (props only, no hooks), so the
 * tests render it directly — no query-client or router harness needed. The
 * CONFIG-5 guard is the point: an empty stale-files list must not render a
 * dangling « Fichiers modifiés : » label.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RestartRequiredBanner } from "@/components/config/panels/RestartRequiredBanner";

describe("RestartRequiredBanner", () => {
  afterEach(cleanup);

  it("masque la ligne « Fichiers modifiés » quand staleFiles est vide (CONFIG-5)", () => {
    render(
      <RestartRequiredBanner
        readOnly={false}
        restartConfigured
        staleFiles={[]}
        restartPending={false}
        onRestart={vi.fn()}
      />,
    );

    // The banner itself is visible…
    expect(screen.getByText("Redémarrage requis")).toBeInTheDocument();
    // …but the stale-files line is absent — no dangling label with no list.
    expect(screen.queryByText(/Fichiers modifiés/)).not.toBeInTheDocument();
  });

  it("affiche la liste jointe des fichiers modifiés quand staleFiles est non vide", () => {
    render(
      <RestartRequiredBanner
        readOnly={false}
        restartConfigured
        staleFiles={["master.json5", "secrets.json5"]}
        restartPending={false}
        onRestart={vi.fn()}
      />,
    );

    expect(
      screen.getByText("Fichiers modifiés : master.json5, secrets.json5"),
    ).toBeInTheDocument();
  });

  it("le bouton de redémarrage appelle onRestart", () => {
    const onRestart = vi.fn();
    render(
      <RestartRequiredBanner
        readOnly={false}
        restartConfigured
        staleFiles={[]}
        restartPending={false}
        onRestart={onRestart}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Redémarrer le daemon" }),
    );
    expect(onRestart).toHaveBeenCalledTimes(1);
  });
});
