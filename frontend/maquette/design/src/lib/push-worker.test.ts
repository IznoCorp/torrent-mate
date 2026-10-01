// The worker's push handling (fcm-push DESIGN § 3.5), run for real: the SOURCE `sw.js`,
// substituted the way the build does, evaluated against a fake `self`.
//
// WHAT MAKES THIS NON-VACUOUS. The words are asserted against the catalogue's own generic
// line and a code worded for the test, the parameters are filled from a payload whose
// `params` arrive JSON-encoded as FCM requires, and every hostile link is asserted to open
// the root — so a worker that echoed the wire, skipped the lookup or trusted the link fails.
import { describe, expect, it, vi } from "vitest";
import catalogue from "../i18n/fr.json";
import workerSource from "../../sw.js?raw";
import { PLACEHOLDERS, pushTexts, substituteWorker } from "../../worker-source.mjs";

const ORIGIN = "https://tm.example";
type Listener = (event: unknown) => void;

const TEST_TEXTS = {
  ...pushTexts(catalogue),
  tracker: { ratio_low: { title: "Low ratio on {{tracker}}", body: "{{ratio}} under {{threshold}} ({{missing}})" } },
};

function bootWorker(push: Record<string, unknown> = TEST_TEXTS) {
  const listeners: Record<string, Listener> = {};
  const shown: Array<{ title: string; options: Record<string, unknown> }> = [];
  const windows: Array<{ url: string; focus: ReturnType<typeof vi.fn>; navigate: ReturnType<typeof vi.fn> }> = [];
  const opened: string[] = [];
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, listener: Listener) => { listeners[type] = listener; },
    skipWaiting: () => undefined,
    registration: {
      showNotification: (title: string, options: Record<string, unknown>) => {
        shown.push({ title, options });
        return Promise.resolve();
      },
    },
    clients: {
      matchAll: () => Promise.resolve(windows),
      openWindow: (url: string) => { opened.push(url); return Promise.resolve(null); },
    },
  };
  const source = substituteWorker(workerSource, { build: "test", shell: ["/"], extras: [], push });
  new Function("self", source)(self);
  const fire = async (type: string, event: Record<string, unknown>) => {
    const pending: Promise<unknown>[] = [];
    listeners[type]!({ ...event, waitUntil: (p: Promise<unknown>) => pending.push(p) });
    await Promise.all(pending);
  };
  const push_ = (payload: unknown) =>
    fire("push", { data: payload === undefined ? null : { json: () => {
      if (payload instanceof Error) throw payload;
      return payload;
    } } });
  const click = (link: unknown) =>
    fire("notificationclick", { notification: { close: vi.fn(), data: { link } } });
  return { listeners, shown, windows, opened, push: push_, click };
}

const generic = (catalogue as unknown as { push: { generic: { title: string; body: string } } }).push.generic;

describe("the worker's push listener", () => {
  it("words a known code from the catalogue, its params filled, a missing one left visible", async () => {
    const worker = bootWorker();
    await worker.push({ data: {
      code: "tracker.ratio_low", params: JSON.stringify({ tracker: "c411", ratio: 1.12, threshold: 1.2 }),
      link: "/trackers/c411", tag: "ratio-c411",
    } });
    expect(worker.shown).toEqual([{ title: "Low ratio on c411", options: expect.objectContaining({
      body: "1.12 under 1.2 ({{missing}})", tag: "ratio-c411", data: { link: "/trackers/c411" },
    }) }]);
  });

  it.each([
    ["an unknown code", { data: { code: "nobody.knows", params: "{}", link: "/" } }],
    ["a code naming a namespace, not an entry", { data: { code: "tracker", link: "/" } }],
    ["no code at all", { data: {} }],
    ["unparseable params", { data: { code: "tracker.ratio_low", params: "{not json", link: "/" } }],
    ["a payload that is not JSON", new Error("not json")],
    ["no payload", undefined],
  ])("shows the generic line for %s — never silence", async (_label, payload) => {
    const worker = bootWorker();
    await worker.push(payload);
    expect(worker.shown).toHaveLength(1);
    if (_label === "unparseable params") {
      expect(worker.shown[0]!.title).toBe("Low ratio on {{tracker}}");
    } else {
      expect(worker.shown[0]!.title).toBe(generic.title);
      expect(worker.shown[0]!.options.body).toBe(generic.body);
    }
  });

  it.each([
    ["https://evil.example/x"], ["//evil.example/x"], ["/\\evil.example"], ["trackers"], [42], [null],
  ])("opens the root for a hostile or malformed link %s", async (link) => {
    const worker = bootWorker();
    await worker.push({ data: { code: "x", link } });
    expect(worker.shown[0]!.options.data).toEqual({ link: "/" });
  });
});

describe("the worker's notificationclick listener", () => {
  it("opens a window at the message's page when none is open", async () => {
    const worker = bootWorker();
    await worker.click("/trackers/c411?tab=torrents");
    expect(worker.opened).toEqual(["/trackers/c411?tab=torrents"]);
  });

  it("focuses an open window of the application and sends it to the page", async () => {
    const worker = bootWorker();
    const open = { url: `${ORIGIN}/acquisition`, focus: vi.fn(), navigate: vi.fn(() => Promise.resolve()) };
    open.focus.mockImplementation(() => Promise.resolve(open));
    worker.windows.push(open);
    await worker.click("/trackers");
    expect(open.focus).toHaveBeenCalled();
    expect(open.navigate).toHaveBeenCalledWith("/trackers");
    expect(worker.opened).toEqual([]);
  });

  it("opens a window at the page when the open one cannot be navigated (an uncontrolled client)", async () => {
    const worker = bootWorker();
    const open = {
      url: `${ORIGIN}/acquisition`,
      focus: vi.fn(),
      navigate: vi.fn(() => Promise.reject(new TypeError("not controlled"))),
    };
    open.focus.mockImplementation(() => Promise.resolve(open));
    worker.windows.push(open);
    await worker.click("/trackers");
    expect(open.navigate).toHaveBeenCalledWith("/trackers");
    expect(worker.opened).toEqual(["/trackers"]);
  });

  it("never follows a link off the application", async () => {
    const worker = bootWorker();
    await worker.click("https://evil.example/");
    expect(worker.opened).toEqual(["/"]);
  });
});

describe("the build's substitution", () => {
  it("writes the four placeholders, the push words included", () => {
    const built = substituteWorker(workerSource, { build: "b1", shell: ["/"], extras: [], push: pushTexts(catalogue) });
    for (const placeholder of PLACEHOLDERS) expect(built).not.toContain(placeholder);
    expect(built).toContain(JSON.stringify(generic.title));
  });

  it("writes a push text holding replacement patterns ($&, $', $`) as it is", async () => {
    const literal = "Ratio $& $' $` $$ $1";
    const worker = bootWorker({ ...TEST_TEXTS, generic: { title: literal, body: literal } });
    await worker.push({ data: { code: "nobody.knows" } });
    expect(worker.shown[0]).toEqual({ title: literal, options: expect.objectContaining({ body: literal }) });
  });

  it("refuses a worker whose __PUSH_TEXTS__ survived", () => {
    const doubled = workerSource.replace("__PUSH_TEXTS__", "__PUSH_TEXTS__ || __PUSH_TEXTS__");
    expect(() => substituteWorker(doubled, { build: "b", shell: ["/"], extras: [], push: pushTexts(catalogue) }))
      .toThrow(/placeholder survived/);
  });

  it("refuses a catalogue without the generic line", () => {
    expect(() => pushTexts({ push: { tracker: {} } })).toThrow(/push.generic/);
    expect(() => pushTexts({})).toThrow(/push.generic/);
  });
});
