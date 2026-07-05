import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authKeys, useLogin, useLogout, useMe } from "@/hooks/useAuth";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** A fresh, retry-free Query provider wrapper for `renderHook`. */
function createWrapper(): (props: { children: ReactNode }) => ReactElement {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
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

describe("authKeys", () => {
  it("expose une clé de requête stable ['auth', 'me']", () => {
    expect(authKeys.me).toEqual(["auth", "me"]);
  });
});

describe("useMe", () => {
  it("renvoie l’utilisateur authentifié sur 200", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, { username: "izno" }));

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toEqual({ username: "izno" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("ne réessaie pas sur 401 (retry: false)", async () => {
    fetchMock.mockResolvedValue(buildResponse(401, { detail: "unauthorized" }));

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("useLogin", () => {
  it("poste les identifiants et réussit sur 204", async () => {
    fetchMock.mockResolvedValue(buildResponse(204, {}));

    const { result } = renderHook(() => useLogin(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ username: "izno", password: "s3cret" });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ username: "izno", password: "s3cret" }),
      }),
    );
  });
});

describe("useLogout", () => {
  it("appelle l’endpoint de déconnexion et réussit sur 204", async () => {
    fetchMock.mockResolvedValue(buildResponse(204, {}));

    const { result } = renderHook(() => useLogout(), {
      wrapper: createWrapper(),
    });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
