import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InstallBanner } from "@/components/InstallBanner";
import type { PwaState } from "@/hooks/usePwa";

/** Build a full {@link PwaState}, overriding only the fields under test. */
function buildState(overrides: Partial<PwaState>): PwaState {
  return {
    needRefresh: false,
    applyUpdate: () => undefined,
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

  it("affiche l’instruction « Partager » sur iOS Safari", () => {
    render(<InstallBanner state={buildState({ isIosInstall: true })} />);

    expect(screen.getByText(/partager/i)).toBeInTheDocument();
    // No native install button on iOS — only the manual instruction.
    expect(
      screen.queryByRole("button", { name: /installer torrentmate/i }),
    ).not.toBeInTheDocument();
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
