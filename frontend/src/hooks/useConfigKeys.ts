/**
 * Stable TanStack Query keys for the config editor domain (S4 — config-editor).
 *
 * Exported so components and tests read / invalidate the exact same cache entries.
 */

export const configKeys = {
  schema: ["config", "schema"] as const,
  files: ["config", "files"] as const,
  file: (name: string) => ["config", "files", name] as const,
  status: ["config", "status"] as const,
  secrets: ["config", "secrets"] as const,
};
