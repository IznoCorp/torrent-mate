/**
 * useViewMode — tests for the persisted display-mode hook.
 *
 * The mode is a preference, not a location — it lives in localStorage, never in
 * the URL (DOIT-10). A storage failure must never throw.
 */

import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useViewMode } from "./useViewMode";

describe("useViewMode", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("démarre en liste (A8)", () => {
    const { result } = renderHook(() => useViewMode());
    expect(result.current[0]).toBe("list");
  });

  it("mémorise le mode localement et le relit au montage (A7)", () => {
    const { result, unmount } = renderHook(() => useViewMode());
    act(() => {
      result.current[1]("grid");
    });
    unmount();

    const { result: result2 } = renderHook(() => useViewMode());
    expect(result2.current[0]).toBe("grid");
  });

  it("le mode n'entre JAMAIS dans l'URL — ?tab= reste la seule chose partageable (DOIT-10)", () => {
    const { result } = renderHook(() => useViewMode());
    act(() => {
      result.current[1]("group");
    });
    expect(window.location.search).not.toMatch(/mode|vue|view/);
  });

  it("survit à un localStorage indisponible (navigation privée)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceeded");
    });
    const { result } = renderHook(() => useViewMode());
    expect(() => {
      act(() => {
        result.current[1]("grid");
      });
    }).not.toThrow();
    // The mode changed for the session even though it could not be persisted.
    expect(result.current[0]).toBe("grid");
  });

  it("ignore une valeur corrompue dans localStorage", () => {
    localStorage.setItem("tm.follows.viewmode", "bogus");
    const { result } = renderHook(() => useViewMode());
    expect(result.current[0]).toBe("list");
  });
});
