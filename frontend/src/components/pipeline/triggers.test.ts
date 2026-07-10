import { describe, expect, it } from "vitest";

import {
  TRIGGER_INFO,
  triggerLabel,
  triggerTone,
} from "@/components/pipeline/triggers";

describe("pipeline triggers", () => {
  it("maps every known trigger to its French label", () => {
    expect(triggerLabel("completion")).toBe("Fin de téléchargement");
    expect(triggerLabel("safety_net")).toBe("Filet de sécurité");
    expect(triggerLabel("manual")).toBe("Manuel");
    expect(triggerLabel("cli")).toBe("Ligne de commande");
    expect(triggerLabel("web")).toBe("Interface web");
    expect(triggerLabel("cron")).toBe("Planifié");
  });

  it("passes an unknown trigger through verbatim", () => {
    expect(triggerLabel("weird_new_trigger")).toBe("weird_new_trigger");
    expect(triggerLabel("")).toBe("");
  });

  it("maps a known trigger to its semantic tone", () => {
    expect(triggerTone("completion")).toBe("success");
    expect(triggerTone("safety_net")).toBe("warning");
    expect(triggerTone("cron")).toBe("info");
  });

  it("defaults an unknown trigger tone to neutral", () => {
    expect(triggerTone("weird_new_trigger")).toBe("neutral");
  });

  it("gives every descriptor a non-empty meaning for the legend", () => {
    for (const info of Object.values(TRIGGER_INFO)) {
      expect(info.meaning.length).toBeGreaterThan(0);
      expect(info.label.length).toBeGreaterThan(0);
    }
  });
});
