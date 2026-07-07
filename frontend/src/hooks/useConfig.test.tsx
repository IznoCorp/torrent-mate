import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { configKeys } from "@/hooks/useConfigKeys";
import {
  useConfigFiles,
  usePutConfigFile,
  useValidateConfig,
} from "@/hooks/useConfig";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

/** A minimal files-listing payload matching ``FilesResponse``. */
const MOCK_FILES_RESPONSE = {
  files: [
    {
      name: "paths.json5",
      owned_keys: ["paths"],
      sha256: "abc123",
      mtime: 1719000000,
      size: 1024,
      shadowed_keys: [],
    },
    {
      name: "master.json5",
      owned_keys: ["staging_dirs", "disks"],
      sha256: "def456",
      mtime: 1719000100,
      size: 2048,
      shadowed_keys: [],
    },
  ],
};

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

/** Create a wrapper that provides a fresh QueryClientProvider for each test. */
function createWrapper(): (props: { children: ReactNode }) => ReactElement {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={client}>
        {children}
      </QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("configKeys", () => {
  it("exposes stable query keys", () => {
    expect(configKeys.schema).toEqual(["config", "schema"]);
    expect(configKeys.files).toEqual(["config", "files"]);
    expect(configKeys.file("paths.json5")).toEqual([
      "config",
      "files",
      "paths.json5",
    ]);
    expect(configKeys.status).toEqual(["config", "status"]);
    expect(configKeys.secrets).toEqual(["config", "secrets"]);
  });
});

describe("useConfigFiles", () => {
  it("returns file list on successful fetch", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, MOCK_FILES_RESPONSE));

    const { result } = renderHook(() => useConfigFiles(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(MOCK_FILES_RESPONSE);
  });
});

describe("usePutConfigFile", () => {
  it("invalidates files, file(name), and status keys on success", async () => {
    let fetchCount = 0;
    fetchMock.mockImplementation(() => {
      fetchCount += 1;
      return Promise.resolve(buildResponse(200, MOCK_FILES_RESPONSE));
    });

    const { result } = renderHook(
      () => ({
        files: useConfigFiles(),
        putFile: usePutConfigFile("paths.json5"),
      }),
      { wrapper: createWrapper() },
    );

    // Wait for the initial useConfigFiles query to settle.
    await waitFor(() => {
      expect(result.current.files.isSuccess).toBe(true);
    });
    const countBeforeMutation = fetchCount;
    expect(countBeforeMutation).toBeGreaterThanOrEqual(1);

    // Execute the mutation — on success it invalidates → the files query
    // should refetch.
    await act(async () => {
      await result.current.putFile.mutateAsync({
        base_sha256: "abc123",
        values: { paths: { staging_dir: "/new/path" } },
      });
    });

    await waitFor(() => {
      expect(fetchCount).toBeGreaterThan(countBeforeMutation);
    });
  });
});

describe("useValidateConfig", () => {
  it("surfaces ApiError on 422 validation failure", async () => {
    fetchMock.mockResolvedValue(
      buildResponse(422, { detail: "Invalid config values" }),
    );

    const { result } = renderHook(() => useValidateConfig(), {
      wrapper: createWrapper(),
    });

    // Fire the mutation — it should surface the error.
    result.current.mutate({
      file_name: "paths.json5",
      values: { paths: { staging_dir: 123 } },
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(422);
  });
});
