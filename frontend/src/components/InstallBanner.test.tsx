import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InstallBanner } from "@/components/InstallBanner";
import type { PwaState } from "@/hooks/usePwa";

/** Build a full {@link PwaState}, overriding only the fields under test. */
function buildState(overrides: Partial<PwaState>): PwaState {
  return {
    canInstall: false,
    promptInstall: vi.fn(() => Promise.resolve()),
    isIosInstall: false,
    dismissInstall: vi.fn(),
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("InstallBanner", () => {
  it("propose l’installation Android/desktop et déclenche promptInstall", () => {
    const promptInstall = vi.fn(() => Promise.resolve());
    render(<InstallBanner state={buildState({ canInstall: true, promptInstall })} />);

    fireEvent.click(
      screen.getByRole("button", { name: /installer torrentmate/i }),
    );
    expect(promptInstall).toHaveBeenCalledTimes(1);
  });

  it("détaille les ÉTAPES d’installation sur iOS Safari (opérateur)", () => {
    render(<InstallBanner state={buildState({ isIosInstall: true })} />);

    // The banner IS the guide: Safari → Partager → Sur l'écran d'accueil.
    const steps = screen.getAllByRole("listitem");
    expect(steps).toHaveLength(3);
    expect(steps[0]).toHaveTextContent(/Safari/);
    expect(steps[1]).toHaveTextContent(/Partager/);
    expect(steps[2]).toHaveTextContent(/écran d’accueil/);
    // No native install button on iOS — only the manual instruction.
    expect(
      screen.queryByRole("button", { name: /installer torrentmate/i }),
    ).not.toBeInTheDocument();
    // The close button is present and REACHABLE (above the bottom bar).
    expect(screen.getByRole("button", { name: /ignorer/i })).toBeInTheDocument();
  });

  it("mémorise le rejet via le bouton de fermeture", () => {
    const dismissInstall = vi.fn();
    render(
      <InstallBanner state={buildState({ canInstall: true, dismissInstall })} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /ignorer/i }));
    expect(dismissInstall).toHaveBeenCalledTimes(1);
  });

  it("ne rend rien quand ni installable ni iOS", () => {
    const { container } = render(<InstallBanner state={buildState({})} />);
    expect(container).toBeEmptyDOMElement();
  });
});
