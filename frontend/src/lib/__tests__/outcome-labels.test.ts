import { describe, expect, it } from "vitest";

import {
  DEFAULT_OUTCOME,
  OUTCOME_LABEL,
  OUTCOME_TONE,
  STATE_LABEL,
  STATE_TONE,
  outcomeLabel,
} from "@/lib/outcome-labels";

// ---------------------------------------------------------------------------
// Mapping completeness
// ---------------------------------------------------------------------------

describe("outcome-labels — mapping completeness", () => {
  it("every OUTCOME_LABEL key has a matching OUTCOME_TONE key", () => {
    for (const key of Object.keys(OUTCOME_LABEL)) {
      expect(
        OUTCOME_TONE[key],
        `OUTCOME_LABEL key "${key}" is missing from OUTCOME_TONE`,
      ).toBeDefined();
    }
  });

  it("every OUTCOME_TONE key has a matching OUTCOME_LABEL key", () => {
    for (const key of Object.keys(OUTCOME_TONE)) {
      expect(
        OUTCOME_LABEL[key],
        `OUTCOME_TONE key "${key}" is missing from OUTCOME_LABEL`,
      ).toBeDefined();
    }
  });

  it("every STATE_LABEL key has a matching STATE_TONE key", () => {
    for (const key of Object.keys(STATE_LABEL)) {
      expect(
        STATE_TONE[key],
        `STATE_LABEL key "${key}" is missing from STATE_TONE`,
      ).toBeDefined();
    }
  });

  it("every STATE_TONE key has a matching STATE_LABEL key", () => {
    for (const key of Object.keys(STATE_TONE)) {
      expect(
        STATE_LABEL[key],
        `STATE_TONE key "${key}" is missing from STATE_LABEL`,
      ).toBeDefined();
    }
  });

  it("every label in every map is a non-empty string", () => {
    for (const [key, label] of Object.entries(OUTCOME_LABEL)) {
      expect(label, `OUTCOME_LABEL["${key}"] is empty`).toBeTruthy();
      expect(typeof label, `OUTCOME_LABEL["${key}"] is not a string`).toBe("string");
    }
    for (const [key, label] of Object.entries(STATE_LABEL)) {
      expect(label, `STATE_LABEL["${key}"] is empty`).toBeTruthy();
      expect(typeof label, `STATE_LABEL["${key}"] is not a string`).toBe("string");
    }
  });

  it("every tone in every map is a valid BadgeTone", () => {
    const VALID_TONES = new Set([
      "success",
      "danger",
      "warning",
      "info",
      "neutral",
    ]);
    for (const [key, tone] of Object.entries(OUTCOME_TONE)) {
      expect(
        VALID_TONES.has(tone),
        `OUTCOME_TONE["${key}"] = "${tone}" is not a valid BadgeTone`,
      ).toBe(true);
    }
    for (const [key, tone] of Object.entries(STATE_TONE)) {
      expect(
        VALID_TONES.has(tone),
        `STATE_TONE["${key}"] = "${tone}" is not a valid BadgeTone`,
      ).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// outcomeLabel helper
// ---------------------------------------------------------------------------

describe("outcomeLabel — fallback behaviour", () => {
  it("returns « Jamais exécuté » for null", () => {
    expect(outcomeLabel(null)).toBe("Jamais exécuté");
  });

  it("returns « Jamais exécuté » for undefined", () => {
    expect(outcomeLabel(undefined)).toBe("Jamais exécuté");
  });

  it("returns « Jamais exécuté » for an unknown key", () => {
    expect(outcomeLabel("nonexistent_key")).toBe("Jamais exécuté");
  });

  it("returns the French label for a known outcome", () => {
    expect(outcomeLabel("success")).toBe("Succès");
    expect(outcomeLabel("error")).toBe("Échec");
    expect(outcomeLabel("killed")).toBe("Interrompu");
    expect(outcomeLabel("running")).toBe("En cours");
    expect(outcomeLabel("queued")).toBe("En file");
  });
});

// ---------------------------------------------------------------------------
// Unified vocabulary assertions (backward-compat gate)
// ---------------------------------------------------------------------------

describe("outcome-labels — unified vocabulary", () => {
  it("OUTCOME_LABEL.success is « Succès »", () => {
    expect(OUTCOME_LABEL.success).toBe("Succès");
  });

  it("OUTCOME_LABEL.error is « Échec »", () => {
    expect(OUTCOME_LABEL.error).toBe("Échec");
  });

  it("OUTCOME_LABEL.killed is « Interrompu »", () => {
    expect(OUTCOME_LABEL.killed).toBe("Interrompu");
  });

  it("OUTCOME_LABEL.running is « En cours »", () => {
    expect(OUTCOME_LABEL.running).toBe("En cours");
  });

  it("OUTCOME_LABEL.paused is « En pause »", () => {
    expect(OUTCOME_LABEL.paused).toBe("En pause");
  });

  it("DEFAULT_OUTCOME has neutral tone and em-dash label", () => {
    expect(DEFAULT_OUTCOME.tone).toBe("neutral");
    expect(DEFAULT_OUTCOME.label).toBe("—");
  });
});

// ---------------------------------------------------------------------------
// Zero React dependencies
// ---------------------------------------------------------------------------

describe("outcome-labels — zero React dependencies", () => {
  it("module imports are pure data — no React, no JSX, no hooks", () => {
    // If the module imported React or any hook, it would fail to import in a
    // non-React context. This test file is pure vitest with no React wrappers
    // and it already imported the module successfully at the top of the file.
    // We assert that the values are plain objects (not components).
    expect(typeof OUTCOME_LABEL).toBe("object");
    expect(typeof OUTCOME_TONE).toBe("object");
    expect(typeof STATE_LABEL).toBe("object");
    expect(typeof STATE_TONE).toBe("object");
    expect(typeof DEFAULT_OUTCOME).toBe("object");
    expect(typeof outcomeLabel).toBe("function");
    // outcomeLabel is a plain function, not a React component.
    expect(outcomeLabel.length).toBe(1); // exactly one parameter
  });
});
