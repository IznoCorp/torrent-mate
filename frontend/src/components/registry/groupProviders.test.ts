import { describe, expect, it } from "vitest";

import type { ProviderStatusItem } from "@/api/registry";
import {
  groupProviders,
  subCircuitHint,
  subCircuitLabel,
  subCircuitParent,
} from "@/components/registry/groupProviders";

function provider(
  name: string,
  overrides: Partial<ProviderStatusItem> = {},
): ProviderStatusItem {
  return {
    provider_name: name,
    circuit_state: "closed",
    failure_count_recent: 0,
    last_success_at: null,
    last_failure_at: null,
    last_latency_ms: null,
    live: true,
    ...overrides,
  };
}

describe("subCircuitParent", () => {
  it("extracts the parent stem for known suffixes", () => {
    expect(subCircuitParent("tvdb-bootstrap")).toBe("tvdb");
    expect(subCircuitParent("tmdb-download")).toBe("tmdb");
  });

  it("returns null for a plain provider", () => {
    expect(subCircuitParent("tvdb")).toBeNull();
    expect(subCircuitParent("omdb")).toBeNull();
  });

  it("does not treat a bare suffix as a sub-circuit", () => {
    expect(subCircuitParent("-bootstrap")).toBeNull();
  });
});

describe("subCircuitLabel / subCircuitHint", () => {
  it("labels known suffixes in plain French", () => {
    expect(subCircuitLabel("tvdb-bootstrap")).toBe("Authentification");
    expect(subCircuitLabel("tmdb-download")).toBe("Téléchargement");
    expect(subCircuitHint("tvdb-bootstrap")).toMatch(/authentification/i);
  });
});

describe("groupProviders", () => {
  it("nests a sub-circuit under its parent instead of a twin top-level card", () => {
    const groups = groupProviders([
      provider("tvdb"),
      provider("tvdb-bootstrap", { circuit_state: "open" }),
      provider("tmdb"),
    ]);

    // Two top-level groups (tvdb, tmdb) — NOT three cards.
    expect(groups.map((g) => g.parent.provider_name)).toEqual(["tvdb", "tmdb"]);
    const tvdb = groups[0];
    expect(tvdb?.subs.map((s) => s.provider_name)).toEqual(["tvdb-bootstrap"]);
    expect(groups[1]?.subs).toEqual([]);
  });

  it("keeps an orphan sub-circuit (absent parent) as its own top-level group", () => {
    const groups = groupProviders([provider("tvdb-bootstrap")]);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.parent.provider_name).toBe("tvdb-bootstrap");
    expect(groups[0]?.subs).toEqual([]);
  });

  it("preserves parent order by first appearance", () => {
    const groups = groupProviders([
      provider("tmdb"),
      provider("tvdb"),
      provider("tvdb-bootstrap"),
      provider("omdb"),
    ]);
    expect(groups.map((g) => g.parent.provider_name)).toEqual([
      "tmdb",
      "tvdb",
      "omdb",
    ]);
  });
});
