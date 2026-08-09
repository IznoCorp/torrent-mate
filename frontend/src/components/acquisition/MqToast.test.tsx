/**
 * MqToast — the maquette in-page toast host and its imperative API.
 */

import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MqToaster, mqtoast } from "./MqToast";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("MqToast", () => {
  it("affiche le message dans le toast maquette et le référence en aria", () => {
    render(<MqToaster />);
    const toast = screen.getByRole("status");
    expect(toast).toHaveClass("mqtoast");
    expect(toast).not.toHaveClass("show");

    act(() => {
      mqtoast("Cadence mise à jour.");
    });

    expect(toast).toHaveClass("show");
    expect(toast).toHaveTextContent("Cadence mise à jour.");
  });

  it("le bouton fermer est le vrai contrôle — il masque immédiatement", () => {
    render(<MqToaster />);
    act(() => {
      mqtoast("Watcher activé.");
    });

    fireEvent.click(screen.getByRole("button", { name: /Fermer la notification/ }));

    expect(screen.getByRole("status")).not.toHaveClass("show");
  });

  it("s'efface seul après le délai maquette (5 s)", () => {
    vi.useFakeTimers();
    render(<MqToaster />);
    act(() => {
      mqtoast("Détection lancée…");
    });
    expect(screen.getByRole("status")).toHaveClass("show");

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByRole("status")).not.toHaveClass("show");
  });
});
