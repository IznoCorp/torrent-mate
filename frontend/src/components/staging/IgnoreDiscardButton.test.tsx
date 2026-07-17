/**
 * Unit tests for IgnoreDiscardButton (§7 non-media artifact egress).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IgnoreDiscardButton } from "@/components/staging/IgnoreDiscardButton";

// ---- mock useDiscardMedia so we can assert mutation calls ----

const mutateMock = vi.fn();
const useDiscardMediaMock = vi.fn();

vi.mock("@/hooks/useDiscardMedia", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDiscardMedia: () => useDiscardMediaMock(),
}));

// ---- helpers ----

function renderButton(onSuccess?: () => void): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <IgnoreDiscardButton
        mediaId="test-media-id"
        {...(onSuccess !== undefined ? { onSuccess } : {})}
      />
    </QueryClientProvider>
  );
  render(tree);
}

function stubMutation(overrides: Record<string, unknown> = {}): void {
  useDiscardMediaMock.mockReturnValue({
    mutate: mutateMock,
    isPending: false,
    isSuccess: false,
    ...overrides,
  });
}

// ---- tests ----

beforeEach(() => {
  stubMutation();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("IgnoreDiscardButton", () => {
  it("renders the trigger button", () => {
    renderButton();
    expect(
      screen.getByRole("button", { name: "Ignorer / nettoyer" }),
    ).toBeInTheDocument();
  });

  it("opens the confirmation dialog on click", () => {
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Ignorer / nettoyer" }));
    expect(screen.getByText("Ignorer cet élément ?")).toBeInTheDocument();
    expect(
      screen.getByText(/Ce dossier ne contient pas un média identifiable/),
    ).toBeInTheDocument();
  });

  it("confirm button calls mutate with the correct mediaId", () => {
    renderButton();
    // Open dialog
    fireEvent.click(screen.getByRole("button", { name: "Ignorer / nettoyer" }));
    // Click confirm
    fireEvent.click(
      screen.getByRole("button", { name: "Confirmer le nettoyage" }),
    );
    expect(mutateMock).toHaveBeenCalledTimes(1);
    // The first positional arg is the mediaId
    expect(mutateMock).toHaveBeenCalledWith(
      "test-media-id",
      expect.objectContaining({
        onSuccess: expect.any(Function) as () => void,
        onError: expect.any(Function) as () => void,
      }),
    );
  });

  it("cancel button closes the dialog without calling mutate", () => {
    renderButton();
    // Open dialog
    fireEvent.click(screen.getByRole("button", { name: "Ignorer / nettoyer" }));
    expect(screen.getByText("Ignorer cet élément ?")).toBeInTheDocument();
    // Click cancel
    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
    // Dialog should close — title no longer in the document
    expect(screen.queryByText("Ignorer cet élément ?")).not.toBeInTheDocument();
    expect(mutateMock).not.toHaveBeenCalled();
  });

  it("calls onSuccess after a successful mutation", () => {
    const onSuccess = vi.fn();
    renderButton(onSuccess);

    // Open dialog
    fireEvent.click(screen.getByRole("button", { name: "Ignorer / nettoyer" }));
    // Click confirm — capture the callbacks so we can simulate the server response
    fireEvent.click(
      screen.getByRole("button", { name: "Confirmer le nettoyage" }),
    );

    // Simulate the onSuccess callback passed to mutate
    const callArgs = mutateMock.mock.calls[0] as [
      string,
      {
        onSuccess: (data: { detail: string }) => void;
        onError: (err: unknown) => void;
      },
    ];
    callArgs[1].onSuccess({ detail: "Nettoyé — /tmp/quarantine/abc" });

    expect(onSuccess).toHaveBeenCalledTimes(1);
  });
});
