import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UpdateToast } from "@/components/UpdateToast";
import type { PwaState } from "@/hooks/usePwa";

const toastMock = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast: toastMock }));

/** Build a full {@link PwaState}, overriding only the fields under test. */
function buildState(overrides: Partial<PwaState>): PwaState {
  return {
    needRefresh: false,
    applyUpdate: vi.fn(),
    canInstall: false,
    promptInstall: () => Promise.resolve(),
    isIosInstall: false,
    dismissInstall: () => undefined,
    ...overrides,
  };
}

beforeEach(() => {
  toastMock.mockClear();
});

afterEach(() => {
  cleanup();
});

describe("UpdateToast", () => {
  it("affiche un toast et applique la mise à jour quand needRefresh", () => {
    const applyUpdate = vi.fn();
    render(
      <UpdateToast state={buildState({ needRefresh: true, applyUpdate })} />,
    );

    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(toastMock).toHaveBeenCalledWith(
      "Nouvelle version disponible — mise à jour…",
    );
    expect(applyUpdate).toHaveBeenCalledTimes(1);
  });

  it("ne fait rien tant que needRefresh est faux", () => {
    const applyUpdate = vi.fn();
    render(
      <UpdateToast state={buildState({ needRefresh: false, applyUpdate })} />,
    );

    expect(toastMock).not.toHaveBeenCalled();
    expect(applyUpdate).not.toHaveBeenCalled();
  });
});
