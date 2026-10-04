// An installed application is updated on demand; a tab still updates itself.
//
// WHAT MAKES THIS NON-VACUOUS. The discipline is driven over a stand-in service worker container whose
// registration holds a WAITING worker (or none), a host that answers `/build.json`, and a display mode
// the way a browser reports it. What is read is what LEFT: whether the waiting worker was asked to take
// over, whether the page reloaded, and what the install state says waits — for the same inputs, once as
// a tab (the control: it applies by itself) and once installed (it does not, until it is asked).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

declare const __BUILD_ID__: string;

type Registration = {
  waiting: { postMessage: ReturnType<typeof vi.fn> } | null;
  update: () => Promise<void>;
  addEventListener: (type: string, listener: () => void) => void;
};

let reload: ReturnType<typeof vi.fn>;
let waiting: { postMessage: ReturnType<typeof vi.fn> };
let registration: Registration;

/** Stands up one browser, one worker container and one host answering `served` as its build. */
function world(options: { standalone: boolean; served: string; hasWaiting: boolean }): void {
  reload = vi.fn();
  waiting = { postMessage: vi.fn() };
  registration = {
    waiting: options.hasWaiting ? waiting : null,
    update: async () => {},
    addEventListener: () => {},
  };
  const container = {
    controller: { postMessage: vi.fn() },
    getRegistration: async () => registration,
    addEventListener: () => {},
  };
  vi.stubGlobal("navigator", { serviceWorker: container, userAgent: "x", platform: "x", maxTouchPoints: 0 });
  vi.stubGlobal("window", { matchMedia: () => ({ matches: options.standalone }), name: "" });
  vi.stubGlobal("document", { addEventListener: () => {}, visibilityState: "visible" });
  vi.stubGlobal("location", { reload });
  vi.stubGlobal("sessionStorage", { getItem: () => null, setItem: () => {} });
  vi.stubGlobal("setInterval", () => 0);
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ build: options.served }), { status: 200 }));
}

/** Boots the discipline and lets its first check settle. */
async function boot() {
  const discipline = await import("./worker-registration");
  const install = await import("./install-state");
  discipline.installUpdateDiscipline();
  await new Promise((settle) => setTimeout(settle, 20));
  return install;
}

beforeEach(() => vi.resetModules());
afterEach(() => vi.unstubAllGlobals());

describe("a tab", () => {
  it("asks the waiting worker to take over by itself — the control", async () => {
    world({ standalone: false, served: __BUILD_ID__, hasWaiting: true });
    const install = await boot();
    expect(waiting.postMessage).toHaveBeenCalledWith("skip-waiting");
    expect(install.installFace()).not.toBe("update");
  });

  it("reloads by itself into a newer build when no worker waits", async () => {
    world({ standalone: false, served: "a-newer-build", hasWaiting: false });
    await boot();
    expect(reload).toHaveBeenCalledTimes(1);
  });
});

describe("an installed application", () => {
  it("leaves a waiting worker waiting, and says an update is there", async () => {
    world({ standalone: true, served: __BUILD_ID__, hasWaiting: true });
    const install = await boot();
    expect(waiting.postMessage).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
    expect(install.installFace()).toBe("update");
  });

  it("activates the waiting worker when it is asked to", async () => {
    world({ standalone: true, served: __BUILD_ID__, hasWaiting: true });
    const install = await boot();
    install.applyUpdate();
    expect(waiting.postMessage).toHaveBeenCalledWith("skip-waiting");
  });

  it("says an update is there when the host serves a newer build, and reloads only when asked", async () => {
    world({ standalone: true, served: "a-newer-build", hasWaiting: false });
    const install = await boot();
    expect(reload).not.toHaveBeenCalled();
    expect(install.installFace()).toBe("update");
    install.applyUpdate();
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("says nothing waits when the running build is the served one", async () => {
    world({ standalone: true, served: __BUILD_ID__, hasWaiting: false });
    const install = await boot();
    expect(install.installFace()).toBe("none");
  });
});
