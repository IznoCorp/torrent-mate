// The FCM notification TYPE_SET and the PUSH CODES, held against the words that say them.
//
// The operator, 2026-10-03: « il faut créer des types de notifications FCM ». The two closed
// sets live in the contract (`NotificationType`, `PushCode`) — what the backend follows — and
// their words in `fr.json`. This holds the three together: every code is worded by the REAL
// worker (never the generic line, which is what a code nobody worded would show), every code
// belongs to a type, and every type has the label and the line the settings surface draws.
import { describe, expect, it } from "vitest";
import catalogue from "../i18n/fr.json";
import contract from "../../../../contract/openapi.json";
import workerSource from "../../sw.js?raw";
import { pushTexts, substituteWorker } from "../../worker-source.mjs";

type Schema = { enum?: string[] };
const schemas = (contract as unknown as { components: { schemas: Record<string, Schema> } }).components.schemas;
const TYPE_SET = schemas.NotificationType?.enum ?? [];
const CODES = schemas.PushCode?.enum ?? [];
const generic = (catalogue as unknown as { push: { generic: { title: string; body: string } } }).push.generic;

/**
 * Reads a dotted path of the catalogue.
 *
 * @param path The dotted path.
 * @returns What it holds, or undefined.
 */
function at(path: string): unknown {
  return path.split(".").reduce<unknown>(
    (node, part) => (node !== null && typeof node === "object" ? (node as Record<string, unknown>)[part] : undefined),
    catalogue,
  );
}

/**
 * Shows one push through the source worker, as the build substitutes it.
 *
 * @param code The push's code.
 * @returns The notification shown.
 */
async function shown(code: string): Promise<{ title: string; body: string }> {
  const listeners: Record<string, (event: unknown) => void> = {};
  const notes: { title: string; body: string }[] = [];
  const self = {
    location: { origin: "https://tm.example" },
    addEventListener: (type: string, listener: (event: unknown) => void) => { listeners[type] = listener; },
    skipWaiting: () => undefined,
    registration: {
      showNotification: (title: string, options: { body: string }) => {
        notes.push({ title, body: options.body });
        return Promise.resolve();
      },
    },
    clients: { matchAll: () => Promise.resolve([]), openWindow: () => Promise.resolve(null) },
  };
  const source = substituteWorker(workerSource, { build: "test", shell: ["/"], extras: [], push: pushTexts(catalogue) });
  new Function("self", source)(self);
  const pending: Promise<unknown>[] = [];
  const params = JSON.stringify({ title: "Ted Lasso S04E08", tracker: "c411", step: "scrape", disk: "Disk 2", service: "TMDB" });
  listeners.push!({
    data: { json: () => ({ data: { code, params, link: "/trackers" } }) },
    waitUntil: (promise: Promise<unknown>) => pending.push(promise),
  });
  await Promise.all(pending);
  return notes[0]!;
}

describe("the FCM notification types and their push codes", () => {
  it("are declared in the contract, closed sets", () => {
    expect(TYPE_SET.length).toBeGreaterThan(0);
    expect(CODES.length).toBeGreaterThanOrEqual(TYPE_SET.length);
  });

  it("splits the two obligation outcomes into two types a reader switches apart", () => {
    expect(TYPE_SET).toEqual(expect.arrayContaining(["obligation.met", "obligation.released"]));
  });

  it("has every code belong to a type: the type itself, or the type and one variant", () => {
    for (const code of CODES) {
      const type = TYPE_SET.find((one) => code === one || code.startsWith(one + "."));
      expect(type, code).toBeDefined();
      expect(code.split(".").length - type!.split(".").length, code).toBeLessThanOrEqual(1);
    }
    for (const type of TYPE_SET) expect(CODES.some((code) => code === type || code.startsWith(type + ".")), type).toBe(true);
  });

  it("has every code worded by the worker — never the generic line, never a placeholder left", async () => {
    for (const code of CODES) {
      const note = await shown(code);
      expect(note.title === generic.title && note.body === generic.body, code).toBe(false);
      expect(`${note.title} ${note.body}`, code).not.toMatch(/\{\{/);
    }
  });

  it("has every type a label and a line for the settings surface", () => {
    for (const type of TYPE_SET) {
      const words = at(`notifications.types.${type}`) as { label?: string; description?: string } | undefined;
      expect(words?.label, type).toBeTruthy();
      expect(words?.description, type).toBeTruthy();
    }
  });
});
