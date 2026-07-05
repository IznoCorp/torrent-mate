import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/LoginForm";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Render {@link LoginForm} inside a fresh, retry-free Query provider. */
function renderLoginForm(): void {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }
  render(<LoginForm />, { wrapper: Wrapper });
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("LoginForm", () => {
  it("rend les champs identifiant / mot de passe et le bouton de connexion", async () => {
    renderLoginForm();

    expect(await screen.findByLabelText(/utilisateur/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/mot de passe/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /se connecter/i }),
    ).toBeInTheDocument();
  });

  it("bloque une soumission vide via zod, sans appeler l’API", async () => {
    renderLoginForm();

    fireEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(await screen.findByText(/utilisateur requis/i)).toBeInTheDocument();
    expect(screen.getByText(/mot de passe requis/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("envoie les identifiants à l’API quand le formulaire est valide", async () => {
    fetchMock.mockResolvedValue(buildResponse(204, {}));
    renderLoginForm();

    fireEvent.change(await screen.findByLabelText(/utilisateur/i), {
      target: { value: "izno" },
    });
    fireEvent.change(screen.getByLabelText(/mot de passe/i), {
      target: { value: "s3cret" },
    });
    fireEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/login",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ username: "izno", password: "s3cret" }),
        }),
      );
    });
  });

  it("affiche « Identifiants invalides » sur une erreur 401", async () => {
    fetchMock.mockResolvedValue(buildResponse(401, { detail: "unauthorized" }));
    renderLoginForm();

    fireEvent.change(await screen.findByLabelText(/utilisateur/i), {
      target: { value: "izno" },
    });
    fireEvent.change(screen.getByLabelText(/mot de passe/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(
      await screen.findByText(/Identifiants invalides/i),
    ).toBeInTheDocument();
  });
});
