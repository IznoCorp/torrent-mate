import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/AuthProvider";
import { UserMenu } from "@/components/layout/UserMenu";

/**
 * Flatten the Radix dropdown into plain elements so the menu item is always
 * rendered and clickable — jsdom lacks the pointer-capture APIs Radix needs to
 * open a real dropdown, and this test targets `UserMenu`'s logout logic, not the
 * DS primitive.
 */
vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: ReactNode }): ReactElement => (
    <div>{children}</div>
  ),
  DropdownMenuTrigger: ({ children }: { children: ReactNode }): ReactElement => (
    <div>{children}</div>
  ),
  DropdownMenuContent: ({ children }: { children: ReactNode }): ReactElement => (
    <div>{children}</div>
  ),
  DropdownMenuLabel: ({ children }: { children: ReactNode }): ReactElement => (
    <div>{children}</div>
  ),
  DropdownMenuSeparator: (): ReactElement => <hr />,
  DropdownMenuItem: ({
    children,
    onSelect,
    disabled,
  }: {
    children: ReactNode;
    onSelect?: () => void;
    disabled?: boolean;
  }): ReactElement => (
    <button type="button" disabled={disabled} onClick={onSelect}>
      {children}
    </button>
  ),
}));

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Extract the request URL from a `fetch` first argument without stringifying. */
function requestUrl(input: Parameters<typeof fetch>[0]): string {
  if (typeof input === "string") {
    return input;
  }
  return input instanceof URL ? input.href : input.url;
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

describe("UserMenu", () => {
  it("déconnecte puis navigue vers « /login »", async () => {
    fetchMock.mockImplementation((input) => {
      const url = requestUrl(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      }
      // /api/auth/logout → 204 No Content.
      return Promise.resolve(buildResponse(204, {}));
    });

    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const router = createMemoryRouter(
      [
        { path: "/", element: <UserMenu /> },
        { path: "/login", element: <div>Écran de connexion</div> },
      ],
      { initialEntries: ["/"] },
    );
    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>,
    );

    // Wait for the authenticated identity to surface (the account label).
    expect(await screen.findByText("izno")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /se déconnecter/i }));

    // The logout endpoint is hit and the router lands on the login screen.
    await waitFor(() => {
      expect(screen.getByText("Écran de connexion")).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
