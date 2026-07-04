import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  INSTALL_DISMISSED_STORAGE_KEY,
  shouldForceUpdate,
  usePwa,
} from "@/hooks/usePwa";

// --- Controllable `virtual:pwa-register/react` mock ------------------------

/** Shared, per-test state driving the mocked `useRegisterSW`. */
interface MockRegisterState {
  registration: { update: ReturnType<typeof vi.fn> } | null;
  updateServiceWorker: ReturnType<typeof vi.fn>;
  registered: boolean;
}

const swMock = vi.hoisted(
  (): { state: MockRegisterState } => ({
    state: {
      registration: null,
      updateServiceWorker: vi.fn(() => Promise.resolve()),
      registered: false,
    },
  }),
);

vi.mock("virtual:pwa-register/react", () => ({
  useRegisterSW: (options?: {
    onRegisteredSW?: (
      swScriptUrl: string,
      registration: ServiceWorkerRegistration | undefined,
    ) => void;
  }) => {
    // Hand the app a resolved registration ONCE, exactly as the real hook does
    // (post-mount, a single time) — the hook itself is called on every render,
    // so guard against re-invoking the callback on subsequent renders.
    if (
      options?.onRegisteredSW &&
      swMock.state.registration !== null &&
      !swMock.state.registered
    ) {
      swMock.state.registered = true;
      options.onRegisteredSW(
        "/sw.js",
        swMock.state.registration as unknown as ServiceWorkerRegistration,
      );
    }
    return {
      needRefresh: [false, (): void => undefined],
      offlineReady: [false, (): void => undefined],
      updateServiceWorker: swMock.state.updateServiceWorker,
    };
  },
}));

// --- Helpers ---------------------------------------------------------------

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

const fetchMock = vi.fn<typeof fetch>();

/** Render a hook behind a fresh, retry-free query client. */
function wrapper({ children }: { children: ReactNode }): ReactElement {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

/** Dispatch a synthetic ``beforeinstallprompt`` carrying a ``prompt`` spy. */
function fireInstallPrompt(prompt: () => Promise<void>): void {
  const event = new Event("beforeinstallprompt") as Event & {
    prompt?: () => Promise<void>;
  };
  event.prompt = prompt;
  window.dispatchEvent(event);
}

beforeEach(() => {
  swMock.state.registration = null;
  swMock.state.registered = false;
  swMock.state.updateServiceWorker.mockClear();
  fetchMock.mockReset();
  window.localStorage.clear();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("shouldForceUpdate", () => {
  it("force la mise à jour quand les commits diffèrent", () => {
    expect(shouldForceUpdate("aaa1111", "bbb2222")).toBe(true);
  });

  it("ignore les builds « dev », vides, absents ou identiques", () => {
    expect(shouldForceUpdate("dev", "bbb2222")).toBe(false);
    expect(shouldForceUpdate("aaa1111", "dev")).toBe(false);
    expect(shouldForceUpdate("aaa1111", undefined)).toBe(false);
    expect(shouldForceUpdate("aaa1111", "")).toBe(false);
    expect(shouldForceUpdate("aaa1111", "aaa1111")).toBe(false);
  });
});

describe("usePwa — mise à jour", () => {
  it("force registration.update() quand /api/version renvoie un autre commit", async () => {
    const registration = { update: vi.fn(() => Promise.resolve()) };
    swMock.state.registration = registration;
    fetchMock.mockResolvedValue(
      buildResponse(200, { version: "0.40.0", build_commit: "served99" }),
    );

    renderHook(
      () => usePwa({ versionPollEnabled: true, bakedCommit: "baked11" }),
      { wrapper },
    );

    // update() fires once on registration (on-load check) and once more when
    // the polled commit is found to differ from the baked one.
    await waitFor(() => {
      expect(registration.update).toHaveBeenCalledTimes(2);
    });
  });

  it("ne force aucune mise à jour quand le commit servi correspond", async () => {
    const registration = { update: vi.fn(() => Promise.resolve()) };
    swMock.state.registration = registration;
    fetchMock.mockResolvedValue(
      buildResponse(200, { version: "0.40.0", build_commit: "baked11" }),
    );

    renderHook(
      () => usePwa({ versionPollEnabled: true, bakedCommit: "baked11" }),
      { wrapper },
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    // Let the post-data effect run; an equal commit must not re-trigger update.
    await act(async () => {
      await Promise.resolve();
    });
    expect(registration.update).toHaveBeenCalledTimes(1);
  });
});

describe("usePwa — installation", () => {
  it("capture beforeinstallprompt puis déclenche prompt()", async () => {
    const promptSpy = vi.fn(() => Promise.resolve());
    const { result } = renderHook(
      () => usePwa({ versionPollEnabled: false, bakedCommit: "baked11" }),
      { wrapper },
    );

    expect(result.current.canInstall).toBe(false);

    act(() => {
      fireInstallPrompt(promptSpy);
    });
    expect(result.current.canInstall).toBe(true);

    await act(async () => {
      await result.current.promptInstall();
    });
    expect(promptSpy).toHaveBeenCalledTimes(1);
    expect(result.current.canInstall).toBe(false);
  });

  it("détecte iOS Safari hors mode standalone", () => {
    const uaDescriptor = Object.getOwnPropertyDescriptor(
      window.navigator,
      "userAgent",
    );
    Object.defineProperty(window.navigator, "userAgent", {
      configurable: true,
      get: () =>
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    });
    vi.stubGlobal(
      "matchMedia",
      (query: string) =>
        ({ matches: false, media: query }) as unknown as MediaQueryList,
    );

    try {
      const { result } = renderHook(
        () => usePwa({ versionPollEnabled: false, bakedCommit: "baked11" }),
        { wrapper },
      );
      expect(result.current.isIosInstall).toBe(true);
    } finally {
      if (uaDescriptor !== undefined) {
        Object.defineProperty(window.navigator, "userAgent", uaDescriptor);
      }
    }
  });

  it("mémorise le rejet de l’installation dans localStorage", () => {
    const first = renderHook(
      () => usePwa({ versionPollEnabled: false, bakedCommit: "baked11" }),
      { wrapper },
    );

    act(() => {
      fireInstallPrompt(() => Promise.resolve());
    });
    expect(first.result.current.canInstall).toBe(true);

    act(() => {
      first.result.current.dismissInstall();
    });
    expect(first.result.current.canInstall).toBe(false);
    expect(window.localStorage.getItem(INSTALL_DISMISSED_STORAGE_KEY)).toBe("1");
    first.unmount();

    // A fresh mount reads the persisted dismissal and stays hidden even when a
    // new install prompt is captured.
    const second = renderHook(
      () => usePwa({ versionPollEnabled: false, bakedCommit: "baked11" }),
      { wrapper },
    );
    act(() => {
      fireInstallPrompt(() => Promise.resolve());
    });
    expect(second.result.current.canInstall).toBe(false);
  });
});
