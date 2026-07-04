import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";

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

/**
 * Inert WebSocket stub — the authenticated shell mounts `EventStreamProvider`,
 * which opens a socket. jsdom's real WebSocket would attempt a live connection;
 * this no-op keeps the shell smoke test hermetic (the stream's own behaviour is
 * covered by `useEventStream.test.tsx`).
 */
class NoopWebSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send(): void {
    // No-op: the shell smoke test never drives the socket.
  }
  close(): void {
    // No-op: nothing to tear down for the inert stub.
  }
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  // An authenticated session so the shell's guard admits the dashboard route.
  fetchMock.mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.includes("/api/auth/me")) {
      return Promise.resolve(buildResponse(200, { username: "izno" }));
    }
    return Promise.resolve(buildResponse(200, {}));
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", NoopWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("monte le shell et rend le tableau de bord à la racine", async () => {
    render(<App />);

    // The browser router boots at jsdom's default path ("/"); once `me`
    // resolves authenticated the guard renders the Dashboard inside the shell.
    expect(
      await screen.findByRole("heading", { name: /tableau de bord/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /menu utilisateur/i }),
    ).toBeInTheDocument();
  });
});
