/**
 * Shared sonner toast mock for use in component/hook tests.
 *
 * Vitest hoists ``vi.mock`` calls, so consumers MUST import ``toast`` from
 * ``sonner`` AFTER the mock is declared. The typical pattern is to call
 * ``mockSonner()`` at the top of the test module (before any other imports) and
 * then ``import { toast } from "sonner"`` inline.
 *
 * Usage::
 *
 *   import { mockSonner } from "@/test/mockSonner";
 *   mockSonner();
 *   // ... other mocks ...
 *   import { toast } from "sonner";
 *
 * Each toast variant (``success``, ``error``, ``warning``, ``info``) is a
 * ``vi.fn()`` — assert with ``expect(toast.warning).toHaveBeenCalledWith(...)``.
 */

import { vi } from "vitest";

export interface SonnerMocks {
  success: ReturnType<typeof vi.fn>;
  error: ReturnType<typeof vi.fn>;
  warning: ReturnType<typeof vi.fn>;
  info: ReturnType<typeof vi.fn>;
}

let cached: SonnerMocks | null = null;

/**
 * Install the sonner module mock. Idempotent — subsequent calls return the same
 * mock functions so resets in ``beforeEach`` work correctly.
 *
 * Returns:
 *   The mock functions, keyed by variant.
 */
export function mockSonner(): SonnerMocks {
  if (cached !== null) return cached;

  const success = vi.fn();
  const error = vi.fn();
  const warning = vi.fn();
  const info = vi.fn();

  vi.mock("sonner", () => ({
    toast: { success, error, warning, info },
  }));

  cached = { success, error, warning, info };
  return cached;
}
