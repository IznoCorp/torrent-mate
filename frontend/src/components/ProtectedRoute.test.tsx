import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import {
  createMemoryRouter,
  RouterProvider,
  useLocation,
  type RouteObject,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/AuthProvider";
import { ProtectedRoute } from "@/components/ProtectedRoute";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Marker for the public login route; echoes the current path + query. */
function LoginMarker(): ReactElement {
  const location = useLocation();
  return <div>connexion:{`${location.pathname}${location.search}`}</div>;
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

/**
 * Mount `ProtectedRoute` guarding a `/dash` child, alongside a `/login` marker,
 * wrapped in a retry-free Query provider + `AuthProvider`.
 */
function renderGuard(path: string): void {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const routes: RouteObject[] = [
    {
      element: <ProtectedRoute />,
      children: [{ path: "/dash", element: <div>Zone protégée</div> }],
    },
    { path: "/login", element: <LoginMarker /> },
  ];
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("ProtectedRoute", () => {
  it("affiche un indicateur de chargement pendant la requête « me »", () => {
    // A never-resolving fetch keeps the `me` query pending → loading branch.
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined));

    renderGuard("/dash");

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText(/chargement/i)).toBeInTheDocument();
    expect(screen.queryByText("Zone protégée")).not.toBeInTheDocument();
  });

  it("rend la route protégée quand la session est authentifiée", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, { username: "izno" }));

    renderGuard("/dash");

    expect(await screen.findByText("Zone protégée")).toBeInTheDocument();
  });

  it("redirige vers « /login » en préservant le chemin quand non authentifié", async () => {
    fetchMock.mockResolvedValue(buildResponse(401, { detail: "unauthorized" }));

    renderGuard("/dash");

    // Lands on the login marker, carrying the intended path in ?redirect=.
    await waitFor(() => {
      expect(
        screen.getByText("connexion:/login?redirect=%2Fdash"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Zone protégée")).not.toBeInTheDocument();
  });
});
